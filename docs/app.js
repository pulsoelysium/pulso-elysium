/* Pulso Elysium: dibuja el tablero a partir de los JSON de data/. */
(function () {
  'use strict';
  const root = document.documentElement;
  const ES = root.lang === 'es';
  const BASE = root.dataset.base || '';
  const LOC = ES ? 'es-AR' : 'en-US';
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const MES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  const NF = {};
  const nf = (d) => (NF[d] = NF[d] || new Intl.NumberFormat(LOC, {minimumFractionDigits: d, maximumFractionDigits: d}));
  const pctSign = ES ? ' %' : '%';

  const F = {
    num: (v) => nf(0).format(v),
    usd: (v) => '$' + nf(0).format(v),
    usdC: (v) => {
      const a = Math.abs(v);
      if (a >= 1e6) return '$' + nf(1).format(v / 1e6) + (ES ? ' M' : 'M');
      if (a >= 1e3) return '$' + nf(a >= 1e4 ? 0 : 1).format(v / 1e3) + (ES ? ' mil' : 'K');
      return '$' + nf(0).format(v);
    },
    hype: (v) => nf(0).format(v) + ' HYPE',
    numC: (v) => {
      const a = Math.abs(v);
      if (a >= 1e6) return nf(1).format(v / 1e6) + (ES ? ' M' : 'M');
      if (a >= 1e3) return nf(a >= 1e4 ? 0 : 1).format(v / 1e3) + (ES ? ' mil' : 'K');
      return nf(0).format(v);
    },
    pct: (v) => nf(1).format(v) + pctSign,
    pct0: (v) => nf(0).format(v) + pctSign,
    day: (s) => (ES ? +s.slice(8, 10) + '/' + +s.slice(5, 7) : MON[+s.slice(5, 7) - 1] + ' ' + +s.slice(8, 10)),
    dayLong: (s) => (ES ? +s.slice(8, 10) + ' de ' + MES[+s.slice(5, 7) - 1] : MON[+s.slice(5, 7) - 1] + ' ' + +s.slice(8, 10)),
    hourUtc: (s) => s.slice(11, 16) + ' UTC',
    text: (v) => String(v),
  };
  const trim = (s) => s.replace(/[.,]0(\s?(?:M|K|mil))$/, '$1');
  F.usdT = (v) => trim(F.usdC(v));
  F.numT = (v) => trim(F.numC(v));

  const T = ES
    ? {
        partial: 'día en curso', noData: 'sin dato', peak: 'Máximo', launch: 'Mainnet pública',
        usdc: 'USDC en la red', tvl: 'TVL en protocolos', bridge: 'HYPE en el bridge', withdrawn: 'HYPE retirado',
        revenue: 'Ingresos del secuenciador', live: 'Actualizado', late: 'Última actualización',
        failed: 'No se pudieron cargar los datos. Probá recargar la página en unos minutos.',
        fewPoints: 'La serie horaria arrancó el 16 de noviembre; todavía hay pocos puntos para dibujarla.',
        risk: 'Riesgo', ok: 'Bien', info: 'Dato',
      }
    : {
        partial: 'day in progress', noData: 'no data', peak: 'Peak', launch: 'Public mainnet',
        usdc: 'USDC on Elysium', tvl: 'TVL in protocols', bridge: 'HYPE held by the bridge', withdrawn: 'HYPE withdrawn',
        revenue: 'Sequencer revenue', live: 'Updated', late: 'Last update',
        failed: 'The data could not be loaded. Try reloading the page in a few minutes.',
        fewPoints: 'The hourly series started on Nov 16; there are not enough points to draw it yet.',
        risk: 'Risk', ok: 'Good', info: 'Info',
      };

  // Textos que vienen en español dentro de los datos.
  const EN = {
    'Recompra y quema de KNTQ': 'KNTQ buyback and burn', 'Builders': 'Builders', 'Tesorería de Kinetiq': 'Kinetiq treasury',
    'Validadores': 'Validators', 'Validación abierta a cualquiera': 'Validation open to anyone',
    'Período de desafío de retiros (bloques de HyperEVM)': 'Withdrawal challenge period (HyperEVM blocks)',
    'Rollup en pausa': 'Rollup paused', 'Lotes publicados en HyperEVM': 'Batches posted to HyperEVM', 'Sí': 'Yes', 'No': 'No',
  };
  const tr = (v) => (ES || EN[v] === undefined ? String(v) : EN[v]);

  const $ = (s, n) => (n || document).querySelector(s);
  const $$ = (s, n) => Array.from((n || document).querySelectorAll(s));
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function el(tag, attrs, kids) {
    const n = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => (k === 'text' ? (n.textContent = v) : n.setAttribute(k, v)));
    (kids || []).forEach((k) => n.append(k));
    return n;
  }
  const strong = (txt) => el('strong', {class: 'num', translate: 'no', text: txt});
  function rich(node, parts) {
    node.replaceChildren(...parts.map((p) => (typeof p === 'string' ? document.createTextNode(p) : strong(p.v))));
  }

  // ------------------------------------------------------------------ gráficos
  function measure(svg, labels) {
    const t = svg.append('text').attr('class', 'tick');
    const w = d3.max(labels, (s) => t.text(s).node().getComputedTextLength()) || 0;
    t.remove();
    return w;
  }

  function roundedTop(x, y, w, h, r) {
    if (h <= 0) return '';
    r = Math.min(r, w / 2, h);
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
  }

  /*
   * opts: rows, key (campo de x), series [{k, name, color}], type 'bar' | 'line',
   * xLabel(row), tipTitle(row), yFmt, vFmt, height, area, time, annotate {x, text}, peak, draw
   */
  function chart(box, opts) {
    const rows = opts.rows;
    box.replaceChildren();
    const W = Math.max(box.clientWidth || 600, 280);
    const H = opts.height || 220;
    const svg = d3.select(box).append('svg').attr('width', '100%').attr('height', H)
      .attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', opts.aria).attr('translate', 'no');
    const val = (r, s) => (r[s.k] === null || r[s.k] === undefined || r[s.k] === '' ? null : +r[s.k]);
    const ymax = d3.max(rows, (r) => d3.max(opts.series, (s) => val(r, s))) || 1;
    const y = d3.scaleLinear().domain([opts.yMin || 0, ymax]).nice(4).range([H - 30, 14]);
    const ticks = y.ticks(4);
    const ml = measure(svg, ticks.map(opts.yFmt)) + 12;
    const mr = opts.mr || 8;

    let x, xs, step;
    if (opts.time) {
      x = d3.scaleUtc().domain(d3.extent(rows, (r) => new Date(r.ts * 1000))).range([ml + 6, W - mr - 6]);
      xs = (r) => x(new Date(r.ts * 1000));
    } else if (opts.type === 'bar') {
      x = d3.scaleBand().domain(rows.map((r) => r[opts.key])).range([ml, W - mr]).padding(0.28);
      xs = (r) => x(r[opts.key]) + x.bandwidth() / 2;
      step = x.step();
    } else {
      x = d3.scalePoint().domain(rows.map((r) => r[opts.key])).range([ml + 10, W - mr - 10]);
      xs = (r) => x(r[opts.key]);
      step = x.step();
    }

    // grilla
    svg.append('g').selectAll('line').data(ticks).join('line')
      .attr('x1', ml).attr('x2', W - mr).attr('y1', (t) => Math.round(y(t)) + 0.5).attr('y2', (t) => Math.round(y(t)) + 0.5)
      .style('stroke', (t) => (t === y.domain()[0] ? '#2a3f5e' : 'var(--grid)'));
    svg.append('g').selectAll('text').data(ticks).join('text').attr('class', 'tick')
      .attr('x', ml - 10).attr('y', (t) => y(t)).attr('dy', '0.32em').attr('text-anchor', 'end').text(opts.yFmt);

    // etiquetas del eje x, sin superposición: se saltean las que no entran
    let xl;
    if (opts.time) {
      const fmt = (d) => (ES ? d.getUTCDate() + '/' + (d.getUTCMonth() + 1) : MON[d.getUTCMonth()] + ' ' + d.getUTCDate()) + ' ' + String(d.getUTCHours()).padStart(2, '0') + ':00';
      const lw = measure(svg, [fmt(new Date(Date.UTC(2026, 10, 30, 23)))]) + 24;
      const n = Math.max(2, Math.floor((W - ml - mr) / lw));
      xl = x.ticks(n).map((d) => ({x: x(d), t: fmt(d)}));
      while (xl.length > 1 && xl.length * lw > W - ml - mr) xl = xl.filter((d, i) => i % 2 === 0);
    } else {
      const labels = rows.map(opts.xLabel);
      const lw = measure(svg, labels) + 14;
      const every = Math.max(1, Math.ceil(lw / step));
      xl = rows.map((r, i) => ({x: xs(r), t: labels[i], keep: (rows.length - 1 - i) % every === 0})).filter((d) => d.keep);
    }
    svg.append('g').selectAll('text').data(xl).join('text').attr('class', 'tick')
      .attr('x', (d) => d.x).attr('y', H - 8).attr('text-anchor', 'middle').text((d) => d.t);

    // anotación vertical (por ejemplo, el lanzamiento de la mainnet pública)
    if (opts.annotate && !opts.time && x.domain().includes(opts.annotate.x)) {
      const ax = opts.type === 'bar' ? x(opts.annotate.x) - (x.step() - x.bandwidth()) / 2 : xs({[opts.key]: opts.annotate.x});
      svg.append('line').attr('x1', ax).attr('x2', ax).attr('y1', 4).attr('y2', H - 30)
        .style('stroke', '#3a5274').attr('stroke-dasharray', '3 4');
      const at = svg.append('text').attr('class', 'anno').attr('y', 10).attr('x', ax + 6).text(opts.annotate.text);
      if (ax + 6 + at.node().getComputedTextLength() > W - mr) at.attr('x', ax - 6).attr('text-anchor', 'end');
    }

    // marcas
    const s0 = opts.series[0];
    if (opts.type === 'bar') {
      svg.append('g').selectAll('path').data(rows).join('path')
        .attr('d', (r) => {
          const v = val(r, s0) || 0;
          return roundedTop(x(r[opts.key]), y(v), x.bandwidth(), y(0) - y(v), 4);
        })
        .style('fill', (r) => (r.parcial ? '#34486a' : s0.color));
    } else {
      opts.series.forEach((s, i) => {
        const def = (r) => val(r, s) !== null;
        if (opts.area && i === 0) {
          const gid = 'g' + Math.random().toString(36).slice(2, 8);
          const g = svg.append('defs').append('linearGradient').attr('id', gid).attr('x1', 0).attr('x2', 0).attr('y1', 0).attr('y2', 1);
          g.append('stop').attr('offset', 0).attr('stop-color', s.color).attr('stop-opacity', 0.32);
          g.append('stop').attr('offset', 1).attr('stop-color', s.color).attr('stop-opacity', 0);
          svg.append('path').attr('class', 'area' + (opts.draw ? ' draw' : ''))
            .attr('d', d3.area().defined(def).x(xs).y0(y(y.domain()[0])).y1((r) => y(val(r, s)))(rows)).attr('fill', `url(#${gid})`);
        }
        const p = svg.append('path').attr('class', 'line' + (opts.draw ? ' draw' : '')).attr('fill', 'none')
          .style('stroke', s.color).attr('stroke-width', opts.strokeW || 2).attr('stroke-linejoin', 'round').attr('stroke-linecap', 'round')
          .attr('d', d3.line().defined(def).x(xs).y((r) => y(val(r, s)))(rows));
        if (opts.draw) p.style('--len', p.node().getTotalLength());
      });
    }

    // máximo marcado
    if (opts.peak) {
      const pr = d3.greatest(rows, (r) => val(r, s0));
      if (pr) {
        const px = xs(pr), py = y(val(pr, s0));
        svg.append('circle').attr('cx', px).attr('cy', py).attr('r', 4.5).style('fill', s0.color).style('stroke', 'var(--bg)').attr('stroke-width', 2);
        const lt = svg.append('text').attr('class', 'anno').attr('y', py - 12).attr('x', px + 10).attr('text-anchor', 'start')
          .text(T.peak + ' ' + opts.vFmt(val(pr, s0)));
        if (px + 10 + lt.node().getComputedTextLength() > W - mr) lt.attr('text-anchor', 'end').attr('x', px - 10);
      }
    }

    // capa de lectura (tooltip)
    const tip = d3.select(box).append('div').attr('class', 'tip').attr('hidden', true).attr('translate', 'no');
    const rule = svg.append('line').attr('y1', 10).attr('y2', H - 30).style('stroke', '#5a7190').style('display', 'none');
    const dots = opts.type === 'bar' ? null : svg.append('g').style('display', 'none');
    const pts = rows.map(xs);
    function show(i) {
      const r = rows[i];
      const cx = pts[i];
      rule.style('display', null).attr('x1', cx).attr('x2', cx);
      if (dots) {
        dots.style('display', null).selectAll('circle').data(opts.series.filter((s) => val(r, s) !== null)).join('circle')
          .attr('cx', cx).attr('cy', (s) => y(val(r, s))).attr('r', 4.5).style('fill', (s) => s.color).style('stroke', 'var(--bg)').attr('stroke-width', 2);
      }
      tip.attr('hidden', null).html('');
      tip.append('div').attr('class', 't').text(opts.tipTitle(r));
      opts.series.forEach((s) => {
        const v = val(r, s);
        const row = tip.append('div').attr('class', 'row');
        row.append('i').style('background', r.parcial && opts.type === 'bar' ? '#34486a' : s.color);
        row.append('span').text((opts.series.length > 1 ? s.name + ': ' : '') + (v === null ? T.noData : opts.vFmt(v)));
      });
      const tw = tip.node().offsetWidth;
      let left = cx + 14;
      if (left + tw > box.clientWidth) left = cx - tw - 14;
      tip.style('left', Math.max(0, left) + 'px').style('top', '8px');
    }
    function hide() { tip.attr('hidden', true); rule.style('display', 'none'); if (dots) dots.style('display', 'none'); }
    svg.append('rect').attr('x', ml).attr('y', 0).attr('width', W - ml - mr).attr('height', H).attr('fill', 'transparent')
      .style('cursor', 'crosshair')
      .on('pointermove pointerdown', (ev) => {
        const mx = d3.pointer(ev)[0];
        show(d3.leastIndex(pts, (a, b) => Math.abs(a - mx) - Math.abs(b - mx)));
      })
      .on('pointerleave', hide);
  }

  // ------------------------------------------------------------------ datos
  const files = ['resumen', 'diario', 'reparto', 'riesgos', 'horario'];
  Promise.all(files.map((f) => fetch(BASE + 'data/' + f + '.json', {cache: 'no-store'}).then((r) => {
    if (!r.ok) throw new Error(f + ' ' + r.status);
    return r.json();
  })))
    .then((js) => {
      const D = {};
      files.forEach((f, i) => (D[f] = js[i].rows || []));
      render(D);
    })
    .catch((e) => {
      console.error(e);
      const h = $('#hero-title');
      if (h) h.textContent = T.failed;
    });

  function render(D) {
    const R = D.resumen[0];
    const daily = D.diario;
    const closed = daily.filter((r) => !r.parcial);

    // valores sueltos marcados en el HTML
    $$('[data-k]').forEach((n) => {
      const v = R[n.dataset.k];
      n.textContent = v === null || v === undefined ? '—' : (F[n.dataset.f] || F.text)(v);
      n.setAttribute('translate', 'no');
      n.classList.add('num');
    });

    // frescura de los datos
    const upd = new Date(R.actualizado_utc.replace(' ', 'T') + ':00Z');
    const ageMin = (Date.now() - upd.getTime()) / 60000;
    const fr = $('.fresh');
    fr.classList.add(ageMin <= 90 ? 'is-live' : 'is-late');
    $('.fresh span').textContent = (ageMin <= 90 ? T.live : T.late) + ' ' + F.hourUtc(R.actualizado_utc);

    // titular
    const drop = R.caida_desde_pico_pct;
    const h1 = $('#hero-title');
    if (ES) {
      rich(h1, drop < 0
        ? ['El secuenciador de Elysium cobró ', {v: F.usd(R.ingresos_ultimo_dia_usd)}, ' el ' + F.dayLong(R.ultimo_dia_cerrado) + ', un ', {v: F.pct0(-drop)}, ' menos que en su máximo del ' + F.dayLong(R.dia_pico) + '.']
        : ['El secuenciador de Elysium cobró ', {v: F.usd(R.ingresos_ultimo_dia_usd)}, ' el ' + F.dayLong(R.ultimo_dia_cerrado) + ', su mejor día hasta ahora.']);
      rich($('#hero-sub'), ['De los ', {v: F.usdC(R.capital_puenteado_usd)}, ' que entraron por el bridge, el ', {v: F.pct(R.pct_en_protocolos)}, ' está depositado en protocolos.']);
    } else {
      rich(h1, drop < 0
        ? ['Elysium’s sequencer earned ', {v: F.usd(R.ingresos_ultimo_dia_usd)}, ' on ' + F.dayLong(R.ultimo_dia_cerrado) + ', ', {v: F.pct0(-drop)}, ' below its ' + F.dayLong(R.dia_pico) + ' peak.']
        : ['Elysium’s sequencer earned ', {v: F.usd(R.ingresos_ultimo_dia_usd)}, ' on ' + F.dayLong(R.ultimo_dia_cerrado) + ', its best day so far.']);
      rich($('#hero-sub'), ['Of the ', {v: F.usdC(R.capital_puenteado_usd)}, ' bridged in, ', {v: F.pct(R.pct_en_protocolos)}, ' is deposited in protocols.']);
    }

    // cambio diario con dirección
    const ch = $('#kpi-change');
    const c = R.cambio_ingresos_pct;
    ch.className = 'delta num ' + (c >= 0 ? 'up' : 'down');
    ch.setAttribute('translate', 'no');
    ch.textContent = (c >= 0 ? '▲ ' : '▼ ') + F.pct(Math.abs(c));

    // barra de capital
    $('#split-fill').style.width = Math.max(0, Math.min(100, R.pct_en_protocolos)) + '%';

    // recompras contra desbloqueos
    const mx = Math.max(R.recompra_mensual_estimada_usd, R.desbloqueo_mensual_usd) || 1;
    $('#vs-buy').style.width = (R.recompra_mensual_estimada_usd / mx) * 78 + '%';
    $('#vs-unlock').style.width = (R.desbloqueo_mensual_usd / mx) * 78 + '%';

    // tablas
    $('#tbl-reparto').replaceChildren(...D.reparto.map((r) => el('tr', {}, [
      el('td', {text: tr(r.destino)}),
      el('td', {class: 'r num', translate: 'no', text: F.pct0(r.porcentaje)}),
      el('td', {class: 'r num', translate: 'no', text: F.num(r.hype)}),
      el('td', {class: 'r num', translate: 'no', text: F.usd(r.usd)}),
    ])));
    const LVL = ES
      ? {ok: 'Bajo', medio: 'Medio', alto: 'Alto', info: 'Dato'}
      : {ok: 'Low', medio: 'Medium', alto: 'High', info: 'Info'};
    const readLbl = ES ? 'Leído de' : 'Read from';
    $('#risks').replaceChildren(...D.riesgos.map((r) => el('div', {class: 'risk'}, [
      el('div', {class: 'r-top'}, [
        el('h3', {text: ES ? r.aspecto : r.aspecto_en}),
        el('span', {class: 'r-val', translate: 'no', text: ES ? r.valor : r.valor_en}),
      ]),
      el('span', {class: 'lvl lvl-' + r.nivel, text: LVL[r.nivel] || r.nivel}),
      el('p', {class: 'r-detail', text: ES ? r.detalle : r.detalle_en}),
      el('p', {class: 'r-src', translate: 'no'}, [document.createTextNode(readLbl + ': ' + (ES ? r.lectura : (r.lectura_en || r.lectura)))]),
    ])));

    // gráficos (se vuelven a dibujar cuando cambia el ancho)
    const cs = getComputedStyle(root);
    const C = {s1: cs.getPropertyValue('--s1').trim(), s2: cs.getPropertyValue('--s2').trim()};
    const dayTitle = (r) => F.dayLong(r.dia) + (r.parcial ? ' · ' + T.partial : '');
    let first = true;
    function drawAll() {
      chart($('#trace'), {
        rows: closed, key: 'dia', type: 'line', area: true, peak: true, draw: first && !reduceMotion, strokeW: 2.5, height: 250, mr: 12,
        series: [{k: 'ingresos_usd', name: T.revenue, color: C.s1}],
        xLabel: (r) => F.day(r.dia), tipTitle: dayTitle, yFmt: F.usdT, vFmt: F.usd,
        annotate: {x: '2026-11-09', text: T.launch}, aria: T.revenue,
      });
      chart($('#ch-capital'), {
        rows: daily, key: 'dia', type: 'line',
        series: [{k: 'usdc_en_red', name: T.usdc, color: C.s1}, {k: 'tvl_usd', name: T.tvl, color: C.s2}],
        xLabel: (r) => F.day(r.dia), tipTitle: dayTitle, yFmt: F.usdT, vFmt: F.usdC, aria: T.usdc + ', ' + T.tvl,
      });
      const hb = $('#ch-bridge');
      if (D.horario.length >= 3) {
        const lo = d3.min(D.horario, (r) => r.hype_en_bridge);
        chart(hb, {
          rows: D.horario, type: 'line', time: true, yMin: Math.floor((lo * 0.9) / 50000) * 50000,
          series: [{k: 'hype_en_bridge', name: T.bridge, color: C.s1}],
          tipTitle: (r) => F.dayLong(r.hora_utc) + ', ' + F.hourUtc(r.hora_utc), yFmt: F.numT, vFmt: F.hype, aria: T.bridge,
        });
      } else {
        hb.replaceChildren(el('div', {class: 'empty', text: T.fewPoints}));
      }
      chart($('#ch-withdrawals'), {
        rows: daily, key: 'dia', type: 'bar',
        series: [{k: 'retiros_hype', name: T.withdrawn, color: C.s1}],
        xLabel: (r) => F.day(r.dia), tipTitle: dayTitle, yFmt: F.numT, vFmt: F.hype, annotate: {x: '2026-11-09', text: T.launch}, aria: T.withdrawn,
      });
      first = false;
    }
    drawAll();
    let lastW = root.clientWidth, timer;
    new ResizeObserver(() => {
      if (Math.abs(root.clientWidth - lastW) < 2) return;
      lastW = root.clientWidth;
      clearTimeout(timer);
      timer = setTimeout(drawAll, 120);
    }).observe(document.body);
  }


  // ------------------------------------------------------------------ radar de lanzamientos
  const TR = ES
    ? {never: 'Nunca se operaron', died: 'Se apagaron en menos de 2 h', lasted: 'Operaron 2 h o más', alive: 'Activos a las 24 h',
       launches: 'lanzamientos', hours: ' h', serial_creator: 'Creador en serie', concentrated: 'Concentrado',
       liquidity_removed: 'Liquidez retirada', inactive: 'Sin movimiento', none: '—', aria: 'Resultado de los lanzamientos por día'}
    : {never: 'Never traded', died: 'Stopped within 2 h', lasted: 'Traded 2 h or more', alive: 'Active after 24 h',
       launches: 'launches', hours: 'h', serial_creator: 'Serial creator', concentrated: 'Concentrated',
       liquidity_removed: 'Liquidity removed', inactive: 'Inactive', none: '—', aria: 'Outcome of launches by day'};
  const SIG_CLASS = {serial_creator: 'warn', concentrated: 'warn', liquidity_removed: 'bad', inactive: ''};

  function stacked(box, rows) {
    box.replaceChildren();
    const W = Math.max(box.clientWidth || 600, 280), H = 210;
    const svg = d3.select(box).append('svg').attr('width', '100%').attr('height', H).attr('viewBox', `0 0 ${W} ${H}`)
      .attr('role', 'img').attr('aria-label', TR.aria).attr('translate', 'no');
    const segs = [
      {k: 'lasted', c: getComputedStyle(root).getPropertyValue('--s1').trim(), v: (r) => 100 - r.nunca_operados_pct - r.murieron_2h_pct},
      {k: 'died', c: getComputedStyle(root).getPropertyValue('--s2').trim(), v: (r) => r.murieron_2h_pct},
      {k: 'never', c: '#34486a', v: (r) => r.nunca_operados_pct},
    ];
    const y = d3.scaleLinear().domain([0, 100]).range([H - 30, 10]);
    const ticks = [0, 50, 100];
    const ml = measure(svg, ticks.map((t) => F.pct0(t))) + 12;
    const x = d3.scaleBand().domain(rows.map((r) => r.dia)).range([ml, W - 8]).padding(0.3);
    const bw = Math.min(x.bandwidth(), 56);
    const off = (x.bandwidth() - bw) / 2;
    svg.append('g').selectAll('line').data(ticks).join('line').attr('x1', ml).attr('x2', W - 8)
      .attr('y1', (t) => Math.round(y(t)) + 0.5).attr('y2', (t) => Math.round(y(t)) + 0.5).style('stroke', 'var(--grid)');
    svg.append('g').selectAll('text').data(ticks).join('text').attr('class', 'tick').attr('x', ml - 10).attr('y', (t) => y(t))
      .attr('dy', '0.32em').attr('text-anchor', 'end').text((t) => F.pct0(t));
    const labels = rows.map((r) => F.day(r.dia));
    const every = Math.max(1, Math.ceil((measure(svg, labels) + 14) / x.step()));
    svg.append('g').selectAll('text').data(rows.filter((r, i) => (rows.length - 1 - i) % every === 0)).join('text').attr('class', 'tick')
      .attr('x', (r) => x(r.dia) + x.bandwidth() / 2).attr('y', H - 8).attr('text-anchor', 'middle').text((r) => F.day(r.dia));
    rows.forEach((r) => {
      let acc = 0;
      segs.forEach((sg) => {
        const v = Math.max(0, sg.v(r));
        const y0 = y(acc), y1 = y(acc + v);
        if (y0 - y1 > 0.5) {
          svg.append('rect').attr('x', x(r.dia) + off).attr('width', bw).attr('y', y1 + 1).attr('height', Math.max(0, y0 - y1 - 2))
            .attr('rx', 2).style('fill', sg.c);
        }
        acc += v;
      });
    });
    const tip = d3.select(box).append('div').attr('class', 'tip').attr('hidden', true).attr('translate', 'no');
    const hl = svg.append('rect').attr('y', 6).attr('height', H - 32).attr('rx', 4).style('fill', 'rgba(154,172,196,0.08)').style('display', 'none');
    svg.append('rect').attr('x', ml).attr('width', W - ml - 8).attr('height', H).attr('fill', 'transparent')
      .on('pointermove pointerdown', (ev) => {
        const mx = d3.pointer(ev)[0];
        const r = rows[d3.leastIndex(rows, (a, b) => Math.abs(x(a.dia) + x.bandwidth() / 2 - mx) - Math.abs(x(b.dia) + x.bandwidth() / 2 - mx))];
        hl.style('display', null).attr('x', x(r.dia) + off - 4).attr('width', bw + 8);
        tip.attr('hidden', null).html('');
        tip.append('div').attr('class', 't').text(F.dayLong(r.dia) + ' · ' + F.num(r.lanzamientos) + ' ' + TR.launches);
        segs.forEach((sg) => {
          const row = tip.append('div').attr('class', 'row');
          row.append('i').style('background', sg.c);
          row.append('span').text(TR[sg.k] + ': ' + F.pct(Math.max(0, sg.v(r))));
        });
        tip.append('div').attr('class', 'row').append('span').text(TR.alive + ': ' + F.pct(r.activos_24h_pct));
        const cx = x(r.dia) + x.bandwidth() / 2, tw = tip.node().offsetWidth;
        let left = cx + bw / 2 + 10;
        if (left + tw > box.clientWidth) left = cx - bw / 2 - tw - 10;
        tip.style('left', Math.max(0, left) + 'px').style('top', '8px');
      })
      .on('pointerleave', () => { tip.attr('hidden', true); hl.style('display', 'none'); });
  }

  fetch(BASE + 'data/radar.json', {cache: 'no-store'})
    .then((r) => { if (!r.ok) throw new Error('radar ' + r.status); return r.json(); })
    .then((RD) => {
      const S = RD.resumen;
      $$('[data-r]').forEach((n) => {
        const v = S[n.dataset.r];
        n.textContent = v === null || v === undefined ? '—' : (F[n.dataset.f] || F.text)(v);
        n.setAttribute('translate', 'no');
        n.classList.add('num');
      });
      const u = S.ultimo_dia;
      if (u) {
        rich($('#rd-lead'), ES
          ? ['De los ', {v: F.num(u.lanzamientos)}, ' tokens lanzados el ' + F.dayLong(u.dia) + ', el ', {v: F.pct0(u.nunca_operados_pct)},
             ' nunca se operó, el ', {v: F.pct0(u.murieron_2h_pct)}, ' se apagó en menos de dos horas y el ', {v: F.pct(u.activos_24h_pct)}, ' seguía activo a las 24 horas.']
          : ['Of the ', {v: F.num(u.lanzamientos)}, ' tokens launched on ' + F.dayLong(u.dia) + ', ', {v: F.pct0(u.nunca_operados_pct)},
             ' never traded, ', {v: F.pct0(u.murieron_2h_pct)}, ' stopped within two hours and ', {v: F.pct(u.activos_24h_pct)}, ' were still active after 24 hours.']);
      }
      const drawCohorts = () => {
        const box = $('#ch-cohorts');
        if (RD.por_dia.length) stacked(box, RD.por_dia);
        else box.replaceChildren(el('div', {class: 'empty', text: ES ? 'El primer día completo se publica 25 horas después de su cierre.' : 'The first full day is published 25 hours after it closes.'}));
      };
      drawCohorts();
      let lw = root.clientWidth, tm;
      new ResizeObserver(() => { if (Math.abs(root.clientWidth - lw) < 2) return; lw = root.clientWidth; clearTimeout(tm); tm = setTimeout(drawCohorts, 120); }).observe(document.body);

      $('#tbl-pads').replaceChildren(...RD.por_launchpad.map((p) => el('tr', {}, [
        el('td', {translate: p.contrato ? 'no' : 'yes'}, [p.contrato
          ? el('a', {class: 'addr', href: 'https://elysium.kinetiq.xyz/address/' + p.contrato, rel: 'noopener', text: p.nombre})
          : document.createTextNode(ES ? 'Otros contratos' : 'Other contracts')]),
        el('td', {class: 'r num', translate: 'no', text: F.num(p.lanzamientos)}),
        el('td', {class: 'r num', translate: 'no', text: F.pct(p.nunca_operados_pct)}),
        el('td', {class: 'r num', translate: 'no', text: F.pct(p.activos_24h_pct)}),
        el('td', {class: 'r num', translate: 'no', text: p.vida_mediana_min < 60 ? F.num(p.vida_mediana_min) + ' min' : nf(1).format(p.vida_mediana_min / 60) + TR.hours}),
      ])));
      $('#tbl-tokens').replaceChildren(...RD.tokens.map((t) => {
        const sig = el('span', {class: 'sig'}, t.senales.length
          ? t.senales.map((k) => el('span', {class: SIG_CLASS[k] || '', text: TR[k] || k}))
          : [document.createTextNode(TR.none)]);
        const a = el('a', {class: 'addr', href: 'https://elysium.kinetiq.xyz/address/' + t.token, rel: 'noopener nofollow', translate: 'no'}, [
          el('span', {class: 'tok-sym', text: t.simbolo || t.token.slice(0, 8) + '…'}),
          el('span', {class: 'tok-name', text: t.nombre || ''}),
        ]);
        const sigM = sig.cloneNode(true);
        sigM.classList.add('sig-m');
        return el('tr', {}, [
          el('td', {}, [a, sigM]),
          el('td', {translate: 'no', text: t.launchpad}),
          el('td', {class: 'r num', translate: 'no', text: nf(1).format(t.edad_h) + TR.hours}),
          el('td', {class: 'r num', translate: 'no', text: F.num(t.transferencias)}),
          el('td', {class: 'r num', translate: 'no', text: F.num(t.tenedores)}),
          el('td', {class: 'r num', translate: 'no', text: t.tenedores ? F.pct(t.top10_pct) : '—'}),
          el('td', {}, [sig]),
        ]);
      }));
    })
    .catch((e) => {
      console.error(e);
      const sec = $('#radar');
      if (sec) sec.hidden = true;
    });

  // aviso de versión en español para navegadores en español
  const hint = $('.lang-hint');
  if (hint && !ES && /^es\b/i.test(navigator.language || '')) {
    let dismissed = false;
    try { dismissed = localStorage.getItem('pe-hint') === '1'; } catch (e) { /* sin almacenamiento */ }
    if (!dismissed) {
      hint.hidden = false;
      $('button', hint).addEventListener('click', () => {
        hint.hidden = true;
        try { localStorage.setItem('pe-hint', '1'); } catch (e) { /* sin almacenamiento */ }
      });
    }
  }
})();
