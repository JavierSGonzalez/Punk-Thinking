"""Prueba rápida de la calculadora, la hora y la memoria, escribiendo frases como en el chat.

Uso (con el entorno activado):   python probar_modulos.py
Salir: escribe  salir

La memoria de esta prueba es TEMPORAL: se borra al cerrar y no toca tu data/memoria.json.
"""
import os
import sys
import tempfile

os.environ["PK_DATA_DIR"] = tempfile.mkdtemp(prefix="pk-prueba-")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import calculadora, memoria, reloj  # noqa: E402

historial = []
print("Prueba de módulos de PK. Escribe frases como en el chat («salir» para terminar).")
print("Ejemplos: cuánto es el 15% de 200 | qué hora es en Tokio | me llamo Ana | cómo me llamo | olvida todo\n")
while True:
    try:
        frase = input("tú > ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if frase.lower() in ("salir", "exit", "q"):
        break
    if not frase:
        continue
    # mismo orden que tendrá PK: memoria → calculadora → reloj
    r = memoria.handle(frase, "prueba", historial)
    quien = "memoria"
    if not r:
        r, quien = calculadora.handle(frase), "calculadora"
    if not r:
        r, quien = reloj.handle(frase), "reloj"
    if r:
        texto = r["message"]
    else:
        texto, quien = "(esto lo contestaría el modelo de lenguaje; los módulos no lo reclaman)", "—"
    guardado = memoria.nota_guardado(memoria.auto_guardar(frase, "prueba"))
    if guardado:
        texto += "\n" + guardado
    print(f"PK [{quien}] > {texto}\n")
    historial += [{"role": "user", "content": frase}, {"role": "assistant", "content": texto}]
