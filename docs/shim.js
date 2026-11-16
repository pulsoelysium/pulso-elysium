// Reemplazo minimo del entorno del tablero para la pagina publica:
// carga los JSON de data/ y vuelve a dibujar cuando llegan o cambia el ancho.
(function () {
  const ids = ['diario', 'resumen', 'reparto', 'rollup'];
  const store = {}, draws = {}, watchers = [];
  ids.forEach((id) => { store[id] = {status: 'loading', data: []}; });
  function render() {
    watchers.forEach((fn) => { try { fn(); } catch (e) { console.error(e); } });
    document.querySelectorAll('[data-draw]').forEach((el) => {
      const fn = draws[el.dataset.draw];
      if (fn) { try { fn(el); } catch (e) { console.error(el.dataset.draw, e); } }
    });
  }
  let timer = null;
  window.dash = {
    colors: ['var(--c0)', 'var(--c1)'],
    data: (id) => store[id] || {status: 'missing', data: []},
    draw: (name, fn) => { if (fn) draws[name] = fn; else render(); },
    onData: (fn) => watchers.push(fn),
    start: () => {
      render();
      ids.forEach((id) => {
        fetch((document.documentElement.dataset.base || '') + 'data/' + id + '.json', {cache: 'no-store'})
          .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
          .then((j) => { store[id] = {status: 'ok', data: j.rows || []}; })
          .catch(() => { store[id] = {status: 'error', data: []}; })
          .then(render);
      });
      window.addEventListener('resize', () => { clearTimeout(timer); timer = setTimeout(render, 150); });
    },
  };
})();
