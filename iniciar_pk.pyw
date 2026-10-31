"""Abre Punk Thinking como una app: doble clic y listo (sin terminal).

Qué hace, en orden:
  1. Si Ollama no está encendido, lo enciende (solo si lo usas y está en este computador).
  2. Enciende el servidor de PK (si no estaba encendido).
  3. Abre PK en su propia ventana (Edge o Chrome, con un perfil aparte de tu navegador).
  4. Cuando CIERRAS esa ventana, apaga lo que él encendió: así no consume recursos cuando no lo usas.

Todo corre en tu computador (127.0.0.1). Si algo falla, avisa con una ventana y deja el detalle en data/pk.log.
La extensión .pyw hace que Windows lo ejecute sin ventana de terminal.
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from core import config  # noqa: E402  (lee tu .env)

WINDOWS = os.name == "nt"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
URL = f"http://127.0.0.1:{config.PORT}/"
LOG = ROOT / "data" / "pk.log"
PROFILE = ROOT / "data" / "navegador"  # perfil propio de la ventana de PK: no toca tu navegador de siempre
WAIT_SERVER = 120  # segundos máximos esperando que el servidor responda


def notify(text: str) -> None:
    """Sin terminal no hay dónde escribir: los avisos salen en una ventana de Windows."""
    if WINDOWS:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, "Punk Thinking", 0x40)
    else:
        print(text, file=sys.stderr)


def is_up(url: str, expect: str = "") -> bool:
    try:  # sin proxy: es una conexión a tu propio computador
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=1.5) as response:
            return response.status == 200 and expect in response.read(2000).decode("utf-8", "ignore")
    except Exception:
        return False


def log_file():
    LOG.parent.mkdir(exist_ok=True)
    if LOG.exists() and LOG.stat().st_size > 1_000_000:
        LOG.write_text("", encoding="utf-8")  # que no crezca sin límite
    handle = open(LOG, "a", encoding="utf-8", errors="replace")
    handle.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    handle.flush()
    return handle


def stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    if WINDOWS:  # /T: también sus procesos hijos (Ollama lanza trabajadores aparte)
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
    else:
        process.terminate()
        try:
            process.wait(5)
        except subprocess.TimeoutExpired:
            process.kill()


def start_ollama(log) -> subprocess.Popen | None:
    """Enciende Ollama solo si PK lo usa, apunta a este computador y no está ya encendido."""
    if config.LLM_PROVIDER != "ollama":
        return None
    host = urlparse(config.OLLAMA_URL).hostname
    if host not in {"127.0.0.1", "localhost"} or is_up(config.OLLAMA_URL):
        return None
    exe = shutil.which("ollama")
    if not exe and WINDOWS:
        local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        exe = str(local) if local.exists() else None
    if not exe:
        return None  # si no está instalado, PK lo explicará al hacer la primera pregunta
    return subprocess.Popen([exe, "serve"], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=NO_WINDOW)


def start_server(log) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(ROOT / "server.py")], cwd=ROOT,
        stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=NO_WINDOW,
    )


def browser_command() -> list[str] | None:
    """Edge (viene con Windows) o Chrome, en modo «app»: ventana sin pestañas ni barra de direcciones."""
    override = os.environ.get("PK_BROWSER")  # solo para pruebas
    if override:
        return override.replace("{url}", URL).split()
    names = [
        r"Microsoft\Edge\Application\msedge.exe",
        r"Google\Chrome\Application\chrome.exe",
    ]
    bases = [os.environ.get(v, "") for v in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
    for name in names:
        for base in bases:
            path = Path(base) / name
            if base and path.exists():
                return [
                    str(path), f"--app={URL}", f"--user-data-dir={PROFILE}", "--no-first-run",
                    "--no-default-browser-check", "--disable-background-mode", "--window-size=1200,800",
                ]
    return None


def main() -> None:
    owned_server = owned_ollama = None
    log = log_file()
    try:
        command = browser_command()
        if command is None:
            notify("No encontré Microsoft Edge ni Google Chrome para abrir la ventana de PK.\n"
                   f"Puedes encender PK con «python server.py» y abrir {URL} en tu navegador.")
            return
        if not is_up(URL + "api/status", config.APP_NAME):
            owned_ollama = start_ollama(log)
            owned_server = start_server(log)
            started = time.time()
            while not is_up(URL + "api/status", config.APP_NAME):
                if owned_server.poll() is not None or time.time() - started > WAIT_SERVER:
                    notify("Punk Thinking no pudo encenderse.\n\n"
                           f"El detalle quedó en:\n{LOG}\n\n"
                           "Causa frecuente: el puerto ya está ocupado por otro programa.")
                    return
                time.sleep(0.4)
        started_window = time.time()
        browser = subprocess.Popen(command, cwd=ROOT)
        while browser.poll() is None:  # espera a que cierres la ventana de PK
            if owned_server is not None and owned_server.poll() is not None:
                notify(f"El servidor de Punk Thinking se detuvo.\nEl detalle quedó en:\n{LOG}")
                stop(browser)
                return
            time.sleep(1)
        if owned_server is not None and time.time() - started_window < 5:
            notify("La ventana de PK se cerró enseguida y no pude abrirla.\n"
                   f"Puedes abrir {URL} en tu navegador; PK ya se apagó.")
    finally:
        stop(owned_server)  # lo que este programa encendió, lo apaga; lo que ya estaba encendido, lo deja
        stop(owned_ollama)
        log.close()


if __name__ == "__main__":
    main()
