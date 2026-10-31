# PK — Plan de actualizaciones y modelo de trabajo

Estado: 28 de octubre de 2026. Basado en tu lista de Notion («Lista de misiones para progresar → Tareas secundarias»).

## 1. Modelo de trabajo (así se hace cada actualización)

| Paso | Qué pasa | Quién |
|---|---|---|
| 1. Idea | La anotas en Notion con un nombre. Si falla algo, lo llamas «error N»; si es una mejora, «actualización …». | Tú |
| 2. Consulta | Te hago las preguntas que cambian lo que construyo (máximo 3). Todo lo que no pediste lo propongo y **espera tu sí**. | Claude → tú |
| 3. Plan corto | Qué cambia, qué archivos toca, qué sale o no sale de tu PC, y qué puede fallar. | Claude |
| 4. Construcción | Por módulos pequeños. Lo que se puede decidir con reglas claras se hace con código, no con el modelo de 1B. | Claude |
| 5. Pruebas | Automáticas (las hago yo) + una lista corta de pruebas que haces tú en tu PC, porque yo no tengo tu Ollama, tu micrófono ni tus voces. | Claude + tú |
| 6. Entrega | Un solo mensaje con todos los archivos y una tabla «carpeta · nuevo / reemplaza». | Claude |
| 7. Registro | README, este plan y la memoria del proyecto se actualizan. | Claude |
| 8. Tu veredicto | «Funciona» cierra la actualización. «Error N» abre una corrección con su número. | Tú |

**Cierre de cada actualización:** las pruebas anteriores siguen pasando (no se rompe lo que ya funcionaba), la privacidad está explicada en el README y tú la probaste en tu PC.

## 2. Reglas que no cambian

- **Privado:** lo que PK sabe de ti o le preguntas no se entrega a ninguna compañía. Con Ollama no sale nada; a internet sale solo una consulta corta de búsqueda, que ves en pantalla.
- **Sin límites de preguntas, sin esperar ni pagar.** Por eso se descartó Venice AI.
- **Sin romper reglas de terceros** (condiciones de uso de WhatsApp, Instagram, etc.).
- **Liviano:** tu PC tiene 4 GB de RAM. Nada de modelos extra si una regla de código lo resuelve.
- **Se enciende con doble clic** y se apaga al cerrar la ventana.
- **Archivos solo en `espacio/`** hasta que decidas dar más acceso (se te consulta antes).
- **Programable desde Visual Studio / VS Code** (Python, HTML, JS). Si hace falta algo extra, te aviso.

## 3. Mapa: tu lista de Notion → actualizaciones

| En Notion | Actualización | Estado |
|---|---|---|
| (pedido el 28 oct) | **Herramientas y memoria**: calculadora, hora real, memoria privada + pestaña «Memoria» | **Integrada** (30 oct): chat, modo voz y pestaña Memoria. Pendiente: tu prueba en tu PC |
| Actualización de voz | Voz propia de PK (Loquendo / personajes) | En pausa. Notas en `actualizacion-de-voz.md` |
| Inteligencia | Respuestas más acertadas y razonadas | Por definir contigo (§5) |
| Sección de resúmenes, mensajes y tareas pendientes | Asistente: pendientes, fechas, resúmenes «mientras no estabas», conexión a apps | Plan por fases (§6) |

## 4. Herramientas y memoria

**Calculadora** (`core/calculadora.py`). Cuentas exactas hechas con código: `cuánto es 25 por 4`, `15% de 200`, `100 más el 15%`, `raíz de 144`, `2 elevado a 10`, `5!`, `cinco más tres` (también para el modo voz). No usa `eval`. Si el texto trae palabras de más («tengo 5 más 3 manzanas»), no responde y la pregunta sigue su camino normal. Formato: `1,234.5`.

**Hora y fechas reales** (`core/reloj.py`). Usa el reloj de tu PC con la zona `America/El_Salvador` (se cambia con `TIMEZONE` en `.env`). Responde hora, fecha, hora en otras ciudades, «qué día cae el 25 de diciembre», «cuántos días faltan para Navidad», «qué fecha será dentro de 30 días». Además, la fecha de hoy se le da al modelo para que no invente el año.

**Memoria privada** (`core/memoria.py`, archivo `data/memoria.json`):
- **Datos sobre ti:** los guarda cuando dices «recuerda que…» o, con el guardado automático encendido, cuando lo dices con frases claras («me llamo…», «vivo en…», «mi comida favorita es…»). Cada vez que guarda algo solo, te lo avisa en la respuesta.
- **Lo que hemos trabajado:** resumen corto de cada tema, para responder en **cualquier chat** «¿qué hicimos con el archivo mundo?». Se responde con búsqueda por palabras clave (no con el modelo), así que si no encuentra nada lo dice, no inventa.
- **Olvidar:** «olvida que vivo en…», «olvida todo» (pide confirmación), o desde la pestaña **Memoria**, donde puedes ver, corregir, borrar uno por uno, apagar el guardado automático y usar el botón «Olvidar todo».
- **Nunca guarda:** contraseñas, claves, tarjetas ni documentos de identidad. Tampoco aprende de documentos, fotos adjuntas ni páginas web: solo de lo que tú escribes o dices.

## 5. Inteligencia (por definir)

Con `gemma3:1b` y 4 GB de RAM hay un techo real: un modelo así no razona como una persona, por mucho prompt que se le ponga. Opciones, de menos a más cambio:

1. **Más reglas de código** para lo que tiene respuesta exacta (como se hizo con cuentas, hora y archivos). Es lo que más sube la fiabilidad por costo.
2. **Verificar antes de responder:** que cada afirmación salga de un fragmento citado, y si no, decir «no lo sé». Ya existe en parte; se puede endurecer.
3. **Razonar por pasos** (dividir una pregunta en subpreguntas) — más lento, ayuda poco en un modelo de 1B.
4. **Más RAM (16 GB) y modelo de 4B+.** Es el único cambio que sube de verdad la comprensión. Se comprueba con el comando de RAM que ya te pasé.

## 6. Resúmenes, mensajes y pendientes (por fases)

Los hallazgos de abajo salen de la documentación oficial (enlaces al final). Lo que no pude confirmar lo digo.

**Fase A — Pendientes y fechas propios (sin conectar nada, 100 % local).** Pestaña «Tareas»: «recuérdame entregar X el viernes», lista con fechas, y al abrir PK un resumen de qué vence hoy y esta semana. Usa el reloj y la memoria de esta actualización.

**Fase B — Notion.** Tiene API oficial: una *integración interna* con token que tú creas, y solo ve las páginas que le compartas («Add connections»). Sirve para leer tu «Lista de misiones». Solo lectura. Hay también tokens de acceso personal; no pude confirmar sus permisos por defecto.

**Fase C — Microsoft Teams.** Graph permite leer chats con el permiso delegado `Chat.Read`, y la referencia indica que **no exige consentimiento de administrador**. Pero: (1) solo cuentas de trabajo o escuela; las cuentas personales de Microsoft **no están soportadas**; (2) hay que registrar una app en Microsoft Entra, y no sé si la política de tu centro lo permite. Hay que comprobarlo con tu cuenta antes de prometer nada.

**Fase D — WhatsApp.** Aquí hay un problema real. Las condiciones de WhatsApp prohíben acceder al servicio «through automated or other means» sin autorización, hacer ingeniería inversa y crear software que funcione como el servicio, y pueden suspender la cuenta. Las librerías no oficiales que «leen» tu WhatsApp caen en eso, y tu regla es no romper reglas. No pude leer la documentación de la Cloud API (pedía iniciar sesión), así que no afirmo qué permite. **Camino dentro de las reglas:** WhatsApp tiene la función oficial «Exportar chat»; tú exportas el chat y lo sueltas en PK, que lo resume y saca tareas y fechas. Es manual, pero legal y 100 % local.

**Fase E — Instagram.** Su API de mensajería es para **cuentas profesionales** (mensajes entre un negocio y sus clientes); la página no menciona cuentas personales y no pude confirmar que no sirvan. Se investiga cuando llegue su turno; probablemente también sea «importar un archivo».

**Fase F — Calendario.** Lo más simple y privado: importar un `.ics` exportado de tu calendario. Conectarse a Google/Outlook por API es posible pero requiere cuenta y permisos; se decide después.

**Lo que esto implica**
- **Los mensajes son datos de otras personas.** Deben quedarse en tu PC, nunca ir a la búsqueda web, y solo procesarse con Ollama (con Anthropic como motor saldrían). PK lo bloquearía en ese modo.
- **«Qué pasó en mi ausencia» no puede ser en vivo:** PK solo corre cuando lo abres (tu regla de no gastar recursos). Lo realista es que **al abrir PK busque lo nuevo desde la última vez** y te resuma.
- **Resumir con un modelo de 1B es flojo.** Los resúmenes se harán por partes y siempre mostrando el mensaje original como evidencia.

## 7. Decisiones que necesito de ti

1. ¿Empezamos por la **Fase A** (pendientes y fechas, local) antes de conectar apps? (Recomendado.)
2. De las apps, ¿cuál te importa más primero: **Notion, Teams o WhatsApp por exportación**?
3. ¿Tu cuenta de Teams es de tu colegio/universidad? Eso decide si la Fase C es posible.
4. **Inteligencia:** ¿quieres ir por más reglas de código (opción 1–2) o primero resolver la RAM?
5. Calculadora: puedo añadir IVA (13 %), descuentos y conversión de unidades. Son extras y no los puse sin tu permiso.

## Fuentes

- Notion, autorización: <https://developers.notion.com/docs/authorization>
- Microsoft Graph, listar mensajes de un chat: <https://learn.microsoft.com/en-us/graph/api/chat-list-messages>
- Permiso `Chat.Read`: <https://graphpermissions.merill.net/permission/Chat.Read>
- Instagram, API de mensajería: <https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api>
- WhatsApp, condiciones de servicio: <https://www.whatsapp.com/legal/terms-of-service>
- WhatsApp, exportar chat (título confirmado, contenido no leído): <https://faq.whatsapp.com/1180414079177245>
