// Pestaña «Memoria»: ver, corregir y olvidar lo que PK sabe de ti. Todo vive en data/memoria.json, en tu PC.
// Usa las funciones de la página principal (el, api, withBody). Escribe siempre con textContent, nunca con innerHTML.
(() => {
  const view = $("#memoria");
  const tab = $("#tab-memoria");
  const state = { active: false, backTitle: "", data: null, editing: null, asking: null };

  const when = (iso) => {
    try {
      return new Date(iso).toLocaleString("es", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    } catch { return ""; }
  };
  const button = (label, cls, onclick, title) => {
    const b = el("button", cls, label);
    b.type = "button";
    if (title) { b.title = title; b.setAttribute("aria-label", title); }
    b.onclick = onclick;
    return b;
  };
  let msgNode = null;
  const say = (text, isError) => {
    if (!msgNode) return;
    msgNode.textContent = text || "";
    msgNode.classList.toggle("err", Boolean(isError));
  };

  async function load() {
    try {
      state.data = await api("/api/memoria");
      draw();
    } catch (error) {
      view.replaceChildren(el("div", "m-wrap", error.message));
    }
  }
  async function run(call, okText) {
    try { await call(); await load(); say(okText || ""); }
    catch (error) { say(error.message, true); }
  }

  function toggles() {
    const box = el("div", "m-box");
    box.append(el("h2", null, "Qué guarda PK"));
    const group = el("div", "m-toggles");
    const options = [
      ["hechos_auto", "Guardar datos míos cuando los digo", "Por ejemplo «me llamo…» o «vivo en…». Siempre te avisa al guardar."],
      ["historial", "Recordar lo que trabajamos", "Un resumen corto de cada pregunta y respuesta, para poder decirte «eso lo hicimos ayer» en cualquier chat."],
      ["usar", "Usar mi memoria al conversar", "Si lo apagas, PK conserva lo guardado pero no lo usa para responder."],
    ];
    for (const [key, label, help] of options) {
      const row = el("label");
      const box2 = el("input");
      box2.type = "checkbox";
      box2.checked = Boolean(state.data.config[key]);
      box2.onchange = () => run(() => api("/api/memoria/ajustes", withBody("PUT", { [key]: box2.checked })), "Guardado.");
      const text = el("span", null, label);
      text.append(el("small", null, help));
      row.append(box2, text);
      group.append(row);
    }
    box.append(group);
    return box;
  }

  function factsBox() {
    const box = el("div", "m-box");
    box.append(el("h2", null, `Datos sobre ti (${state.data.hechos.length})`));
    box.append(el("p", "m-sub", "Puedes corregirlos o borrarlos uno por uno."));
    const list = el("ul", "m-list");
    if (!state.data.hechos.length) list.append(el("li", "m-none", "Todavía no sé nada tuyo."));
    for (const fact of state.data.hechos) {
      const item = el("li");
      if (state.editing === fact.id) {
        const field = el("input", "m-edit");
        field.value = fact.texto; field.maxLength = 200; field.setAttribute("aria-label", "Corregir este dato");
        const save = () => run(() => api(`/api/memoria/hechos/${fact.id}`, withBody("PATCH", { texto: field.value })).then(() => { state.editing = null; }), "Dato corregido.");
        field.addEventListener("keydown", (event) => {
          if (event.key === "Enter") save();
          if (event.key === "Escape") { state.editing = null; draw(); }
        });
        item.append(field, button("Guardar", "m-ico", save), button("Cancelar", "m-ico", () => { state.editing = null; draw(); }));
        list.append(item);
        setTimeout(() => field.focus());
        continue;
      }
      const text = el("span", "m-text", fact.texto);
      const origin = { auto: "guardado solo", pedido: "me lo pediste", manual: "escrito aquí" }[fact.origen] || "";
      text.append(el("span", "m-meta", `${when(fact.actualizado || fact.creado)}${origin ? " · " + origin : ""}`));
      item.append(text,
        button("✎", "m-ico", () => { state.editing = fact.id; draw(); }, "Corregir este dato"),
        button("×", "m-ico", () => run(() => api(`/api/memoria/hechos/${fact.id}`, { method: "DELETE" }), "Dato olvidado."), "Olvidar este dato"));
      list.append(item);
    }
    box.append(list);
    const add = el("form", "m-add");
    const field = el("input");
    field.placeholder = "Algo que quieres que recuerde… (Enter lo guarda)"; field.maxLength = 200;
    field.setAttribute("aria-label", "Agregar un dato");
    add.append(field, button("Agregar", "btn small", () => add.requestSubmit()));
    add.onsubmit = (event) => {
      event.preventDefault();
      if (field.value.trim().length < 2) return;
      run(() => api("/api/memoria/hechos", withBody("POST", { texto: field.value })), "Guardado.");
    };
    box.append(add);
    return box;
  }

  function historyBox() {
    const box = el("div", "m-box");
    box.append(el("h2", null, `Lo que hemos trabajado (${state.data.episodios.length})`));
    box.append(el("p", "m-sub", "Se recuerda en cualquier chat. Borrar un chat no borra esto; se borra aquí."));
    const list = el("ul", "m-list");
    if (!state.data.episodios.length) list.append(el("li", "m-none", "Aún no hay recuerdos de conversaciones."));
    for (const episode of state.data.episodios.slice(0, 40)) {
      const item = el("li");
      const text = el("span", "m-text", episode.pregunta);
      text.append(el("span", "m-meta", `${when(episode.ts)} · ${episode.respuesta}`));
      item.append(text, button("×", "m-ico", () => run(() => api(`/api/memoria/episodios/${episode.id}`, { method: "DELETE" }), "Recuerdo borrado."), "Borrar este recuerdo"));
      list.append(item);
    }
    box.append(list);
    if (state.data.episodios.length > 40) box.append(el("p", "m-sub", `Se muestran los 40 más recientes de ${state.data.episodios.length}.`));
    return box;
  }

  function forgetBox() {
    const box = el("div", "m-box");
    box.append(el("h2", null, "Olvidar"));
    const hechos = state.data.hechos.length, episodios = state.data.episodios.length;
    if (state.asking) {
      const all = state.asking === "todo";
      const sure = el("div", "m-confirm");
      sure.setAttribute("role", "alertdialog");
      sure.append(el("span", null, all
        ? `¿Seguro? Se borran ${hechos} datos y ${episodios} recuerdos. No se puede deshacer.`
        : `¿Seguro? Se borran ${episodios} recuerdos de lo trabajado (tus datos se quedan). No se puede deshacer.`));
      sure.append(
        button(all ? "Sí, olvidar todo" : "Sí, borrar historial", "btn small m-danger", () =>
          run(() => api(`/api/memoria?confirmar=si${all ? "" : "&solo_historial=true"}`, { method: "DELETE" }).then(() => { state.asking = null; }),
              all ? "Listo: PK olvidó todo." : "Listo: historial borrado.")),
        button("Cancelar", "btn small ghost", () => { state.asking = null; draw(); }));
      box.append(sure);
    } else {
      const actions = el("div", "m-actions");
      actions.append(
        button("Olvidar todo mi información", "btn small m-danger", () => { state.asking = "todo"; draw(); }),
        button("Borrar solo lo trabajado", "btn small ghost", () => { state.asking = "historial"; draw(); }),
        Object.assign(el("a", "btn small ghost", "Descargar mi memoria"), { href: "/api/memoria/exportar", download: "mi-memoria-pk.json" }));
      box.append(actions);
    }
    return box;
  }

  function draw() {
    const wrap = el("div", "m-wrap");
    const where = state.data.local
      ? "🔒 Todo esto vive solo en tu computador (data/memoria.json). No se envía a ninguna compañía ni a la búsqueda web."
      : "⚠️ Tu motor es la nube (Anthropic): lo que PK use de tu memoria para responder viajaría allí junto con tu pregunta. Con Ollama no sale nada.";
    wrap.append(el("p", state.data.local ? "m-intro" : "m-intro warn", where),
      el("p", "m-intro", "PK nunca guarda contraseñas, claves, tarjetas ni documentos de identidad, y solo aprende de lo que tú escribes o dices (no de tus archivos ni de la web)."));
    msgNode = el("div", "m-msg");
    msgNode.setAttribute("role", "status");
    wrap.append(toggles(), factsBox(), historyBox(), forgetBox(), msgNode);
    view.replaceChildren(wrap);
  }

  function setTabs(on) {
    document.body.dataset.view = on ? "memoria" : "chat";
    tab.classList.toggle("on", on); tab.setAttribute("aria-pressed", String(on));
  }
  function enter() {
    if (state.active) return;
    state.active = true;
    state.backTitle = $("#title").textContent;
    $("#tab-chat").classList.remove("on"); $("#tab-chat").setAttribute("aria-pressed", "false");
    setTabs(true);
    $("#title").textContent = "Memoria";
    state.editing = null; state.asking = null;
    load();
  }
  function leave() {
    if (!state.active) return;
    state.active = false;
    tab.classList.remove("on"); tab.setAttribute("aria-pressed", "false");
    document.body.dataset.view = "chat";
    $("#tab-chat").classList.add("on"); $("#tab-chat").setAttribute("aria-pressed", "true");
    $("#title").textContent = state.backTitle || "Chat nuevo";
  }

  tab.onclick = enter;
  // En la fase de captura: se sale de Memoria ANTES de que Chat o Asistente hagan lo suyo
  $("#tab-chat").addEventListener("click", leave, true);
  $("#tab-voice").addEventListener("click", leave, true);
  $("#side").addEventListener("click", leave, true);   // abrir un chat o crear uno también te saca de Memoria
})();
