# Instalar PK en otra computadora

Sirve para el cambio de PC o para tener una copia. Tiempo: ~30 min (casi todo es descargar).

## 1. Programas (una sola vez)
1. **Python 3.12** (python.org). Marca «Add Python to PATH».
2. **Git** (git-scm.com).
3. **Ollama** (ollama.com).
4. Un editor: **VS Code** con la extensión *Python*.

## 2. Bajar el proyecto
```powershell
cd $HOME\Documents
git clone https://github.com/TU-USUARIO/punk-thinking.git ia-personal
cd ia-personal
```
(Si el repositorio es privado, Git te pedirá iniciar sesión en GitHub en el navegador.)

## 3. Preparar Python
```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 4. Configuración y modelos
```powershell
copy .env.example .env
ollama pull gemma3:1b
ollama pull moondream
```
Edita `.env` si cambiaste algo (modelo, `WEB_BACKEND=duckduckgo`, etc.). Si la nueva PC tiene más RAM, puedes usar un modelo mayor en `OLLAMA_MODEL`.

## 5. Tus datos privados (NO están en GitHub, a propósito)
Cópialos de la PC vieja con memoria USB (o un disco externo) a la carpeta del proyecto nuevo:

| Carpeta o archivo | Qué es |
|---|---|
| `.env` | tu configuración |
| `knowledge\` | tus documentos |
| `data\memoria.json` | lo que PK sabe de ti |
| `data\perfil.json` | su nombre, voz y colores |
| `data\chats\` | tus chats |
| `espacio\` | los archivos que PK creó |

No copies `data\index`, `data\models` ni `data\whisper`: se regeneran solos.
Guarda esa copia en un lugar seguro: contiene información personal.

## 6. Reconstruir y abrir
```powershell
python ingest.py
python -m unittest discover -s tests
python crear_acceso.py
```
Debe terminar con `OK`. Luego haz doble clic en el ícono **Punk Thinking** del Escritorio.
La primera vez descarga el modelo de búsqueda (~220 MB) y, al usar la voz, el de oído (~150 MB).

## Si algo falla
- `Activate.ps1` bloqueado → `Set-ExecutionPolicy -Scope Process Bypass`.
- «No pude conectar con Ollama» → abre la aplicación Ollama.
- «llama-server not found» → reinstala Ollama con su instalador.
