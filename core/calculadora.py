"""Calculadora de PK: cuentas EXACTAS hechas con código, sin que el modelo adivine.

Entiende preguntas en español («cuánto es 25 por 4», «15% de 200», «raíz de 144»,
«2 elevado a 10», «cinco más tres») y operaciones escritas como «(3+5)*2».

Reglas de seguridad:
  * Nunca usa eval(): lee la operación con su propio analizador.
  * Solo responde si TODO el texto es una operación. Si sobran palabras
    («tengo 5 más 3 manzanas»), devuelve None y la pregunta sigue su camino normal.
  * Solo interpreta lo que el usuario escribe o dice, nunca documentos ni páginas web.

Formato de números: punto decimal y coma de miles (1,234.5), como se usa en
El Salvador. Al leer, «1,500» = 1500 y «3,5» = 3.5; «1.500,50» = 1500.5.
"""
from __future__ import annotations

import math
import re
import unicodedata
from fractions import Fraction

MAX_DIGITOS = 60          # resultados enteros más largos se muestran en notación científica
MAX_EXPONENTE = 1000
MAX_FACTORIAL = 170


class _NoEsCuenta(Exception):
    """El texto no es una operación: PK debe seguir con el camino normal."""


class _CuentaMala(Exception):
    """Parece una operación pero no se puede resolver; el mensaje se muestra tal cual."""


def _plain(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


# ───────────────────────── números escritos con palabras ─────────────────────────

_UNIDADES = {
    "cero": 0, "uno": 1, "un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
    "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17,
    "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21, "veintiuno": 21,
    "veintiuna": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24,
    "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28,
    "veintinueve": 29,
}
_DECENAS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
            "setenta": 70, "ochenta": 80, "noventa": 90}
_CENTENAS = {"cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200,
             "trescientos": 300, "trescientas": 300, "cuatrocientos": 400,
             "cuatrocientas": 400, "quinientos": 500, "quinientas": 500,
             "seiscientos": 600, "seiscientas": 600, "setecientos": 700,
             "setecientas": 700, "ochocientos": 800, "ochocientas": 800,
             "novecientos": 900, "novecientas": 900}
_PALABRAS_NUM = set(_UNIDADES) | set(_DECENAS) | set(_CENTENAS) | {"mil", "millon", "millones"}
_PALABRAS_OPERADOR = {"mas", "menos", "por", "entre", "veces", "x", "elevado", "dividido",
                      "multiplicado", "raiz", "factorial", "mitad", "doble", "triple", "de",
                      "al", "a", "la", "el", "los", "las", "potencia", "cuadrado", "cubo"}


def _palabras_a_digitos(texto: str) -> str:
    """Cambia «veinticinco» por 25 y «dos mil quinientos» por 2500."""
    palabras = texto.split(" ")
    salida: list[str] = []
    i = 0
    while i < len(palabras):
        w = palabras[i]
        if w not in _PALABRAS_NUM:
            salida.append(w)
            i += 1
            continue
        # «un/una» son artículos casi siempre: solo cuentan si van junto a números u operadores.
        if w in ("un", "una"):
            sig = palabras[i + 1] if i + 1 < len(palabras) else ""
            ant = palabras[i - 1] if i > 0 else ""
            junto = (sig in ("mil", "millon", "millones") or sig in _PALABRAS_OPERADOR
                     or ant in _PALABRAS_OPERADOR or sig.isdigit() or ant.isdigit())
            if not junto:
                salida.append(w)
                i += 1
                continue
        total = 0
        actual = 0
        j = i
        previa_decena = False
        while j < len(palabras):
            p = palabras[j]
            if p in _UNIDADES:
                actual += _UNIDADES[p]
                previa_decena = False
            elif p in _DECENAS:
                actual += _DECENAS[p]
                previa_decena = True
            elif p in _CENTENAS:
                actual += _CENTENAS[p]
                previa_decena = False
            elif p == "mil":
                total += (actual or 1) * 1000
                actual = 0
                previa_decena = False
            elif p in ("millon", "millones"):
                total += (actual or 1) * 1_000_000
                actual = 0
                previa_decena = False
            elif (p == "y" and previa_decena and j + 1 < len(palabras)
                  and palabras[j + 1] in _UNIDADES and 1 <= _UNIDADES[palabras[j + 1]] <= 9):
                previa_decena = False
            else:
                break
            j += 1
        salida.append(str(total + actual))
        i = j
    return " ".join(salida)


# ───────────────────────── lectura de números ─────────────────────────

def _leer_numero(s: str) -> Fraction:
    s = s.strip()
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):          # 1.500,50
            s = s.replace(".", "").replace(",", ".")
        else:                                     # 1,500.50
            s = s.replace(",", "")
    elif "," in s:
        partes = s.split(",")
        if len(partes) > 2 or (len(partes) == 2 and len(partes[1]) == 3 and len(partes[0]) <= 3
                               and partes[0] != "0"):
            s = s.replace(",", "")               # 1,500  /  1,500,000
        else:
            s = s.replace(",", ".")              # 3,5
    if s.count(".") > 1:
        raise _CuentaMala("Ese número tiene demasiados puntos.")
    try:
        return Fraction(s)
    except (ValueError, ZeroDivisionError):
        raise _NoEsCuenta()


# ───────────────────────── formato de resultados ─────────────────────────

def _con_miles(entero: str) -> str:
    signo = "-" if entero.startswith("-") else ""
    cuerpo = entero.lstrip("-")
    return signo + f"{int(cuerpo):,}"


def formatear(valor) -> str:
    """Muestra un número de forma legible: 1,234.5 ; 3.3333333333 ; 1.2e+80."""
    if isinstance(valor, Fraction):
        if valor.denominator == 1:
            if len(str(abs(valor.numerator))) > MAX_DIGITOS:
                return f"{float(valor):.6e}"
            return _con_miles(str(valor.numerator))
        valor = float(valor)
    if isinstance(valor, float):
        if math.isnan(valor) or math.isinf(valor):
            raise _CuentaMala("El resultado es demasiado grande para mostrarlo.")
        if abs(valor) >= 1e15 or (valor != 0 and abs(valor) < 1e-9):
            return f"{valor:.6e}"
        txt = f"{valor:.10f}".rstrip("0").rstrip(".")
        if txt in ("", "-", "-0"):
            return "0"
        entero, _, dec = txt.partition(".")
        entero = _con_miles(entero)
        return entero + ("." + dec if dec else "")
    return str(valor)


# ───────────────────────── lectura de la operación ─────────────────────────

_FRASES = [  # se aplican en orden sobre el texto sin acentos
    (r"\bmultiplicad[oa]s? (?:por|con)\b", " * "),
    (r"\bdividid[oa]s? (?:entre|por|en)\b", " / "),
    (r"\belevad[oa]s? a la (?:potencia de )?", " ^ "),
    (r"\belevad[oa]s? (?:a|al)\b", " ^ "),
    (r"\ba la potencia(?: de)?\b", " ^ "),
    (r"\bal cuadrado\b", " sq "),
    (r"\bal cubo\b", " cube "),
    (r"\bpor ciento\b", " % "),
    (r"\braiz cuadrada(?: de)?\b", " sqrt "),
    (r"\braiz cubica(?: de)?\b", " cbrt "),
    (r"\braiz(?: de)?\b", " sqrt "),
    (r"\bfactorial(?: de)?\b", " fact "),
    (r"\bla mitad de\b", " half "),
    (r"\bel doble de\b", " double "),
    (r"\bel triple de\b", " triple "),
]
_PALABRA_OP = {"mas": "+", "menos": "-", "por": "*", "veces": "*", "x": "*", "entre": "/"}
_FUNCIONES = {"sqrt", "cbrt", "fact", "half", "double", "triple"}
_POSTFIJOS = {"sq", "cube"}
_IGNORAR = {"el", "la", "los", "las"}
_TOKEN = re.compile(r"\d+(?:[.,]\d+)*|[a-z]+|[()+\-*/^%!×÷]")

_TRIGGER = re.compile(
    r"^(?:cuanto\s+(?:es|son|da|dan|seria|serian|vale|valen|resulta|sale|salen)"
    r"|calcula(?:me)?|calcular|resuelve(?:me)?|resolver"
    r"|(?:cual|dame|dime)\s+(?:es\s+)?el\s+resultado\s+de|resultado\s+de)\b\s*")
_SOLO_MATEMATICA = re.compile(r"^[\d\s.,+\-*/x×÷^()%=:]+$")


def _tokenizar(s: str) -> list[tuple[str, str]]:
    s = s.replace("**", "^").replace("×", "*").replace("÷", "/").replace("$", " ")
    for patron, cambio in _FRASES:
        s = re.sub(patron, cambio, s)
    s = _palabras_a_digitos(re.sub(r"\s+", " ", s).strip())
    tokens: list[tuple[str, str]] = []
    resto = _TOKEN.sub("", s).replace(" ", "")
    if resto:
        raise _NoEsCuenta()                      # símbolos raros: no es una cuenta
    for m in _TOKEN.finditer(s):
        t = m.group()
        if t[0].isdigit():
            tokens.append(("num", t))
        elif t in "+-*/^()%!":
            tokens.append(("op" if t in "+-*/^" else t, t))
        elif t in _PALABRA_OP:
            tokens.append(("op", _PALABRA_OP[t]))
        elif t in _FUNCIONES:
            tokens.append(("func", t))
        elif t in _POSTFIJOS:
            tokens.append(("post", t))
        elif t == "de":
            tokens.append(("de", t))
        elif t in _IGNORAR:
            continue
        else:
            raise _NoEsCuenta()                  # palabra desconocida: no es una cuenta
    return tokens


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]):
        self.t = tokens
        self.i = 0
        self.vista: list[str] = []               # para mostrar «lo que entendí»

    # utilidades
    def _ver(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else ("fin", "")

    def _tomar(self):
        tok = self._ver()
        self.i += 1
        return tok

    def _esperar(self, tipo):
        if self._ver()[0] != tipo:
            raise _CuentaMala("No pude entender esa operación. Escríbela así: 25 por 4, 15% de 200, raíz de 144.")
        return self._tomar()

    # gramática
    def expresion(self):
        izq = self.termino()
        while self._ver()[0] == "op" and self._ver()[1] in "+-":
            op = self._tomar()[1]
            self.vista.append(op)
            # «100 más 15%» = 100 aumentado en 15 %
            if (self._ver()[0] == "num" and self._ver(1)[0] == "%" and self._ver(2)[0] != "de"):
                p = _leer_numero(self._tomar()[1])
                self._tomar()
                self.vista[-1:] = [op, formatear(p), "%"]
                izq = _a_fraccion(izq) * (1 + p / 100) if op == "+" else _a_fraccion(izq) * (1 - p / 100)
                continue
            der = self.termino()
            izq = _sumar(izq, der) if op == "+" else _sumar(izq, _neg(der))
        return izq

    def termino(self):
        izq = self.potencia()
        while self._ver()[0] == "op" and self._ver()[1] in "*/":
            op = self._tomar()[1]
            self.vista.append("×" if op == "*" else "÷")
            der = self.potencia()
            izq = _multiplicar(izq, der) if op == "*" else _dividir(izq, der)
        return izq

    def potencia(self):
        base = self.unario()
        if self._ver()[0] == "op" and self._ver()[1] == "^":
            self._tomar()
            self.vista.append("^")
            return _potencia(base, self.potencia())
        return base

    def unario(self):
        if self._ver()[0] == "op" and self._ver()[1] in "+-":
            op = self._tomar()[1]
            self.vista.append(op + "\x00")
            v = self.unario()
            return _neg(v) if op == "-" else v
        return self.sufijos(self.atomo())

    def sufijos(self, v):
        while True:
            tipo, txt = self._ver()
            if tipo == "post":
                self._tomar()
                self.vista.append("²" if txt == "sq" else "³")
                v = _potencia(v, Fraction(2 if txt == "sq" else 3))
            elif tipo == "!":
                self._tomar()
                self.vista.append("!")
                v = _factorial(v)
            else:
                return v

    def atomo(self):
        tipo, txt = self._tomar()
        if tipo == "num":
            n = _leer_numero(txt)
            self.vista.append(formatear(n))
            if self._ver()[0] == "%":
                self._tomar()
                self.vista.append("%")
                if self._ver()[0] == "de":
                    self._tomar()
                    self.vista.append("de")
                    return _multiplicar(n / 100, self.sufijos(self.atomo()))
                return n / 100
            return n
        if tipo == "(":
            self.vista.append("(")
            v = self.expresion()
            self._esperar(")")
            self.vista.append(")")
            return v
        if tipo == "func":
            nombre = {"sqrt": "√", "cbrt": "∛", "fact": "factorial de", "half": "la mitad de",
                      "double": "el doble de", "triple": "el triple de"}[txt]
            self.vista.append(nombre)
            if self._ver()[0] == "de":
                self._tomar()
            arg = self.sufijos(self.atomo()) if txt != "fact" else self.atomo()
            return {"sqrt": _raiz, "cbrt": _raiz_cubica, "fact": _factorial,
                    "half": lambda a: _dividir(a, Fraction(2)),
                    "double": lambda a: _multiplicar(a, Fraction(2)),
                    "triple": lambda a: _multiplicar(a, Fraction(3))}[txt](arg)
        raise _CuentaMala("No pude entender esa operación. Escríbela así: 25 por 4, 15% de 200, raíz de 144.")


# ───────────────────────── aritmética exacta ─────────────────────────

def _a_fraccion(x):
    return x if isinstance(x, Fraction) else Fraction(x)


def _ambos_exactos(a, b):
    return isinstance(a, Fraction) and isinstance(b, Fraction)


def _neg(a):
    return -a


def _sumar(a, b):
    return a + b if _ambos_exactos(a, b) else float(a) + float(b)


def _multiplicar(a, b):
    return a * b if _ambos_exactos(a, b) else float(a) * float(b)


def _dividir(a, b):
    if b == 0:
        raise _CuentaMala("No se puede dividir entre cero.")
    return a / b if _ambos_exactos(a, b) else float(a) / float(b)


def _potencia(base, exp):
    if isinstance(exp, Fraction) and exp.denominator == 1:
        n = exp.numerator
        if abs(n) > MAX_EXPONENTE:
            raise _CuentaMala("Ese exponente es demasiado grande.")
        if isinstance(base, Fraction):
            if base == 0 and n < 0:
                raise _CuentaMala("No se puede dividir entre cero.")
            if base not in (0, 1, -1) and abs(n) * math.log10(abs(float(base)) or 1) > 300:
                raise _CuentaMala("Ese resultado es demasiado grande.")
            return base ** n
    b, e = float(base), float(exp)
    if b < 0 and e != int(e):
        raise _CuentaMala("Esa potencia no tiene resultado real (base negativa con exponente decimal).")
    try:
        return b ** e
    except (OverflowError, ZeroDivisionError):
        raise _CuentaMala("Ese resultado es demasiado grande o no existe.")


def _raiz(a):
    if a < 0:
        raise _CuentaMala("No existe raíz cuadrada real de un número negativo.")
    if isinstance(a, Fraction):
        n, d = a.numerator, a.denominator
        rn, rd = math.isqrt(n), math.isqrt(d)
        if rn * rn == n and rd * rd == d:
            return Fraction(rn, rd)
    return math.sqrt(float(a))


def _raiz_cubica(a):
    x = float(a)
    r = math.copysign(round(abs(x) ** (1 / 3), 12), x)
    if isinstance(a, Fraction):
        cand = Fraction(round(r)) if abs(r - round(r)) < 1e-9 else None
        if cand is not None and cand ** 3 == a:
            return cand
    return r


def _factorial(a):
    if not (isinstance(a, Fraction) and a.denominator == 1 and a >= 0):
        raise _CuentaMala("El factorial solo existe para números enteros desde 0.")
    if a > MAX_FACTORIAL:
        raise _CuentaMala(f"El factorial solo lo calculo hasta {MAX_FACTORIAL}.")
    return Fraction(math.factorial(int(a)))


# ───────────────────────── entrada pública ─────────────────────────

_PORCENTAJE_DE = [
    re.compile(r"(?:que|cual)\s+porcentaje\s+(?:es|son|representa|representan)\s+(?:el\s+)?([\d.,]+)\s+de(?:l)?\s+([\d.,]+)"),
    re.compile(r"([\d.,]+)\s+(?:es|son|representa|representan)\s+(?:el\s+)?(?:que|cual)\s+(?:porcentaje|%)\s+de(?:l)?\s+([\d.,]+)"),
]


def _limpiar(texto: str) -> str:
    t = _plain(texto).strip()
    t = re.sub(r"[¿?¡!]+", " ", t)
    t = t.replace("=", " ")
    t = re.sub(r"\s+", " ", t).strip(" .:;")
    return t


def handle(texto: str) -> dict | None:
    """Devuelve {'message': ..., 'expresion': ..., 'resultado': ...} o None si no es una cuenta."""
    if not texto or len(texto) > 200:
        return None
    # el factorial usa «!»: se protege antes de limpiar signos de exclamación
    crudo = re.sub(r"(\d)\s*!", r"\1 fact_signo ", texto)
    t = _limpiar(crudo).replace("fact_signo", "!")
    if not t:
        return None

    try:
        for patron in _PORCENTAJE_DE:
            m = patron.search(t)
            if m:
                a, b = _leer_numero(m.group(1)), _leer_numero(m.group(2))
                if b == 0:
                    raise _CuentaMala("No se puede calcular un porcentaje de cero.")
                r = a / b * 100
                return _respuesta(f"{formatear(a)} es el {formatear(r)}% de {formatear(b)}",
                                  f"{formatear(a)} ÷ {formatear(b)} × 100", r)

        con_disparador = bool(_TRIGGER.match(t))
        cuerpo = _TRIGGER.sub("", t, count=1) if con_disparador else t
        cuerpo = re.sub(r"^(?:de|a)\s+", "", cuerpo) if con_disparador else cuerpo
        if not con_disparador and not _SOLO_MATEMATICA.match(cuerpo):
            # sin «cuánto es», solo se acepta si es una frase corta de cuenta pura
            if len(cuerpo) > 60:
                return None
        tokens = _tokenizar(cuerpo)
        numeros = sum(1 for k, _ in tokens if k == "num")
        if numeros == 0:
            return None
        hay_operacion = any(k in ("op", "%", "func", "post", "!", "de", "(") for k, _ in tokens)
        if not hay_operacion:
            return None                           # un número suelto no es una cuenta
        if not con_disparador and numeros < 2 and not any(k in ("func", "post", "!") for k, _ in tokens):
            return None                           # «5%» o «-3» sueltos no se toman como cuenta
        p = _Parser(tokens)
        valor = p.expresion()
        if p.i != len(tokens):
            raise _CuentaMala("No pude entender esa operación. Escríbela así: 25 por 4, 15% de 200, raíz de 144.")
        vista = _armar_vista(p.vista)
        return _respuesta(f"{vista} = {formatear(valor)}", vista, valor)
    except _NoEsCuenta:
        return None
    except _CuentaMala as e:
        # un error solo se muestra si la persona pidió expresamente calcular
        if _TRIGGER.match(t) or _SOLO_MATEMATICA.match(t):
            return {"message": str(e), "expresion": None, "resultado": None}
        return None
    except (ZeroDivisionError, OverflowError, ValueError):
        return {"message": "No pude resolver esa operación (resultado inválido o demasiado grande).",
                "expresion": None, "resultado": None}


def _armar_vista(partes: list[str]) -> str:
    s = " ".join(partes)
    for a, b in ((" ²", "²"), (" ³", "³"), (" !", "!"), (" %", "%"), ("( ", "("), (" )", ")"),
                 ("√ ", "√"), ("∛ ", "∛"), ("\x00 ", "")):
        s = s.replace(a, b)
    return s.replace("\x00", "")


def _respuesta(mensaje: str, expresion: str, resultado) -> dict:
    return {"message": mensaje, "expresion": expresion,
            "resultado": formatear(resultado) if not isinstance(resultado, str) else resultado}
