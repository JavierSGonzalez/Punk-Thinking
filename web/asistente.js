// Modo asistente: hablas, PK te oye (Whisper en tu PC), piensa con el mismo cerebro del chat y te responde con voz.
// Usa las funciones de la página principal (el, api, withBody, showAnswer, refreshList).
(() => {
  const MAX_SECONDS = 30, SILENCE_MS = 1300, NO_SPEECH_MS = 8000;
  const HINT = {
    idle: "Pulsa el botón (o la barra espaciadora) y habla.",
    listening: "Te escucho… (cuando termines de hablar, PK lo nota solo)",
    thinking: "Pensando…",
    speaking: "Hablando… (pulsa para interrumpir)",
  };
  const view = $("#voice");
  const state = { mode: "idle", run: 0, chatId: null, stream: null, ctx: null, recorder: null, timer: null, audio: null,
                  audioUrl: null, status: null, active: false, backTitle: "" };

  // ---------- Estructura ----------
  const mic = el("button", "orb");
  mic.type = "button";
  mic.innerHTML = '<svg width="46" height="46" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/>' +
    '<path d="M5 11a7 7 0 0 0 14 0M12 18v4"/></svg>';
  const statusLine = el("div", "v-status");
  statusLine.setAttribute("role", "status");
  const hint = el("div", "v-hint", "🔒 Tu voz se transcribe en este computador y el audio no se guarda.");
  const voiceTag = el("div", "v-hint");

  const speakBox = el("input"); speakBox.type = "checkbox"; speakBox.checked = true;
  const loopBox = el("input"); loopBox.type = "checkbox";
  const speakLabel = el("label"); speakLabel.append(speakBox, "Responder con voz");
  const loopLabel = el("label"); loopLabel.append(loopBox, "Conversación continua");
  const fresh = el("button", null, "Nueva conversación"); fresh.type = "button";
  const opts = el("div", "v-opts"); opts.append(speakLabel, loopLabel, fresh);

  const stage = el("div", "v-stage"); stage.append(mic, statusLine, hint, voiceTag, opts);
  const vlog = el("div", "v-log"); vlog.setAttribute("role", "log"); vlog.setAttribute("aria-live", "polite");
  view.append(stage, vlog);

  const toEnd = () => vlog.scrollTo({ top: vlog.scrollHeight });
  const intro = () => {
    const note = el("p", "empty");
    note.style.marginTop = "4vh";
    note.append("Habla conmigo como con un asistente.", el("br"),
                "Puedo charlar, responder con tus documentos y buscar en la web.");
    vlog.replaceChildren(note);
  };
  intro();

  function setMode(mode, message) {
    state.mode = mode;
    mic.dataset.mode = mode;
    mic.setAttribute("aria-label", { idle: "Empezar a hablar", listening: "Terminar de hablar", thinking: "Cancelar", speaking: "Interrumpir y hablar" }[mode]);
    statusLine.classList.remove("err");
    statusLine.textContent = message || HINT[mode];
    if (mode !== "listening") mic.style.setProperty("--lvl", 0);
  }
  function fail(message) {
    setMode("idle");
    statusLine.classList.add("err");
    statusLine.textContent = message;
  }

  // ---------- Detener todo (y soltar el micrófono) ----------
  function stopMic() {
    clearInterval(state.timer); state.timer = null;
    const recorder = state.recorder; state.recorder = null;
    if (recorder && recorder.state !== "inactive") { recorder.onstop = null; try { recorder.stop(); } catch {} }
    state.stream?.getTracks().forEach((track) => track.stop()); state.stream = null;
    state.ctx?.close().catch(() => {}); state.ctx = null;
  }
  function stopSound() {
    if (state.audio) { state.audio.onended = null; state.audio.pause(); state.audio = null; }
    if (state.audioUrl) { URL.revokeObjectURL(state.audioUrl); state.audioUrl = null; }
    window.speechSynthesis?.cancel();
  }
  function cancelAll() {
    state.run++;
    stopMic(); stopSound();
    setMode("idle");
  }

  // ---------- Escuchar ----------
  async function listen() {
    cancelAll();
    const run = state.run;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) return fail("Este navegador no permite usar el micrófono.");
    if (state.status && !state.status.stt.available) return fail("Falta instalar el oído de PK: ejecuta  pip install -r requirements.txt");
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch {
      return fail("No pude usar el micrófono. Permite el acceso cuando el navegador lo pida y revisa que esté conectado.");
    }
    if (run !== state.run) { stream.getTracks().forEach((track) => track.stop()); return; }
    state.stream = stream;

    const ctx = new AudioContext();
    state.ctx = ctx;
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const samples = new Float32Array(analyser.fftSize);
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
    const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    const chunks = [];
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    state.recorder = recorder;
    recorder.start(250);
    setMode("listening");

    const began = performance.now();
    let floor = 0, floorCount = 0, heard = false, lastVoice = 0;
    const finish = () => {
      if (state.run !== run || !state.recorder || recorder.state === "inactive") return;
      clearInterval(state.timer); state.timer = null;
      recorder.onstop = () => {
        const type = recorder.mimeType || "audio/webm";
        stopMic();
        if (state.run !== run) return;
        if (!heard) return fail("No te escuché. Pulsa el botón y habla de nuevo.");
        understand(new Blob(chunks, { type }), (type.split("/")[1] || "webm").split(";")[0], run);
      };
      recorder.stop();
    };
    state.finish = finish;
    state.timer = setInterval(() => {
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (const value of samples) sum += value * value;
      const level = Math.sqrt(sum / samples.length);
      const now = performance.now();
      mic.style.setProperty("--lvl", Math.min(1, level * 8));
      if (now - began < 500) { floor = (floor * floorCount + level) / ++floorCount; return; }  // mide el ruido de fondo
      if (level > Math.max(0.015, floor * 2.5 + 0.008)) { heard = true; lastVoice = now; }
      if (heard && now - lastVoice > SILENCE_MS) finish();
      else if (!heard && now - began > NO_SPEECH_MS) finish();
      else if (now - began > MAX_SECONDS * 1000) finish();
    }, 60);
  }

  // ---------- Entender → pensar → responder ----------
  async function postJson(path, body) {
    const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    return response;
  }

  async function understand(blob, ext, run) {
    setMode("thinking", state.status?.stt.ready ? "Entendiendo lo que dijiste…" : "Preparando el oído de PK (la primera vez tarda)…");
    let text = "";
    try {
      const response = await fetch(`/api/voice/listen?ext=${encodeURIComponent(ext)}`, {
        method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: blob,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "No pude entender el audio.");
      text = (data.text || "").trim();
      if (state.status) state.status.stt.ready = true;
    } catch (error) {
      if (run === state.run) fail(error instanceof TypeError ? "No pude conectar con el servidor local." : error.message);
      return;
    }
    if (run !== state.run) return;
    if (!text) return fail("No entendí lo que dijiste. Pulsa el botón y repítelo.");
    ask(text, run);
  }

  async function ask(text, run) {
    vlog.querySelector(".empty")?.remove();
    vlog.querySelectorAll(".confirm").forEach((box) => box.replaceWith(el("div", "notice", UNCONFIRMED)));
    const mine = el("div", "msg me"), bubble = el("div", "mebox");
    bubble.append(el("p", null, text)); mine.append(bubble); vlog.append(mine);
    const row = el("div", "msg");
    const body = el("div", "body warn", "Pensando"); body.append(el("span", "dots")); row.append(body); vlog.append(row);
    toEnd();
    setMode("thinking");
    try {
      const data = await api("/api/ask", withBody("POST", { question: text, chat_id: state.chatId, attachments: [], voice: true }));
      state.chatId = data.chat_id;
      if (run !== state.run) { showAnswer(row, data, true, { chatId: state.chatId, onAnswer: onWebAnswer }); return toEnd(); }
      showAnswer(row, data, true, { chatId: state.chatId, onAnswer: onWebAnswer });
      toEnd();
      refreshList();
      say(data.spoken, run);
    } catch (error) {
      row.replaceChildren(el("div", "body err", error.message));
      if (error.status === 404) state.chatId = null;
      if (run === state.run) setMode("idle");
    }
  }

  function onWebAnswer(result) {  // la búsqueda web que esperaba tu permiso ya se confirmó
    toEnd();
    if (state.active && state.mode === "idle") say(result.spoken, state.run);
  }

  // ---------- Hablar ----------
  async function say(text, run) {
    if (!text || !speakBox.checked) return finishedSpeaking(run);
    setMode("speaking");
    if (state.status?.tts.engine === "windows") {
      try {
        const response = await postJson("/api/voice/speak", { text });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(typeof data.detail === "string" ? data.detail : "No pude generar la voz.");
        }
        const name = decodeURIComponent(response.headers.get("X-Voice") || "");
        const blob = await response.blob();
        if (run !== state.run) return;
        voiceTag.textContent = name ? `Voz: ${name}` : "";
        state.audioUrl = URL.createObjectURL(blob);
        const audio = new Audio(state.audioUrl);
        state.audio = audio;
        audio.onended = () => { stopSound(); finishedSpeaking(run); };
        audio.onerror = () => { stopSound(); fail("No pude reproducir la voz."); };
        await audio.play();
        return;
      } catch (error) {
        if (run !== state.run) return;
        voiceTag.textContent = `La voz de Windows falló (${error.message}). Uso la del navegador.`;
      }
    }
    browserSpeak(text, run);
  }

  function browserSpeak(text, run) {
    const synth = window.speechSynthesis;
    // Solo voces LOCALES en español: las voces «online» del navegador mandan el texto a un servidor de Microsoft o Google.
    const voices = synth ? synth.getVoices().filter((v) => v.localService && /^es/i.test(v.lang)) : [];
    if (!voices.length) {
      voiceTag.textContent = "Tu navegador no tiene voces locales en español: PK responde solo en pantalla.";
      return finishedSpeaking(run);
    }
    const wanted = (state.status?.tts.name || "").toLowerCase();
    const voice = voices.find((v) => wanted && v.name.toLowerCase().includes(wanted)) || voices[0];
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.voice = voice; utterance.lang = voice.lang;
    utterance.onend = () => finishedSpeaking(run);
    utterance.onerror = () => finishedSpeaking(run);
    voiceTag.textContent = `Voz: ${voice.name}`;
    synth.speak(utterance);
  }

  function finishedSpeaking(run) {
    if (run !== state.run) return;
    setMode("idle");
    if (loopBox.checked && state.active) listen();
  }

  // ---------- Entrar y salir del modo ----------
  async function enter() {
    state.active = true;
    state.backTitle = $("#title").textContent;
    document.body.dataset.view = "voice";
    $("#tab-chat").classList.remove("on"); $("#tab-chat").setAttribute("aria-pressed", "false");
    $("#tab-voice").classList.add("on"); $("#tab-voice").setAttribute("aria-pressed", "true");
    $("#title").textContent = "Asistente de voz";
    setMode("idle");
    try { state.status = await api("/api/voice/status?warm=1"); } catch { state.status = null; }
    if (state.status && !state.status.stt.available) fail("Falta instalar el oído de PK: ejecuta  pip install -r requirements.txt");
    mic.focus();
  }
  function leave() {
    if (!state.active) return;
    state.active = false;
    cancelAll();
    document.body.dataset.view = "chat";
    $("#tab-voice").classList.remove("on"); $("#tab-voice").setAttribute("aria-pressed", "false");
    $("#tab-chat").classList.add("on"); $("#tab-chat").setAttribute("aria-pressed", "true");
    $("#title").textContent = state.backTitle || "Chat nuevo";
  }

  // ---------- Controles ----------
  mic.onclick = () => {
    if (state.mode === "idle" || state.mode === "speaking") listen();
    else if (state.mode === "listening") state.finish?.();
    else cancelAll();
  };
  fresh.onclick = () => { cancelAll(); state.chatId = null; voiceTag.textContent = ""; intro(); };
  $("#tab-voice").onclick = enter;
  $("#tab-chat").onclick = leave;
  document.addEventListener("keydown", (event) => {
    if (!state.active) return;
    if (event.key === "Escape") cancelAll();
    else if (event.code === "Space" && event.target === document.body) { event.preventDefault(); mic.click(); }
  });
  // Al cambiar de ventana o pestaña, el micrófono se suelta
  document.addEventListener("visibilitychange", () => { if (document.hidden && state.mode === "listening") cancelAll(); });
  window.addEventListener("pagehide", () => { stopMic(); stopSound(); });
})();
