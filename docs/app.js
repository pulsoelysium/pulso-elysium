const L = 'es-AR';
const n0 = (v) => Number(v).toLocaleString(L, {maximumFractionDigits: 0});
const n1 = (v) => Number(v).toLocaleString(L, {minimumFractionDigits: 1, maximumFractionDigits: 1});
const F = {
  usd: (v) => '$' + n0(v),
  usdM: (v) => (Math.abs(v) >= 1e6 ? '$' + n1(v / 1e6) + ' M' : Math.abs(v) >= 1e3 ? '$' + n0(v / 1e3) + ' mil' : '$' + n0(v)),
  num: (v) => n0(v),
  hype: (v) => n0(v) + ' HYPE',
  pct: (v) => n1(v) + ' %',
  spct: (v) => (v > 0 ? '+' : '') + n1(v) + ' %',
  day: (v) => String(v).slice(8, 10) + '/' + String(v).slice(5, 7),
  text: (v) => String(v),
};
F.pct0 = (v) => n0(v) + ' %';
const C = (i) => dash.colors[i % dash.colors.length];

// Un valor suelto: lee su fuente, campo y formato de los atributos del propio elemento.
dash.draw('val', (el) => {
  const g = dash.data(el.dataset.source);
  const row = g.status === 'ok' ? g.data[+(el.dataset.row || 0)] : null;
  const v = row ? row[el.dataset.field] : null;
  if (v === null || v === undefined) { el.textContent = '—'; el.style.color = ''; return; }
  el.textContent = (F[el.dataset.fmt] || F.text)(v);
  if (el.dataset.good === 'up') el.style.color = v >= 0 ? 'var(--color-ok)' : 'var(--color-bad)';
});

function fail(el, g) {
  el.replaceChildren();
  el.textContent = g.status === 'error' ? 'No se pudo cargar' : '—';
}

function frame(el, aria, fmt, ymax, H) {
  el.replaceChildren();
  const W = Math.max(el.clientWidth || 600, 260);
  const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`)
    .attr('role', 'img').attr('aria-label', aria);
  const y = d3.scaleLinear().domain([0, ymax || 1]).nice(4).range([H - 26, 10]);
  const ticks = y.ticks(4);
  const probe = svg.append('text').attr('class', 'pe-tick');
  const ml = d3.max(ticks, (t) => probe.text(fmt(t)).node().getComputedTextLength()) + 10;
  probe.remove();
  svg.append('g').selectAll('line').data(ticks).join('line')
    .attr('x1', ml).attr('x2', W).attr('y1', y).attr('y2', y).style('stroke', 'var(--cds-chart-grid)');
  svg.append('g').selectAll('text').data(ticks).join('text').attr('class', 'pe-tick')
    .attr('x', ml - 6).attr('y', y).attr('dy', '0.32em').attr('text-anchor', 'end').text((t) => fmt(t));
  const tip = d3.select(el).append('div').attr('class', 'pe-tip').attr('hidden', true);
  const show = (px, lines) => {
    tip.attr('hidden', null).selectAll('div').data(lines).join('div').text((d) => d);
    const w = tip.node().offsetWidth;
    tip.style('left', Math.min(Math.max(px - w / 2, 0), el.clientWidth - w) + 'px');
  };
  return {svg, W, H, ml, y, show, hide: () => tip.attr('hidden', true)};
}

function xLabels(f, days, pos, step) {
  const every = Math.max(1, Math.ceil(44 / step));
  f.svg.append('g').selectAll('text').data(days.filter((d, i) => (days.length - 1 - i) % every === 0)).join('text')
    .attr('class', 'pe-tick').attr('x', pos).attr('y', f.H - 8).attr('text-anchor', 'middle').text((d) => F.day(d));
}

function bars(el, field, fmt, tickFmt, aria) {
  const g = dash.data('diario');
  if (g.status !== 'ok') return fail(el, g);
  const rows = g.data;
  const f = frame(el, aria, tickFmt, d3.max(rows, (r) => +r[field]), 230);
  const x = d3.scaleBand().domain(rows.map((r) => r.dia)).range([f.ml, f.W - 2]).padding(0.25);
  f.svg.append('g').selectAll('rect').data(rows).join('rect')
    .attr('x', (r) => x(r.dia)).attr('width', x.bandwidth())
    .attr('y', (r) => f.y(+r[field])).attr('height', (r) => f.y(0) - f.y(+r[field])).attr('rx', 2)
    .style('fill', (r) => (r.parcial ? 'var(--cds-chart-muted)' : C(0)))
    .on('pointerenter pointermove click', (ev, r) =>
      f.show(x(r.dia) + x.bandwidth() / 2, [F.day(r.dia) + (r.parcial ? ' (día en curso)' : ''), fmt(+r[field])]))
    .on('pointerleave', f.hide);
  xLabels(f, rows.map((r) => r.dia), (d) => x(d) + x.bandwidth() / 2, x.step());
}

dash.draw('chart-ingresos', (el) => bars(el, 'ingresos_usd', F.usd, F.usdM, 'Ingresos diarios del secuenciador en dólares'));
dash.draw('chart-retiros', (el) => bars(el, 'retiros_hype', F.hype, F.num, 'HYPE retirado por día hacia HyperEVM'));

dash.draw('chart-capital', (el) => {
  const g = dash.data('diario');
  if (g.status !== 'ok') return fail(el, g);
  const rows = g.data;
  const series = [['usdc_en_red', 'USDC en la red'], ['tvl_usd', 'TVL en protocolos']];
  const ok = (r, k) => r[k] !== null && r[k] !== undefined && r[k] !== '';
  const f = frame(el, 'USDC en la red y TVL en protocolos, por día, en dólares', F.usdM,
    d3.max(rows, (r) => d3.max(series, (s) => (ok(r, s[0]) ? +r[s[0]] : 0))), 230);
  const x = d3.scalePoint().domain(rows.map((r) => r.dia)).range([f.ml + 22, f.W - 24]);
  series.forEach((s, i) => {
    f.svg.append('path').attr('fill', 'none').style('stroke', C(i)).attr('stroke-width', 2)
      .attr('d', d3.line().defined((r) => ok(r, s[0])).x((r) => x(r.dia)).y((r) => f.y(+r[s[0]]))(rows));
  });
  const rule = f.svg.append('line').attr('y1', 10).attr('y2', f.H - 26).style('stroke', 'var(--cds-chart-axis)').attr('hidden', true);
  f.svg.append('rect').attr('x', f.ml).attr('width', f.W - f.ml).attr('height', f.H).attr('fill', 'transparent')
    .on('pointerenter pointermove click', (ev) => {
      const px = d3.pointer(ev)[0];
      const r = rows[d3.leastIndex(rows, (a, b) => Math.abs(x(a.dia) - px) - Math.abs(x(b.dia) - px))];
      rule.attr('hidden', null).attr('x1', x(r.dia)).attr('x2', x(r.dia));
      f.show(x(r.dia), [F.day(r.dia) + (r.parcial ? ' (día en curso)' : '')]
        .concat(series.map((s) => s[1] + ': ' + (ok(r, s[0]) ? F.usdM(+r[s[0]]) : 'sin dato'))));
    })
    .on('pointerleave', () => { rule.attr('hidden', true); f.hide(); });
  xLabels(f, rows.map((r) => r.dia), (d) => x(d), x.step());
});

// Barra de capital: parte en protocolos contra parte ociosa.
dash.draw('split', (el) => {
  const g = dash.data('resumen');
  el.replaceChildren();
  if (g.status !== 'ok' || !g.data.length) return;
  const p = Math.max(0, Math.min(100, +g.data[0].pct_en_protocolos));
  const a = document.createElement('div');
  a.style.width = p + '%';
  a.style.background = C(0);
  el.append(a);
});

function body(name, id, cols) {
  dash.draw(name, (tb) => {
    const g = dash.data(id);
    tb.replaceChildren();
    if (g.status !== 'ok') return;
    g.data.forEach((r) => {
      const tr = tb.insertRow();
      cols.forEach(([k, fmt]) => {
        const td = tr.insertCell();
        td.textContent = (F[fmt] || F.text)(r[k]);
        if (fmt !== 'text') td.className = 'pe-num';
        if (k === 'estado') td.className = 'pe-st pe-st-' + (r[k] === 'riesgo' ? 'bad' : r[k] === 'ok' ? 'ok' : 'info');
      });
    });
  });
}
body('reparto-body', 'reparto', [['destino', 'text'], ['porcentaje', 'pct0'], ['hype', 'num'], ['usd', 'usd']]);
body('rollup-body', 'rollup', [['aspecto', 'text'], ['valor', 'text'], ['estado', 'text'], ['lectura', 'text']]);

dash.onData(() => {
  document.querySelectorAll('.pe-sw').forEach((e) => { if (e.dataset.c !== undefined) e.style.background = C(+e.dataset.c || 0); });
});
