# Punk Thinking — tu IA personal privada

Responde preguntas **solo con lo que hay en tus documentos**, cita de dónde sacó cada dato y, si no lo sabe, lo dice en vez de inventar.

## Cómo funciona

```
Tu pregunta → busca los fragmentos más parecidos en TUS documentos (local)
            → se los entrega al motor de lenguaje con reglas estrictas
            → respuesta con citas [1] [2] + los fragmentos exactos como evidencia
```

## Estructura

```
ia-personal/
├── knowledge/        ← TUS documentos (.txt .md .pdf .docx). Lo único que la IA conoce
├── espacio/          ← los archivos que PK crea por ti (se genera solo)
├── data/             ← índice, chats y perfil.json (se genera solo)
├── core/
│   ├── config.py     ← lee el archivo .env
│   ├── documents.py  ← lee archivos y los parte en fragmentos
│   ├── embeddings.py ← convierte texto en vectores (local)
│   ├── store.py      ← guarda y busca en el índice
│   ├── llm.py        ← motor de lenguaje: Ollama (local) o Claude (API)
│   ├── rag.py        ← responder con tus documentos y sus REGLAS
│   ├── assistant.py  ← decide: charla, documentos o web (y la personalidad de PK)
│   ├── web.py        ← búsqueda web (SearXNG o DuckDuckGo)
│   ├── attachments.py← archivos y fotos adjuntos al chat (leer, analizar, recordar)
│   ├── voice.py      ← modo asistente: oír (Whisper local) y hablar (voces de Windows)
│   ├── archivos.py   ← crear y ampliar archivos de texto en espacio/ (solo ahí)
│   ├── perfil.py     ← identidad de PK: nombre, voz y colores (se guarda en data/perfil.json)
│   ├── calculadora.py← cuentas exactas («cuánto es 25 por 4», «15% de 200»), sin usar el modelo
│   ├── reloj.py      ← hora y fechas reales del PC («qué hora es», «cuántos días faltan para Navidad»)
│   ├── memoria.py    ← memoria privada: tus datos y lo que hemos trabajado (data/memoria.json)
│   └── chats.py      ← chats guardados en data/chats/
├── searxng/config/   ← configuración del buscador web privado
├── web/              ← la página: index.html (chat), asistente.js/.css (voz), memoria.js/.css (pestaña Memoria), perfil.js (nombre y colores), íconos
├── ingest.py         ← comando: leer/actualizar documentos
├── ask.py            ← comando: preguntar desde la terminal
├── server.py         ← comando: abrir la página de chat
├── iniciar_pk.pyw    ← doble clic: enciende PK, lo abre como app y lo apaga al cerrar
├── crear_acceso.py   ← crea el ícono «Punk Thinking» en el Escritorio (una sola vez)
├── .env.example      ← plantilla de configuración
└── requirements.txt  ← librerías de Python
```

## Lo que necesitas instalar (extras)

1. **Python 3.12** (python.org). En Windows marca «Add Python to PATH».
2. **Visual Studio Code** con la extensión *Python*. (Con Visual Studio 2022: instala la carga de trabajo «Desarrollo de Python», abre la carpeta con *Archivo → Abrir → Carpeta* y usa su terminal.)
3. **Un motor de lenguaje**, uno de estos:
   - **Ollama** (ollama.com): local, gratis y 100 % privado. Es el valor por defecto.
   - **Clave de API de Anthropic** (console.anthropic.com): mejor calidad, requiere saldo y envía la pregunta y los fragmentos encontrados a Anthropic.

## Paso a paso

**1. Abre la carpeta** `ia-personal` en VS Code (*Archivo → Abrir carpeta*) y abre la terminal (*Ver → Terminal*).

**2. Crea el entorno virtual** (una «caja» aislada para las librerías):

```powershell
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```
```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

**3. Instala las librerías:** `pip install -r requirements.txt`

**4. Crea tu configuración:** copia `.env.example` como `.env` (`copy .env.example .env` en Windows, `cp` en macOS/Linux).

**5. Prepara el motor de lenguaje.**
- Ollama: instálalo, ábrelo y ejecuta `ollama pull gemma3:4b`.
- Claude: en `.env` pon `LLM_PROVIDER=anthropic` y pega tu `ANTHROPIC_API_KEY`.

**6. Agrega tus documentos** a `knowledge/`. Puedes borrar `bienvenida.md` cuando pongas los tuyos.

**7. Indexa:** `python ingest.py`. La primera vez descarga el modelo de búsqueda (~220 MB, solo una vez).

**8. Prueba por terminal:** `python ask.py "¿Cómo se actualiza esta IA?"`

**9. Abre la página:** `python server.py` y entra a http://127.0.0.1:8000

**10. Para actualizar:** cambia, agrega o borra archivos en `knowledge/` y ejecuta otra vez `python ingest.py`. Solo procesa lo que cambió. Si tienes el servidor abierto, toma el índice nuevo solo.

## Abrir PK como una app (doble clic)

Sin terminal y sin que nada arranque con Windows: **solo consume recursos mientras lo usas.**

1. Una sola vez, con el entorno activo: `python crear_acceso.py`. Crea el ícono **Punk Thinking** en tu Escritorio.
2. Haz **doble clic** en el ícono. PK enciende Ollama (si no estaba abierto) y su servidor, y se abre en su propia ventana (Edge o Chrome, con un perfil aparte, sin pestañas ni barra de direcciones).
3. **Cierra la ventana** y PK apaga lo que él encendió. Si Ollama ya estaba abierto antes, lo deja como estaba.

- Todo sigue en tu computador (127.0.0.1); no hay nada publicado en internet.
- Si algo falla, sale un aviso y el detalle queda en `data/pk.log`.
- Si el servidor ya estaba encendido con `python server.py`, el ícono solo abre la ventana y no lo apaga.
- La primera vez tarda unos segundos en abrirse la ventana.

## Modo asistente (hablar con PK)

Pestaña **Asistente**, arriba a la derecha. Pulsa el círculo (o la **barra espaciadora**) y habla: PK nota cuando terminas, te transcribe, piensa igual que en el chat (charla, tus documentos, web con tu permiso) y **te responde con voz**. `Esc` cancela; el micrófono solo está abierto mientras escuchas.

- **Oído (voz → texto):** Whisper corre **en tu PC** (`faster-whisper`). El audio se borra al instante y nunca sale. La primera vez descarga el modelo (~145 MB, una sola vez; necesita internet). Se elige con `WHISPER_MODEL` (`tiny`, `base`, `small`).
- **Voz (texto → audio):** usa las voces instaladas en tu Windows. En voz alta PK dice una versión corta (sin citas ni enlaces); lo demás queda en pantalla. Si Windows falla, usa solo voces **locales** del navegador (las «online» mandarían el texto a Microsoft o Google, por eso no se usan).
- **Opciones en pantalla:** *Responder con voz* (apagado = solo pantalla) y *Conversación continua* (PK te vuelve a escuchar al terminar de hablar).
- Las conversaciones quedan guardadas como chats llamados «Voz: …».

**Elegir la voz.** Para ver qué voces tiene tu PC: `python -m core.voice`. Luego pon en `.env` una parte del nombre, por ejemplo `VOICE_NAME=Helena`. La voz **Loquendo** es un producto comercial con licencia y **este proyecto no la incluye**: si ya la tienes instalada en tu PC, aparece en esa lista (las voces antiguas son de 32 bits y PK también las busca ahí) y `VOICE_NAME=Loquendo` (o el nombre de la voz, p. ej. `Jorge`) la activa.

## Crear y modificar archivos (carpeta espacio/)

PK puede crear y ampliar archivos de texto, **solo dentro de la carpeta `espacio/`** de tu proyecto (se crea sola la primera vez). Funciona en el **chat** y en el **modo asistente**.

| Dile algo como… | Qué pasa |
|---|---|
| «Crea un bloc de notas que contenga los nombres de los continentes, llama al archivo mundo» | Crea `espacio/mundo.txt` con ese contenido y te lo muestra |
| «Al archivo mundo agrégale el nombre de 5 países por cada continente» | Añade al final de `mundo.txt` (el modelo ve lo que ya tiene el archivo) |
| «Muéstrame el archivo mundo» · «¿Qué archivos tengo?» | Muestra su contenido · lista los archivos de `espacio/` |
| «Reemplaza el contenido del archivo mundo por una lista de ríos» | Cambia todo el contenido (guarda antes la versión anterior) |
| «Cambia el nombre del archivo mundo a continentes» · «Renombra el archivo mundo a continentes» | Le cambia el nombre (no pisa a otro archivo) |
| «Crea un archivo con esa información» · «un resumen de eso» | Usa **tu respuesta anterior** de PK como material (si no pides resumir o traducir, la copia tal cual) |
| «Deshaz el último cambio del archivo mundo» | Lo devuelve a como estaba antes del último «agregar» o «reemplazar» |
| «Cambia el nombre del archivo a …» (sin decir cuál) | Se refiere al **último archivo del que hablaron** en esa charla |
| «Crea un archivo markdown / csv / json llamado …» | Crea `.md`, `.csv` (se abre bien en Excel) o `.json` |

- **Formatos:** `.txt` (bloc de notas, el predeterminado), `.md`, `.csv` y `.json`. Sin decir nombre, PK lo llama `nota-FECHA`. Si el nombre tiene espacios, pónlo entre comillas: *crea un archivo "mi lista de tareas"…*
- **Seguridad:** solo escribe dentro de `espacio/` (nombres con rutas, `..`, símbolos o extensiones raras se rechazan). **Nunca borra**. «Crear» se niega si el archivo ya existe. Solo «agregar» y «reemplazar el contenido» cambian un archivo, y antes guardan la versión anterior en `espacio/.versiones/` (se recupera con «deshaz…»). Renombrar no se deshace con «deshaz»: se vuelve a renombrar. **Nunca ejecuta** lo que crea. Solo se interpreta lo que **tú** escribes o dices: una orden escondida en un documento, un adjunto o la web nunca crea ni cambia archivos.
- **Límites reales:** el contenido lo redacta el modelo local (`gemma3:1b` es pequeño): sirve para lo que tú le dictas o para listas sencillas, pero **puede equivocarse (por ejemplo, con datos de países) y hay que revisarlo**. Cada archivo llega hasta 200 KB. JSON no se amplía (podría romperse; sí se puede reemplazar). Si pides PDF, Word o Excel, PK te avisa que por ahora solo hace texto y lo guarda como `.txt`. Si el modelo se pierde y suelta texto vacío o repetido, PK **no guarda nada** y te lo dice. Para quitar un archivo, bórralo tú de la carpeta.
- Más adelante, cuando decidas darle acceso a todo tu PC, ese será un cambio aparte y se te consultará antes.

## Calculadora y hora real

PK resuelve **con código** (no con el modelo, que se equivoca con las cuentas) las operaciones y la hora. Funciona igual en el chat y en el modo asistente.

- **Cuentas:** `cuánto es 25 por 4`, `15% de 200`, `100 más el 15%`, `qué porcentaje es 30 de 200`, `raíz de 144`, `2 elevado a 10`, `5!`, `(3+5)*2`, `cinco más tres`, `dos mil quinientos más trescientos`. Si dices otra cosa («tengo 5 más 3 manzanas»), no la toma como cuenta y sigue el camino normal.
- **Hora y fechas:** `qué hora es`, `qué hora es en Tokio`, `qué día es hoy`, `qué día cae el 25 de diciembre`, `cuántos días faltan para Navidad`, `cuántos días han pasado desde el 1 de enero`, `qué fecha será dentro de 30 días`. Usa el reloj de tu PC en la zona `America/El_Salvador` (se cambia con `TIMEZONE` en `.env`). Además, el modelo recibe la fecha de hoy para no inventar el año.
- En Windows hace falta el paquete `tzdata` (está en `requirements.txt`): `pip install -r requirements.txt`.
- Nada de esto usa internet.

## Memoria privada (pestaña «Memoria»)

PK guarda **solo en tu PC** (`data/memoria.json`) dos cosas:

- **Datos sobre ti:** cuando dices `recuerda que mi examen es el viernes`, o solo si dejas activado el guardado automático y lo dices claro (`me llamo…`, `vivo en…`, `estudio…`, `mi comida favorita es…`, `mi perro se llama…`). **Siempre te avisa** al final de la respuesta: «Guardé en tu memoria: …».
- **Lo que hemos trabajado:** un resumen corto de cada pregunta y respuesta. Así, en **cualquier chat**, puedes preguntar `¿qué hicimos con el archivo mundo?` o `¿en qué hemos trabajado?`. Se busca por palabras clave, sin inventar: si no encuentra nada, lo dice.

Preguntas que entiende: `cómo me llamo`, `dónde vivo`, `qué sabes de mí`, `cuál es mi color favorito`. Para olvidar: `olvida que vivo en…`, `olvida todo` (pide confirmación), `olvida lo que hemos trabajado`, `desactiva la memoria` / `activa la memoria`.

La pestaña **Memoria** te deja ver todo, **corregir o borrar dato por dato**, agregar datos, apagar cada función, **descargar** tu memoria (`mi-memoria-pk.json`) y **olvidar todo** (con confirmación). Borrar un chat no borra lo recordado: se borra ahí.

**Reglas:** nunca guarda contraseñas, claves, tarjetas ni documentos de identidad; solo aprende de lo que tú escribes o dices (no de tus archivos ni de la web); y tus datos **nunca** entran en una búsqueda web.

## Cambiar la identidad de PK hablándole (nombre, voz, colores)

En el **chat** o en el **modo asistente** puedes decirle cómo quieres que sea, y **se guarda** en `data/perfil.json` hasta que pidas otro cambio (sobrevive a cerrar y abrir PK). Se aplica al instante, sin recargar.

| Dile algo como… | Qué cambia |
|---|---|
| «Cambia tu nombre a Jarvis» · «Tu nombre es Punk Thinking» | Su nombre: título, encabezado y cómo se presenta |
| «Usa la voz Sabina» · «Quiero la voz femenina» | La voz con la que habla (solo entre las **instaladas** en tu Windows) |
| «Habla más rápido» · «Habla más lento» | La velocidad de la voz |
| «Cambia tu interfaz a un celeste claro» | Fondo y botones del mismo tono (claro u oscuro, con texto legible) |
| «Cambia el color de los botones a rosa» · «Pon el fondo azul oscuro» | Solo los botones/detalles · solo el fondo (también sirve un código como `#12ab34`) |
| «Modo claro» · «Modo oscuro» | El aspecto claro u oscuro original |
| «Deshaz el último cambio» · «Restablece todo» (o «los colores», «la voz», «el nombre») | Vuelve atrás |
| «¿Cuál es tu configuración?» | Te dice cómo está, sin cambiar nada |

Se pueden mezclar en una frase: *«Quiero que tengas la voz masculina (Jorge), y cambia tu interfaz a un celeste claro»*.

- **Si la voz no existe en tu PC** (por ejemplo Jorge o Esperanza sin instalar), PK **no la cambia** y te lo dice, con la lista de voces que sí tiene. Para ver las instaladas: `python -m core.voice`. PK no puede crear voces: solo usa las de Windows.
- **Seguridad:** solo se interpreta **lo que tú escribes o dices** en la conversación. Una orden escondida en un documento, un archivo adjunto o una página web **nunca** se ejecuta (y en el mensaje en que subes un archivo, nada se interpreta como orden). Los cambios son solo de apariencia e identidad: no tocan tus archivos, y siempre se deshacen. Los valores del archivo se vuelven a validar al leerlos.
- Si borras `data/perfil.json`, PK vuelve a como venía de fábrica.

## Cómo decide PK qué responder

−1. **Memoria, cuentas y hora** (junto con los ajustes, antes que el modelo): `recuerda que…`, `olvida…`, `qué hicimos con…`, `cuánto es 25 por 4`, `qué hora es` se resuelven con código. Etiquetas *Memoria* y *Cálculo / hora*.
0. **Ajuste** (primero de todo): si lo que escribiste es una orden de cambiar su nombre, voz o colores, la aplica y lo confirma. Etiqueta *Ajuste guardado*.
1. **Charla** (hola, gracias, perdón, bromas, «¿cómo te llamas?»): conversa de forma natural. Los saludos y las preguntas sobre PK se reconocen al instante, sin consultar al modelo. Etiqueta *Conversación*. (Si adjuntas un archivo con el mensaje, nunca se trata como charla.)
2. **Pregunta**: primero busca en el **archivo que adjuntaste** (si hay) y en tus documentos guardados. Tus documentos guardados solo se usan si **tratan del tema** (comparten palabras con la pregunta o se parecen mucho); así una pregunta ajena, como «biografía de Sonic», ya no se contesta con un PDF sin relación. Si responden, contesta con citas. Etiqueta *Tu archivo* o *Tus documentos*.
3. Si ninguno responde, **busca en la web** y lo avisa con «Se buscó en la web: …» y enlaces. Etiqueta *Web*. Si la pregunta tiene que ver con tu archivo, la consulta usa **el tema** del archivo (se quitan correos y números largos) y la página lo indica: «usando el tema de tu archivo».
   - **Con permiso:** si esa consulta lleva palabras tomadas de tu archivo que tú no escribiste, PK **no busca sola**. Etiqueta *Falta tu permiso*: te muestra la consulta, qué palabras vienen del archivo, y puedes **editarla** y pulsar *Buscar en la web*, o *No buscar*. Hasta que decidas, no sale nada de tu computador. Se controla con `WEB_CONFIRM_FILE_QUERY` (por defecto `on`).
4. Si tampoco hay web, dice «No tengo esa información». Etiqueta *Sin respaldo*.

**Consultas web:** si tu pregunta es corta y clara, PK la busca tal cual la escribiste (el modelo pequeño a veces deformaba la consulta). Si DuckDuckGo falla, reintenta una vez.

PK recuerda los últimos mensajes **del chat abierto** (`HISTORY_MESSAGES` en `.env`), así entiende «¿y el segundo?». Un chat nuevo empieza sin recuerdos.

## Adjuntar archivos y fotos al chat

Tres formas de adjuntar, todas en la página de chat: el **clip 📎**, **arrastrar** el archivo a cualquier parte de la página, o **pegar** una captura con `Ctrl + V`. Hasta 4 archivos por mensaje, de 15 MB cada uno. Puedes enviar solo el archivo, sin escribir nada: PK pregunta «¿de qué trata?» por ti, y el chat se titula «Archivo: nombre».

| Tipo | Formatos | Cómo se analiza |
|---|---|---|
| Documentos | PDF, DOCX, TXT, MD, CSV | Se lee el texto en tu PC |
| Fotos | PNG, JPG, WEBP, GIF, BMP | Un **modelo de visión de Ollama** las describe y transcribe su texto |

**Cómo los usa PK:**
- El archivo queda «a mano» en ese chat: puedes seguir preguntando por él en mensajes siguientes («¿y el total?»). Una pregunta que no tiene nada que ver con él se responde sin tocarlo.
- Para archivos largos, PK usa los fragmentos que mejor responden tu pregunta. Con «resume el documento» o «¿de qué trata?» toma una **muestra repartida de principio a fin** y avisa que el resumen es parcial.
- Si el archivo no responde, busca en la web (ver arriba). Si preguntas «busca en internet sobre lo que sale en la foto», usa el tema del archivo para armar la búsqueda.
- **Se guardan solo para ese chat.** No se agregan a `knowledge/` ni a tu índice permanente. De cada archivo se conserva su texto y, si es foto, una miniatura reducida; **el original no se guarda**. Al borrar el chat se borran sus archivos. Los que subiste pero nunca enviaste se borran solos a las 24 horas (al encender el servidor).

**PK no identifica personas por su cara.** Si adjuntas la foto de alguien y preguntas «¿quién es?», PK lo dice, describe lo que se ve y te invita a decirle quién crees que es. Si respondes «es Fulano», busca información sobre Fulano en la web (aclarando que no puede confirmar que sea la persona de tu foto).

**Para que PK vea fotos necesitas un modelo de visión** (el de texto `gemma3:1b` no ve imágenes). Se configura con `VISION_MODEL` en `.env` y se descarga una vez:

```powershell
ollama pull moondream
```

| Modelo | Tamaño | Para qué |
|---|---|---|
| `moondream` (por defecto) | 1,7 GB | El más liviano; describe escenas. Es débil leyendo texto y a veces responde en inglés |
| `qwen2.5vl:3b` | 3,2 GB | Pensado para documentos, tablas y gráficos |
| `gemma3:4b` | 3,4 GB | Uso general; multilingüe |

El modelo de visión solo se usa al subir una foto y se descarga de la memoria a los 30 segundos para dejar sitio al de texto. **La descripción de una foto es automática y puede equivocarse** (sobre todo con cifras y texto): PK la presenta como «lo que se ve según el análisis» y la página la marca como *análisis automático*. Para datos importantes, verifica contra la foto.

**PDF escaneados** (solo imágenes, sin texto): súbelos como foto (PNG o JPG), no como PDF.

## Búsqueda web con SearXNG (Docker)

SearXNG es un buscador que corre **en tu computador** y consulta varios buscadores sin cuenta ni cookies. PK solo le manda una consulta corta de pocas palabras.

**Requisitos de Docker Desktop (Windows):** Windows 10 22H2 o Windows 11, 8 GB de RAM como mínimo y virtualización activada en la BIOS. Si tu PC no cumple, usa el plan B (más abajo).

1. Instala **Docker Desktop** (docker.com), reinicia el PC, ábrelo y espera a que diga *Engine running*.
2. Genera tu clave propia:
   ```powershell
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Copia el resultado y pégalo en `searxng/config/settings.yml`, reemplazando `CAMBIA-ESTO-POR-TU-CLAVE`.
3. Desde la carpeta del proyecto, enciende SearXNG (una sola línea):
   ```powershell
   docker run --name searxng -d --restart unless-stopped -p 127.0.0.1:8888:8080 -v "${PWD}\searxng\config:/etc/searxng" -v "${PWD}\searxng\data:/var/cache/searxng" docker.io/searxng/searxng:latest
   ```
   `127.0.0.1` hace que solo tu computador pueda usarlo.
4. Comprueba que funciona: abre http://127.0.0.1:8888/search?q=prueba&format=json en el navegador. Debe mostrar texto JSON con resultados.
   - Si dice **403**, falta `json` en `search.formats` de `settings.yml`; corrígelo y ejecuta `docker restart searxng`.
   - Si no abre, mira el motivo con `docker logs searxng`.
5. En tu `.env` deja: `WEB_SEARCH=on` y `WEB_BACKEND=searxng`.

Para liberar RAM cuando no lo uses: `docker stop searxng`. Para encenderlo: `docker start searxng`. Si no quieres que arranque solo con Docker: `docker update --restart=no searxng`.

**Plan B sin Docker:** en `.env` pon `WEB_BACKEND=duckduckgo` y ejecuta `pip install -r requirements.txt`. DuckDuckGo ve la consulta, y su librería no es oficial, así que puede fallar de vez en cuando.

**Apagar la web:** `WEB_SEARCH=off`.

## Privacidad: qué se queda y qué sale

| Parte | Dónde ocurre |
|---|---|
| Tus documentos y el índice | Solo en tu computador (`knowledge/`, `data/`) |
| Búsqueda de fragmentos | Local. El modelo se descarga una vez (es público) y luego funciona sin internet |
| Redacción con **Ollama** | Local: nada sale de tu equipo |
| Redacción con **Claude (API)** | La pregunta y los 5 fragmentos encontrados viajan a Anthropic; los documentos completos, nunca |
| Servidor web | Solo acepta tu propio computador (127.0.0.1) |
| Chats guardados | Solo en tu computador (`data/chats/`) |
| Identidad de PK (nombre, voz, colores) | Solo en tu computador (`data/perfil.json`) |
| Archivos que PK crea | Se guardan solo en tu computador (`espacio/`). Con **Ollama** nada sale. **Con Claude (API)** viaja a Anthropic tu pedido y, al ampliar, el texto que ya tiene ese archivo |
| **Archivos y fotos adjuntos** | Se leen y se guardan solo en tu computador (`data/attachments/`: texto y miniatura, nunca el original). Las fotos las analiza **tu modelo de Ollama**: nada sale. **Con Claude (API) las fotos sí viajan a Anthropic** para que las describa |
| **Memoria privada** | `data/memoria.json`, solo en tu PC. Con **Ollama** nada sale. Con **Claude (API)**, los datos tuyos relevantes y lo que PK conteste con ellos viajarían a Anthropic junto con tu pregunta (la pestaña Memoria te lo avisa). Nunca van a la búsqueda web |
| **Búsqueda web** | Sale **una consulta corta** (nunca el texto de tus documentos, tus archivos ni tu historial). SearXNG la reenvía a buscadores externos con tu IP, sin cuenta ni cookies; ellos ven la consulta. Una VPN oculta tu IP. Se apaga con `WEB_SEARCH=off` |
| Búsqueda web **sobre un archivo** | La consulta corta se arma con el **tema** del archivo; se le quitan correos y números de 7 o más cifras, pero **un nombre o una palabra del archivo sí puede quedar**. Por eso, si lleva palabras de tu archivo, PK te la muestra y **espera tu OK** (puedes editarla). Con `WEB_CONFIRM_FILE_QUERY=off` busca sola y no hay garantía de que no salga alguna palabra. Si prefieres que el archivo no influya, pon `WEB_USE_FILE_CONTEXT=off` |

`.gitignore` evita que `.env`, `knowledge/` y `data/` se suban si algún día usas Git.

## Problemas comunes

- **PowerShell bloquea `Activate.ps1`:** ejecuta `Set-ExecutionPolicy -Scope Process Bypass` y vuelve a activar (solo vale para esa terminal).
- **«No pude conectar con Ollama»:** abre la aplicación Ollama y repite.
- **«El modelo no está descargado»:** ejecuta el `ollama pull` que indica el mensaje.
- **Un PDF no aporta nada:** si `ingest.py` dice «SIN TEXTO», es un escaneo; necesita OCR (se puede agregar como mejora). Para un PDF escaneado adjunto al chat, súbelo como foto.
- **Al subir una foto dice «El modelo 'moondream' no está descargado»:** ejecuta `ollama pull moondream` (o el modelo que pusiste en `VISION_MODEL`).
- **Dice «no puede analizar imágenes»:** el modelo de `VISION_MODEL` no tiene visión. Usa `moondream`, `qwen2.5vl:3b` o `gemma3:4b`.
- **Subir una foto tarda mucho:** es normal en equipos sin tarjeta gráfica. Mientras analiza, el archivo muestra «analizando la foto…». Un modelo más liviano acelera.
- **La IA lee mal el texto de una foto:** `moondream` es débil con texto. Prueba `qwen2.5vl:3b` si tu RAM lo permite, o sube el documento original en PDF o DOCX.
- **Sale «Falta tu permiso» y solo quería que buscara:** es el aviso de privacidad; pulsa *Buscar en la web*. Si prefieres que busque sola, pon `WEB_CONFIRM_FILE_QUERY=off` en `.env`.
- **Doble clic y no pasa nada / sale un aviso:** abre `data/pk.log`. Lo más común es que el puerto 8000 lo use otro programa (cambia `PORT` en `.env`; el ícono lo toma solo).
- **El modo asistente dice «Falta instalar el oído de PK»:** ejecuta `pip install -r requirements.txt` con el entorno activo.
- **La primera frase tarda mucho:** está descargando y cargando el modelo de oído (una sola vez). Si va lento siempre, usa `WHISPER_MODEL=tiny`; si entiende mal, `small`.
- **No me escucha / «No pude usar el micrófono»:** permite el micrófono cuando la ventana lo pida y revisa en Windows (*Configuración → Privacidad → Micrófono*) que esté permitido.
- **No suena la voz que pedí:** ejecuta `python -m core.voice` para ver los nombres exactos que Windows tiene y ajusta `VOICE_NAME`.
- **«Uno de los archivos adjuntos ya no existe»:** se borró (por ejemplo, tras 24 horas sin enviarlo). Vuelve a subirlo.
- **Responde «no tengo esa información» y sí está:** baja `MIN_SCORE` en `.env` o revisa `data/index/meta.json` para ver cómo se partió el documento.
- **El modelo local inventa o ignora las citas:** usa un modelo más grande en `OLLAMA_MODEL` o cambia a Claude.
- **Cambiaste `EMBED_MODEL`:** ejecuta `python ingest.py --todo`.

## Mejoras posibles (nada de esto está construido; se consulta antes)

Respuesta escribiéndose en vivo · OCR para PDFs escaneados · búsqueda híbrida (palabras clave + significado) · más formatos (Excel, PowerPoint, páginas web) · pruebas automáticas · contraseña de acceso.
