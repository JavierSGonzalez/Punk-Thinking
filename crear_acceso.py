"""Crea el ícono «Punk Thinking» en tu Escritorio. Se ejecuta UNA vez:   python crear_acceso.py

El ícono abre PK con doble clic (iniciar_pk.pyw), sin terminal. Para quitarlo, bórralo del Escritorio.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("Este paso es solo para Windows.")
    pythonw = Path(sys.executable).with_name("pythonw.exe")  # el Python de tu .venv, sin ventana de terminal
    if not pythonw.exists():
        raise SystemExit(f"No encontré {pythonw}. Activa el entorno (.venv) y repite.")
    script = f"""
$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path $desktop 'Punk Thinking.lnk'))
$link.TargetPath = '{pythonw}'
$link.Arguments = '"{ROOT / "iniciar_pk.pyw"}"'
$link.WorkingDirectory = '{ROOT}'
$link.IconLocation = '{ROOT / "web" / "favicon.ico"}'
$link.Description = 'Punk Thinking - tu IA personal privada'
$link.Save()
Write-Output (Join-Path $desktop 'Punk Thinking.lnk')
"""
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit("No pude crear el ícono:\n" + result.stderr.strip())
    print("Listo. Ícono creado en:", result.stdout.strip())
    print("Haz doble clic en «Punk Thinking» en tu Escritorio. Al cerrar su ventana, PK se apaga.")


if __name__ == "__main__":
    main()
