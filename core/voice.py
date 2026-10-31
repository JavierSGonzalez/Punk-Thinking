"""Voz del modo asistente: OÍR (Whisper, local) y HABLAR (las voces instaladas en este computador).

  oír    : faster-whisper corre en tu PC. El audio se transcribe y se borra al instante; nunca sale ni se guarda.
  hablar : voces de Windows (SAPI) con PowerShell, en 64 y 32 bits (las voces antiguas, como Loquendo, son de 32 bits).
           Si no hay, la página usa las voces locales de tu navegador.

Para ver qué voces tiene tu PC:   python -m core.voice
"""
import importlib.util
import os
import re
import struct
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from . import AssistantError, config, perfil

WINDOWS = os.name == "nt"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
MAX_SPEAK_CHARS = 2000

# ---------------------------------------------------------------- OÍR (Whisper)
_model = None
_lock = threading.Lock()
_warming = False


def stt_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def stt_ready() -> bool:
    return _model is not None


def _whisper():
    global _model
    with _lock:
        if _model is None:
            if not stt_available():
                raise AssistantError("Falta instalar el oído de PK. Ejecuta en la terminal: pip install -r requirements.txt")
            from faster_whisper import WhisperModel
            config.WHISPER_DIR.mkdir(parents=True, exist_ok=True)
            try:
                _model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8",
                                      download_root=str(config.WHISPER_DIR))
            except Exception as error:
                raise AssistantError(
                    f"No pude cargar el modelo de voz '{config.WHISPER_MODEL}'. La primera vez necesita internet para "
                    f"descargarlo una sola vez (no se envía nada tuyo). Detalle: {str(error)[:150]}"
                )
        return _model


def warm_up() -> None:
    """Carga el modelo en segundo plano para que la primera frase no espere."""
    global _warming
    if _model is not None or _warming or not stt_available():
        return
    _warming = True

    def load():
        global _warming
        try:
            _whisper()
        except Exception:
            pass  # el error se mostrará al intentar hablar
        finally:
            _warming = False

    threading.Thread(target=load, daemon=True).start()


def transcribe(data: bytes, ext: str = "webm") -> str:
    """Audio → texto. El archivo temporal se borra siempre, haya error o no."""
    ext = re.sub(r"[^a-z0-9]", "", ext.lower())[:5] or "webm"
    model = _whisper()
    handle = tempfile.NamedTemporaryFile(suffix="." + ext, delete=False)
    try:
        with handle:
            handle.write(data)
        try:
            segments, _info = model.transcribe(handle.name, language=config.VOICE_LANGUAGE, beam_size=1, vad_filter=True)
            parts = [s.text.strip() for s in segments if getattr(s, "no_speech_prob", 0) < 0.6]
        except Exception as error:
            raise AssistantError(f"No pude entender ese audio ({str(error)[:120]}). Intenta de nuevo.")
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
    return " ".join(part for part in parts if part).strip()


# --------------------------------------------------------------- HABLAR
def tts_engine() -> str:
    return "windows" if (WINDOWS and config.VOICE_ENGINE == "windows") else "browser"


def _para_voz_herramienta(texto: str) -> str:
    """Cuentas y horas escritas con símbolos (25 × 4 = 100, 1,024, 11:34 p. m.) → como se dicen en voz alta."""
    texto = re.sub(r"(?<=\d),(?=\d{3}\b)", "", texto)             # 1,024 → 1024 (si no, la voz dice «uno coma cero…»)
    texto = re.sub(r"(?<=\d)\.(?=\d)", " punto ", texto)            # 3.5 → 3 punto 5
    for simbolo, palabra in (("×", " por "), ("÷", " entre "), ("√", " raíz de "), ("∛", " raíz cúbica de "),
                             ("²", " al cuadrado"), ("³", " al cubo"), ("^", " elevado a "), ("=", " es "),
                             ("%", " por ciento"), ("!", " factorial")):
        texto = texto.replace(simbolo, palabra)
    texto = re.sub(r"(?<=\d) - (?=\d)", " menos ", texto)
    texto = re.sub(r"(?<=\d) \+ (?=\d)", " más ", texto)
    texto = re.sub(r"(?<!\w)-(?=\d)", "menos ", texto)

    def franja(m):
        h = int(m.group(1)) % 12
        if m.group(3).startswith("a"):
            return f"{m.group(1)}:{m.group(2)} de la mañana"
        return f"{m.group(1)}:{m.group(2)} de la {'tarde' if (h or 12) < 7 or h == 0 else 'noche'}"
    return re.sub(r"(\d{1,2}):(\d{2}) ([ap])\. m\.", franja, texto)


def speakable(answer: str, mode: str = "") -> str:
    """Convierte la respuesta escrita en algo agradable de oír: sin citas, enlaces ni formato, y corta."""
    if mode == "web_pendiente":
        return "Necesito tu permiso para buscar en la web. Revisa la consulta en pantalla."
    if mode == "espacio":  # al crear o ampliar un archivo, en voz alta solo se dice el aviso; el contenido queda en pantalla
        answer = answer.split("\n", 1)[0]
        answer = re.sub(r"\s*Revísalo:.*$", "", answer)
    answer = re.sub(r"\s*\(Guardé en tu memoria:.*?\)", "", answer, flags=re.S)  # el aviso de memoria queda en pantalla
    if mode == "herramienta":
        answer = _para_voz_herramienta(answer)
    text = re.sub(r"\[\d+(?:\s*[,;]\s*\d+)*\]", "", answer)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"^\s*(?:[-•*]|\d+[.)])\s+", "", text, flags=re.M)
    text = re.sub(r"[*_`#>~|]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    limit = config.VOICE_MAX_CHARS
    if len(text) <= limit:
        return text
    cut = max(text.rfind(mark, 0, limit) for mark in (". ", "! ", "? "))
    cut = cut + 1 if cut > limit * 0.4 else text.rfind(" ", 0, limit)
    return text[: cut if cut > 0 else limit].rstrip(" ,;:") + " El resto lo tienes en pantalla."


_SPEAK_PS = r"""
param([string]$TextFile, [string]$Out, [string]$Name, [int]$Rate, [int]$Strict)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = @($s.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object { $_.VoiceInfo })
$pick = $null
if ($Name) { $pick = $voices | Where-Object { $_.Name -like "*$Name*" -or $_.Description -like "*$Name*" } | Select-Object -First 1 }
if (-not $pick -and $Strict -eq 1) { exit 3 }
if (-not $pick) { $pick = $voices | Where-Object { $_.Culture.Name -like 'es*' } | Select-Object -First 1 }
if ($pick) { $s.SelectVoice($pick.Name) }
$s.Rate = $Rate
$s.SetOutputToWaveFile($Out)
$s.Speak([System.IO.File]::ReadAllText($TextFile, [System.Text.Encoding]::UTF8))
$s.Dispose()
if ($pick) { [Console]::Out.Write($pick.Name) }
"""

_LIST_PS = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
foreach ($v in $s.GetInstalledVoices()) { if ($v.Enabled) { "{0}|{1}|{2}" -f $v.VoiceInfo.Name, $v.VoiceInfo.Culture.Name, $v.VoiceInfo.Gender } }
"""


def _powershells() -> list[tuple[str, str]]:
    """[(etiqueta, ruta)]: PowerShell de 64 bits y de 32 bits (las voces viejas solo las ve el de 32)."""
    root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    native = "Sysnative" if struct.calcsize("P") * 8 == 32 else "System32"
    found = [("64 bits", root / native / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
             ("32 bits", root / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe")]
    return [(label, str(path)) for label, path in found if path.exists()]


def _run_ps(exe: str, script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
        capture_output=True, timeout=60, creationflags=NO_WINDOW,
    )


def _windows_speak(text: str, name: str, rate: int) -> tuple[bytes, str]:
    shells = _powershells()
    if not shells:
        raise AssistantError("No encontré PowerShell para usar las voces de Windows.")
    # Con nombre: busca primero en 64 bits, luego en 32 bits (Loquendo), y si no existe usa una voz en español.
    plan = ([(exe, 1) for _l, exe in shells] + [(shells[0][1], 0)]) if name else [(shells[0][1], 0)]
    with tempfile.TemporaryDirectory(prefix="pk-voz-") as folder:
        folder = Path(folder)
        script, text_file, out = folder / "voz.ps1", folder / "texto.txt", folder / "voz.wav"
        script.write_text(_SPEAK_PS, encoding="utf-8-sig")
        text_file.write_text(text, encoding="utf-8")
        last = ""
        for exe, strict in plan:
            try:
                done = _run_ps(exe, script, "-TextFile", str(text_file), "-Out", str(out), "-Name", name,
                               "-Rate", str(max(-10, min(10, rate))), "-Strict", str(strict))
            except subprocess.TimeoutExpired:
                last = "tardó demasiado"
                continue
            if done.returncode == 3:
                continue  # esa arquitectura no tiene la voz pedida
            if done.returncode != 0 or not out.exists():
                last = done.stderr.decode("utf-8", "ignore").strip()[:150] or f"código {done.returncode}"
                continue
            return out.read_bytes(), done.stdout.decode("utf-8", "ignore").strip()
        raise AssistantError("No pude generar la voz" + (f": {last}" if last else "."))


def speak(text: str) -> tuple[bytes, str]:
    """Texto → (audio WAV, nombre de la voz usada). Solo con el motor 'windows'."""
    text = " ".join(text.split())[:MAX_SPEAK_CHARS]
    if not text:
        raise AssistantError("No hay nada que decir.")
    if tts_engine() != "windows":
        raise AssistantError("La voz de este equipo la pone el navegador (VOICE_ENGINE=browser).")
    name = perfil.get("voz") or config.VOICE_NAME  # la voz que le pediste a PK pesa más que la del .env
    speed = perfil.get("velocidad")
    rate = config.VOICE_RATE if speed is None else speed
    return _windows_speak(text, name, rate)


def list_voices() -> list[tuple[str, str, str]]:
    """[(nombre, idioma, arquitectura)] de todas las voces instaladas."""
    voices = []
    if not WINDOWS:
        return voices
    with tempfile.TemporaryDirectory(prefix="pk-voz-") as folder:
        script = Path(folder) / "lista.ps1"
        script.write_text(_LIST_PS, encoding="utf-8-sig")
        for label, exe in _powershells():
            try:
                done = _run_ps(exe, script)
            except subprocess.TimeoutExpired:
                continue
            for line in done.stdout.decode("utf-8", "ignore").splitlines():
                if "|" in line:
                    name, culture = line.strip().split("|")[:2]
                    voices.append((name, culture, label))
    return voices


_voices_cache = {"at": 0.0, "voices": []}


def windows_voices() -> list[dict]:
    """[{name, culture, gender}] de las voces de Windows (sin repetir las de 32 y 64 bits). Se recuerda 2 minutos."""
    import time
    if time.time() - _voices_cache["at"] < 120 and _voices_cache["voices"]:
        return _voices_cache["voices"]
    found: dict[str, dict] = {}
    if WINDOWS and tts_engine() == "windows":
        with tempfile.TemporaryDirectory(prefix="pk-voz-") as folder:
            script = Path(folder) / "lista.ps1"
            script.write_text(_LIST_PS, encoding="utf-8-sig")
            for _label, exe in _powershells():
                try:
                    done = _run_ps(exe, script)
                except subprocess.TimeoutExpired:
                    continue
                for line in done.stdout.decode("utf-8", "ignore").splitlines():
                    parts = line.strip().split("|")
                    if len(parts) >= 2 and parts[0] not in found:
                        found[parts[0]] = {"name": parts[0], "culture": parts[1], "gender": parts[2] if len(parts) > 2 else ""}
    voices = list(found.values())
    _voices_cache.update(at=time.time(), voices=voices)
    return voices


def installed_voices() -> list[dict]:
    """Las voces de Windows [{name, culture, gender}]."""
    return windows_voices()


if __name__ == "__main__":
    found = list_voices()
    if not found:
        print("No encontré voces de Windows en este equipo (o no estás en Windows).")
    for name, culture, label in found:
        print(f"{name}  [{culture}]  ({label})")
    print(f"\nVoz pedida en .env (VOICE_NAME): {config.VOICE_NAME or '(ninguna: se usa una voz en español)'}")
