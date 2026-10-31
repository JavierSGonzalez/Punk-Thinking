"""Búsqueda web privada.

Lo ÚNICO que sale de tu computador es una consulta corta de pocas palabras (nunca tus
documentos ni tu historial). Los resultados se leen y resumen con tu modelo local.

  WEB_BACKEND=searxng     → SearXNG corriendo en tu PC (Docker); consulta varios buscadores sin cuenta.
  WEB_BACKEND=duckduckgo  → DuckDuckGo directo, sin instalar nada más (plan B).
"""
import time
from urllib.parse import urlparse

import httpx

from . import AssistantError, config


def search(query: str) -> list[dict]:
    """Devuelve [{n, title, url, snippet}] con enlaces http(s) únicos."""
    if config.WEB_BACKEND == "searxng":
        raw = _searxng(query)
    elif config.WEB_BACKEND == "duckduckgo":
        raw = _duckduckgo(query)
    else:
        raise AssistantError(f"WEB_BACKEND='{config.WEB_BACKEND}' no existe. Usa 'searxng' o 'duckduckgo' en .env.")
    results, seen = [], set()
    for item in raw:
        url = (item.get("url") or "").strip()
        if urlparse(url).scheme not in {"http", "https"} or url in seen:
            continue  # solo enlaces web normales (nada de javascript: ni repetidos)
        seen.add(url)
        results.append({
            "n": len(results) + 1,
            "title": " ".join((item.get("title") or url).split())[:120],
            "url": url,
            "snippet": " ".join((item.get("snippet") or "").split())[:300],
        })
        if len(results) >= config.WEB_RESULTS:
            break
    return results


def _searxng(query: str) -> list[dict]:
    try:
        response = httpx.get(
            f"{config.SEARXNG_URL}/search",
            params={"q": query, "format": "json", "language": "es"},
            timeout=httpx.Timeout(25.0, connect=4.0),
        )
    except httpx.ConnectError:
        raise AssistantError(
            f"SearXNG no está encendido en {config.SEARXNG_URL}. Abre Docker Desktop y ejecuta: docker start searxng "
            "(o cambia a WEB_BACKEND=duckduckgo en .env)."
        )
    except httpx.TimeoutException:
        raise AssistantError("SearXNG tardó demasiado en responder.")
    if response.status_code == 403:
        raise AssistantError(
            "SearXNG rechazó el formato JSON. Revisa que searxng/config/settings.yml incluya 'json' "
            "en search.formats y reinicia con: docker restart searxng"
        )
    if response.status_code >= 400:
        raise AssistantError(f"SearXNG devolvió un error ({response.status_code}).")
    try:
        data = response.json()
    except ValueError:
        raise AssistantError("SearXNG no devolvió JSON. Revisa searxng/config/settings.yml (search.formats).")
    return [
        {"title": r.get("title"), "url": r.get("url"), "snippet": r.get("content")}
        for r in data.get("results", [])
    ]


def _duckduckgo(query: str) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        raise AssistantError("Falta la librería ddgs. Ejecuta: pip install ddgs")
    items, failure = None, None
    for attempt in range(2):  # DuckDuckGo limita o falla de vez en cuando: un segundo intento suele bastar
        try:
            items = DDGS().text(query, max_results=config.WEB_RESULTS + 3, region="wt-wt")
            break
        except Exception as error:
            failure = error
            time.sleep(1.5)
    if items is None:
        raise AssistantError(f"DuckDuckGo no respondió ({type(failure).__name__}). Intenta de nuevo en un momento.")
    return [{"title": i.get("title"), "url": i.get("href"), "snippet": i.get("body")} for i in items]
