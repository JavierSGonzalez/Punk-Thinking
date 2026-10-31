"""Conexión con el motor de lenguaje que REDACTA las respuestas (y con el que "ve" las fotos).

  LLM_PROVIDER=ollama     → modelos locales: gratis, privados y sin internet.
  LLM_PROVIDER=anthropic  → Claude por API: mejor calidad, pero lo que se le envía (fragmentos y
                            fotos adjuntas) viaja a los servidores de Anthropic.

Para cambiar de motor solo editas el archivo .env; el resto del proyecto no se toca.
"""
import base64
import re

import httpx

from . import AssistantError, config, perfil

_THINK = re.compile(r"<think>.*?</think>", flags=re.DOTALL)  # modelos que "piensan" en voz alta
_ECHO = re.compile(r"^[ \t*#>]*(PREGUNTA|FRAGMENTOS|RESULTADOS WEB|CONTEXTO DEL ARCHIVO ADJUNTO|RESPUESTA)[ \t*]*:.*$", flags=re.M)


def clean_echo(text: str) -> str:
    """Los modelos pequeños a veces repiten la plantilla («PREGUNTA: …»): se queda solo lo que va después."""
    marks = list(_ECHO.finditer(text))
    if not marks:
        return text
    rest = text[marks[-1].end():].strip()
    if marks[-1].group(1) == "RESPUESTA":  # «RESPUESTA: texto»: el texto va en la misma línea
        rest = (text[marks[-1].start():].split(":", 1)[1]).strip()
    return rest if len(rest) >= 10 else text


def describe() -> str:
    model = config.OLLAMA_MODEL if config.LLM_PROVIDER == "ollama" else config.ANTHROPIC_MODEL
    return f"{config.LLM_PROVIDER} · {model}"


def vision_name() -> str:
    return config.VISION_MODEL if config.LLM_PROVIDER == "ollama" else config.ANTHROPIC_MODEL


def _unknown_provider() -> AssistantError:
    return AssistantError(
        f"LLM_PROVIDER='{config.LLM_PROVIDER}' no existe. Usa 'ollama' o 'anthropic' en el archivo .env."
    )


def generate(system: str, user: str, history: list[dict] | None = None, max_tokens: int | None = None) -> str:
    """`history` = mensajes previos [{"role": "user"|"assistant", "content": str}] para recordar el chat."""
    history = history or []
    system = perfil.fill(system)  # {NOMBRE} → el nombre actual de PK (puede haberlo cambiado el usuario)
    if config.LLM_PROVIDER == "ollama":
        text = _ollama(system, user, history, max_tokens)
    elif config.LLM_PROVIDER == "anthropic":
        text = _anthropic(system, user, history, max_tokens)
    else:
        raise _unknown_provider()
    text = clean_echo(_THINK.sub("", text).strip()).strip()
    return text or "El modelo no devolvió texto. Intenta de nuevo."


# moondream es muy pequeño: con instrucciones largas en español a veces no responde nada.
# Para él se usa una orden corta; si aun así viene vacío, se reintenta con otra más simple.
_SHORT_PROMPTS = ("Describe this image in detail.", "What is in this image?")


def describe_image(image: bytes, prompt: str) -> str:
    """Pide al modelo de visión que describa una imagen (JPEG). Devuelve '' si no respondió nada."""
    encoded = base64.b64encode(image).decode()
    if config.LLM_PROVIDER == "ollama":
        small = config.VISION_MODEL.lower().startswith("moondream")
        prompts = list(_SHORT_PROMPTS) if small else [prompt, _SHORT_PROMPTS[0]]
        text = ""
        for attempt in prompts:
            payload = {
                "model": config.VISION_MODEL,
                "stream": False,
                "keep_alive": "30s",  # se descarga pronto de la RAM para dejar sitio al modelo de texto
                "messages": [{"role": "user", "content": attempt, "images": [encoded]}],
                "options": {"temperature": 0.1, "num_predict": 400},  # tope de palabras: acorta la espera
            }
            text = _THINK.sub("", _ollama_post(payload, config.VISION_MODEL, vision=True)).strip()
            if len(text) >= 8:
                break
    elif config.LLM_PROVIDER == "anthropic":
        blocks = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encoded}},
            {"type": "text", "text": prompt},
        ]
        text = _anthropic("Describes imágenes con precisión y sin inventar nada.", blocks, [], 1024)
    else:
        raise _unknown_provider()
    return _THINK.sub("", text).strip()


def _ollama_post(payload: dict, model: str, vision: bool = False) -> str:
    try:
        response = httpx.post(
            f"{config.OLLAMA_URL}/api/chat", json=payload, timeout=httpx.Timeout(600.0, connect=5.0)
        )
        response.raise_for_status()
    except httpx.ConnectError:
        raise AssistantError(
            f"No pude conectar con Ollama en {config.OLLAMA_URL}. Abre la aplicación Ollama "
            "(o ejecuta 'ollama serve') y vuelve a intentar."
        )
    except httpx.TimeoutException:
        raise AssistantError("Ollama tardó demasiado en responder. Prueba con un modelo más pequeño en .env.")
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            raise AssistantError(
                f"El modelo '{model}' no está descargado. Ejecuta en la terminal: ollama pull {model}"
            )
        body = error.response.text[:200]
        if vision and "image" in body.lower():
            raise AssistantError(
                f"El modelo '{model}' no puede analizar imágenes. Elige uno con visión en VISION_MODEL "
                "(por ejemplo: ollama pull moondream)."
            )
        raise AssistantError(f"Ollama devolvió un error ({error.response.status_code}): {body}")
    return response.json()["message"]["content"]


def _ollama(system: str, user: str, history: list[dict], max_tokens: int | None) -> str:
    options = {"temperature": 0.1, "num_ctx": config.OLLAMA_NUM_CTX}  # 0.1 = respuestas fieles
    if max_tokens:
        options["num_predict"] = max_tokens
    payload = {
        "model": config.OLLAMA_MODEL,
        "stream": False,
        "messages": [{"role": "system", "content": system}, *history, {"role": "user", "content": user}],
        "options": options,
    }
    return _ollama_post(payload, config.OLLAMA_MODEL)


def _anthropic(system: str, user, history: list[dict], max_tokens: int | None) -> str:
    """`user` es texto, o una lista de bloques (texto + imagen) cuando se analiza una foto."""
    if not config.ANTHROPIC_API_KEY:
        raise AssistantError("Falta ANTHROPIC_API_KEY en el archivo .env (o cambia a LLM_PROVIDER=ollama).")
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    try:
        message = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=max_tokens or config.MAX_ANSWER_TOKENS,
            system=system,
            messages=[*history, {"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError:
        raise AssistantError("La clave ANTHROPIC_API_KEY del archivo .env no es válida.")
    except anthropic.NotFoundError:
        raise AssistantError(f"El modelo '{config.ANTHROPIC_MODEL}' no existe o no tienes acceso. Revisa ANTHROPIC_MODEL en .env.")
    except anthropic.APIConnectionError:
        raise AssistantError("No pude conectar con la API de Anthropic. Revisa tu conexión a internet.")
    except anthropic.APIError as error:
        raise AssistantError(f"La API de Anthropic devolvió un error: {error}")
    return "".join(block.text for block in message.content if block.type == "text")
