"""Convierte texto en vectores (listas de números) para buscar por SIGNIFICADO.

Corre 100% en tu computador. El modelo (público) se descarga una sola vez; no se envía
nada tuyo. Después de la primera descarga funciona sin internet.
"""
from functools import lru_cache

import numpy as np

from . import config


def _logs(enabled: bool) -> None:
    """fastembed imprime errores ruidosos si el modelo aún no está descargado."""
    try:
        from loguru import logger

        (logger.enable if enabled else logger.disable)("fastembed")
    except ImportError:
        pass


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    options = {"model_name": config.EMBED_MODEL, "cache_dir": str(config.MODELS_DIR)}
    _logs(False)
    try:
        return TextEmbedding(local_files_only=True, **options)  # ya descargado: sin internet
    except Exception:
        pass
    finally:
        _logs(True)
    print("Descargando el modelo de búsqueda (solo la primera vez; unos 220 MB)...")
    return TextEmbedding(**options)


def _normalize(vectors) -> np.ndarray:
    matrix = np.asarray(list(vectors), dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.clip(norms, 1e-12, None)


def embed_passages(texts: list[str]) -> np.ndarray:
    """Vectores de los fragmentos de tus documentos (una fila por fragmento)."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    return _normalize(_model().passage_embed(texts, batch_size=32))


def embed_query(text: str) -> np.ndarray:
    """Vector de la pregunta."""
    return _normalize(_model().query_embed(text))[0]
