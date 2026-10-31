"""La carpeta de trabajo de PK: crea y modifica archivos de texto dentro de  espacio/  (y SOLO ahí).

    «Crea un bloc de notas que contenga los nombres de los continentes, llama al archivo mundo»
    «Al archivo mundo agrégale el nombre de 5 países por cada continente»
    «Muéstrame el archivo mundo»  ·  «¿Qué archivos tengo?»  ·  «Deshaz el último cambio del archivo mundo»
    «Reemplaza el contenido del archivo mundo por…»  ·  «Cambia el nombre del archivo mundo a continentes»
    «Crea un archivo con esa información» (usa tu respuesta anterior)  ·  «Cambia el nombre del archivo a …» (el último de la charla)

Reglas de seguridad (a propósito, mientras PK no tenga acceso a todo tu PC):
  · Solo escribe dentro de la carpeta  espacio/  del proyecto. Nombres con rutas, «..» o símbolos raros se rechazan.
  · Solo formatos de texto: .txt .md .csv .json. Nunca ejecuta lo que crea.
  · Nunca borra. «Crear» se niega si el archivo ya existe. Solo «reemplazar el contenido» y «agregar» cambian un archivo,
    y siempre guardan antes la versión anterior en  espacio/.versiones/  para poder deshacer.
  · Solo se interpreta lo que TÚ escribes o dices; el texto de documentos, adjuntos o la web nunca crea ni cambia archivos.
"""
import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

from . import config, perfil

ESPACIO = config.ROOT / "espacio"
EXTS = (".txt", ".md", ".csv", ".json")
MAX_BYTES = 200_000            # tamaño máximo de un archivo
MAX_NEW_CHARS = 20_000         # lo máximo que se escribe de una vez
SHOW_CHARS = 1500              # cuánto se muestra en el chat
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}

plain = perfil.plain
_W = r"[\w\-]+"
_NAME = r"(?!(?:por|a|al|con|y|e|que|de|del|el|la|los|las|un|una|en|para|como|su|mi|adjunt\w*|anterior|siguiente|mismo|misma)\b)" + _W + r"(?:\.\w{1,5})?(?:\s+" + _W + r"){0,3}?"   # acepta cualquier extensión para poder rechazar las no permitidas
_STOP = (r"(?=\s+(?:\d+|por|cada|y|e|que|con|donde|para|el|la|los|las|un|una|unos|unas|lo|le|en|sobre|de|del|este|esto|esa|"
         r"agreg\w*|anad\w*|pon\w*|inclu\w*|escrib\w*|anot\w*|sum\w*|complet\w*|insert\w*|actualiz\w*|ampli\w*)\b|[,.;:!?\"»”']|$)")
_QUOTED = r"[\"«“']([^\"»”']{1,60})[\"»”']"

_NOUN = r"(?:archivo(?:\s+de\s+texto)?|bloc\s+de\s+notas|block\s+de\s+notas|nota)"
_FILE_REF = re.compile(r"\b(?:al|en\s+el|del|a\s+el|el)\s+" + _NOUN + r"\s+(?:(?:llamad[oa]|de\s+nombre)\s+)?(?:" + _QUOTED + r"|(" + _NAME + r")" + _STOP + r")")
_APPEND = re.compile(r"\b(agreg\w*|anad\w*|ponle|pon\w*|inclu\w*|escrib\w*|anot\w*|sum\w*|complet\w*|insert\w*|actualiz\w*|ampli\w*)\b")
_CREATE = re.compile(
    r"\b(cre[ae]\w*|haz|hazme|genera\w*|escribe\w*|redacta\w*|guarda\w*|prepara\w*|construye\w*)\b[^.?!]*?"
    r"\b(?:un|una|el|otro|otra|mi|nuevo|nueva)\s+(?:nuevo\s+|nueva\s+)?(bloc\s+de\s+notas|block\s+de\s+notas|archivo(?:\s+de\s+texto)?|nota|csv|markdown|json)\b"
)
_NAME_CREATE = [
    re.compile(r"\b" + _NOUN + r"\s+(?:de\s+texto\s+)?" + _QUOTED + r"()"),   # «archivo "mi lista"»: el nombre entre comillas, sin decir «llama»
    re.compile(r"\bll[aá]m(?:ad[oa]|a(?:lo|la|le)?)\s+(?:al\s+)?(?:" + _NOUN + r"\s+)?(?:como\s+)?(?:" + _QUOTED + r"|(" + _NAME + r")" + _STOP + r")", re.I),
    re.compile(r"\b(?:con\s+(?:el\s+)?nombre|de\s+nombre|que\s+se\s+llame|se\s+llame|nombrado|titulado|con\s+t[ií]tulo)\s+(?:de\s+)?(?:" + _QUOTED + r"|(" + _NAME + r")" + _STOP + r")", re.I),
]
_VIEW = re.compile(r"\b(muestra\w*|ensena\w*|lee|leer|lee\w*|abre|abrir|ver|dime|que\s+(?:dice|contiene|tiene)|cual\s+es\s+el\s+contenido)\b")
_LIST = re.compile(r"\b(que|cuales|lista\w*|muestra\w*|ver|dime|cuantos)\b.*\b(archivos|notas|blocs\s+de\s+notas)\b.*\b(tengo|mis|creados|creaste|guardados|hay|espacio|hiciste)\b|"
                   r"\b(que|cuales)\b.*\b(archivos|notas)\b.*\b(tengo|creaste|hiciste)\b")
_RENAME = re.compile(r"\b(renombr\w*|(?:cambi\w*|reemplaz\w*|modific\w*|actualiz\w*|pon\w*)\s+(?:el\s+)?(?:nombre|titulo)\s+(?:del|de\s+el)\s+(?:archivo|bloc\s+de\s+notas|block\s+de\s+notas|nota)|ponle\s+(?:de\s+)?(?:por\s+)?nombre)\b")
_REPLACE = re.compile(r"\b(?:reemplaz\w*|sustituy\w*|cambi\w*|modific\w*|actualiz\w*|borra\w*)\b[^.?!]*?\bcontenido\b|\b(?:sobrescrib\w*|reescrib\w*|rehaz|rehac\w*)\b[^.?!]*?\b(?:archivo|bloc\s+de\s+notas|nota)\b")
_GENERIC_REF = re.compile(r"\b(?:el|al|del|este|ese|dicho|mi)\s+(?:archivo|bloc\s+de\s+notas|block\s+de\s+notas|nota)\b")
_REF_INFO = re.compile(r"\b(?:esa|esta|dicha|aquella|la\s+misma)\s+informacion\b|\blo\s+anterior\b|\blo\s+que\s+(?:dijiste|respondiste|me\s+diste|acabas\s+de)\b|\b(?:esa|esta|la)\s+(?:respuesta|lista|tabla|explicacion)\b|\b(?:eso|esto)\b")
_TRANSFORM = re.compile(r"\b(resum\w*|traduc\w*|ordena\w*|acorta\w*|mejora\w*|corrige\w*|convierte\w*|tabla|formato|explica\w*|simplifica\w*)\b")
_OFFICE = re.compile(r"\b(pdf|word|docx|excel|xlsx|powerpoint|pptx)\b")
_UNDO = re.compile(r"\b(deshaz|deshacer|revierte|revertir|restaura\w*|vuelve\s+atras)\b.*\b(?:archivo|bloc\s+de\s+notas|block\s+de\s+notas|nota)\b")


# ------------------------------------------------------------------ carpeta y nombres
def _files() -> list[Path]:
    if not ESPACIO.exists():
        return []
    return sorted((p for p in ESPACIO.iterdir() if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in EXTS),
                  key=lambda p: p.name.lower())


def _find(name: str):
    """El archivo existente que se llama así (con o sin extensión, sin importar mayúsculas ni tildes)."""
    target = plain(name.strip())
    for path in _files():
        if plain(path.name) == target or plain(path.stem) == target:
            return path
    return None


def _clean_name(raw: str, default_ext: str):
    """(nombre_de_archivo, None) o (None, motivo)."""
    raw = " ".join(raw.strip(" .,;:!¡¿?\"'«»“”").split())
    stem, ext = raw, default_ext
    if "." in raw:
        stem, ext = raw.rsplit(".", 1)
        ext = "." + ext.lower()
        if ext not in EXTS:
            return None, f"Solo creo archivos {', '.join(EXTS)}; «{ext}» no."
    stem = stem.strip(" .")
    if not stem or len(stem) > 60 or not re.fullmatch(r"[\w\- ()]+", stem):
        return None, "Ese nombre no me sirve: usa hasta 60 letras, números, espacios o guiones (sin símbolos ni rutas)."
    if stem.lower() in RESERVED:
        return None, f"«{stem}» es un nombre reservado de Windows; elige otro."
    return stem + ext, None


def _inside(path: Path) -> bool:
    try:
        return path.resolve().parent == ESPACIO.resolve()
    except OSError:
        return False


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _write(path: Path, text: str) -> None:
    ESPACIO.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=ESPACIO, suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8-sig" if path.suffix.lower() == ".csv" else "utf-8", newline="") as out:
        out.write(text)
    os.replace(tmp, path)  # reemplazo atómico: el archivo nunca queda a medias


def _versions(path: Path) -> list[Path]:
    folder = ESPACIO / ".versiones"
    return sorted(folder.glob(path.name + ".*.bak")) if folder.exists() else []


def _backup(path: Path) -> None:
    folder = ESPACIO / ".versiones"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, folder / f"{path.name}.{time.time_ns()}.bak")


# ------------------------------------------------------------------ el contenido lo redacta el modelo
_SYSTEM = (
    "Eres {NOMBRE}, y redactas el contenido de archivos de texto que te pide el usuario. "
    "Responde SOLO con el contenido del archivo: sin saludo, sin explicaciones, sin comillas y sin bloques de código. "
    "Cuando sea una lista, escribe una línea por elemento. Escribe en español. "
    "No inventes: incluye solo datos que conozcas con seguridad y no repitas elementos."
)
_FORMAT = {".csv": " Formato CSV: valores separados por comas y, si es una tabla nueva, primera línea con los encabezados.",
           ".json": " Responde únicamente con JSON válido.",
           ".md": " Puedes usar formato Markdown.", ".txt": " Texto plano, sin formato Markdown."}


def _tidy(text: str) -> str:
    """Quita lo que el modelo suele añadir por cortesía: cercas de código, «Claro, aquí tienes…» y despedidas."""
    text = re.sub(r"^```[a-z]*\n?|\n?```$", "", text.strip(), flags=re.M).strip()
    lines = text.splitlines()
    if lines and re.match(r"^(claro|por supuesto|aqu[ií]|listo|ok|entendido|de acuerdo)\b.*[:.!]?\s*$", plain(lines[0])) and lines[0].rstrip().endswith(":") and len(lines) > 1:
        lines = lines[1:]
    while lines and re.match(r"^(espero|si necesitas|si quieres|avisame|dime si|¿necesitas|puedo ayudarte)", plain(lines[-1].strip())):
        lines.pop()
    return "\n".join(lines).strip()


def _compose(generate, instruction: str, ext: str, existing: str | None = None, context: str | None = None) -> str:
    system = _SYSTEM + _FORMAT.get(ext, "")
    base = f"INFORMACIÓN DE LA CONVERSACIÓN (úsala como base y no inventes nada fuera de ella):\n{context[:3000]}\n\n" if context else ""
    if existing is None:
        user = f"{base}Pedido del usuario: {instruction}\n\nContenido del archivo:"
    else:
        system += " El archivo ya tiene contenido: escribe SOLO el texto nuevo que hay que añadirle al final, sin repetir lo que ya está, y mantén su estilo."
        user = f"{base}CONTENIDO ACTUAL DEL ARCHIVO:\n{existing[-3000:]}\n\nPedido del usuario: {instruction}\n\nTexto nuevo a añadir al final:"
    return _tidy(generate(system, user, None, 900))[:MAX_NEW_CHARS]


def _looks_bad(text: str) -> bool:
    """Textos que un modelo pequeño suelta cuando se pierde: vacíos, repetidos o solo encabezados que terminan en «:»."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(text.strip()) < 2 or not lines:
        return True
    if all(line.endswith(":") for line in lines):
        return True
    return len(lines) >= 3 and len(set(lines)) * 2 <= len(lines)


BAD_MESSAGE = ("El modelo no logró escribirlo bien (salió texto vacío, repetido o sin contenido), así que no cambié nada. "
               "Prueba con un pedido más concreto, por ejemplo: «crea un bloc de notas llamado mundo que contenga los 6 continentes».")


def _clean_answer(text: str) -> str:
    """Una respuesta anterior de PK, lista para guardarla en un archivo: sin citas [1], enlaces ni marcas de formato."""
    text = re.sub(r"\[\d+(?:\s*[,;]\s*\d+)*\]", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_`#>]+", "", text)
    return re.sub(r"[ \t]+\n", "\n", text).strip()[:6000]


def _is_file_message(content: str) -> bool:
    return (content.startswith("Listo") and bool(re.search(r"«[^»]+\.(?:txt|md|csv|json)»", content))) \
        or content.startswith("Esto tiene «") or content.startswith("Archivos en espacio/")


def _prev_answer(history) -> str:
    """La última respuesta de PK que NO fue sobre archivos (es a lo que se refiere «esa información»)."""
    for message in reversed(history or []):
        if message.get("role") == "assistant" and message.get("content") and not _is_file_message(message["content"]):
            return _clean_answer(message["content"])
    return ""


def _last_file(history):
    """El archivo del que se habló en el último mensaje de PK sobre archivos (a lo que se refiere «el archivo»)."""
    for message in reversed(history or []):
        if message.get("role") == "assistant" and _is_file_message(message.get("content", "")):
            found = re.search(r"«([^»]+\.(?:txt|md|csv|json))»", message["content"])
            return _find(found.group(1)) if found else None
    return None


def _make_content(generate, instruction: str, ext: str, history, existing: str | None = None):
    """(texto, nota, error): lo que se va a escribir. Si dices «esa información», parte de la respuesta anterior de PK."""
    asks_context = _REF_INFO.search(plain(instruction)) and not re.search(r":\s*\S.{20,}", instruction)
    context = _prev_answer(history) if asks_context else ""
    try:
        if context and not _TRANSFORM.search(plain(instruction)):
            return context, "copié tu respuesta anterior tal cual", None
        text = _compose(generate, instruction, ext, existing, context or None)
    except Exception as error:
        return None, None, f"No pude escribirlo ({str(error)[:120]}). No cambié nada."
    if _looks_bad(text):
        return None, None, BAD_MESSAGE
    return text, ("usé tu respuesta anterior como base" if context else None), None


def _shown(text: str) -> str:
    return text if len(text) <= SHOW_CHARS else text[:SHOW_CHARS].rstrip() + "\n…(el resto está en el archivo)"


# ------------------------------------------------------------------ entender lo que pides
def _name_from(text: str, p: str, patterns):
    """(nombre, tramo completo, tramo del nombre) tras «llama al archivo…». Se busca sin tildes, pero el nombre conserva
    mayúsculas y tildes cuando el texto original mide lo mismo."""
    source = text if len(text) == len(p) else p
    for pattern in patterns:
        found = pattern.search(p)
        if found:
            group = 1 if found.group(1) else 2
            return " ".join(source[found.start(group):found.end(group)].split()), found.span(), found.span(group), source
    return None, None, None, source


def _known_ref(p: str):
    """Un archivo que YA existe y se nombra en el mensaje tras «archivo / bloc de notas / nota»: (nombre, tramo)."""
    for path in sorted(_files(), key=lambda f: -len(f.stem)):
        found = re.search(r"\b(?:(?:al|en\s+el|del|a\s+el|el)\s+)?" + _NOUN + r"\s+(?:llamad[oa]\s+|de\s+nombre\s+)?" + re.escape(plain(path.stem)) + r"(?:\.\w{1,4})?\b", p)
        if found:
            return path.stem, found.span()
    return None


def _file_ref(p: str):
    found = _FILE_REF.search(p)
    if not found:
        return None
    return (found.group(1) or found.group(2) or "").strip(), found.span()


def _resolve_target(p: str, history):
    """(archivo, tramo del mensaje que lo nombra, nombre que no existe): por su nombre, o «el archivo» = el último de la charla."""
    known = _known_ref(p)
    if known:
        return _find(known[0]), known[1], None
    ref = _file_ref(p)
    if ref:
        return _find(ref[0]), ref[1], ref[0]
    generic = _GENERIC_REF.search(p)
    if generic:
        last = _last_file(history)
        if last:
            return last, generic.span(), None
    return None, None, None


def _new_name(text: str, p: str, start: int):
    """El nombre nuevo tras «a / por / como / :», buscando desde `start`: (nombre, tramo) o (None, None)."""
    pattern = re.compile(r"(?:\b(?:a|por|como)\s+|:\s*)(?:" + _QUOTED + r"|(" + _NAME + r")" + _STOP + r")")
    found = pattern.search(p, start)
    if not found:
        return None, None
    group = 1 if found.group(1) else 2
    source = text if len(text) == len(p) else p
    return " ".join(source[found.start(group):found.end(group)].split()), found.span()


def handle(text: str, generate, history=None) -> dict | None:
    """Si el mensaje pide crear, ampliar, reemplazar, renombrar, ver o deshacer un archivo, lo hace y devuelve {"message"}.

    `generate(system, user, history, max_tokens)` es el modelo de lenguaje (llm.generate); `history`, los mensajes
    anteriores del chat (para entender «esa información» o «el archivo»). Si el mensaje no es de archivos, devuelve None.
    """
    text = " ".join(text.split())
    p = plain(text)
    if not text:
        return None
    source = text if len(text) == len(p) else p

    # --- deshacer el último cambio de contenido
    if _UNDO.search(p):
        known = _known_ref(p)
        ref = known or re.search(r"\b(?:archivo|bloc\s+de\s+notas|block\s+de\s+notas|nota)\s+(?:llamad[oa]\s+)?(" + _NAME + r")" + _STOP, p)
        path = _find(known[0]) if known else (_find(ref.group(1)) if ref else None)
        if path is None and not ref:
            path = _last_file(history) or (max(_files(), key=lambda f: f.stat().st_mtime_ns) if _files() else None)
        if path is None:
            return {"message": "No encontré ese archivo en espacio/. " + _inventory()}
        versions = _versions(path)
        if not versions:
            return {"message": f"«{path.name}» no tiene cambios que deshacer. (PK nunca borra archivos: si quieres quitarlo, bórralo tú de la carpeta espacio/.)"}
        _write(path, _read(versions[-1]))
        versions[-1].unlink()
        return {"message": f"Listo: devolví «{path.name}» a como estaba antes de su último cambio.\n\n{_shown(_read(path))}"}

    # --- reemplazar el contenido, cambiar el nombre y/o agregar a un archivo que ya existe
    rename = _RENAME.search(p)
    rename_name = rename_span = None
    masked = p
    if rename:
        rename_name, name_span = _new_name(text, p, rename.end())
        rename_span = (rename.start(), name_span[1] if name_span else rename.end())
        masked = p[:rename_span[0]] + " " + p[rename_span[1]:]
    replace = bool(_REPLACE.search(masked))
    append = bool(_APPEND.search(masked)) and not replace
    if rename or replace or append:
        path, span, missing = _resolve_target(p, history)
        strong = bool(re.search(r"\b(agreg\w*|anad\w*|ponle)\b", p)) or replace or rename
        if path is None and missing and strong:  # con verbos ambiguos («escribe el resumen del archivo X») no me meto
            return {"message": f"No encuentro «{missing}» en la carpeta espacio/. {_inventory()} Si quieres crearlo: «crea un bloc de notas llamado {missing} que contenga…»."}
        if path is None and rename:
            return {"message": f"¿A qué archivo te refieres? Dime su nombre, por ejemplo «cambia el nombre del archivo mundo a continentes». {_inventory()}"}
        if path is not None:
            return _change(text, p, source, path, span, rename, rename_name, rename_span, replace, append, generate, history)

    # --- crear un archivo nuevo
    made = _CREATE.search(p)
    asking = (text.startswith("¿") or text.endswith("?")) and not re.search(r"\b(puedes|podrias|podria|quiero|quisiera|necesito|por favor)\b", p)
    if made and re.match(r"^\W*(como|por que|que es|cual es|cuando|donde|para que)\b", p):
        made = None
    if made and asking:
        made = None
    if made and not (made.group(2) == "nota" and not re.match(r"(cre[ae]|guarda|genera|prepara)", made.group(1))):
        kind = re.search(r"\b(markdown|csv|json)\b", p[made.start():made.end() + 25])  # «archivo markdown», «archivo csv»…
        default_ext = {"markdown": ".md", "csv": ".csv", "json": ".json"}.get(kind.group(1) if kind else "", ".txt")
        name, whole, _span, source = _name_from(text, p, _NAME_CREATE)
        if name:
            filename, problem = _clean_name(name, default_ext)
            if problem:
                return {"message": problem}
        else:
            filename = f"nota-{time.strftime('%Y%m%d-%H%M%S')}{default_ext}"
            counter = 1
            while _find(Path(filename).stem) is not None:  # dos «sin nombre» en el mismo segundo
                counter += 1
                filename = f"nota-{time.strftime('%Y%m%d-%H%M%S')}-{counter}{default_ext}"
        path = ESPACIO / filename
        if not _inside(path):
            return {"message": "Ese nombre no es válido: solo trabajo dentro de la carpeta espacio/."}
        existing = _find(path.stem)
        if existing is not None:
            return {"message": f"Ya existe «{existing.name}» en espacio/ y no lo sobrescribo. Para añadirle cosas dime «al archivo {existing.stem} agrégale…»; para cambiarlo todo, «reemplaza el contenido del archivo {existing.stem} por…»; o elige otro nombre."}
        instruction = (source[:whole[0]] + " " + source[whole[1]:]).strip() if whole else text
        content, note, problem = _make_content(generate, instruction, path.suffix.lower(), history)
        if problem:
            return {"message": problem.replace("No cambié nada.", "No creé ningún archivo.").replace("así que no cambié nada", "así que no creé el archivo")}
        if path.suffix.lower() == ".json":
            try:
                json.loads(content)
            except ValueError:
                return {"message": "El modelo no produjo un JSON válido, así que no guardé nada. Prueba de nuevo o pídelo como .txt."}
        _write(path, content + "\n")
        auto = "" if name else f" (no me dijiste el nombre, así que lo llamé «{filename}»)"
        office = _OFFICE.search(p)
        extra = f" Pediste {office.group(1).upper()}: por ahora solo hago .txt, .md, .csv y .json, así que lo guardé como texto." if office else ""
        return {"message": f"Listo: creé «{filename}» en la carpeta espacio/ de tu proyecto{auto}{f' ({note})' if note else ''}. Revísalo: lo redactó el modelo y puede tener errores.{extra}\n\n"
                           f"{_shown(content)}\n\nPara ampliarlo: «al archivo {path.stem} agrégale…»."}

    # --- ver un archivo
    if _VIEW.search(p):
        known = _known_ref(p)
        ref = known or re.search(r"\b(?:el\s+)?(?:archivo|bloc\s+de\s+notas|block\s+de\s+notas|nota)\s+(?:llamad[oa]\s+)?(" + _NAME + r")" + _STOP, p)
        path = _find(known[0]) if known else (_find(ref.group(1)) if ref else None)
        if path is not None:  # si no existe en espacio/, no es asunto mío: puede ser un adjunto o una pregunta normal
            body = _read(path)
            return {"message": f"Esto tiene «{path.name}» (carpeta espacio/):\n\n{_shown(body) if body.strip() else '(está vacío)'}"}

    # --- qué archivos hay
    if _LIST.search(p):
        return {"message": _inventory()}
    return None


def _change(text, p, source, path, span, rename, rename_name, rename_span, replace, append, generate, history):
    """Reemplaza el contenido, agrega y/o renombra. Primero se valida todo; solo si todo está bien se escribe algo."""
    ext = path.suffix.lower()
    if (replace or append) and ext == ".json" and append:
        return {"message": f"«{path.name}» es JSON: no lo amplío a ciegas porque podría dejarlo roto. Dime «reemplaza el contenido del archivo {path.stem} por…» o «crea un archivo json llamado otro nombre…»."}
    # el pedido, sin las partes que solo nombran el archivo o su nuevo nombre
    cuts = sorted([c for c in (span, rename_span) if c], reverse=True)
    instruction = source
    for start, end in cuts:
        instruction = instruction[:start] + " " + instruction[end:]
    instruction = re.sub(r"^(?:\s*(?:y|e|entonces|ahora|oye|muy bien|en efecto)\b[\s,]*)+", "", " ".join(instruction.split()), flags=re.I).strip(" ,") or text

    new_content = note = None
    if replace or append:
        current = _read(path)
        new_content, note, problem = _make_content(generate, instruction, ext, history, None if replace else current)
        if problem:
            return {"message": problem}
        if ext == ".json" and replace:
            try:
                json.loads(new_content)
            except ValueError:
                return {"message": "El modelo no produjo un JSON válido, así que no cambié nada."}
        final = new_content + "\n" if (replace or not current.strip()) else current.rstrip("\n") + "\n" + new_content + "\n"
        if len(final.encode("utf-8")) > MAX_BYTES:
            return {"message": f"«{path.name}» se haría demasiado grande (máximo {MAX_BYTES // 1000} KB). No cambié nada."}
    target = path
    if rename:
        if not rename_name:
            return {"message": "No entendí el nombre nuevo. Dime por ejemplo: «cambia el nombre del archivo mundo a continentes» (si lleva espacios, entre comillas)."}
        new_filename, problem = _clean_name(rename_name, ext)
        if problem:
            return {"message": problem}
        target = ESPACIO / new_filename
        clash = _find(target.stem)
        if not _inside(target) or (clash is not None and clash != path):
            return {"message": f"Ya existe «{clash.name}»: no lo sobrescribo. Elige otro nombre." if clash else "Ese nombre no es válido: solo trabajo dentro de la carpeta espacio/."}

    steps = []
    if new_content is not None:  # lo único que cambia el contenido: antes se guarda la versión anterior
        _backup(path)
        _write(path, final)
        steps.append("reemplacé el contenido" if replace else "agregué texto")
    if target != path:
        for old_version in _versions(path):
            old_version.rename(old_version.with_name(old_version.name.replace(path.name + ".", target.name + ".", 1)))
        path.rename(target)
        steps.append(f"ahora se llama «{target.name}»")
    shown = _read(target)
    head = f"Listo, en «{target.name}» (carpeta espacio/): " + " y ".join(steps) + (f" ({note})" if note else "") + "."
    tail = "Revísalo: lo redactó el modelo y puede tener errores." if new_content is not None and not note else ""
    undo = f"Si no te gusta: «deshaz el último cambio del archivo {target.stem}»." if new_content is not None else \
        f"Para volver al nombre anterior: «cambia el nombre del archivo {target.stem} a {path.stem}»."
    body = f"\n\n{_shown(new_content if append and new_content else shown)}" if new_content is not None else ""
    return {"message": f"{head} {tail}".strip() + f"{body}\n\n{undo}"}


def _inventory() -> str:
    files = _files()
    if not files:
        return "En la carpeta espacio/ todavía no hay archivos. Prueba: «crea un bloc de notas que contenga los nombres de los continentes, llama al archivo mundo»."
    return "Archivos en espacio/: " + ", ".join(f.name for f in files) + "."
