"""Índice local: el texto y los vectores de tus fragmentos, en archivos simples.

  data/index/vectors.npy  → un vector por fragmento
  data/index/meta.json    → texto, archivo de origen y página de cada fragmento

Sin servidores ni bases de datos. Puedes abrir meta.json y ver exactamente qué sabe tu IA.
"""
import json
import os
from pathlib import Path

import numpy as np

from . import AssistantError, config


class Store:
    def __init__(self, directory: Path = config.INDEX_DIR):
        self.dir = Path(directory)
        self._signature = None
        self._reset()
        self.load()

    def _reset(self) -> None:
        self.vectors = np.zeros((0, 0), dtype=np.float32)
        self.chunks: list[dict] = []
        self.files: dict[str, str] = {}  # archivo → huella, para detectar cambios
        self.model = ""                  # modelo con el que se calcularon los vectores

    @property
    def _vectors_path(self) -> Path:
        return self.dir / "vectors.npy"

    @property
    def _meta_path(self) -> Path:
        return self.dir / "meta.json"

    def _current_signature(self):
        try:
            return (self._vectors_path.stat().st_mtime_ns, self._meta_path.stat().st_mtime_ns)
        except FileNotFoundError:
            return None

    # --- Cargar / guardar --------------------------------------------------
    def load(self) -> None:
        signature = self._current_signature()
        if signature is None:
            self._reset()
            self._signature = None
            return
        meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
        vectors = np.load(self._vectors_path)
        if len(vectors) != len(meta["chunks"]):  # ingest.py está escribiendo justo ahora
            raise AssistantError("El índice se está actualizando. Intenta de nuevo en unos segundos.")
        self.vectors, self.chunks = vectors, meta["chunks"]
        self.files, self.model = meta["files"], meta["model"]
        self._signature = signature

    def reload_if_changed(self) -> None:
        """Si ejecutaste ingest.py con el servidor abierto, toma el índice nuevo solo."""
        if self._current_signature() != self._signature:
            self.load()

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp_vectors, tmp_meta = self.dir / "vectors.tmp", self.dir / "meta.tmp"
        with open(tmp_vectors, "wb") as f:
            np.save(f, self.vectors)
        meta = {"model": self.model, "files": self.files, "chunks": self.chunks}
        tmp_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp_vectors, self._vectors_path)  # reemplazo atómico: nunca queda a medias
        os.replace(tmp_meta, self._meta_path)
        self._signature = self._current_signature()

    # --- Modificar ---------------------------------------------------------
    def clear(self) -> None:
        self._reset()

    def replace_sources(self, sources: set[str], chunks: list[dict], vectors: np.ndarray) -> None:
        """Quita los fragmentos de los archivos en `sources` y agrega los nuevos."""
        keep = [i for i, c in enumerate(self.chunks) if c["source"] not in sources]
        parts = [v for v in (self.vectors[keep], vectors) if len(v)]
        self.vectors = np.vstack(parts) if parts else np.zeros((0, 0), dtype=np.float32)
        self.chunks = [self.chunks[i] for i in keep] + chunks

    # --- Buscar ------------------------------------------------------------
    def search(self, query: np.ndarray, k: int, min_score: float) -> list[dict]:
        """Los k fragmentos más parecidos a la pregunta (similitud coseno de 0 a 1)."""
        self.reload_if_changed()
        if not self.chunks:
            return []
        if self.vectors.shape[1] != query.shape[0]:
            raise AssistantError(
                "El modelo de búsqueda cambió desde la última vez. "
                "Reconstruye el índice con: python ingest.py --todo"
            )
        scores = self.vectors @ query
        k = min(k, len(scores))
        top = np.argpartition(-scores, k - 1)[:k]
        top = top[np.argsort(-scores[top])]
        return [{**self.chunks[i], "score": float(scores[i])} for i in top if scores[i] >= min_score]
