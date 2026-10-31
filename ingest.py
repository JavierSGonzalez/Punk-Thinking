"""Construye o actualiza el índice con los documentos de la carpeta knowledge/.

Uso:
    python ingest.py          → procesa solo lo nuevo, lo modificado y lo borrado
    python ingest.py --todo   → reconstruye todo desde cero
"""
import sys
import time

from core import AssistantError, config, documents, embeddings
from core.store import Store


def main() -> int:
    full = "--todo" in sys.argv
    config.KNOWLEDGE_DIR.mkdir(exist_ok=True)
    store = Store()
    if full or (store.chunks and store.model != config.EMBED_MODEL):
        if not full:
            print("El modelo de búsqueda cambió: se reconstruye todo el índice.")
        store.clear()

    found = documents.list_files(config.KNOWLEDGE_DIR)
    hashes = {name: documents.file_hash(path) for name, path in found.items()}
    removed = {name for name in store.files if name not in found}
    changed = {name for name, digest in hashes.items() if store.files.get(name) != digest}
    if not removed and not changed:
        print(f"Todo al día: {len(store.files)} documento(s), {len(store.chunks)} fragmentos.")
        return 0

    for name in sorted(removed):
        print(f"  quitando {name} (ya no está en knowledge/)")

    new_chunks, done = [], {}
    for name in sorted(changed):
        print(f"  leyendo {name} ... ", end="", flush=True)
        try:
            chunks = documents.make_chunks(found[name], name, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        except Exception as error:  # archivo dañado, PDF con clave, etc.
            print(f"ERROR ({error}). Se omite; se reintentará la próxima vez.")
            continue
        print(f"{len(chunks)} fragmentos" if chunks else "SIN TEXTO (¿PDF escaneado? necesita OCR). Se omite.")
        new_chunks += chunks
        done[name] = hashes[name]

    started = time.time()
    if new_chunks:
        print(f"Calculando vectores de {len(new_chunks)} fragmentos (en tu computador)...")
    vectors = embeddings.embed_passages([chunk["text"] for chunk in new_chunks])

    drop = removed | changed  # los fragmentos viejos de lo modificado se reemplazan
    store.replace_sources(drop, new_chunks, vectors)
    store.files = {name: digest for name, digest in store.files.items() if name not in drop} | done
    store.model = config.EMBED_MODEL
    store.save()

    print(f"Listo en {time.time() - started:.0f} s: {len(store.files)} documento(s), {len(store.chunks)} fragmentos.")
    if not store.chunks:
        print("El índice quedó vacío. Copia archivos .txt, .md, .pdf o .docx a la carpeta knowledge/.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        sys.exit(main())
    except AssistantError as error:
        print(f"\nAviso: {error}")
        sys.exit(1)
