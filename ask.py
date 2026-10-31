"""Pregúntale a tu IA desde la terminal (útil para probar rápido).

Uso:
    python ask.py "¿Qué dicen mis documentos sobre X?"
    python ask.py                    → modo conversación ('salir' para terminar)
"""
import sys

from core import AssistantError, assistant, config


def show(question: str) -> bool:
    try:
        result = assistant.reply(question)  # (en la terminal cada pregunta va sola, sin memoria)
    except AssistantError as error:
        print(f"\nAviso: {error}\n")
        return False
    print(f"\n[{result['mode']}] {result['answer']}")
    if result["web_query"]:
        print(f"\nSe buscó en la web: «{result['web_query']}»")
    for link in result["web"]:
        print(f"  [{link['n']}] {link['title']} - {link['url']}")
    if result["sources"]:
        print("\nFuentes:")
        for source in result["sources"]:
            where = source["source"] + (f", {source['page']}" if source["page"] else "")
            print(f"  [{source['n']}] {where}  (similitud {source['score']})")
    print()
    return True


def main() -> int:
    if len(sys.argv) > 1:
        return 0 if show(" ".join(sys.argv[1:])) else 1
    print(f"{config.APP_NAME}: escribe tu pregunta ('salir' para terminar).")
    while True:
        try:
            question = input("\nTú > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if question.lower() in {"salir", "exit", "q"}:
            return 0
        if question:
            show(question)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
