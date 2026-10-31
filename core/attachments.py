"""Archivos adjuntos del chat: fotos y documentos que se analizan al momento.

Cada archivo se lee en tu computador, se parte en fragmentos y se indexa SOLO para ese chat
(carpeta data/attachments/<id>/). No se agrega a tu carpeta knowledge/ ni a tu índice permanente.
  - Se borran junto con el chat. Los que se subieron pero nunca se enviaron, a las 24 horas.
  - El archivo original no se conserva: solo su texto (y una miniatura reducida si es una foto).
  - Las fotos las analiza un modelo de visión de Ollama (VISION_MODEL en .env): su descripción
    es automática y puede equivocarse, y así se le avisa a la IA y a ti.
"""
import io
import json
import re
import shutil
import threading
import time
import unicodedata
import uuid
from pathlib import Path

import numpy as np

from . import AssistantError, config, documents, embeddings, llm
from .store import Store

DOC_TYPES = {".pdf", ".docx", ".txt", ".md", ".csv"}
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
FULL_IF_CHUNKS = 4    # un archivo recién subido así de corto (o una foto) se entrega completo a la IA
CONTEXT_CHARS = 1200  # cuánto del archivo se usa como contexto al buscar en la web

_ID = re.compile(r"^[0-9a-f]{32}$")  # solo ids que nosotros generamos (evita rutas peligrosas)
_work = threading.Lock()             # un archivo a la vez: cuida la RAM de tu PC

# Corto a propósito: los modelos de visión pequeños (como moondream) fallan con instrucciones largas.
VISION_PROMPT = (
    "Describe esta imagen con detalle, en español, y transcribe tal cual todo el texto que aparezca en ella. "
    "Si hay tablas, gráficos o cifras, indica sus valores exactos. "
    "Describe solo lo que realmente se ve; si algo no se distingue, dilo, y no identifiques a las personas por su cara."
)

# Preguntas de "visión general" (resume, de qué trata…): no se parecen a ningún fragmento en particular,
# así que en vez de buscar por parecido se toma una muestra repartida por todo el archivo.
_OVERVIEW_STEMS = ("resum", "sintetiz", "analiz", "describ", "explic", "revis", "trat", "dice", "contiene", "habla",
                   "contenido", "idea", "principal", "general", "puntos", "clave")
_FILLER = {
    "el", "la", "lo", "los", "las", "un", "una", "este", "esta", "esto", "ese", "esa", "eso", "archivo", "archivos",
    "documento", "documentos", "imagen", "imagenes", "foto", "fotos", "pdf", "adjunto", "adjuntos", "texto", "captura",
    "de", "del", "que", "me", "te", "se", "dime", "dame", "hazme", "por", "favor", "y", "en", "a", "al", "con",
    "sobre", "todo", "va", "hay", "ves", "cual", "cuales", "es", "son", "puedes", "podrias", "breve", "corto", "rapido",
}


class AttachmentError(AssistantError):
    """Problema con un archivo concreto. `status` es el código HTTP que recibe la página."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


# --- Nombres, tipos y carpetas -----------------------------------------------
def _safe_name(name: str) -> str:
    name = Path(name.replace("\\", "/")).name  # sin carpetas: solo el nombre del archivo
    name = " ".join("".join(ch for ch in name if ch.isprintable()).split())
    return name[:120] or "archivo"


def kind_of(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in IMAGE_TYPES:
        return "imagen"
    if ext in DOC_TYPES:
        return "documento"
    raise AttachmentError(
        f"No puedo leer archivos «{ext or 'sin extensión'}». Formatos: PDF, DOCX, TXT, MD, CSV "
        "y fotos (PNG, JPG, WEBP, GIF, BMP).",
        415,
    )


def check(name: str) -> tuple[str, str]:
    """(nombre seguro, tipo) o AttachmentError 415 si el formato no se puede leer."""
    name = _safe_name(name)
    return name, kind_of(name)


def _dir(att_id: str) -> Path | None:
    return config.ATTACH_DIR / att_id if _ID.match(att_id or "") else None


def info(att_id: str) -> dict | None:
    folder = _dir(att_id)
    if folder is None:
        return None
    try:
        return json.loads((folder / "info.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def image_path(att_id: str) -> Path | None:
    item = info(att_id)
    if not item or item["kind"] != "imagen":
        return None
    path = _dir(att_id) / "image.jpg"
    return path if path.is_file() else None


# --- Leer y analizar ---------------------------------------------------------
def _read(folder: Path, name: str, data: bytes) -> list[tuple[str, str]]:
    source = folder / f"original{Path(name).suffix.lower()}"
    source.write_bytes(data)
    try:
        return documents.read_file(source)
    except Exception as error:  # archivo dañado, PDF con contraseña, etc.
        raise AttachmentError(
            f"No pude leer «{name}» ({type(error).__name__}). ¿Está dañado o protegido con contraseña?"
        )
    finally:
        source.unlink(missing_ok=True)  # el original no se conserva


def _look(folder: Path, name: str, data: bytes) -> str:
    """Reduce la foto y le pide al modelo de visión que la describa y transcriba su texto."""
    from PIL import Image, ImageOps

    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception:
        raise AttachmentError(f"«{name}» no es una imagen válida (o es demasiado grande).")
    image = ImageOps.exif_transpose(image)  # fotos de celular giradas
    if image.mode in ("RGBA", "LA", "P"):  # transparencias → fondo blanco
        image = image.convert("RGBA")
        base = Image.new("RGB", image.size, "white")
        base.paste(image, mask=image.getchannel("A"))
        image = base
    else:
        image = image.convert("RGB")
    image.thumbnail((1280, 1280))  # suficiente para leer texto y mucho más liviano para tu PC
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=85)
    jpeg = buffer.getvalue()
    (folder / "image.jpg").write_bytes(jpeg)
    text = llm.describe_image(jpeg, VISION_PROMPT)
    if len(text) < 8:
        raise AttachmentError("El modelo de visión no devolvió una descripción. Intenta de nuevo.")
    return text


def _truncate(pages: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], bool]:
    kept, total = [], 0
    for location, text in pages:
        room = config.ATTACH_MAX_CHARS - total
        if room <= 0:
            return kept, True
        if len(text) > room:
            kept.append((location, text[:room]))
            return kept, True
        kept.append((location, text))
        total += len(text)
    return kept, False


def _chunks(name: str, pages: list[tuple[str, str]]) -> list[dict]:
    header = ""
    if name.lower().endswith(".csv") and pages:  # cada fragmento de un CSV lleva sus encabezados
        header = pages[0][1].lstrip("﻿").split("\n", 1)[0].strip()[:300]
    chunks = []
    for location, text in pages:
        for piece in documents.split_text(text, config.CHUNK_SIZE, config.CHUNK_OVERLAP):
            if header and not piece.startswith(header):
                piece = f"{header}\n{piece}"
            chunks.append({"source": name, "page": location, "text": piece})
    return chunks


def process(name: str, data: bytes) -> dict:
    """Analiza un archivo subido y devuelve sus datos {id, name, kind, chars, chunks, truncated, size}."""
    name, kind = check(name)
    if not data:
        raise AttachmentError(f"«{name}» está vacío.")
    if len(data) > config.ATTACH_MAX_MB * 1024 * 1024:
        raise AttachmentError(f"«{name}» pesa más de {config.ATTACH_MAX_MB} MB.", 413)

    with _work:
        att_id = uuid.uuid4().hex
        folder = config.ATTACH_DIR / att_id
        folder.mkdir(parents=True)
        try:
            pages = [("", _look(folder, name, data))] if kind == "imagen" else _read(folder, name, data)
            pages, truncated = _truncate(pages)
            chunks = _chunks(name, pages)
            if not chunks:
                raise AttachmentError(
                    f"No encontré texto en «{name}»."
                    + (" Si es un PDF escaneado, súbelo como foto (PNG o JPG) para que lo lea el modelo de visión."
                       if name.lower().endswith(".pdf") else "")
                )
            vectors = embeddings.embed_passages([chunk["text"] for chunk in chunks])
            store = Store(folder)
            store.replace_sources(set(), chunks, vectors)
            store.files = {name: att_id}
            store.model = config.EMBED_MODEL
            store.save()
            item = {
                "id": att_id, "name": name, "kind": kind, "size": len(data), "chunks": len(chunks),
                "chars": sum(len(text) for _, text in pages), "truncated": truncated, "created": time.time(),
            }
            (folder / "info.json").write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
            return item
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)  # no deja restos si algo falla
            raise


# --- Usar los archivos al responder ------------------------------------------
def plain(text: str) -> str:
    """Minúsculas y sin tildes, para comparar palabras sin que importe cómo se escribieron."""
    return "".join(ch for ch in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(ch) != "Mn")


def is_overview(question: str) -> bool:
    """¿Pide una visión general del archivo ("resume el documento", "¿de qué trata?")?

    Si la pregunta nombra un tema concreto ("resume la política de vacaciones", "¿qué dice el artículo 5?"),
    NO es general: ahí conviene buscar por parecido.
    """
    words = re.findall(r"[a-z0-9ñ]+", plain(question))
    has_trigger = any(word.startswith(_OVERVIEW_STEMS) for word in words)
    leftover = [w for w in words if w not in _FILLER and not w.startswith(_OVERVIEW_STEMS)]
    return has_trigger and not leftover


def retrieve(att_ids: list[str], query: np.ndarray, fresh_ids=(), overview: bool = False) -> list[dict]:
    """Fragmentos de los archivos del chat.

    Los recién subidos se usan siempre (completos si son cortos); los anteriores, solo si se
    parecen a la pregunta. Así una pregunta ajena al archivo no se contesta con el archivo.
    Con `overview=True` (resumen / "de qué trata"), un archivo largo aporta una muestra repartida
    de principio a fin en vez de los fragmentos más parecidos.
    """
    fresh_ids = set(fresh_ids)
    stores = []
    for att_id in att_ids:
        item = info(att_id)
        if not item:
            continue  # ya se borró
        store = Store(_dir(att_id))
        if store.chunks and store.vectors.shape[1] == query.shape[0]:
            stores.append((att_id, item, store))
    if not stores:
        return []
    targets: set[str] = set()  # archivos de los que se pide una visión general
    if overview:
        valid = {att_id for att_id, _, _ in stores}
        targets = (fresh_ids & valid) or {stores[-1][0]}  # sin recién subidos: el archivo más reciente del chat
    per_file = max(2, config.ATTACH_TOP_K // len(targets)) if targets else 0

    forced, ranked = [], []
    for att_id, item, store in stores:
        scores = store.vectors @ query
        fresh, count = att_id in fresh_ids, len(store.chunks)
        base = {"origin": "adjunto", "kind": item["kind"], "att_id": att_id, "total": count}
        every = list(range(count))
        if (fresh and count <= FULL_IF_CHUNKS) or (att_id in targets and count <= per_file):
            picks = every  # archivo corto: se entrega completo
        elif att_id in targets:
            picks = sorted(set(np.linspace(0, count - 1, per_file).round().astype(int).tolist()))  # muestra repartida
        else:
            for i in np.argsort(-scores)[: config.ATTACH_TOP_K]:
                if fresh or scores[i] >= config.ATTACH_MIN_SCORE:
                    ranked.append({**store.chunks[i], **base, "score": float(scores[i])})
            continue
        forced += [{**store.chunks[i], **base, "score": float(scores[i])} for i in picks]
    ranked.sort(key=lambda hit: hit["score"], reverse=True)
    return (forced + ranked)[: max(config.ATTACH_TOP_K, len(forced))]


def excerpt(att_ids: list[str], limit: int = CONTEXT_CHARS) -> str:
    """El comienzo de cada archivo: sirve para saber DE QUÉ trata (y armar una búsqueda web)."""
    parts, used = [], 0
    for att_id in att_ids:
        item = info(att_id)
        if not item:
            continue
        store = Store(_dir(att_id))
        room = limit - used
        if not store.chunks or room < 80:
            continue
        label = "foto (descripción automática)" if item["kind"] == "imagen" else "documento"
        part = f"[{label} «{item['name']}»] {store.chunks[0]['text'][: room - 60]}"
        parts.append(part)
        used += len(part)
    return "\n\n".join(parts)


def source_text(att_ids: list[str]) -> str:
    """Nombre y texto inicial de cada archivo, SIN etiquetas: lo que el modelo pudo ver al armar una búsqueda web.

    Sirve para saber qué palabras de una consulta vienen del archivo (ver assistant.file_terms).
    """
    parts = []
    for att_id in att_ids:
        item = info(att_id)
        if not item:
            continue
        store = Store(_dir(att_id))
        if store.chunks:
            parts.append(f"{Path(item['name']).stem} {store.chunks[0]['text']}")
    return "\n".join(parts)


# --- Borrado y limpieza ------------------------------------------------------
def delete(att_ids) -> None:
    for att_id in att_ids:
        folder = _dir(att_id)
        if folder is not None:
            shutil.rmtree(folder, ignore_errors=True)


def cleanup(referenced: set[str], max_age_hours: float = 24) -> int:
    """Borra los archivos subidos que ningún chat usa y tienen más de `max_age_hours`."""
    if not config.ATTACH_DIR.exists():
        return 0
    removed, oldest = 0, time.time() - max_age_hours * 3600
    for folder in config.ATTACH_DIR.iterdir():
        if not folder.is_dir() or not _ID.match(folder.name) or folder.name in referenced:
            continue
        item = info(folder.name)
        created = item["created"] if item else folder.stat().st_mtime  # sin info.json = subida incompleta
        if created < oldest:
            shutil.rmtree(folder, ignore_errors=True)
            removed += 1
    return removed
