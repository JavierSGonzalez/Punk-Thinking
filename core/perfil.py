"""La identidad de PK: su nombre, su voz y los colores de su interfaz.

Se guarda en  data/perfil.json  y dura hasta que pidas otro cambio. Se cambia hablándole o escribiéndole:

    «Cambia tu nombre a Jarvis»  ·  «Usa la voz Sabina»  ·  «Habla más lento»
    «Cambia tu interfaz a un celeste claro»  ·  «Modo oscuro»  ·  «Deshaz el último cambio»  ·  «Restablece todo»

Seguridad: SOLO se interpreta lo que tú escribes o dices en esa conversación. El texto de tus documentos, de tus
archivos adjuntos o de la web nunca se interpreta como una orden. Los cambios son solo de apariencia e identidad
(no tocan tus archivos) y se pueden deshacer.
"""
import json
import os
import re
import tempfile
import threading
import unicodedata
from pathlib import Path

from . import config

FILE = config.ROOT / "data" / "perfil.json"
FIELDS = ("nombre", "voz", "velocidad", "acento", "fondo")  # None = el valor por defecto
_lock = threading.Lock()
_cache = {"mtime": None, "data": None}

RETIRED_VOICES = {"Loquendo masculina", "Loquendo femenina", "Amy", "Stolas niño"}
DEFAULT_LIGHT_ACCENT = "#d4006e"   # el acento del modo claro original
LIGHT_BG = "#f4f1e8"               # el fondo claro original


def plain(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


# ------------------------------------------------------------------ guardar y leer
def _empty() -> dict:
    return {f: None for f in FIELDS}


def _read() -> dict:
    """{"actual": {...}, "anterior": {...}}; si el archivo falta o está dañado, todo por defecto."""
    try:
        mtime = FILE.stat().st_mtime_ns
    except OSError:
        return {"actual": _empty(), "anterior": _empty()}
    if _cache["mtime"] == mtime and _cache["data"] is not None:
        return _cache["data"]
    try:
        raw = json.loads(FILE.read_text(encoding="utf-8"))
        data = {key: {f: _clean_field(f, (raw.get(key) or {}).get(f)) for f in FIELDS} for key in ("actual", "anterior")}
    except (OSError, ValueError, AttributeError):
        data = {"actual": _empty(), "anterior": _empty()}
    _cache.update(mtime=mtime, data=data)
    return data


def _clean_field(field: str, value):
    """Lo que viene del archivo se vuelve a validar: nada raro llega al prompt ni a la página."""
    if value is None:
        return None
    if field == "nombre":
        return _valid_name(str(value))
    if field == "voz":
        value = " ".join(str(value).split())
        if value in RETIRED_VOICES:   # voces de la «actualización de voz» (retiradas): se olvidan al leer el archivo
            return None
        return value[:60] if re.fullmatch(r"[\w .'\-]{1,60}", value) else None
    if field == "velocidad":
        return max(-10, min(10, value)) if isinstance(value, int) and not isinstance(value, bool) else None
    return value if isinstance(value, str) and re.fullmatch(r"#[0-9a-f]{6}", value) else None


def _write(actual: dict, anterior: dict) -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=FILE.parent, suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8") as f:
        json.dump({"actual": actual, "anterior": anterior}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, FILE)  # reemplazo atómico: el archivo nunca queda a medias
    _cache["mtime"] = None


def get(field: str):
    return _read()["actual"].get(field)


def nombre() -> str:
    return get("nombre") or config.APP_NAME


def fill(system: str) -> str:
    """Pone el nombre actual donde las instrucciones dicen {NOMBRE}."""
    return system.replace("{NOMBRE}", nombre()) if "{NOMBRE}" in system else system


# ------------------------------------------------------------------ colores
def _rgb(h: str):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in rgb)


def mix(a: str, b: str, t: float) -> str:
    """t=0 → a; t=1 → b."""
    return _hex(tuple(x + (y - x) * t for x, y in zip(_rgb(a), _rgb(b))))


def luminance(h: str) -> float:
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def ink(bg: str) -> str:
    """Texto negro o blanco, el que se lea mejor sobre ese color."""
    return "#111111" if contrast(bg, "#111111") >= contrast(bg, "#ffffff") else "#ffffff"


def readable(color: str, bg: str, ratio: float = 3.0) -> str:
    """Oscurece o aclara el color hasta que se distinga del fondo."""
    target = "#000000" if luminance(bg) > 0.4 else "#ffffff"
    for step in range(12):
        shade = mix(color, target, step * 0.07)
        if contrast(shade, bg) >= ratio:
            return shade
    return mix(color, target, 0.8)


COLORS = {
    "celeste": "#38bdf8", "azul": "#3b82f6", "verde": "#22c55e", "lima": "#a3e635", "amarillo": "#facc15",
    "naranja": "#fb923c", "anaranjado": "#fb923c", "rojo": "#ef4444", "rosa": "#f472b6", "rosado": "#f472b6",
    "fucsia": "#e11d9a", "morado": "#8b5cf6", "violeta": "#8b5cf6", "lila": "#c4a1ff", "turquesa": "#2dd4bf",
    "cian": "#22d3ee", "magenta": "#d946ef", "blanco": "#ffffff", "negro": "#111111", "gris": "#9ca3af",
    "dorado": "#f59e0b", "marron": "#a16207", "cafe": "#a16207", "coral": "#fb7185", "menta": "#6ee7b7",
    "vino": "#9f1239", "guinda": "#9f1239", "plateado": "#cbd5e1",
}
for _fem in ("negra", "blanca", "roja", "amarilla"):          # «interfaz negra», «botones roja»…
    COLORS[_fem] = COLORS[_fem[:-1] + "o"]
for _word in [w for w in COLORS if w.endswith("ado")]:
    COLORS[_word[:-1] + "a"] = COLORS[_word]                   # rosada, morada, anaranjada, dorada, plateada
_COLOR_WORD = re.compile(r"\b(" + "|".join(COLORS) + r")\b")
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


def find_color(text: str):
    """(base, claro, oscuro, etiqueta) del primer color nombrado en el texto, o None."""
    p = plain(text)
    found = _HEX.search(text)
    light = bool(re.search(r"\b(claro|clara|suave|pastel)\b", p))
    dark = bool(re.search(r"\b(oscuro|oscura|profundo|profunda)\b", p))
    if found:
        return found.group(0).lower(), light, dark, found.group(0).lower()
    word = _COLOR_WORD.search(p)
    if not word:
        return None
    label = word.group(1) + (" claro" if light else " oscuro" if dark else "")
    return COLORS[word.group(1)], light, dark, label


def palette_for(target: str, base: str, light: bool, dark: bool) -> dict:
    """Qué cambia según lo que se pidió: la interfaz entera, solo el acento o solo el fondo."""
    if target == "acento":
        return {"acento": mix(base, "#ffffff", 0.35) if light else mix(base, "#000000", 0.35) if dark else base}
    if target == "fondo":
        return {"fondo": mix(base, "#ffffff", 0.88) if light else mix(base, "#000000", 0.82) if dark else base}
    # interfaz entera: fondo del mismo tono (claro si lo pidió claro, oscuro si no) y acento que se distinga de él
    if base == "#111111":
        return {"fondo": None, "acento": None}                       # «negra»: el aspecto oscuro original
    if base == "#ffffff":
        return {"fondo": "#ffffff", "acento": DEFAULT_LIGHT_ACCENT}
    bg = mix(base, "#ffffff", 0.88) if light else mix(base, "#000000", 0.82)
    return {"fondo": bg, "acento": readable(base, bg)}


def css_vars(p: dict | None = None) -> dict:
    """Variables CSS de la página para este perfil (vacío = aspecto original)."""
    p = p or _read()["actual"]
    acento, fondo = p.get("acento"), p.get("fondo")
    out = {}
    if fondo:
        light = luminance(fondo) > 0.4
        text = "#151515" if light else "#f1efe8"
        out.update({
            "--bg": fondo, "--text": text, "--muted": mix(text, fondo, 0.45),
            "--panel": mix(fondo, "#ffffff", 0.55 if light else 0.06),
            "--line": mix(fondo, "#000000", 0.16) if light else mix(fondo, "#ffffff", 0.14),
            "--side": mix(fondo, "#000000", 0.05 if light else 0.25),
            "--danger": "#b3261e" if light else "#ff7b7b",
        })
        if not acento and light:
            acento = DEFAULT_LIGHT_ACCENT
    if acento:
        if fondo:
            acento = readable(acento, fondo, 2.6)
        out["--accent"], out["--accent-ink"] = acento, ink(acento)
    return out


def payload() -> dict:
    """Lo que la página necesita para aplicar el perfil al momento."""
    return {"nombre": nombre(), "vars": css_vars(), "voz": get("voz"), "velocidad": get("velocidad")}


def style_block() -> str:
    pairs = "".join(f"{k}:{v};" for k, v in css_vars().items())
    return f":root{{{pairs}}}" if pairs else ""


# ------------------------------------------------------------------ entender lo que pides
def _valid_name(text: str) -> str | None:
    name = " ".join(text.strip(" .,;:!¡¿?\"'«»“”").split())
    if not name or len(name) > 40 or not re.fullmatch(r"[\w .'\-áéíóúüñÁÉÍÓÚÜÑ]+", name):
        return None
    return name.title() if name.islower() else name


_CUE = re.compile(
    r"\b(cambia\w*|pon\w*|usa\w*|utiliza\w*|quiero|quisiera|actualiza\w*|modifica\w*|configura\w*|llamate|tengas|tenga|"
    r"sea|hazte|habla\w*|desde ahora|a partir de ahora|prefiero|que te|que tu|puedes|podrias|restablece\w*|restaura\w*|"
    r"resetea\w*|deshaz|deshacer|revierte|vuelve|regresa|dime|muestrame)\b"
)
_ASK_OK = re.compile(r"\b(cambia\w*|pon\w*|usa\w*|puedes|podrias|quisiera|quiero|deshaz|restablece\w*)\b")
_SPLIT = re.compile(
    r"\s*(?:[,;]|\.(?:\s|$)|\by\b(?=\s+(?:cambia|pon|usa|quiero|ahora|tambien|que te|habla|llamate))|\bademas\b|\btambien\b)\s*", re.I
)
_NAME_PATTERNS = [
    re.compile(r"(?:cambia\w*|actualiza\w*|modifica\w*|pon\w*)\s+(?:tu|el)\s+nombre(?!\s+(?:del?|de\s+(?:la|los|las|este|esta|ese|esa))\s)\s+(?:a|por|como|en|:)?\s*(.+)$", re.I),
    re.compile(r"\b(?:te\s+llames|ll[aá]mate|te\s+vas\s+a\s+llamar|te\s+llamar[aá]s)\s+(.+)$", re.I),
    re.compile(r"\b(?:tu\s+nombre\s+(?:es|sera|será|va\s+a\s+ser)|te\s+llamas)\s+(.+)$", re.I),
]
_UNDO = re.compile(r"\b(deshaz|deshacer|revierte|revertir|vuelve atras|regresa al anterior)\b")
_RESET = re.compile(
    r"\b(restablece\w*|restaura\w*|resetea\w*|vuelve a (?:la |el |los |tu )?(?:configuracion|valores|identidad|nombre|voz|colores|interfaz))\b"
)
_SHOW = re.compile(r"\b(muestrame|dime|cual es|cuales son|que)\b.*\b(tu|tus)\b.*\b(configuracion|ajustes|identidad|perfil)\b")


def _installed_short(voice: dict) -> str:
    return re.sub(r"^Microsoft\s+|\s+Desktop$", "", voice["name"]).strip()


KNOWN_VOICES = {
    "jorge", "esperanza", "diego", "carlos", "carmen", "soledad", "juan", "francisca", "helena", "pablo", "paulina",
    "monica", "raul", "laura", "marisol", "jose", "dalia", "elvira", "sabina", "zira", "david",
}


_VENDOR_WORDS = {"microsoft", "loquendo", "desktop"}


def _gender_word(p: str):
    if re.search(r"\b(masculin[oa]|de hombre|varon|hombre)\b", p):
        return "Male"
    if re.search(r"\b(femenin[oa]|de mujer|mujer)\b", p):
        return "Female"
    return None


def _describe_voices(voices: list[dict]) -> str:
    gender = {"Male": "hombre", "Female": "mujer"}
    return ", ".join(f"{_installed_short(v)} ({v['culture']}, {gender.get(v['gender'], 'neutra')})" for v in voices)


def _voice_clause(clause: str, p: str, voices_fn, changes: dict, done: list, refused: list) -> bool:
    """Procesa lo relativo a la voz y su velocidad. Devuelve True si la frase hablaba de eso."""
    wants_voice = bool(re.search(r"\bvoz\b", p))
    rate = None
    if re.search(r"\b(habla\w*|voz|velocidad)\b", p):
        rate = re.search(r"\b(mas rapid[oa]|mas lent[oa]|mas despacio|acelera)\b", p)
    if not wants_voice and not rate:
        return False

    def change_speed() -> None:
        faster = "rapid" in rate.group(1) or "acelera" in rate.group(1)
        stored = get("velocidad")
        current = stored if stored is not None else config.VOICE_RATE
        new = max(-10, min(10, current + (2 if faster else -2)))
        if new == current:
            refused.append(f"Ya hablo a la velocidad {'más rápida' if faster else 'más lenta'} posible.")
        else:
            changes["velocidad"] = new
            done.append(f"ahora hablo más {'rápido' if faster else 'lento'}")

    if not wants_voice:
        change_speed()
        return True
    voices = voices_fn() or []
    words = set(re.findall(r"[a-z]+", p))
    gender = _gender_word(p)
    for voice in voices:  # una voz de Windows instalada, nombrada por su nombre
        key = [w for w in plain(_installed_short(voice)).split() if w not in _VENDOR_WORDS]
        if key and key[0] in words:
            changes["voz"] = _installed_short(voice)
            done.append(f"ahora hablo con la voz {_installed_short(voice)}")
            return True
    named = next((w for w in re.findall(r"[a-záéíóúñ]+", clause.lower()) if plain(w) in KNOWN_VOICES), None)
    if not voices and (named or gender):
        refused.append("No encontré voces de Windows para elegir (o la voz la pone el navegador), así que no pude cambiarla.")
    elif named:  # pidió una voz concreta que no está instalada: no se cambia nada
        alternative = [v for v in voices if v["culture"].lower().startswith("es") and (not gender or v["gender"] == gender)
 ]
        hint = f" La que sí tengo en español: {_describe_voices(alternative)}." if alternative else ""
        refused.append(f"La voz «{named.title()}» no está instalada en tu PC, así que no puedo usarla y sigo con la actual."
                       f"{hint} Las voces instaladas son: {_describe_voices(voices)}.")
    elif gender:
        spanish = [v for v in voices if v["culture"].lower().startswith("es") and v["gender"] == gender]
        if spanish:
            changes["voz"] = _installed_short(spanish[0])
            done.append(f"ahora hablo con la voz {_installed_short(spanish[0])}")
        else:
            others = [v for v in voices if v["gender"] == gender]
            refused.append(
                f"No tengo una voz {'masculina' if gender == 'Male' else 'femenina'} en español instalada"
                + (f"; solo {_describe_voices(others)}, que leería el español con acento raro. Si la quieres igual, dime «usa la voz {_installed_short(others[0])}»." if others else ".")
            )
    elif rate:
        change_speed()
    else:
        refused.append(f"No entendí qué voz quieres. Dime un nombre (las instaladas: {_describe_voices(voices)}) o «masculina»/«femenina».")
    return True


def handle(text: str, voices_fn=lambda: []) -> dict | None:
    """Si el mensaje es una orden de cambio de identidad, la aplica y devuelve {"message", "perfil"}; si no, None.

    `voices_fn` entrega las voces instaladas [{name, culture, gender}] y solo se llama si hablas de la voz.
    """
    text = " ".join(text.split())
    p = plain(text)
    if not text:
        return None
    if _SHOW.search(p):
        gender = {"Male": "hombre", "Female": "mujer"}
        actual = _read()["actual"]
        parts = [f"Me llamo {nombre()}.", f"Mi voz: {get('voz') or config.VOICE_NAME or 'una en español de las instaladas (por defecto)'}.",
                 "Colores: " + ("personalizados." if (actual["acento"] or actual["fondo"]) else "los originales.")]
        return {"message": " ".join(parts), "perfil": None}
    preset_only = re.fullmatch(r"(?:(?:activa|activar|pon|poner|usa|usar|cambia|cambiar|quiero)\s+)?(?:(?:a|al|el|en)\s+)?(?:modo|tema)\s+(?:claro|oscuro)", p.strip(" .!¡"))
    if not (_CUE.search(p) or preset_only):
        return None
    if (text.startswith("¿") or text.endswith("?")) and not _ASK_OK.search(p):
        return None

    state = _read()
    changes: dict = {}
    done: list[str] = []
    refused: list[str] = []
    undo = reset = False
    reset_scope: set[str] = set()

    if _UNDO.search(p):
        undo = True
    elif _RESET.search(p):
        reset = True
        reset_scope = {f for f, hit in (("nombre", "nombre"), ("voz", "voz"), ("velocidad", "voz"),
                                         ("acento", "color|interfaz|tema|colores|aspecto"), ("fondo", "color|interfaz|tema|colores|aspecto"))
                       if re.search(r"\b(" + hit + r")\b", p)} or set(FIELDS)
    else:
        for clause in [c for c in _SPLIT.split(text) if c and c.strip()]:
            cp = plain(clause)
            matched = False
            # nombre
            for pattern in _NAME_PATTERNS:
                found = pattern.search(clause)
                if found and _CUE.search(cp):
                    name = _valid_name(found.group(1))
                    if name:
                        changes["nombre"] = name
                        done.append(f"ahora me llamo {name}")
                    else:
                        refused.append("Ese nombre no me sirve: usa hasta 40 letras, números, espacios o guiones.")
                    matched = True
                    break
            if matched:
                continue
            # voz y velocidad
            if _voice_clause(clause, cp, voices_fn, changes, done, refused):
                continue
            # colores
            preset = re.search(r"\b(modo|tema|fondo)\s+(claro|oscuro)\b", cp)
            if preset and (preset_only or re.search(r"\b(pon\w*|activa\w*|cambia\w*|usa\w*|quiero|interfaz|pantalla)\b", cp)) and not re.search(r"\b(celeste|azul|verde|rojo|rosa|morado|amarillo|naranja)\b", cp):
                if preset.group(2) == "claro":
                    changes.update(fondo=LIGHT_BG, acento=DEFAULT_LIGHT_ACCENT)
                    done.append("la interfaz ahora está en modo claro")
                else:
                    changes.update(fondo=None, acento=None)
                    done.append("la interfaz ahora está en modo oscuro")
                continue
            color = find_color(clause)
            whole = re.search(r"\b(interfaz|pantalla|apariencia|diseno|aspecto|tema|todo|pagina)\b", cp)
            accent = re.search(r"\b(botones|acento|detalles|principal)\b", cp)
            background = re.search(r"\bfondo\b", cp)
            if color and (whole or accent or background or re.search(r"\bcolor(es)?\b", cp)):
                target = "fondo" if background and not whole else "interfaz" if whole else "acento"
                base, light, dark, label = color
                changes.update(palette_for(target, base, light, dark))
                what = {"interfaz": "la interfaz", "fondo": "el fondo", "acento": "el color de los botones y detalles"}[target]
                done.append(f"{what} ahora es {label}")
            elif re.search(r"\b(interfaz|pantalla|fondo|botones|acento|colo(?:r|res))\b", cp):
                refused.append("No reconocí ese color. Prueba con uno como «celeste claro», «verde lima», «rosa», «morado oscuro» o un código como #12ab34.")
    if not (changes or undo or reset or refused):
        return None

    actual, anterior = dict(state["actual"]), state["anterior"]
    with _lock:
        if undo:
            _write(dict(anterior), dict(actual))
            message = "Listo, deshice el último cambio."
        elif reset:
            new = {**actual, **{f: None for f in reset_scope}}
            _write(new, dict(actual))
            message = "Listo, restablecí " + ("todo a como venía de fábrica." if reset_scope == set(FIELDS) else "lo que pediste a como venía de fábrica.")
        elif changes:
            _write({**actual, **changes}, dict(actual))
            message = "Listo: " + "; ".join(done) + ". Se queda así hasta que me pidas otro cambio; si no te gusta, dime «deshaz el último cambio»."
            if refused:
                message += " Pero ojo: " + " ".join(refused)
        else:
            return {"message": " ".join(refused), "perfil": None}
    return {"message": message, "perfil": payload()}
