"""Lee tus archivos y los parte en fragmentos ("chunks") listos para buscar.

Formatos soportados: .txt  .md  .pdf  .docx
"""
import hashlib
import re
from pathlib import Path

SUPPORTED = {".txt", ".md", ".pdf", ".docx"}
SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|\n")


# --- Descubrir archivos ----------------------------------------------------
def list_files(folder: Path) -> dict[str, Path]:
    """Devuelve {ruta_relativa: ruta_completa} de todos los archivos soportados."""
    found = {}
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        if path.name.startswith(("~$", ".")):  # temporales de Word y archivos ocultos
            continue
        found[path.relative_to(folder).as_posix()] = path
    return found


def file_hash(path: Path) -> str:
    """Huella del contenido: si no cambia, no hace falta volver a procesar el archivo."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# --- Leer archivos ---------------------------------------------------------
def _read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):  # cp1252 = archivos viejos de Windows
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1")


def _read_pdf(path: Path) -> list[tuple[str, str]]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        reader.decrypt("")  # PDFs protegidos solo contra edición
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)      # palabras cortadas al final de línea
        text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)       # saltos de línea sueltos → espacio
        pages.append((f"p. {number}", text))
    return pages


def _read_docx(path: Path) -> list[tuple[str, str]]:
    import docx

    document = docx.Document(str(path))
    parts = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    for table in document.tables:  # las tablas suelen contener los datos importantes
        for row in table.rows:
            cells = []
            for cell in row.cells:
                text = cell.text.strip()
                if text and (not cells or cells[-1] != text):  # celdas combinadas se repiten
                    cells.append(text)
            if cells:
                parts.append(" | ".join(cells))
    return [("", "\n\n".join(parts))]


def read_file(path: Path) -> list[tuple[str, str]]:
    """Devuelve [(ubicación, texto)]. La ubicación es 'p. 3' en PDFs y '' en el resto."""
    extension = path.suffix.lower()
    if extension == ".pdf":
        return _read_pdf(path)
    if extension == ".docx":
        return _read_docx(path)
    return [("", _read_text_file(path))]


# --- Trocear ---------------------------------------------------------------
def _units(text: str, size: int) -> list[str]:
    """Piezas pequeñas del texto: párrafos; si son largos, frases; si aún son largas, cortes."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    units = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= size:
            units.append(paragraph)
            continue
        for piece in SENTENCE_END.split(paragraph):
            piece = piece.strip()
            while len(piece) > size:  # frase gigante sin puntuación
                cut = piece.rfind(" ", 0, size)
                cut = cut if cut > size // 2 else size
                units.append(piece[:cut].strip())
                piece = piece[cut:].strip()
            if piece:
                units.append(piece)
    return units


def split_text(text: str, size: int, overlap: int) -> list[str]:
    """Agrupa las piezas en fragmentos de ~size caracteres, repitiendo el final del anterior."""
    chunks, current, length = [], [], 0
    for unit in _units(text, size):
        if current and length + len(unit) + 1 > size:
            chunks.append("\n".join(current))
            keep, kept = [], 0  # solapamiento: últimas piezas que caben en `overlap`
            for previous in reversed(current):
                if kept + len(previous) > overlap:
                    break
                keep.insert(0, previous)
                kept += len(previous) + 1
            current, length = keep, kept
        current.append(unit)
        length += len(unit) + 1
    if current:
        chunks.append("\n".join(current))
    # descarta fragmentos sin contenido real (números de página, líneas vacías...)
    return [c for c in chunks if sum(ch.isalnum() for ch in c) >= 8]


def make_chunks(path: Path, relative: str, size: int, overlap: int) -> list[dict]:
    """Lee un archivo y devuelve sus fragmentos como diccionarios {source, page, text}."""
    chunks = []
    for location, text in read_file(path):
        for piece in split_text(text, size, overlap):
            chunks.append({"source": relative, "page": location, "text": piece})
    return chunks
