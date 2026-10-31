"""Hora y fecha reales de PK: salen del reloj de tu PC, no del modelo ni de internet.

Responde (sin gastar el modelo de lenguaje):
  «¿qué hora es?», «¿qué hora es en Tokio?», «¿qué día es hoy?», «¿a cuántos estamos?»
  «¿qué día cae el 25 de diciembre?», «¿cuántos días faltan para Navidad?»
  «¿cuántos días han pasado desde el 1 de enero?», «¿qué fecha será dentro de 30 días?»

La zona horaria se elige con TIMEZONE en .env (por defecto America/El_Salvador).
En Windows hace falta el paquete `tzdata` (está en requirements.txt); si no está, se
usa UTC-6 fijo para El Salvador (no tiene horario de verano).
"""
from __future__ import annotations

import calendar
import os
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9 no se usa, pero por si acaso
    ZoneInfo = None  # type: ignore

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
_MES_NUM = {m.replace("é", "e").replace("á", "a"): i + 1 for i, m in enumerate(MESES)}
_MES_NUM["setiembre"] = 9
_DIA_NUM = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4,
            "sabado": 5, "domingo": 6}

_FIESTAS = {  # fechas fijas (día, mes)
    "navidad": (25, 12, "Navidad"), "nochebuena": (24, 12, "Nochebuena"),
    "ano nuevo": (1, 1, "Año Nuevo"), "nochevieja": (31, 12, "Nochevieja"),
    "fin de ano": (31, 12, "fin de año"), "dia de la independencia": (15, 9, "la Independencia"),
    "independencia": (15, 9, "la Independencia"), "dia de la madre": (10, 5, "el Día de la Madre"),
    "dia del trabajo": (1, 5, "el Día del Trabajo"), "san valentin": (14, 2, "San Valentín"),
    "halloween": (31, 10, "Halloween"), "dia de los muertos": (2, 11, "el Día de los Difuntos"),
    "dia de los difuntos": (2, 11, "el Día de los Difuntos"),
}

_CIUDADES = {
    "san salvador": "America/El_Salvador", "el salvador": "America/El_Salvador",
    "guatemala": "America/Guatemala", "tegucigalpa": "America/Tegucigalpa",
    "honduras": "America/Tegucigalpa", "managua": "America/Managua",
    "nicaragua": "America/Managua", "costa rica": "America/Costa_Rica",
    "san jose": "America/Costa_Rica", "panama": "America/Panama", "mexico": "America/Mexico_City",
    "ciudad de mexico": "America/Mexico_City", "bogota": "America/Bogota",
    "colombia": "America/Bogota", "lima": "America/Lima", "peru": "America/Lima",
    "quito": "America/Guayaquil", "ecuador": "America/Guayaquil", "caracas": "America/Caracas",
    "venezuela": "America/Caracas", "la habana": "America/Havana", "cuba": "America/Havana",
    "santo domingo": "America/Santo_Domingo", "buenos aires": "America/Argentina/Buenos_Aires",
    "argentina": "America/Argentina/Buenos_Aires", "santiago": "America/Santiago",
    "chile": "America/Santiago", "sao paulo": "America/Sao_Paulo", "brasil": "America/Sao_Paulo",
    "nueva york": "America/New_York", "new york": "America/New_York", "miami": "America/New_York",
    "washington": "America/New_York", "chicago": "America/Chicago",
    "los angeles": "America/Los_Angeles", "california": "America/Los_Angeles",
    "madrid": "Europe/Madrid", "espana": "Europe/Madrid", "barcelona": "Europe/Madrid",
    "londres": "Europe/London", "london": "Europe/London", "paris": "Europe/Paris",
    "francia": "Europe/Paris", "berlin": "Europe/Berlin", "alemania": "Europe/Berlin",
    "roma": "Europe/Rome", "italia": "Europe/Rome", "moscu": "Europe/Moscow",
    "tokio": "Asia/Tokyo", "japon": "Asia/Tokyo", "seul": "Asia/Seoul",
    "pekin": "Asia/Shanghai", "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
    "china": "Asia/Shanghai", "dubai": "Asia/Dubai", "nueva delhi": "Asia/Kolkata",
    "india": "Asia/Kolkata", "el cairo": "Africa/Cairo", "egipto": "Africa/Cairo",
    "sidney": "Australia/Sydney", "sydney": "Australia/Sydney",
}
_ETIQUETA_ZONA = {"America/El_Salvador": "hora de El Salvador"}


def _plain(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


# ───────────────────────── reloj ─────────────────────────

def _zona(nombre: str | None = None):
    nombre = nombre or os.getenv("TIMEZONE", "America/El_Salvador")
    if ZoneInfo is not None:
        try:
            return ZoneInfo(nombre)
        except Exception:
            pass
    if nombre in ("America/El_Salvador", "America/Guatemala", "America/Costa_Rica",
                  "America/Tegucigalpa", "America/Managua"):
        return timezone(timedelta(hours=-6))      # sin horario de verano
    return None


def ahora(nombre_zona: str | None = None) -> datetime:
    """La hora actual del PC, en la zona pedida (o en la tuya)."""
    z = _zona(nombre_zona)
    return datetime.now(z) if z is not None else datetime.now().astimezone()


def hoy() -> date:
    return ahora().date()


def fecha_larga(d: date) -> str:
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} de {d.year}"


def hora_12(dt: datetime) -> str:
    h = dt.hour % 12 or 12
    return f"{h}:{dt.minute:02d} {'a. m.' if dt.hour < 12 else 'p. m.'}"


def _frase_hora(dt: datetime) -> str:
    h12 = dt.hour % 12 or 12
    verbo = "Es la" if h12 == 1 else "Son las"
    return f"{verbo} {hora_12(dt)}"


def contexto_actual() -> str:
    """Una línea para darle al modelo la fecha de hoy (así no inventa el año)."""
    dt = ahora()
    return f"Fecha y hora actuales: {fecha_larga(dt.date())}, {hora_12(dt)}."


# ───────────────────────── lectura de fechas ─────────────────────────

class _FechaMala(Exception):
    pass


def _bisiesto_seguro(dia: int, mes: int, anio: int) -> date:
    try:
        return date(anio, mes, dia)
    except ValueError:
        raise _FechaMala(f"Esa fecha no existe: {dia} de {MESES[mes - 1]} de {anio}.")


def _proxima(dia: int, mes: int, base: date, pasado: bool) -> date:
    """Día y mes sin año: la próxima vez (o la última, si se habla en pasado)."""
    for delta in (0, 1, -1, 2, -2):
        anio = base.year + delta
        try:
            d = date(anio, mes, dia)
        except ValueError:
            continue
        if not pasado and d >= base:
            return d
        if pasado and d <= base:
            candidato = d
            try:
                sig = date(anio + 1, mes, dia)
                if sig <= base:
                    candidato = sig
            except ValueError:
                pass
            return candidato
    raise _FechaMala(f"Esa fecha no existe: {dia} de {MESES[mes - 1]}.")


def _leer_fecha(t: str, base: date, pasado: bool = False) -> date | None:
    """Lee una fecha escrita en español (sin acentos, en minúsculas). None si no hay."""
    t = t.strip()
    if re.search(r"\bpasado manana\b", t):
        return base + timedelta(days=2)
    if re.search(r"\b(anteayer|antier|antes de ayer)\b", t):
        return base - timedelta(days=2)
    if re.search(r"\bayer\b", t):
        return base - timedelta(days=1)
    if re.search(r"\bmanana\b", t):
        return base + timedelta(days=1)
    if re.search(r"\bhoy\b", t):
        return base
    for clave, (dia, mes, _n) in sorted(_FIESTAS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{clave}\b", t):
            return _proxima(dia, mes, base, pasado)

    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t)
    if m:
        return _bisiesto_seguro(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", t)
    if m:                                         # día/mes/año, como se escribe en Latinoamérica
        anio = int(m.group(3))
        anio += 2000 if anio < 100 else 0
        if not 1 <= int(m.group(2)) <= 12:
            raise _FechaMala("El mes tiene que ir entre 1 y 12 (escribo las fechas como día/mes/año).")
        return _bisiesto_seguro(int(m.group(1)), int(m.group(2)), anio)
    meses = "|".join(_MES_NUM)
    m = re.search(rf"\b(\d{{1,2}})\s+de\s+({meses})(?:\s+(?:de(?:l)?\s+)?(\d{{4}}))?", t)
    if m:
        dia, mes = int(m.group(1)), _MES_NUM[m.group(2)]
        if m.group(3):
            return _bisiesto_seguro(dia, mes, int(m.group(3)))
        if not 1 <= dia <= 31:
            raise _FechaMala("Ese día no existe.")
        return _proxima(dia, mes, base, pasado)
    m = re.search(rf"\b({'|'.join(_DIA_NUM)})\b", t)
    if m:
        objetivo = _DIA_NUM[m.group(1)]
        delta = (objetivo - base.weekday()) % 7
        if re.search(r"\bproximo\b", t) and delta == 0:
            delta = 7
        if pasado:
            delta = -((base.weekday() - objetivo) % 7)
        return base + timedelta(days=delta)
    return None


def _nombre_fiesta(t: str) -> str | None:
    for clave, (_d, _m, nombre) in sorted(_FIESTAS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{clave}\b", t):
            return nombre
    return None


def _sumar_meses(d: date, n: int) -> date:
    total = d.year * 12 + (d.month - 1) + n
    anio, mes = divmod(total, 12)
    mes += 1
    return date(anio, mes, min(d.day, calendar.monthrange(anio, mes)[1]))


def _dias(n: int) -> str:
    n = abs(n)
    return f"{n:,} día" + ("" if n == 1 else "s")


def _semanas(n: int) -> str:
    n = abs(n)
    if n < 14:
        return ""
    s, r = divmod(n, 7)
    extra = f" y {r} día" + ("" if r == 1 else "s") if r else ""
    return f" ({s} semanas{extra})"


# ───────────────────────── preguntas ─────────────────────────

_HORA = re.compile(r"\b(?:que hora (?:es|son|tenemos)|(?:dime|dame|me das|me dices|tienes|sabes) la hora|la hora (?:actual|exacta)|hora actual)\b")
_HOY = re.compile(r"\b(?:que (?:dia|fecha) es hoy|que (?:dia|fecha) es(?: ahora)?|hoy (?:es|que dia es|a cuanto estamos)|"
                  r"a cuantos estamos|en que fecha estamos|fecha de hoy|fecha actual|que dia de la semana es hoy|"
                  r"que dia estamos|en que dia estamos|que dia de la semana es)\b")
_QUE_DIA = re.compile(r"\bque (?:dia|dia de la semana|fecha)\s+(?:(?:sera|fue|es|cae|caera|cayo|caia|seria)\s+)?(.+)$")
_FALTAN = re.compile(r"\b(?:cuantos dias (?:faltan|quedan|hay) (?:para|hasta)|cuanto (?:falta|queda) para|"
                     r"en cuantos dias (?:es|sera|cae|llega)|cuantas semanas (?:faltan|quedan) para)\s+(.+)$")
_DESDE = re.compile(r"\b(?:cuantos dias (?:han pasado|pasaron|llevamos|van|hace)|cuanto tiempo (?:ha pasado|llevamos|hace)|"
                    r"hace cuantos dias (?:fue|paso|era|empezo|comenzo)?)\s*(?:desde)?\s*(.+)$")
_ENTRE = re.compile(r"\bcuantos dias (?:hay|pasan|van) entre\s+(.+?)\s+y\s+(?:el\s+)?(.+)$")
_DENTRO = re.compile(r"\b(?:que (?:fecha|dia)(?: sera| cae| es)?|en que fecha (?:sera|estaremos|caera)|fecha (?:sera|de))\s*"
                     r"(?:dentro de|en|hace)\s+(\d+)\s+(dia|dias|semana|semanas|mes|meses|ano|anos)\b")
_HACE = re.compile(r"\bque (?:fecha|dia) (?:fue|era|cayo|seria)\s+hace\s+(\d+)\s+(dia|dias|semana|semanas|mes|meses|ano|anos)\b")


def _ciudad(t: str) -> tuple[str, str] | None:
    m = re.search(r"\ben\s+(?:la ciudad de\s+|el pais de\s+|)([a-z ]{3,30}?)\s*$", t)
    if not m:
        return None
    nombre = m.group(1).strip()
    for k in sorted(_CIUDADES, key=len, reverse=True):
        if nombre == k or nombre.endswith(k):
            return k, _CIUDADES[k]
    return nombre, ""


def handle(texto: str) -> dict | None:
    """Devuelve {'message': ...} si la pregunta es de hora o fecha; si no, None."""
    if not texto or len(texto) > 160:
        return None
    t = re.sub(r"[¿?¡!.,;:]+", " ", _plain(texto))
    t = re.sub(r"\s+", " ", t).strip()
    try:
        return _responder(t)
    except _FechaMala as e:
        return {"message": str(e)}


def _responder(t: str) -> dict | None:
    base = hoy()

    # ── hora (también en otra ciudad) ──
    if _HORA.search(t):
        c = _ciudad(t)
        if c and c[1]:
            if _zona(c[1]) is None:
                return {"message": "No tengo la base de zonas horarias. Instálala con: pip install tzdata"}
            dt = ahora(c[1])
            dia = ""
            local = ahora().date()
            if dt.date() != local:
                dia = " de mañana" if dt.date() > local else " de ayer"
            return {"message": f"En {c[0].title()} {_frase_hora(dt).lower()}{dia} ({fecha_larga(dt.date())})."}
        if c and not c[1]:
            return {"message": f"No conozco la zona horaria de «{c[0]}». Prueba con una ciudad grande o un país (Madrid, Tokio, Nueva York…)."}
        dt = ahora()
        zona = getattr(dt.tzinfo, "key", None)
        etq = _ETIQUETA_ZONA.get(zona or "", "")
        extra = f" ({etq})" if etq else ""
        puntuar = f"{extra}." if extra else ""
        return {"message": f"{_frase_hora(dt)}{puntuar} Hoy es {fecha_larga(dt.date())}."}

    # ── cuántos días faltan / han pasado / hay entre ──
    m = _ENTRE.search(t)
    if m:
        a = _leer_fecha(m.group(1), base)
        b = _leer_fecha(m.group(2), base)
        if a and b:
            n = abs((b - a).days)
            return {"message": f"Entre el {fecha_larga(a)} y el {fecha_larga(b)} hay {_dias(n)}{_semanas(n)}."}
    m = _FALTAN.search(t)
    if m:
        d = _leer_fecha(m.group(1), base)
        if d:
            n = (d - base).days
            nombre = _nombre_fiesta(m.group(1)) or fecha_larga(d)
            if n == 0:
                return {"message": f"¡Es hoy! {fecha_larga(d)}."}
            if n > 0:
                return {"message": f"Faltan {_dias(n)} para {nombre}{_semanas(n)}: será el {fecha_larga(d)}."}
            return {"message": f"Esa fecha ya pasó hace {_dias(n)}: fue el {fecha_larga(d)}."}
    m = _DESDE.search(t)
    if m and m.group(1):
        d = _leer_fecha(m.group(1), base, pasado=True)
        if d:
            n = (base - d).days
            if n == 0:
                return {"message": "Es hoy mismo."}
            if n < 0:
                return {"message": f"Esa fecha todavía no llega: faltan {_dias(n)} (será el {fecha_larga(d)})."}
            return {"message": f"Han pasado {_dias(n)}{_semanas(n)} desde el {fecha_larga(d)}."}

    # ── fecha dentro de / hace N unidades ──
    for patron, signo in ((_DENTRO, 1), (_HACE, -1)):
        m = patron.search(t)
        if m:
            n, unidad = int(m.group(1)), m.group(2)
            if n > 100000:
                return {"message": "Ese número es demasiado grande para una fecha."}
            try:
                if unidad.startswith("dia"):
                    d = base + timedelta(days=signo * n)
                elif unidad.startswith("semana"):
                    d = base + timedelta(weeks=signo * n)
                elif unidad.startswith("mes"):
                    d = _sumar_meses(base, signo * n)
                else:
                    d = _sumar_meses(base, signo * n * 12)
            except (OverflowError, ValueError):
                return {"message": "Esa fecha queda fuera del calendario."}
            verbo = "será" if signo > 0 else "fue"
            return {"message": f"{'Dentro de' if signo > 0 else 'Hace'} {n} {unidad} {verbo} {fecha_larga(d)}."}

    # ── qué día es hoy / ayer / mañana ──
    if _HOY.search(t) and not re.search(r"\b(manana|ayer)\b", t):
        return {"message": f"Hoy es {fecha_larga(base)}."}
    m = _QUE_DIA.search(t)
    if m:
        cola = m.group(1)
        pasado = bool(re.search(r"\b(fue|cayo|caia|era)\b", t))
        d = _leer_fecha(cola, base, pasado=pasado)
        if d:
            rel = ""
            n = (d - base).days
            if n == 0:
                rel = " (hoy)"
            elif n == 1:
                rel = " (mañana)"
            elif n == -1:
                rel = " (ayer)"
            elif n > 0:
                rel = f" (en {_dias(n)})"
            else:
                rel = f" (hace {_dias(n)})"
            verbo = "fue" if n < 0 else "es" if n == 0 else "será"
            return {"message": f"{'Ayer' if n == -1 else 'Mañana' if n == 1 else 'Ese día'} {verbo} {fecha_larga(d)}{rel}."
                    if n in (-1, 1) else f"{fecha_larga(d).capitalize()}{rel}."}
    return None
