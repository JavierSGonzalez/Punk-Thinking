"""Configuración central de tu IA personal.

Casi todo se cambia desde el archivo .env (copia .env.example y renómbralo a .env).
Aquí solo se leen esos valores y se definen las carpetas del proyecto.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _text(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


def _number(name: str, default, kind=int):
    try:
        return kind(_text(name, str(default)))
    except ValueError:
        raise SystemExit(f"En el archivo .env, {name} debe ser un número válido.")


def _flag(name: str, default: bool) -> bool:
    return _text(name, "on" if default else "off").lower() in {"on", "si", "sí", "true", "1", "yes"}


# --- Identidad -------------------------------------------------------------
APP_NAME = _text("APP_NAME", "Punk Thinking")
PORT = _number("PORT", 8000)

# --- Carpetas --------------------------------------------------------------
KNOWLEDGE_DIR = ROOT / "knowledge"   # TUS documentos privados (lo único que la IA conoce)
INDEX_DIR = ROOT / "data" / "index"  # índice generado por ingest.py (no se edita a mano)
MODELS_DIR = ROOT / "data" / "models"  # modelo de búsqueda descargado una sola vez

# --- Búsqueda (qué fragmentos se le muestran a la IA) ----------------------
EMBED_MODEL = _text("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
CHUNK_SIZE = _number("CHUNK_SIZE", 800)        # caracteres por fragmento
CHUNK_OVERLAP = _number("CHUNK_OVERLAP", 150)  # solapamiento entre fragmentos
TOP_K = _number("TOP_K", 5)                    # cuántos fragmentos usa para responder
MIN_SCORE = _number("MIN_SCORE", 0.25, float)  # similitud mínima (0 a 1) para considerar un fragmento

# --- Motor de lenguaje (quien redacta la respuesta) ------------------------
LLM_PROVIDER = _text("LLM_PROVIDER", "ollama").lower()  # "ollama" (local) o "anthropic" (Claude)
OLLAMA_URL = _text("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = _text("OLLAMA_MODEL", "gemma3:4b")
OLLAMA_NUM_CTX = _number("OLLAMA_NUM_CTX", 4096)
ANTHROPIC_API_KEY = _text("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = _text("ANTHROPIC_MODEL", "claude-sonnet-5-5")
MAX_ANSWER_TOKENS = _number("MAX_ANSWER_TOKENS", 1024)

# --- Conversación y búsqueda web --------------------------------------------
HISTORY_MESSAGES = _number("HISTORY_MESSAGES", 6)  # mensajes previos del chat que PK recuerda
WEB_SEARCH = _text("WEB_SEARCH", "on").lower() in {"on", "si", "sí", "true", "1", "yes"}
WEB_BACKEND = _text("WEB_BACKEND", "searxng").lower()  # "searxng" (recomendado) o "duckduckgo"
SEARXNG_URL = _text("SEARXNG_URL", "http://127.0.0.1:8888")
WEB_RESULTS = _number("WEB_RESULTS", 5)
WEB_USE_FILE_CONTEXT = _flag("WEB_USE_FILE_CONTEXT", True)  # armar la búsqueda web con el TEMA del archivo adjunto
WEB_CONFIRM_FILE_QUERY = _flag("WEB_CONFIRM_FILE_QUERY", True)  # pedir tu OK si la consulta lleva palabras sacadas del archivo

# --- Archivos y fotos adjuntos al chat ---------------------------------------
ATTACH_DIR = ROOT / "data" / "attachments"          # copia de trabajo de cada archivo (se borra con el chat)
VISION_MODEL = _text("VISION_MODEL", "moondream")   # modelo de Ollama que "ve" las fotos
ATTACH_MAX_MB = _number("ATTACH_MAX_MB", 15)        # tamaño máximo por archivo
ATTACH_MAX_PER_MESSAGE = _number("ATTACH_MAX_PER_MESSAGE", 4)
ATTACH_MAX_CHARS = _number("ATTACH_MAX_CHARS", 300000)  # texto máximo que se lee de un archivo (~100 páginas)
ATTACH_TOP_K = _number("ATTACH_TOP_K", 5)           # fragmentos del archivo que se usan para responder
ATTACH_MIN_SCORE = _number("ATTACH_MIN_SCORE", 0.15, float)  # parecido mínimo para usar archivos de mensajes anteriores
ATTACH_CONTEXT_FILES = _number("ATTACH_CONTEXT_FILES", 6)    # cuántos archivos del chat siguen "a mano"

# --- Modo asistente (hablar con PK) -------------------------------------------
WHISPER_MODEL = _text("WHISPER_MODEL", "base")       # oído local: tiny (rápido) · base · small (más preciso, más lento)
WHISPER_DIR = ROOT / "data" / "whisper"              # el modelo de oído se descarga aquí una sola vez
VOICE_LANGUAGE = _text("VOICE_LANGUAGE", "es")       # idioma en que se te escucha
VOICE_ENGINE = _text("VOICE_ENGINE", "windows").lower()  # "windows" (voces de este PC) o "browser" (voces del navegador)
VOICE_NAME = _text("VOICE_NAME", "")                 # parte del nombre de la voz, p. ej. "Loquendo", "Jorge" o "Helena"
VOICE_RATE = _number("VOICE_RATE", 0)                # velocidad de la voz, de -10 (lenta) a 10 (rápida)
VOICE_MAX_CHARS = _number("VOICE_MAX_CHARS", 450)    # lo máximo que PK dice en voz alta; el resto queda en pantalla
