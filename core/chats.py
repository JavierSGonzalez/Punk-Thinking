"""Chats guardados en tu computador: un archivo .json por chat dentro de data/chats/.

Sobreviven a recargar la página y a apagar el servidor. Puedes abrir esos archivos
con el Bloc de notas para ver exactamente qué se guardó, o borrarlos para olvidar un chat.
"""
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone

from . import config

CHATS_DIR = config.ROOT / "data" / "chats"
DEFAULT_TITLE = "Chat nuevo"
_ID = re.compile(r"^[0-9a-f]{32}$")  # solo ids que nosotros generamos (evita rutas peligrosas)
_lock = threading.Lock()


class ChatNotFound(Exception):
    pass


class NoPendingWeb(Exception):
    """Se intentó confirmar una búsqueda web que ya no está esperando (otra pregunta la dejó atrás)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _clean(title: str) -> str:
    return " ".join(title.split())[:80] or DEFAULT_TITLE


def _path(chat_id: str):
    if not _ID.match(chat_id or ""):
        raise ChatNotFound(chat_id)
    return CHATS_DIR / f"{chat_id}.json"


def _read(chat_id: str) -> dict:
    try:
        return json.loads(_path(chat_id).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        raise ChatNotFound(chat_id)


def _write(chat: dict) -> None:
    CHATS_DIR.mkdir(parents=True, exist_ok=True)
    path = _path(chat["id"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(chat, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)  # reemplazo atómico: un corte de luz no deja el chat a medias


def list_chats() -> list[dict]:
    """Resumen de todos los chats, el más reciente primero."""
    items = []
    if CHATS_DIR.exists():
        for file in CHATS_DIR.glob("*.json"):
            try:
                chat = json.loads(file.read_text(encoding="utf-8"))
                items.append({"id": chat["id"], "title": chat["title"], "updated": chat["updated"]})
            except (json.JSONDecodeError, KeyError, OSError):
                continue  # archivo dañado: se ignora
    return sorted(items, key=lambda c: c["updated"], reverse=True)


def get(chat_id: str) -> dict:
    return _read(chat_id)


def history(chat: dict, drop_last: int = 0) -> list[dict]:
    """Los últimos mensajes del chat, en el formato que entiende el motor de lenguaje.

    `drop_last` ignora los N mensajes finales (por ejemplo, la pregunta que se está terminando de responder).
    """
    messages = chat["messages"][: len(chat["messages"]) - drop_last] if drop_last else chat["messages"]
    count = config.HISTORY_MESSAGES - config.HISTORY_MESSAGES % 2  # siempre pares: empieza con el usuario
    recent = messages[-count:] if count > 0 else []
    return [
        {"role": m["role"], "content": (m["text"] if m["role"] == "user" else m["answer"])[:600]}
        for m in recent
    ]


def pending_web(chat: dict) -> dict | None:
    """Si la última respuesta espera tu permiso para buscar en la web: {question, query, terms, fresh}."""
    messages = chat["messages"]
    if len(messages) < 2:
        return None
    asked, last = messages[-2], messages[-1]
    pending = last.get("pending_web") if last["role"] == "assistant" else None
    if not pending or asked["role"] != "user":
        return None
    return {
        "question": asked["text"],
        "query": pending["query"],
        "terms": pending.get("terms", []),
        "fresh": [item["id"] for item in asked.get("attachments", [])],  # los archivos que venían con esa pregunta
    }


def attachment_ids(chat: dict, limit: int | None = None) -> list[str]:
    """Ids de los archivos adjuntos del chat, del más antiguo al más reciente, sin repetir."""
    ids = []
    for message in chat["messages"]:
        for item in message.get("attachments", []):
            if item["id"] in ids:
                ids.remove(item["id"])
            ids.append(item["id"])
    return ids[-limit:] if limit else ids


def referenced_attachment_ids() -> set[str]:
    """Todos los archivos adjuntos que algún chat guardado está usando."""
    ids = set()
    if CHATS_DIR.exists():
        for file in CHATS_DIR.glob("*.json"):
            try:
                ids.update(attachment_ids(json.loads(file.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, KeyError, OSError):
                continue
    return ids


def rename(chat_id: str, title: str) -> dict:
    with _lock:
        chat = _read(chat_id)
        chat["title"] = _clean(title)
        _write(chat)
        return chat


def delete(chat_id: str) -> None:
    with _lock:
        try:
            _path(chat_id).unlink()
        except FileNotFoundError:
            raise ChatNotFound(chat_id)


def _assistant_message(result: dict, now: str) -> dict:
    return {
        "role": "assistant",
        "answer": result["answer"],
        "sources": result["sources"],
        "grounded": result["grounded"],
        "mode": result.get("mode", "documentos"),
        "web_query": result.get("web_query"),
        "file_context": result.get("file_context", False),
        "web": result.get("web", []),
        **({"pending_web": result["pending_web"]} if result.get("pending_web") else {}),
        "time": now,
    }


def save_exchange(chat_id: str | None, question: str, result: dict, attachments: list[dict] | None = None,
                  title: str | None = None) -> dict:
    """Agrega pregunta + respuesta a un chat. Sin chat_id, crea uno nuevo titulado con la pregunta.

    `attachments` = archivos que venían con la pregunta, como [{"id", "name", "kind"}].
    `title` = título del chat nuevo si no conviene usar la pregunta (por ejemplo, si solo se envió un archivo).
    """
    with _lock:
        now = _now()
        if chat_id:
            chat = _read(chat_id)
        else:
            chat = {"id": uuid.uuid4().hex, "title": DEFAULT_TITLE, "created": now, "messages": []}
        if chat["title"] == DEFAULT_TITLE:
            chat["title"] = _clean(title or question[:60])
        chat["messages"] += [
            {"role": "user", "text": question, "time": now, **({"attachments": attachments} if attachments else {})},
            _assistant_message(result, now),
        ]
        chat["updated"] = now
        _write(chat)
        return chat


def replace_last_answer(chat_id: str, result: dict) -> dict:
    """Cambia la respuesta que esperaba tu permiso por el resultado de la búsqueda (o por la cancelación)."""
    with _lock:
        chat = _read(chat_id)
        if pending_web(chat) is None:
            raise NoPendingWeb(chat_id)
        now = _now()
        chat["messages"][-1] = _assistant_message(result, now)
        chat["updated"] = now
        _write(chat)
        return chat
