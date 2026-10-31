/* Aplica al instante los cambios de nombre y colores que le pides a PK (por chat o por voz).
   La página ya llega con el perfil puesto (lo hace el servidor); esto solo la actualiza cuando cambia. */
(function () {
  function apply(perfil) {
    if (!perfil) return;
    const style = document.getElementById("perfil-vars");
    if (style) {
      const pairs = Object.entries(perfil.vars || {}).map(([key, value]) => `${key}:${value};`).join("");
      style.textContent = pairs ? `:root{${pairs}}` : "";
    }
    if (perfil.nombre) {
      const name = document.getElementById("name");
      if (name) name.textContent = perfil.nombre;
      document.title = perfil.nombre;
    }
  }
  window.aplicarPerfil = apply;

  const original = window.fetch.bind(window);
  window.fetch = async function (...args) {
    const response = await original(...args);
    try {
      const url = typeof args[0] === "string" ? args[0] : args[0].url;
      if (/\/api\/(ask|web)(\?|$)/.test(url)) {
        response.clone().json().then((data) => data && data.perfil && apply(data.perfil)).catch(() => {});
      }
    } catch (error) { /* nunca debe romper la página */ }
    return response;
  };
})();
