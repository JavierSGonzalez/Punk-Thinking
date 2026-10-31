"""Memoria privada de PK.

Guarda, SOLO en tu PC (data/memoria.json), dos cosas:

  * HECHOS sobre ti: «Nombre: Ana», «Vive en: Santa Ana», «Estudia: Economía…».
    Se guardan cuando tú lo pides («recuerda que…») o, si dejas activado el guardado
    automático, cuando lo dices con frases muy claras («me llamo Ana», «vivo en…»).
  * RECUERDOS de lo trabajado: un resumen corto de cada pregunta y su respuesta, para
    poder contestar en cualquier chat «¿qué hicimos con el archivo mundo?».

Todo se puede ver, corregir y borrar desde la pestaña «Memoria» o por chat
(«olvida que vivo en…», «olvida todo»).

Reglas de privacidad:
  * Nada de esto se envía a internet: ni a la búsqueda web ni a ningún servicio.
    (Con LLM_PROVIDER=anthropic, lo que PK te conteste con ayuda de la memoria sí viajaría
    a Anthropic junto con la pregunta; con Ollama no sale nada.)
  * No guarda contraseñas, claves, tarjetas ni documentos de identidad.
  * Solo aprende de lo que TÚ escribes o dices. Nunca de documentos, fotos adjuntas ni
    páginas web.
  * El recuerdo del pasado se contesta con código (palabras clave), sin dejar que el
    modelo invente: si no encuentra nada, lo dice.
"""
from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import threading
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_HECHOS = 300
MAX_EPISODIOS = 500
MAX_TEXTO_HECHO = 200
MAX_PREGUNTA = 240
MAX_RESPUESTA = 320

CONFIG_INICIAL = {
    "hechos_auto": True,   # guardar datos tuyos cuando los dices con frases claras
    "historial": True,     # recordar lo que trabajamos (preguntas y respuestas resumidas)
    "usar": True,          # dejar que PK use tu memoria al responder
}

# Modos de respuesta de PK que no valen la pena como recuerdo
MODOS_SIN_RECUERDO = {"herramienta", "memoria", "ajuste", "web_pendiente"}
# Respuestas a órdenes (archivos, ajustes, memoria): ahí no se «descubren» datos personales por su cuenta
MODOS_SIN_AUTOGUARDADO = {"herramienta", "memoria", "ajuste", "espacio", "web_pendiente"}

CONFIRMA_TODO = "Responde «sí, olvídalo todo» para confirmar o «no» para cancelar."
CONFIRMA_HISTORIAL = "Responde «sí, borra el historial» para confirmar o «no» para cancelar."

_lock = threading.RLock()
_cache: dict = {"mtime": None, "datos": None}


# ───────────────────────── archivo ─────────────────────────

def _ruta() -> Path:
    base = os.getenv("PK_DATA_DIR")
    carpeta = Path(base) if base else Path(__file__).resolve().parent.parent / "data"
    return carpeta / "memoria.json"


def _vacio() -> dict:
    return {"version": 1, "config": dict(CONFIG_INICIAL), "hechos": [], "episodios": []}


def _cargar() -> dict:
    ruta = _ruta()
    try:
        mtime = ruta.stat().st_mtime_ns
    except OSError:
        return _vacio()
    if _cache["mtime"] == mtime and _cache["datos"] is not None:
        return copy.deepcopy(_cache["datos"])
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        datos = _vacio()
    if not isinstance(datos, dict):
        datos = _vacio()
    cfg = dict(CONFIG_INICIAL)
    if isinstance(datos.get("config"), dict):
        for k in CONFIG_INICIAL:
            if isinstance(datos["config"].get(k), bool):
                cfg[k] = datos["config"][k]
    datos["config"] = cfg
    datos["hechos"] = [h for h in datos.get("hechos", []) if isinstance(h, dict) and h.get("texto")]
    datos["episodios"] = [e for e in datos.get("episodios", []) if isinstance(e, dict) and e.get("pregunta")]
    _cache.update(mtime=mtime, datos=copy.deepcopy(datos))
    return datos


def _guardar(datos: dict) -> None:
    ruta = _ruta()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(ruta.parent), prefix=".memoria-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)
        os.replace(tmp, ruta)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    _cache.update(mtime=ruta.stat().st_mtime_ns, datos=copy.deepcopy(datos))


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id() -> str:
    return uuid.uuid4().hex[:8]


# ───────────────────────── texto ─────────────────────────

def _plain(s: str) -> str:
    """Minúsculas sin acentos y con el MISMO largo que el original (para recortar por posición)."""
    out = []
    for ch in s:
        d = unicodedata.normalize("NFD", ch.lower())
        out.append(d[0] if d else ch)
    return "".join(out)


_STOP = set("""a al algo ante con contra cual cuales cuando de del desde donde el ella ellos en entre era
es esa ese eso esta este esto estas estos fue ha han hay la las le les lo los me mi mis mas muy no nos o otra
otro para pero por que se si sin sobre su sus te tu tus un una uno unos unas y ya yo hemos hicimos hablamos
trabajamos dijiste dije pedi pedido recuerdas recuerdo acuerdas acuerdo vez otra anterior chat conversacion
cosa cosas algo""".split())


_SINONIMOS = {
    "llamo": "nombr", "llama": "nombr", "llamas": "nombr", "nombre": "nombr",
    "vivo": "vive", "vives": "vive", "vivir": "vive", "viviendo": "vive", "viven": "vive",
    "estudio": "estud", "estudias": "estud", "estudia": "estud", "estudiar": "estud",
    "trabajo": "traba", "trabajas": "traba", "trabaja": "traba", "trabajar": "traba",
    "gusta": "gusta", "gustan": "gusta", "encanta": "gusta", "encantan": "gusta",
}


def _raices(texto: str) -> set[str]:
    """Palabras importantes recortadas (continentes/continente → conti) para comparar."""
    out = set()
    for w in re.findall(r"[a-z0-9ñ]+", _plain(texto)):
        if w in _STOP or len(w) < 3:
            continue
        out.add(_SINONIMOS.get(w) or (w[:5] if len(w) > 5 else w))
    return out


_SECRETO = re.compile(
    r"\b(?:contrasena|password|passwd|clave(?: de| del| para)?|pin|token|api ?key|secreto|cvv|cvc|"
    r"tarjeta|iban|cuenta bancaria|numero de cuenta|dui|pasaporte|seguro social|licencia de conducir)\b"
    r"|(?:\d[ -]?){13,19}|\b\d{8}-\d\b|\b\d{9,}\b")


def es_secreto(texto: str) -> bool:
    return bool(_SECRETO.search(_plain(texto)))


def _plural(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


def _recortar(texto: str, n: int) -> str:
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto if len(texto) <= n else texto[: n - 1].rstrip() + "…"


def _mayuscula_inicial(s: str) -> bool:
    return bool(s) and s[0].isalpha() and s[0].isupper()


# ───────────────────────── hechos ─────────────────────────

def hechos() -> list[dict]:
    with _lock:
        return [dict(h) for h in _cargar()["hechos"]]


def _norm(texto: str) -> str:
    return re.sub(r"[^a-z0-9ñ]+", " ", _plain(texto)).strip()


def agregar_hecho(texto: str, clave: str | None = None, origen: str = "manual",
                  chat: str | None = None) -> tuple[dict | None, str]:
    """Guarda un hecho. Devuelve (hecho, estado): 'nuevo' | 'actualizado' | 'repetido' | 'lleno' | 'secreto' | 'vacio'."""
    texto = _recortar(texto or "", MAX_TEXTO_HECHO)
    if len(texto) < 2:
        return None, "vacio"
    if es_secreto(texto):
        return None, "secreto"
    with _lock:
        datos = _cargar()
        lista = datos["hechos"]
        for h in lista:
            if _norm(h["texto"]) == _norm(texto):
                return h, "repetido"
        if clave:
            for h in lista:
                if h.get("clave") == clave:
                    h.update(texto=texto, origen=origen, actualizado=_ahora())
                    _guardar(datos)
                    return dict(h), "actualizado"
        if len(lista) >= MAX_HECHOS:
            return None, "lleno"
        h = {"id": _id(), "texto": texto, "clave": clave, "origen": origen,
             "creado": _ahora(), "chat": chat}
        lista.append(h)
        _guardar(datos)
        return dict(h), "nuevo"


def editar_hecho(hid: str, texto: str) -> bool:
    texto = _recortar(texto or "", MAX_TEXTO_HECHO)
    if len(texto) < 2 or es_secreto(texto):
        return False
    with _lock:
        datos = _cargar()
        for h in datos["hechos"]:
            if h["id"] == hid:
                h.update(texto=texto, actualizado=_ahora(), clave=None)
                _guardar(datos)
                return True
    return False


def borrar_hecho(hid: str) -> bool:
    with _lock:
        datos = _cargar()
        antes = len(datos["hechos"])
        datos["hechos"] = [h for h in datos["hechos"] if h["id"] != hid]
        if len(datos["hechos"]) != antes:
            _guardar(datos)
            return True
    return False


# Frases claras para guardar datos sin que lo pidas (solo texto escrito por el usuario).
_INTERROGATIVO = re.compile(r"^(?:que|como|donde|cuando|quien|quienes|cual|cuales|cuanto|cuantos|por que|"
                            r"puedes|podrias|sabes|dime|dame|hazme|crea|escribe|busca|cambia|agrega|"
                            r"muestra|abre|lee|resume|traduce|explica)\b")
_NO_VALOR = re.compile(r"^(?:que|como|cuando|este|esta|eso|esa|tu|su|el que|lo que|poco|mucho|todo|nada|"
                       r"estar|ver|hacer|cuando)\b")
_CORTE = re.compile(r"\s+(?:y|e|pero|porque|aunque|ademas|asi que|entonces|y que|que|para|cuando|"
                    r"desde|hace|tambien|soy|tengo|estoy|vivo|estudio|trabajo)\s+.*$|[.,;!?\n].*$")

_RELACIONES = ("mama", "papa", "madre", "padre", "hermano", "hermana", "hermanito", "hermanita",
               "novio", "novia", "esposo", "esposa", "amigo", "amiga", "mejor amigo", "mejor amiga",
               "primo", "prima", "tio", "tia", "abuelo", "abuela", "perro", "perra", "gato", "gata",
               "mascota", "profesor", "profesora", "jefe", "jefa", "companero", "companera")
_REL_RE = "|".join(sorted(_RELACIONES, key=len, reverse=True))
_CARRERA = ("licenciatura|carrera|ingenieria|maestria|doctorado|bachillerato|tecnico|medicina|derecho|"
            "economia|administracion|arquitectura|psicologia|diseno|contaduria|negocios|biologia|"
            "quimica|fisica|matematica|matematicas|informatica|sistemas|periodismo|enfermeria")


_CORTE_SUAVE = re.compile(r"\s+(?:pero|porque|aunque|asi que|entonces)\s+.*$|[.,;!?\n].*$")


def _valor(original: str, plano: str, inicio: int, maximo: int = 60, suave: bool = False) -> str:
    resto_plano = plano[inicio:]
    corte = (_CORTE_SUAVE if suave else _CORTE).search(resto_plano)
    fin = inicio + (corte.start() if corte else len(resto_plano))
    return _recortar(original[inicio:fin].strip(" \"'«»()"), maximo)


def _bonito_nombre(s: str) -> str:
    return " ".join(p[:1].upper() + p[1:] if p.islower() else p for p in s.split())


def extraer_hechos(texto: str) -> list[tuple[str, str]]:
    """Datos claros dentro de lo que escribió la persona: lista de (clave, texto a guardar)."""
    if not texto or len(texto) > 400 or texto.lstrip().startswith("¿"):
        return []
    texto = texto.split("¿")[0]                      # lo que sigue a «¿» es una pregunta
    plano = _plain(texto)
    if _INTERROGATIVO.match(plano.strip()):
        return []
    out: list[tuple[str, str]] = []

    m = re.search(r"\b(?:me llamo|mi nombre es|mi nombre completo es|soy conocid[oa] como)\s+", plano)
    if m:
        v = _valor(texto, plano, m.end(), 40)
        palabras = v.split()
        if v and 1 <= len(palabras) <= 4 and all(w.replace("-", "").isalpha() for w in palabras):
            out.append(("nombre", f"Nombre: {_bonito_nombre(v)}"))

    m = re.search(r"\b(?:vivo en|resido en|vivimos en)\s+", plano)
    if m:
        v = _valor(texto, plano, m.end())
        if _mayuscula_inicial(v):
            out.append(("vive", f"Vive en: {v}"))
    m = re.search(r"\bsoy de\s+", plano)
    if m:
        v = _valor(texto, plano, m.end())
        if _mayuscula_inicial(v):
            out.append(("origen", f"Es de: {v}"))

    m = re.search(rf"\bestudio\s+((?:la\s+|el\s+)?(?:{_CARRERA})\b)", plano)
    if m:
        v = _valor(texto, plano, m.start(1), 80, suave=True)
        out.append(("estudia", f"Estudia: {v}"))
    else:
        m = re.search(r"\bestudio en\s+", plano)
        if m:
            v = _valor(texto, plano, m.end())
            if _mayuscula_inicial(v):
                out.append(("estudia", f"Estudia en: {v}"))

    m = re.search(r"\btrabajo en\s+", plano)
    if m:
        v = _valor(texto, plano, m.end())
        if _mayuscula_inicial(v):
            out.append(("trabaja", f"Trabaja en: {v}"))
    else:
        m = re.search(r"\btrabajo como\s+", plano)
        if m:
            v = _valor(texto, plano, m.end(), 50, suave=True)
            if v:
                out.append(("trabaja", f"Trabaja como: {v}"))

    m = re.search(r"\bmi\s+([a-z]+(?: [a-z]+)?)\s+favorit[oa]\s+es\s+", plano)
    if m:
        tema = texto[m.start(1):m.end(1)].lower()
        v = _valor(texto, plano, m.end(), 50, suave=True)
        if v:
            out.append((f"fav:{_norm(tema)}", f"Favorito — {tema}: {v}"))

    for m in re.finditer(rf"\bmi\s+({_REL_RE})\s+se llama\s+", plano):
        v = _valor(texto, plano, m.end(), 40)
        if v and _mayuscula_inicial(v):
            rel = texto[m.start(1):m.end(1)].lower()
            out.append((f"rel:{_norm(rel)}", f"Su {rel}: {_bonito_nombre(v)}"))
    for m in re.finditer(rf"\btengo\s+(?:un|una)\s+({_REL_RE})\s+(?:llamad[oa]|que se llama)\s+", plano):
        v = _valor(texto, plano, m.end(), 40)
        if v and _mayuscula_inicial(v):
            rel = texto[m.start(1):m.end(1)].lower()
            out.append((f"rel:{_norm(rel)}", f"Su {rel}: {_bonito_nombre(v)}"))

    m = re.search(r"\bme (?:gusta|gustan|encanta|encantan)\s+", plano)
    if m:
        v = _valor(texto, plano, m.end(), 45, suave=True)
        vp = _plain(v)
        if v and 3 <= len(v) and not _NO_VALOR.match(vp) and len(v.split()) <= 6:
            out.append((None, f"Le gusta: {v}"))
    return out


_EXPLICITO = re.compile(
    r"^(?:por favor[, ]+)?(?:(?:quiero que )?(?:recuerda(?:me)?|acuerdate|anota|apunta|memoriza|"
    r"no olvides|ten en cuenta|guarda(?:lo)?(?: en tu memoria)?)\s+(?:que\s+|esto:\s*|lo siguiente:?\s*|:\s*)"
    r"|(?:guarda|anota|apunta)\s+en\s+(?:tu\s+)?memoria\s+(?:que\s+|esto:\s*|:\s*)?"
    r"|memoriza\s+)(.+)$", re.S)


def _frase_estado(estado: str, texto: str) -> str:
    if estado == "secreto":
        return "No guardo contraseñas, claves, tarjetas ni documentos de identidad, así que eso no lo recordaré."
    if estado == "lleno":
        return "Mi memoria de datos está llena. Borra algunos en la pestaña Memoria y lo guardo."
    if estado == "vacio":
        return "No entendí qué quieres que recuerde."
    if estado == "repetido":
        return f"Eso ya lo tenía guardado: «{texto}»."
    if estado == "actualizado":
        return f"Actualicé lo que sabía: «{texto}»."
    return f"Listo, lo recordaré: «{texto}»."


# ───────────────────────── historial («lo que hemos trabajado») ─────────────────────────

def episodios() -> list[dict]:
    with _lock:
        return [dict(e) for e in _cargar()["episodios"]]


def registrar(chat_id: str | None, pregunta: str, respuesta: str, modo: str = "") -> bool:
    """Guarda un resumen corto de lo que se trabajó. No guarda nada si es privado o trivial."""
    with _lock:
        datos = _cargar()
        if not datos["config"]["historial"] or modo in MODOS_SIN_RECUERDO:
            return False
        pregunta = _recortar(pregunta or "", MAX_PREGUNTA)
        respuesta = re.sub(r"\[\d+(?:\s*[,;]\s*\d+)*\]|https?://\S+", "", respuesta or "")
        respuesta = _recortar(respuesta, MAX_RESPUESTA)
        if len(pregunta) < 12 or not respuesta:
            return False
        if modo == "charla" and len(pregunta) < 25:
            return False
        if es_secreto(pregunta) or es_secreto(respuesta):
            return False
        if datos["episodios"]:
            u = datos["episodios"][-1]
            if u.get("chat") == chat_id and _norm(u["pregunta"]) == _norm(pregunta):
                return False
        datos["episodios"].append({"id": _id(), "chat": chat_id, "ts": _ahora(),
                                   "pregunta": pregunta, "respuesta": respuesta, "modo": modo})
        if len(datos["episodios"]) > MAX_EPISODIOS:
            datos["episodios"] = datos["episodios"][-MAX_EPISODIOS:]
        _guardar(datos)
        return True


def borrar_episodio(eid: str) -> bool:
    with _lock:
        datos = _cargar()
        antes = len(datos["episodios"])
        datos["episodios"] = [e for e in datos["episodios"] if e["id"] != eid]
        if len(datos["episodios"]) != antes:
            _guardar(datos)
            return True
    return False


_PASADO_FUERTE = re.compile(
    r"\b(?:hablamos|trabajamos|hicimos|hemos (?:hecho|hablado|trabajado|visto)|"
    r"te (?:pregunte|dije|pedi|mande|comente)|me (?:dijiste|respondiste|contestaste|explicaste)|dijiste|"
    r"la otra vez|el otro dia|en otro chat|chat anterior|conversacion anterior|ayer hablamos|"
    r"lo que (?:hicimos|hablamos|trabajamos)|en que (?:hemos )?trabajamos|que (?:hemos )?hecho)\b")
_PASADO_FLOJO = re.compile(r"\b(?:te acuerdas|recuerdas|te acordas)\b")
_PASADO = re.compile(f"(?:{_PASADO_FUERTE.pattern})|(?:{_PASADO_FLOJO.pattern})")
_NO_PASADO = re.compile(r"\b(?:recuerda(?:me)? que|recuerdame)\b")


def _fecha_corta(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso).astimezone()
    except ValueError:
        return ""
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    hoy = datetime.now().astimezone().date()
    if d.date() == hoy:
        return "hoy"
    if d.date() == hoy - timedelta(days=1):
        return "ayer"
    return f"{d.day} {meses[d.month - 1]}"


def buscar_episodios(texto: str, limite: int = 3) -> list[dict]:
    """Los recuerdos que mejor se parecen a lo que preguntas (por palabras clave)."""
    claves = _raices(texto)
    with _lock:
        eps = list(_cargar()["episodios"])
    if not eps:
        return []
    if not claves:                                    # «¿en qué hemos trabajado?» → lo más reciente
        return list(reversed(eps[-limite:]))
    minimo = 1 if len(claves) <= 2 else 2
    puntuados = []
    for pos, e in enumerate(eps):
        q = _raices(e["pregunta"])
        a = _raices(e["respuesta"])
        n = 2 * len(claves & q) + len(claves & a - q)
        if len(claves & (q | a)) >= minimo:
            puntuados.append((n, pos, e))
    puntuados.sort(key=lambda x: (-x[0], -x[1]))
    return [e for _, _, e in puntuados[:limite]]


def _responder_pasado(texto: str, estricto: bool) -> dict | None:
    # quita las palabras del disparador para quedarse con el tema
    tema = _PASADO.sub(" ", _plain(texto))
    tema = re.sub(r"\b(?:sobre|acerca|lo|que|el|la|los|las|de|del|en|con|un|una)\b", " ", tema)
    hallados = buscar_episodios(tema)
    if not hallados:
        if not estricto:
            return None                       # «¿recuerdas la capital de Francia?» no es de memoria
        if not episodios():
            return {"message": "Todavía no tengo recuerdos guardados de lo que hemos trabajado. "
                               "Desde ahora iré guardando un resumen de cada tema."}
        return {"message": "No encuentro nada así en lo que hemos trabajado. Puede que fuera antes de "
                           "activar la memoria, o que lo hayas borrado. Prueba con otras palabras."}
    lineas = ["Esto es lo que encuentro en nuestras conversaciones:"]
    for e in hallados:
        q = _recortar(e["pregunta"], 130)
        r = _recortar(e["respuesta"], 130)
        lineas.append(f"• {_fecha_corta(e['ts'])} — me pediste: «{q}» → {r}")
    lineas.append("Puedes ver y borrar todo esto en la pestaña Memoria.")
    return {"message": "\n".join(lineas)}


# ───────────────────────── preguntas sobre ti ─────────────────────────

_LISTAR = re.compile(
    r"\b(?:que (?:sabes|recuerdas|tienes guardado|has guardado|guardaste|conoces) (?:de|sobre) mi|"
    r"que datos (?:mios|miyos|de mi) tienes|que hay en tu memoria|muestrame tu memoria|"
    r"dime (?:todo )?lo que sabes de mi|que sabes sobre mi|que tienes en tu memoria)\b")


def _hecho_por_clave(clave: str) -> dict | None:
    for h in _cargar()["hechos"]:
        if h.get("clave") == clave:
            return h
    return None


def _valor_hecho(h: dict) -> str:
    return h["texto"].split(": ", 1)[-1]


def _listar() -> dict:
    hs = hechos()
    n_ep = len(episodios())
    if not hs:
        extra = f" Tengo {n_ep} recuerdos de lo que hemos trabajado." if n_ep else ""
        return {"message": "Todavía no sé nada tuyo. Puedes decirme «me llamo…», «vivo en…» o «recuerda que…»." + extra}
    lineas = ["Esto es lo que sé de ti:"] + [f"• {h['texto']}" for h in hs[:25]]
    if len(hs) > 25:
        lineas.append(f"… y {len(hs) - 25} más.")
    if n_ep:
        lineas.append(f"Además tengo {n_ep} recuerdos de lo que hemos trabajado.")
    lineas.append("Puedes corregir o borrar cualquier cosa en la pestaña Memoria.")
    return {"message": "\n".join(lineas)}


_CONSULTAS = [  # (regex, clave, respuesta con valor, respuesta si no sé)
    (r"\b(?:como me llamo|cual es mi nombre|sabes como me llamo|recuerdas mi nombre|como te dije que me llamo)\b",
     "nombre", "Te llamas {v}.", "Todavía no me has dicho tu nombre. Dímelo con «me llamo…» y lo recordaré."),
    (r"\b(?:donde vivo|en que (?:ciudad|lugar|pais) vivo|sabes donde vivo)\b",
     "vive", "Vives en {v}.", "Todavía no me has dicho dónde vives."),
    (r"\b(?:de donde soy|sabes de donde soy)\b",
     "origen", "Eres de {v}.", "Todavía no me has dicho de dónde eres."),
    (r"\b(?:que estudio|que carrera estudio|donde estudio|sabes que estudio)\b",
     "estudia", "Estudias: {v}.", "Todavía no me has dicho qué estudias."),
    (r"\b(?:donde trabajo|en que trabajo|de que trabajo|sabes donde trabajo)\b",
     "trabaja", "Trabajas: {v}.", "Todavía no me has dicho dónde trabajas."),
]


def _responder_consulta(plano: str) -> dict | None:
    for patron, clave, si, no in _CONSULTAS:
        if re.search(patron, plano):
            h = _hecho_por_clave(clave)
            return {"message": si.format(v=_valor_hecho(h)) if h else no}
    m = re.search(r"\bcual es mi ([a-z]+(?: [a-z]+)?) favorit[oa]\b", plano)
    if m:
        h = _hecho_por_clave(f"fav:{_norm(m.group(1))}")
        return {"message": f"Tu {m.group(1)} favorito: {_valor_hecho(h)}." if h
                else f"Todavía no me has dicho cuál es tu {m.group(1)} favorito."}
    m = re.search(rf"\bcomo se llama mi ({_REL_RE})\b", plano)
    if m:
        h = _hecho_por_clave(f"rel:{m.group(1)}")
        return {"message": f"Tu {m.group(1)} se llama {_valor_hecho(h)}." if h
                else f"Todavía no me has dicho cómo se llama tu {m.group(1)}."}
    return None


# ───────────────────────── olvidar ─────────────────────────

_OLVIDAR_TODO = re.compile(
    r"^(?:(?:olvida|olvidate de)\s+(?:todo|todos mis datos|toda mi informacion|mis datos)\b"
    r"|(?:borra|elimina|limpia|resetea|reinicia|vacia)\s+(?:toda\s+)?(?:tu|la)\s+memoria\b"
    r"|(?:borra|elimina)\s+(?:todos\s+)?(?:mis datos|toda mi informacion|todo lo que (?:sabes|recuerdas|tienes) de mi"
    r"|todo lo que te (?:dije|he dicho))\b)")
_OLVIDAR_HISTORIAL = re.compile(
    r"^(?:olvida|borra|elimina|limpia)\s+(?:todo\s+)?(?:nuestras conversaciones|el historial de (?:lo que hemos|nuestras)|"
    r"lo que hemos (?:hablado|trabajado|hecho)|los recuerdos|lo que trabajamos)\b")
_OLVIDAR_ALGO = re.compile(
    r"^(?:olvida|(?:borra|elimina|quita)\s+de\s+(?:tu|la)\s+memoria)\s+(?:que\s+|lo de\s+|lo que dije (?:de|sobre)\s+|"
    r"lo que te dije (?:de|sobre)\s+|mi\s+|el dato (?:de|sobre)\s+)?(.+)$")
_SI = re.compile(r"^(?:si|claro|confirmo|confirmado|dale|adelante|ok|okay|olvidalo(?: todo)?|"
                 r"si olvidalo(?: todo)?|si borra(?:lo)?(?: el historial)?|si olvida(?:lo)? todo)\b")
_NO = re.compile(r"^(?:no|cancela|cancelar|mejor no|detente|para)\b")


def _contenido(m) -> str:
    if isinstance(m, dict):
        for k in ("content", "text", "answer", "message"):
            if isinstance(m.get(k), str):
                return m[k]
    return m if isinstance(m, str) else ""


def _rol(m) -> str:
    return str(m.get("role", "")) if isinstance(m, dict) else ""


def _ultimo_de_pk(history) -> str:
    for m in reversed(history or []):
        if _rol(m) in ("assistant", "pk", "bot", "asistente"):
            return _contenido(m)
    return ""


def olvidar_todo(solo_historial: bool = False) -> tuple[int, int]:
    with _lock:
        datos = _cargar()
        h, e = len(datos["hechos"]), len(datos["episodios"])
        if not solo_historial:
            datos["hechos"] = []
        datos["episodios"] = []
        _guardar(datos)
        return (0 if solo_historial else h), e


def _olvidar_algo(tema: str) -> dict:
    claves = _raices(tema)
    if not claves:
        return {"message": "¿Qué quieres que olvide? Dímelo así: «olvida que vivo en…» o usa la pestaña Memoria."}
    with _lock:
        datos = _cargar()
        puntos = [(len(claves & _raices(h["texto"])), h) for h in datos["hechos"]]
        mejor = max((n for n, _ in puntos), default=0)
        if mejor == 0:
            return {"message": "No tengo guardado nada que coincida con eso. Mira la pestaña Memoria o dime «qué sabes de mí»."}
        coinciden = [h for n, h in puntos if n == mejor]
        if len(coinciden) > 1:
            # con empate NO se borra nada: es mejor preguntar que perder un dato por error
            lista = "; ".join(h["texto"] for h in coinciden[:4])
            return {"message": f"Eso coincide con varias cosas ({lista}). Dime cuál exactamente o bórrala en la pestaña Memoria."}
        ids = {h["id"] for h in coinciden}
        datos["hechos"] = [h for h in datos["hechos"] if h["id"] not in ids]
        _guardar(datos)
    cuerpo = "; ".join(h["texto"] for h in coinciden)
    return {"message": f"Olvidé: {cuerpo}."}


# ───────────────────────── configuración ─────────────────────────

def config() -> dict:
    with _lock:
        return dict(_cargar()["config"])


def cambiar_config(**cambios) -> dict:
    with _lock:
        datos = _cargar()
        for k, v in cambios.items():
            if k in CONFIG_INICIAL and isinstance(v, bool):
                datos["config"][k] = v
        _guardar(datos)
        return dict(datos["config"])


_ENCENDER = re.compile(r"^(?:activa|enciende|reanuda|prende|vuelve a activar)\s+(?:la\s+|tu\s+)?memoria\b")
_APAGAR = re.compile(r"^(?:desactiva|apaga|pausa|detén|deten|para)\s+(?:la\s+|tu\s+)?memoria\b|"
                     r"^(?:deja de|no)\s+(?:guardar|recordar|guardes|recuerdes)\s+(?:mas\s+)?(?:cosas|datos|nada)\b")


# ───────────────────────── entrada principal ─────────────────────────

def handle(texto: str, chat_id: str | None = None, history=None) -> dict | None:
    """Órdenes y preguntas de memoria. Devuelve {'message': ...} o None si no es de memoria.

    Debe llamarse SOLO con lo que escribió o dijo la persona, nunca con texto de documentos.
    """
    if not texto or len(texto) > 600:
        return None
    plano = re.sub(r"\s+", " ", _plain(texto)).strip(" ¿?¡!.")
    plano_corto = re.sub(r"[¿?¡!.,;]+", " ", plano).strip()

    # confirmaciones pendientes («¿Seguro?» en el mensaje anterior de PK)
    ultimo = _ultimo_de_pk(history)
    if ultimo and (CONFIRMA_TODO in ultimo or CONFIRMA_HISTORIAL in ultimo):
        if _SI.match(plano_corto):
            solo_hist = CONFIRMA_HISTORIAL in ultimo
            h, e = olvidar_todo(solo_historial=solo_hist)
            if solo_hist:
                return {"message": f"Listo, borré {_plural(e, 'recuerdo', 'recuerdos')} de lo que hemos trabajado."}
            return {"message": f"Listo, olvidé todo: {_plural(h, 'dato tuyo', 'datos tuyos')} y "
                               f"{_plural(e, 'recuerdo', 'recuerdos')} de conversaciones."}
        if _NO.match(plano_corto):
            return {"message": "Cancelado. No borré nada."}

    # guardar de forma explícita
    original = texto.strip()
    m = _EXPLICITO.match(_plain(original))
    if m:
        contenido = original[m.start(1):].strip()
        h, estado = agregar_hecho(contenido, origen="pedido", chat=chat_id)
        return {"message": _frase_estado(estado, h["texto"] if h else contenido)}

    # olvidar
    if _OLVIDAR_TODO.match(plano_corto):
        h, e = len(hechos()), len(episodios())
        if not (h or e):
            return {"message": "No tengo nada guardado de ti, así que no hay nada que olvidar."}
        return {"message": f"¿Seguro? Voy a borrar todo lo que sé de ti: {_plural(h, 'dato', 'datos')} y "
                           f"{_plural(e, 'recuerdo', 'recuerdos')} de conversaciones. No se puede deshacer. {CONFIRMA_TODO}"}
    if _OLVIDAR_HISTORIAL.match(plano_corto):
        e = len(episodios())
        if not e:
            return {"message": "No tengo recuerdos de conversaciones guardados."}
        return {"message": f"¿Seguro? Voy a borrar {_plural(e, 'recuerdo', 'recuerdos')} de lo que hemos trabajado (tus datos personales "
                           f"se quedan). No se puede deshacer. {CONFIRMA_HISTORIAL}"}
    m = _OLVIDAR_ALGO.match(plano_corto)
    if m:
        return _olvidar_algo(m.group(1))

    # configuración
    if _APAGAR.match(plano_corto):
        cambiar_config(hechos_auto=False, historial=False)
        return {"message": "Memoria en pausa: no guardaré datos nuevos ni recuerdos de lo que trabajemos. "
                           "Lo que ya tenía sigue ahí (puedes borrarlo en la pestaña Memoria). "
                           "Dime «activa la memoria» para reanudarla."}
    if _ENCENDER.match(plano_corto):
        cambiar_config(hechos_auto=True, historial=True)
        return {"message": "Memoria activada otra vez."}

    # preguntas sobre ti y sobre lo trabajado
    if _LISTAR.search(plano):
        return _listar()
    r = _responder_consulta(plano)
    if r:
        return r
    if not _NO_PASADO.search(plano):
        if _PASADO_FUERTE.search(plano):
            return _responder_pasado(texto, estricto=True)
        if _PASADO_FLOJO.search(plano):
            return _responder_pasado(texto, estricto=False)
    return None


def auto_guardar(texto: str, chat_id: str | None = None) -> list[dict]:
    """Guarda datos claros que la persona dijo de sí misma. Devuelve lo guardado (para avisarle)."""
    with _lock:
        if not _cargar()["config"]["hechos_auto"]:
            return []
    guardados = []
    for clave, frase in extraer_hechos(texto):
        h, estado = agregar_hecho(frase, clave=clave, origen="auto", chat=chat_id)
        if h and estado in ("nuevo", "actualizado"):
            guardados.append({**h, "estado": estado})
    return guardados


def nota_guardado(guardados: list[dict]) -> str:
    """Aviso corto para añadir al final de la respuesta cuando se guardó algo solo."""
    if not guardados:
        return ""
    cuerpo = "; ".join(g["texto"] for g in guardados[:3])
    return f"(Guardé en tu memoria: {cuerpo}. Puedes borrarlo en la pestaña Memoria.)"


def contexto(pregunta: str, max_chars: int = 500) -> str:
    """Datos tuyos relevantes para darle al modelo al conversar. Vacío si no hay o está desactivado."""
    with _lock:
        datos = _cargar()
        if not datos["config"]["usar"] or not datos["hechos"]:
            return ""
        hs = list(datos["hechos"])
    claves = _raices(pregunta)

    def peso(h):
        base = 3 if h.get("clave") == "nombre" else 0
        return base + len(claves & _raices(h["texto"]))
    hs.sort(key=lambda h: -peso(h))
    lineas, total = [], 0
    for h in hs:
        linea = f"- {h['texto']}"
        if total + len(linea) > max_chars:
            break
        lineas.append(linea)
        total += len(linea) + 1
    if not lineas:
        return ""
    return ("Datos que la persona te pidió recordar o dijo de sí misma (úsalos solo si vienen al caso; "
            "no los repitas sin que los necesite):\n" + "\n".join(lineas))


# ───────────────────────── para la pestaña «Memoria» ─────────────────────────

def exportar() -> dict:
    """Todo lo que PK sabe de ti, para descargarlo como archivo."""
    with _lock:
        d = _cargar()
        return {"exportado": _ahora(), "datos_sobre_ti": [dict(h) for h in d["hechos"]],
                "lo_que_hemos_trabajado": [dict(e) for e in d["episodios"]], "ajustes": dict(d["config"])}


def instantanea() -> dict:
    """Todo lo que muestra la pestaña Memoria."""
    with _lock:
        d = _cargar()
        return {"config": dict(d["config"]),
                "hechos": [dict(h) for h in d["hechos"]],
                "episodios": [dict(e) for e in reversed(d["episodios"])],
                "limites": {"hechos": MAX_HECHOS, "episodios": MAX_EPISODIOS}}
