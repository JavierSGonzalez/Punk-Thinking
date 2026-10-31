"""Servidor local: sirve la página de chat y la API para preguntar.

Uso:    python server.py      → abre http://127.0.0.1:8000 en tu navegador
Solo acepta conexiones desde TU computador (127.0.0.1), nunca desde la red.
"""
import html
import json
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from core import AssistantError, assistant, attachments, chats, config, llm, memoria, perfil, rag, voice

WEB_DIR = Path(__file__).resolve().parent / "web"
MAX_UPLOAD = config.ATTACH_MAX_MB * 1024 * 1024
MAX_AUDIO = 10 * 1024 * 1024  # ~ varios minutos de voz; PK recibe frases cortas
ALLOWED_ORIGINS = {f"http://127.0.0.1:{config.PORT}", f"http://localhost:{config.PORT}"}


@asynccontextmanager
async def lifespan(_app):
    try:  # al encender: borra los archivos subidos que nunca se enviaron (más de 24 h)
        attachments.cleanup(chats.referenced_attachment_ids())
    except Exception:
        pass  # la limpieza nunca debe impedir que el servidor arranque
    yield


app = FastAPI(title=config.APP_NAME, docs_url=None, redoc_url=None, lifespan=lifespan)
# Evita que una página web externa le hable a tu IA a escondidas (ataque "DNS rebinding").
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


@app.middleware("http")
async def same_origin_only(request: Request, call_next):
    """Subir, preguntar o borrar solo se acepta desde TU página, no desde otra pestaña u otro sitio."""
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return JSONResponse({"detail": "Origen no permitido."}, status_code=403)
    return await call_next(request)


class Question(BaseModel):
    question: str = Field(default="", max_length=2000)  # puede ir vacía si se adjunta un archivo
    chat_id: str | None = None                          # si falta, se crea un chat nuevo
    attachments: list[str] = Field(default_factory=list, max_length=config.ATTACH_MAX_PER_MESSAGE)
    voice: bool = False                                 # True = viene del modo asistente (se devuelve también el texto para decir en voz alta)


class Hecho(BaseModel):
    texto: str = Field(min_length=2, max_length=memoria.MAX_TEXTO_HECHO)


class AjustesMemoria(BaseModel):
    hechos_auto: bool | None = None
    historial: bool | None = None
    usar: bool | None = None


class Speak(BaseModel):
    text: str = Field(min_length=1, max_length=voice.MAX_SPEAK_CHARS)


class Rename(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class WebConfirm(BaseModel):
    chat_id: str
    query: str = Field(default="", max_length=100)  # la consulta, tal como la dejó la persona
    cancel: bool = False                            # True = «No buscar»
    voice: bool = False                             # True = viene del modo asistente (se devuelve el texto para decir en voz alta)


def _chat(call, *args):
    try:
        return call(*args)
    except chats.ChatNotFound:
        raise HTTPException(status_code=404, detail="Ese chat ya no existe.")


@app.get("/")
def home():
    """La página, ya con el nombre y los colores de PK (sin parpadeo al abrirla)."""
    page = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    page = page.replace("{{NOMBRE}}", html.escape(perfil.nombre())).replace("/*PERFIL_CSS*/", perfil.style_block())
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


@app.get("/api/perfil")
def get_perfil():
    return perfil.payload()


# Ícono, datos de "app instalable" y el modo asistente (solo estos archivos de web/ se sirven; nada más de esa carpeta)
APP_FILES = {
    "/favicon.ico": ("favicon.ico", "image/x-icon"),
    "/icon-192.png": ("icon-192.png", "image/png"),
    "/icon-512.png": ("icon-512.png", "image/png"),
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/asistente.js": ("asistente.js", "text/javascript"),
    "/asistente.css": ("asistente.css", "text/css"),
    "/perfil.js": ("perfil.js", "text/javascript"),
    "/memoria.js": ("memoria.js", "text/javascript"),
    "/memoria.css": ("memoria.css", "text/css"),
}


def _app_file(name: str, media_type: str):
    def serve():
        return FileResponse(WEB_DIR / name, media_type=media_type, headers={"Cache-Control": "no-cache"})
    return serve


for _path, (_name, _type) in APP_FILES.items():
    app.add_api_route(_path, _app_file(_name, _type), methods=["GET"], include_in_schema=False)


@app.get("/api/status")
def status():
    store = rag.get_store()
    try:
        store.reload_if_changed()
    except AssistantError:
        pass  # el índice se está escribiendo; mostramos lo último que se cargó
    return {
        "app_name": config.APP_NAME,  # el interno (el ícono de inicio lo usa para reconocer el servidor)
        "nombre": perfil.nombre(),    # el que se muestra: puede haberlo cambiado el usuario
        "documents": len(store.files),
        "fragments": len(store.chunks),
        "engine": llm.describe(),
        "local": config.LLM_PROVIDER == "ollama",  # True = el motor de lenguaje corre en tu computador
        "web": config.WEB_BACKEND if config.WEB_SEARCH else None,  # buscador web activo (o None)
        "vision": llm.vision_name(),
        "attach_max_mb": config.ATTACH_MAX_MB,
        "attach_max": config.ATTACH_MAX_PER_MESSAGE,
    }


# --- Chats guardados ---------------------------------------------------------
@app.get("/api/chats")
def list_chats():
    return chats.list_chats()


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str):
    return _chat(chats.get, chat_id)


@app.patch("/api/chats/{chat_id}")
def rename_chat(chat_id: str, body: Rename):
    return _chat(chats.rename, chat_id, body.title)


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str):
    chat = _chat(chats.get, chat_id)
    _chat(chats.delete, chat_id)
    attachments.delete(chats.attachment_ids(chat))  # los archivos del chat se van con él
    return {"ok": True}


# --- Archivos y fotos adjuntos -----------------------------------------------
@app.post("/api/upload")
async def upload(request: Request, name: str = Query(..., min_length=1, max_length=200)):
    """Recibe un archivo (bytes en crudo; el nombre va en la dirección) y lo analiza al momento."""
    try:
        attachments.check(name)  # formato no compatible: se rechaza antes de recibir el archivo
    except attachments.AttachmentError as error:
        raise HTTPException(error.status, str(error))
    too_big = f"El archivo pesa más de {config.ATTACH_MAX_MB} MB."
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_UPLOAD:
        raise HTTPException(413, too_big)
    data = bytearray()
    async for part in request.stream():
        data += part
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, too_big)
    try:
        item = await run_in_threadpool(attachments.process, name, bytes(data))
    except attachments.AttachmentError as error:
        raise HTTPException(error.status, str(error))
    except AssistantError as error:  # Ollama apagado, modelo de visión sin descargar, etc.
        raise HTTPException(503, str(error))
    return {key: item[key] for key in ("id", "name", "kind", "chars", "chunks", "truncated")}


@app.get("/api/attachments/{att_id}/image")
def attachment_image(att_id: str):
    path = attachments.image_path(att_id)
    if path is None:
        raise HTTPException(404, "Esa imagen ya no existe.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


# --- Preguntar ---------------------------------------------------------------
@app.post("/api/ask")
def ask(body: Question):
    new = []
    for att_id in dict.fromkeys(body.attachments):  # sin repetidos, en orden
        item = attachments.info(att_id)
        if item is None:
            raise HTTPException(409, "Uno de los archivos adjuntos ya no existe. Vuelve a subirlo.")
        new.append(item)
    question = body.question.strip() or (assistant.DEFAULT_ATTACH_QUESTION if new else "")
    if not question:
        raise HTTPException(422, "Escribe una pregunta o adjunta un archivo.")

    history, known = [], []
    if body.chat_id:  # comprobar que existe antes de gastar tiempo, y de paso recordar la charla y sus archivos
        chat = _chat(chats.get, body.chat_id)
        history = chats.history(chat)
        known = chats.attachment_ids(chat, config.ATTACH_CONTEXT_FILES)
    fresh = [item["id"] for item in new]
    try:
        result = assistant.reply(question, history, [i for i in known if i not in fresh] + fresh, set(fresh),
                                 chat_id=body.chat_id)
    except AssistantError as error:
        raise HTTPException(status_code=503, detail=str(error))
    typed_only = body.question.strip()  # solo lo que la persona escribió o dijo (nunca el texto de un archivo)
    if typed_only and result.get("mode") not in memoria.MODOS_SIN_AUTOGUARDADO:
        try:  # datos claros que dijo de sí misma («me llamo…», «vivo en…»): se guardan y se le avisa
            aviso = memoria.nota_guardado(memoria.auto_guardar(typed_only, body.chat_id))
            if aviso:
                result = {**result, "answer": f"{result['answer']}\n\n{aviso}"}
        except Exception:
            pass  # la memoria nunca debe impedir una respuesta
    saved = [{"id": i["id"], "name": i["name"], "kind": i["kind"]} for i in new]
    typed = body.question.strip()  # si solo se envió un archivo, el chat se titula con su nombre
    title = typed[:60] or "Archivo: " + ", ".join(i["name"] for i in new)
    if body.voice:  # las conversaciones por voz se reconocen en la lista de chats
        title = ("Voz: " + (typed or question))[:60]
    chat = _chat(chats.save_exchange, body.chat_id, question, result, saved, title)
    if typed_only:
        try:  # resumen corto de lo trabajado, para recordarlo desde cualquier chat
            memoria.registrar(chat["id"], typed_only, result["answer"], result.get("mode", ""))
        except Exception:
            pass
    reply = {**result, "chat_id": chat["id"], "title": chat["title"]}
    if body.voice:
        reply["spoken"] = voice.speakable(result["answer"], result.get("mode", ""))
    return reply


# --- Modo asistente: oír y hablar (todo local) ---------------------------------
@app.get("/api/voice/status")
def voice_status(warm: bool = False):
    if warm:
        voice.warm_up()  # carga el oído en segundo plano al entrar a la pestaña
    return {
        "stt": {"available": voice.stt_available(), "ready": voice.stt_ready(), "model": config.WHISPER_MODEL},
        "tts": {"engine": voice.tts_engine(), "name": perfil.get("voz") or config.VOICE_NAME},
    }


@app.post("/api/voice/listen")
async def voice_listen(request: Request, ext: str = Query("webm", pattern="^[a-z0-9]{2,5}$")):
    """Recibe audio de tu micrófono, lo transcribe en tu PC y lo descarta."""
    too_big = "El audio es demasiado largo."
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_AUDIO:
        raise HTTPException(413, too_big)
    data = bytearray()
    async for part in request.stream():
        data += part
        if len(data) > MAX_AUDIO:
            raise HTTPException(413, too_big)
    if not data:
        raise HTTPException(422, "No llegó audio.")
    try:
        text = await run_in_threadpool(voice.transcribe, bytes(data), ext)
    except AssistantError as error:
        raise HTTPException(503, str(error))
    return {"text": text}


@app.post("/api/voice/speak")
async def voice_speak(body: Speak):
    try:
        audio, name = await run_in_threadpool(voice.speak, body.text)
    except AssistantError as error:
        raise HTTPException(503, str(error))
    return Response(audio, media_type="audio/wav", headers={"X-Voice": quote(name), "Cache-Control": "no-store"})


@app.post("/api/web")
def confirm_web(body: WebConfirm):
    """Responde al aviso «esta consulta lleva palabras de tu archivo»: buscar (quizá editada) o cancelar."""
    chat = _chat(chats.get, body.chat_id)
    pending = chats.pending_web(chat)
    if pending is None:
        raise HTTPException(409, "Esa búsqueda ya no está esperando tu permiso.")
    if body.cancel:
        result = assistant.cancelled_web()
    else:
        query = " ".join(body.query.split())
        if not query:
            raise HTTPException(422, "Escribe la consulta que quieres buscar.")
        known = chats.attachment_ids(chat, config.ATTACH_CONTEXT_FILES)
        fresh = pending["fresh"]
        try:
            result = assistant.search_confirmed(
                pending["question"], chats.history(chat, drop_last=2),
                [i for i in known if i not in fresh] + [i for i in fresh if i in known], query,
            )
        except AssistantError as error:
            raise HTTPException(status_code=503, detail=str(error))
    try:
        _chat(chats.replace_last_answer, body.chat_id, result)
    except chats.NoPendingWeb:
        raise HTTPException(409, "Esa búsqueda ya no está esperando tu permiso.")
    if not body.cancel and result.get("mode") == "web":
        try:
            memoria.registrar(body.chat_id, pending["question"], result["answer"], "web")
        except Exception:
            pass
    if body.voice:
        result = {**result, "spoken": voice.speakable(result["answer"], result.get("mode", ""))}
    return result


# --- Memoria privada: ver, corregir y olvidar (todo vive en data/memoria.json) --------------
@app.get("/api/memoria")
def get_memoria():
    return {**memoria.instantanea(), "local": config.LLM_PROVIDER == "ollama"}


@app.post("/api/memoria/hechos")
def add_hecho(body: Hecho):
    hecho, estado = memoria.agregar_hecho(body.texto, origen="manual")
    if estado == "secreto":
        raise HTTPException(422, "No guardo contraseñas, claves, tarjetas ni documentos de identidad.")
    if estado == "lleno":
        raise HTTPException(409, "La memoria de datos está llena. Borra alguno primero.")
    if hecho is None:
        raise HTTPException(422, "Escribe qué quieres que recuerde.")
    return {"hecho": hecho, "estado": estado}


@app.patch("/api/memoria/hechos/{hecho_id}")
def edit_hecho(hecho_id: str, body: Hecho):
    if not memoria.editar_hecho(hecho_id, body.texto):
        raise HTTPException(422, "No se pudo guardar ese cambio (el dato ya no existe, o parece una contraseña o clave).")
    return {"ok": True}


@app.delete("/api/memoria/hechos/{hecho_id}")
def del_hecho(hecho_id: str):
    if not memoria.borrar_hecho(hecho_id):
        raise HTTPException(404, "Ese dato ya no existe.")
    return {"ok": True}


@app.delete("/api/memoria/episodios/{episodio_id}")
def del_episodio(episodio_id: str):
    if not memoria.borrar_episodio(episodio_id):
        raise HTTPException(404, "Ese recuerdo ya no existe.")
    return {"ok": True}


@app.put("/api/memoria/ajustes")
def set_ajustes(body: AjustesMemoria):
    return memoria.cambiar_config(**{k: v for k, v in body.model_dump().items() if v is not None})


@app.delete("/api/memoria")
def forget_all(solo_historial: bool = False, confirmar: str = ""):
    """Olvidar todo (o solo lo trabajado). Exige confirmar=si para que un clic suelto no pueda borrar."""
    if confirmar != "si":
        raise HTTPException(422, "Falta confirmar el borrado.")
    hechos, episodios = memoria.olvidar_todo(solo_historial=solo_historial)
    return {"hechos": hechos, "episodios": episodios}


@app.get("/api/memoria/exportar")
def export_memoria():
    cuerpo = json.dumps(memoria.exportar(), ensure_ascii=False, indent=1)
    return Response(cuerpo, media_type="application/json; charset=utf-8", headers={
        "Content-Disposition": 'attachment; filename="mi-memoria-pk.json"', "Cache-Control": "no-store"})


if __name__ == "__main__":
    print(f"{config.APP_NAME} listo en http://127.0.0.1:{config.PORT}  (Ctrl+C para detener)")
    uvicorn.run(app, host="127.0.0.1", port=config.PORT, log_level="warning")
