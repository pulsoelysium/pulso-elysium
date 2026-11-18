#!/usr/bin/env python3
"""Genera docs/index.html (inglés) y docs/es/index.html (español) desde una sola plantilla."""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://pulsoelysium.github.io/pulso-elysium/"

S = {
    "title": ("Pulso Elysium: network health and capital flow on Elysium",
              "Pulso Elysium: salud de la red y flujo de capital en Elysium"),
    "desc": ("Independent analytics for Elysium, Kinetiq's Layer 2 on Hyperliquid: sequencer revenue, idle capital, withdrawals and rollup status.",
             "Analítica independiente de Elysium, la L2 de Kinetiq sobre Hyperliquid: ingresos del secuenciador, capital ocioso, retiros y estado del rollup."),
    "hint": ("Esta página también está en español.", "Esta página también está en español."),
    "hint_link": ("Ver en español", "Ver en español"),
    "hint_close": ("Close", "Cerrar"),
    "fresh": ("Loading data", "Cargando datos"),
    "other_lang": ("Español", "English"),
    "other_href": ("es/", "../"),
    "other_code": ("es", "en"),
    "loading": ("Reading the chain…", "Leyendo la cadena…"),
    "trace_cap": ("Daily sequencer revenue in US dollars, closed UTC days. Days before Nov 9 belong to the private mainnet.",
                  "Ingresos diarios del secuenciador en dólares, por día UTC cerrado. Los días anteriores al 9/11 son de la mainnet privada."),
    "k1": ("Sequencer revenue, last closed day", "Ingresos del secuenciador, último día cerrado"),
    "k1s": ("from the day before", "frente al día anterior"),
    "k2": ("Capital bridged in", "Capital que entró por el bridge"),
    "k2s_a": ("", ""), "k2s_b": (" and ", " y "), "k2s_c": (" in USDC", " en USDC"),
    "k3": ("Share deposited in protocols", "Parte depositada en protocolos"),
    "k3s_a": ("TVL of ", "TVL de "), "k3s_b": (" per DefiLlama", " según DefiLlama"),
    "k4": ("HYPE withdrawn since Nov 9", "HYPE retirado desde el 9/11"),
    "k4s_a": ("in ", "en "), "k4s_b": (" withdrawals", " retiros"),
    "cap_h": ("Where the bridged capital is", "Dónde está el capital que entró"),
    "cap_l": ("Capital has arrived on Elysium, but most of it is not yet deposited in any protocol DefiLlama tracks.",
              "El capital llegó a Elysium, pero la mayor parte todavía no está depositada en ningún protocolo que siga DefiLlama."),
    "split_aria": ("Share of bridged capital deposited in protocols", "Parte del capital puenteado que está en protocolos"),
    "split_a": ("In protocols", "En protocolos"),
    "split_b": ("In wallets or untracked contracts", "En billeteras o contratos no contabilizados"),
    "p1_h": ("USDC on Elysium and TVL", "USDC en Elysium y TVL"),
    "p1_d": ("Daily, in US dollars.", "Por día, en dólares."),
    "usdc": ("USDC on Elysium", "USDC en la red"), "tvl": ("TVL in protocols (DefiLlama)", "TVL en protocolos (DefiLlama)"),
    "p2_h": ("HYPE held by the bridge", "HYPE en custodia del bridge"),
    "p2_d": ("Hourly, read from the Bridge contract on HyperEVM.", "Por hora, leído del contrato Bridge en HyperEVM."),
    "wd_h": ("HYPE leaving for HyperEVM", "HYPE que sale hacia HyperEVM"),
    "wd_l": ("Native HYPE whose withdrawal to HyperEVM was started each day. On the last closed day, ",
             "HYPE nativo cuyo retiro hacia HyperEVM se inició cada día. El último día cerrado salieron "),
    "wd_l2": (" left.", "."),
    "wd_cap": ("Withdrawals of other tokens are not included. Grey bar: day in progress.",
               "No incluye retiros de otros tokens. Barra gris: día en curso."),
    "rd_h": ("What happens to new tokens", "Qué pasa con los tokens nuevos"),
    "rd_k1": ("Launches, last 24 hours", "Lanzamientos, últimas 24 horas"),
    "rd_k2": ("Never traded, last 24 hours", "Nunca operados, últimas 24 horas"),
    "rd_k2s": ("Launches over an hour old with no purchase from a pool", "Lanzamientos de más de una hora sin ninguna compra en un pool"),
    "rd_k3": ("Serial creators, last 7 days", "Creadores en serie, últimos 7 días"),
    "rd_k3s_a": ("Wallets with 5+ launches, behind ", "Billeteras con 5 o más lanzamientos, detrás del "),
    "rd_k3s_b": (" of all launches", " de todos los lanzamientos"),
    "rd_c_h": ("Outcome of each day's launches", "Qué pasó con los lanzamientos de cada día"),
    "rd_c_d": ("Share of tokens launched that day, by UTC day of launch.", "Porcentaje de los tokens lanzados ese día, por día UTC de lanzamiento."),
    "rd_never": ("Never traded", "Nunca se operaron"),
    "rd_died": ("Stopped within 2 hours", "Se apagaron en menos de 2 horas"),
    "rd_lasted": ("Traded for 2 hours or more", "Operaron 2 horas o más"),
    "rd_p_h": ("By launch platform, last 7 days", "Por plataforma de lanzamiento, últimos 7 días"),
    "rd_p_d": ("Platforms are identified by the contract that created the pool. Contracts with fewer than 100 launches are grouped.", "Las plataformas se identifican por el contrato que creó el pool. Los contratos con menos de 100 lanzamientos van agrupados."),
    "th_pad": ("Platform", "Plataforma"), "th_launches": ("Launches", "Lanzamientos"), "th_never": ("Never traded", "Nunca operados"),
    "th_alive": ("Active after 24 h", "Activos a las 24 h"), "th_life": ("Median life when traded", "Vida mediana si se operó"),
    "rd_t_h": ("Launches of the last 24 hours, most active first", "Lanzamientos de las últimas 24 horas, los más activos primero"),
    "rd_t_d": ("Ranked by trades in the last 6 hours. Signals are on-chain indicators, not a verdict on any token.",
               "Ordenados por operaciones en las últimas 6 horas. Las señales son indicadores de la cadena, no un veredicto sobre ningún token."),
    "th_token": ("Token", "Token"), "th_age": ("Age", "Edad"), "th_tx": ("Transfers", "Transferencias"), "th_holders": ("Holders", "Tenedores"),
    "th_top10": ("Top 10", "Top 10"), "th_signals": ("Signals", "Señales"),
    "rd_note": ("A token counts as traded once a wallet buys it from a pool. It stops when its last trade happens, and it is active after 24 hours if it had at least 3 trades between hours 18 and 24 after launch. Top 10 share is measured over the tokens held by wallets, excluding the pool and the launch contract. Concentrated: 10+ holders and the top 10 hold 70% or more. Serial creator: the wallet launched 5+ tokens in 7 days. Tokens are tracked for 8 days; activity after 48 hours of silence is not followed.",
                "Un token cuenta como operado cuando una billetera lo compra en un pool. Se apaga con su última operación, y está activo a las 24 horas si tuvo al menos 3 operaciones entre las horas 18 y 24 desde su lanzamiento. La parte del top 10 se mide sobre los tokens que tienen las billeteras, sin contar el pool ni el contrato de lanzamiento. Concentrado: 10 o más tenedores y el top 10 con el 70 % o más. Creador en serie: la billetera lanzó 5 o más tokens en 7 días. Cada token se sigue 8 días; la actividad después de 48 horas de silencio no se registra."),
    "bb_h": ("Buybacks versus unlocks", "Recompras contra desbloqueos"),
    "bb_l_a": ("Half of sequencer revenue is earmarked to buy back KNTQ. At the pace of the last three closed days, that covers ",
               "La mitad de los ingresos del secuenciador se destina a recomprar KNTQ. Al ritmo de los últimos tres días cerrados, eso cubre el "),
    "bb_l_b": (" of the monthly unlock.", " del desbloqueo mensual."),
    "vs1": ("Estimated monthly buybacks", "Recompras mensuales estimadas"),
    "vs2_a": ("Monthly unlock of ", "Desbloqueo mensual de "), "vs2_b": (" KNTQ", " KNTQ"),
    "bb_note": ("Estimate. The unlock schedule (first tranche Nov 27) comes from third-party sources not verified on-chain, and the address Kinetiq uses for buybacks has not been located yet.",
                "Estimación. El calendario de desbloqueos (primer tramo el 27/11) viene de fuentes de terceros sin verificar en la cadena, y todavía no ubicamos la dirección desde la que Kinetiq recompra."),
    "rep_h": ("Announced split of the revenue collected so far", "Reparto anunciado de lo recaudado hasta ahora"),
    "rep_d_a": ("The network fee account holds ", "La cuenta de comisiones de la red acumula "),
    "rep_d_b": (" and shows no outflows yet.", " y todavía no registra ninguna salida."),
    "th_dest": ("Destination", "Destino"), "th_share": ("Share", "Parte"), "th_usd": ("US dollars", "Dólares"),
    "ro_h": ("Who controls the rollup", "Quién controla el rollup"),
    "ro_l": ("Values read directly from Elysium's contracts on HyperEVM. A single permissioned validator is normal for a young chain and worth watching as it decentralizes.",
             "Valores leídos directamente de los contratos de Elysium en HyperEVM. Un único validador autorizado es normal en una red joven, y conviene seguirlo mientras se descentraliza."),
    "th_item": ("Item", "Aspecto"), "th_val": ("Value", "Valor"), "th_st": ("Assessment", "Evaluación"), "th_fn": ("Function read", "Función leída"),
    "m_sum": ("How each number is calculated", "Cómo se calcula cada número"),
    "m1": ("Sequencer revenue is the daily change in the balance of the network fee account, valued at each day's HYPE price. Days close at 00:00 UTC.",
           "Los ingresos del secuenciador son la variación diaria del saldo de la cuenta de comisiones de la red, valuada al precio de HYPE de cada día. Los días cierran a las 00:00 UTC."),
    "m2": ("Capital bridged in is the HYPE held by the Bridge contract on HyperEVM, at the current price, plus the USDC issued on Elysium. It excludes kHYPE, UBTC, UETH and other bridged tokens, so the real total is somewhat higher and the share in protocols somewhat lower.",
           "El capital que entró es el HYPE en custodia del contrato Bridge en HyperEVM, al precio actual, más el USDC emitido en Elysium. No incluye kHYPE, UBTC, UETH ni otros tokens puenteados, así que el total real es algo mayor y la parte en protocolos algo menor."),
    "m3": ("TVL and prices come from DefiLlama. Chain data comes from the public Elysium and HyperEVM RPCs. The code is open on GitHub.",
           "El TVL y los precios vienen de DefiLlama. Los datos de la cadena salen de los RPC públicos de Elysium y HyperEVM. El código es abierto y está en GitHub."),
    "disclaimer": ("Independent project, not affiliated with Kinetiq or Hyperliquid. Not financial advice.",
                   "Proyecto independiente, sin relación con Kinetiq ni Hyperliquid. No es asesoramiento financiero."),
    "x": ("X", "X"), "code": ("Code", "Código"),
}

LOGO = ('<svg viewBox="0 0 64 64" aria-hidden="true"><defs><linearGradient id="lg" x1="0" x2="1">'
        '<stop offset="0" stop-color="#6ea8e6"/><stop offset=".55" stop-color="#6ea8e6"/><stop offset="1" stop-color="#f0a35c"/>'
        '</linearGradient></defs><circle cx="32" cy="32" r="29" fill="#13233a" stroke="#2a4466" stroke-width="2"/>'
        '<polyline points="11,33 22,33 26,26 30,42 35,19 40,37 43,33 50,33" fill="none" stroke="url(#lg)" stroke-width="3.6" '
        'stroke-linecap="round" stroke-linejoin="round"/><circle cx="53" cy="33" r="2.6" fill="#f0a35c"/></svg>')

TEMPLATE = """<!DOCTYPE html>
<html lang="{lang}"{base}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t:title}</title>
<meta name="description" content="{t:desc}">
<meta property="og:title" content="Pulso Elysium">
<meta property="og:description" content="{t:desc}">
<meta property="og:url" content="{url}">
<meta name="theme-color" content="#0c1624">
<link rel="alternate" hreflang="{t:other_code}" href="{alt_url}">
<link rel="icon" href="data:image/svg+xml,{favicon}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Instrument+Serif&display=swap">
<link rel="stylesheet" href="{rel}style.css">
</head>
<body>
{hint}<header class="top">
  <div class="wrap">
    <a class="brand" href="{rel}{home}" aria-label="Pulso Elysium">{logo}<b translate="no">Pulso Elysium</b></a>
    <div class="top-right">
      <span class="fresh"><i aria-hidden="true"></i><span>{t:fresh}</span></span>
      <a class="lang" href="{t:other_href}" hreflang="{t:other_code}" lang="{t:other_code}">{t:other_lang}</a>
    </div>
  </div>
</header>

<main class="wrap">
  <div class="hero">
    <h1 id="hero-title">{t:loading}</h1>
    <p class="sub" id="hero-sub"></p>
    <div class="trace" id="trace"></div>
    <p class="caption">{t:trace_cap}</p>
  </div>

  <div class="kpis">
    <div class="kpi">
      <h3>{t:k1}</h3>
      <p class="v" data-k="ingresos_ultimo_dia_usd" data-f="usd">—</p>
      <p><span id="kpi-change">—</span> {t:k1s}</p>
    </div>
    <div class="kpi">
      <h3>{t:k2}</h3>
      <p class="v" data-k="capital_puenteado_usd" data-f="usdC">—</p>
      <p>{t:k2s_a}<span data-k="hype_en_bridge" data-f="hype">—</span>{t:k2s_b}<span data-k="usdc_en_red" data-f="usdC">—</span>{t:k2s_c}</p>
    </div>
    <div class="kpi">
      <h3>{t:k3}</h3>
      <p class="v" data-k="pct_en_protocolos" data-f="pct">—</p>
      <p>{t:k3s_a}<span data-k="tvl_usd" data-f="usdC">—</span>{t:k3s_b}</p>
    </div>
    <div class="kpi">
      <h3>{t:k4}</h3>
      <p class="v" data-k="retiros_hype_desde_mainnet" data-f="num">—</p>
      <p>{t:k4s_a}<span data-k="retiros_cantidad_desde_mainnet" data-f="num">—</span>{t:k4s_b}</p>
    </div>
  </div>

  <section id="capital">
    <h2>{t:cap_h}</h2>
    <p class="lead">{t:cap_l}</p>
    <div class="split">
      <div class="split-bar" role="img" aria-label="{t:split_aria}"><div id="split-fill"></div></div>
      <div class="split-keys">
        <span><i style="background:var(--s1)"></i>{t:split_a}: <strong data-k="tvl_usd" data-f="usdC">—</strong></span>
        <span><i style="background:#24364f"></i>{t:split_b}: <strong data-k="capital_ocioso_usd" data-f="usdC">—</strong></span>
      </div>
    </div>
    <div class="grid-2">
      <div class="panel">
        <h3>{t:p1_h}</h3>
        <p class="d">{t:p1_d}</p>
        <div class="chart" id="ch-capital"></div>
        <div class="legend"><span><i style="background:var(--s1)"></i>{t:usdc}</span><span><i style="background:var(--s2)"></i>{t:tvl}</span></div>
      </div>
      <div class="panel">
        <h3>{t:p2_h}</h3>
        <p class="d">{t:p2_d}</p>
        <div class="chart" id="ch-bridge"></div>
      </div>
    </div>
  </section>

  <section id="withdrawals">
    <h2>{t:wd_h}</h2>
    <p class="lead">{t:wd_l}<strong data-k="retiros_ultimo_dia_hype" data-f="hype">—</strong>{t:wd_l2}</p>
    <div class="panel" style="margin-top:24px">
      <div class="chart short" id="ch-withdrawals"></div>
      <p class="caption">{t:wd_cap}</p>
    </div>
  </section>

  <section id="radar">
    <h2>{t:rd_h}</h2>
    <p class="lead" id="rd-lead"></p>
    <div class="kpis kpis-3">
      <div class="kpi">
        <h3>{t:rd_k1}</h3>
        <p class="v" data-r="lanzamientos_24h" data-f="num">—</p>
      </div>
      <div class="kpi">
        <h3>{t:rd_k2}</h3>
        <p class="v" data-r="nunca_operados_24h_pct" data-f="pct">—</p>
        <p>{t:rd_k2s}</p>
      </div>
      <div class="kpi">
        <h3>{t:rd_k3}</h3>
        <p class="v" data-r="creadores_en_serie_7d" data-f="num">—</p>
        <p>{t:rd_k3s_a}<span data-r="pct_lanzamientos_de_creadores_en_serie_7d" data-f="pct">—</span>{t:rd_k3s_b}</p>
      </div>
    </div>
    <div class="panel" style="margin-top:28px">
      <h3>{t:rd_c_h}</h3>
      <p class="d">{t:rd_c_d}</p>
      <div class="chart short" id="ch-cohorts"></div>
      <div class="legend"><span><i style="background:var(--s1)"></i>{t:rd_lasted}</span><span><i style="background:var(--s2)"></i>{t:rd_died}</span><span><i style="background:#34486a"></i>{t:rd_never}</span></div>
    </div>
    <div class="panel" style="margin-top:20px">
      <h3>{t:rd_p_h}</h3>
      <p class="d">{t:rd_p_d}</p>
      <div class="tbl-wrap"><table class="tbl-pads">
        <thead><tr><th>{t:th_pad}</th><th class="r">{t:th_launches}</th><th class="r">{t:th_never}</th><th class="r">{t:th_alive}</th><th class="r">{t:th_life}</th></tr></thead>
        <tbody id="tbl-pads"></tbody>
      </table></div>
    </div>
    <div class="panel" style="margin-top:20px">
      <h3>{t:rd_t_h}</h3>
      <p class="d">{t:rd_t_d}</p>
      <div class="tbl-wrap"><table class="tbl-tokens">
        <thead><tr><th>{t:th_token}</th><th>{t:th_pad}</th><th class="r">{t:th_age}</th><th class="r">{t:th_tx}</th><th class="r">{t:th_holders}</th><th class="r">{t:th_top10}</th><th>{t:th_signals}</th></tr></thead>
        <tbody id="tbl-tokens"></tbody>
      </table></div>
    </div>
    <p class="note">{t:rd_note}</p>
  </section>

  <section id="buybacks">
    <h2>{t:bb_h}</h2>
    <p class="lead">{t:bb_l_a}<strong data-k="cobertura_recompra_pct" data-f="pct">—</strong>{t:bb_l_b}</p>
    <div class="versus">
      <div class="vs-row">
        <h3>{t:vs1}</h3>
        <div class="vs-track"><div class="vs-bar" id="vs-buy" style="background:var(--s1)"></div><span class="vs-val" data-k="recompra_mensual_estimada_usd" data-f="usdC">—</span></div>
      </div>
      <div class="vs-row">
        <h3>{t:vs2_a}<span data-k="desbloqueo_mensual_kntq" data-f="numC">—</span>{t:vs2_b}</h3>
        <div class="vs-track"><div class="vs-bar" id="vs-unlock" style="background:var(--s2)"></div><span class="vs-val" data-k="desbloqueo_mensual_usd" data-f="usdC">—</span></div>
      </div>
    </div>
    <p class="note">{t:bb_note}</p>
    <div class="panel" style="margin-top:28px">
      <h3>{t:rep_h}</h3>
      <p class="d">{t:rep_d_a}<span data-k="ingresos_acum_hype" data-f="hype">—</span> (<span data-k="ingresos_acum_usd" data-f="usd">—</span>){t:rep_d_b}</p>
      <div class="tbl-wrap"><table>
        <thead><tr><th>{t:th_dest}</th><th class="r">{t:th_share}</th><th class="r">HYPE</th><th class="r">{t:th_usd}</th></tr></thead>
        <tbody id="tbl-reparto"></tbody>
      </table></div>
    </div>
  </section>

  <section id="rollup">
    <h2>{t:ro_h}</h2>
    <p class="lead">{t:ro_l}</p>
    <div class="tbl-wrap" style="margin-top:20px"><table>
      <thead><tr><th>{t:th_item}</th><th>{t:th_val}</th><th>{t:th_st}</th><th>{t:th_fn}</th></tr></thead>
      <tbody id="tbl-rollup"></tbody>
    </table></div>
  </section>
</main>

<footer>
  <div class="wrap">
    <details>
      <summary>{t:m_sum}</summary>
      <p>{t:m1}</p>
      <p>{t:m2}</p>
      <p>{t:m3}</p>
    </details>
    <div class="foot-row">
      <span>{t:disclaimer}</span>
      <nav><a href="https://x.com/pulsoelysium" rel="noopener">{t:x} @pulsoelysium</a><a href="https://github.com/pulsoelysium/pulso-elysium" rel="noopener">{t:code}</a></nav>
    </div>
  </div>
</footer>

<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>
<script src="{rel}app.js"></script>
</body>
</html>
"""


def build(i, lang, path, rel, base):
    from urllib.parse import quote
    hint = ""
    if lang == "en":
        hint = ('<div class="lang-hint" hidden lang="es"><div class="wrap"><span>{t:hint} <a href="es/">{t:hint_link}</a></span>'
                '<button type="button" aria-label="{t:hint_close}">✕</button></div></div>\n')
    out = TEMPLATE.replace("{hint}", hint)
    out = re.sub(r"\{t:(\w+)\}", lambda m: S[m.group(1)][i], out)
    out = (out.replace("{lang}", lang).replace("{base}", base).replace("{rel}", rel).replace("{home}", "es/" if lang == "es" else "")
           .replace("{logo}", LOGO).replace("{favicon}", quote(LOGO.replace('aria-hidden="true"', 'xmlns="http://www.w3.org/2000/svg"')))
           .replace("{url}", SITE + ("es/" if lang == "es" else "")).replace("{alt_url}", SITE + ("" if lang == "es" else "es/")))
    assert "{" + "t:" not in out
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(out)


build(0, "en", os.path.join(HERE, "docs", "index.html"), "", "")
build(1, "es", os.path.join(HERE, "docs", "es", "index.html"), "../", ' data-base="../"')
print("Páginas generadas")
