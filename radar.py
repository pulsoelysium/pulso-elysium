#!/usr/bin/env python3
"""
Pulso Elysium - radar de lanzamientos (etapa 2).

Detecta los tokens nuevos que se lanzan en pools de Uniswap v4 de Elysium, sigue sus
transferencias y su liquidez, y calcula:
  - por día de lanzamiento: cuántos nunca se operaron, cuántos murieron en menos de 2 horas
    y cuántos seguían activos a las 24 horas;
  - por launchpad: las mismas tasas en los últimos 7 días;
  - una lista de los lanzamientos de las últimas 24 horas con señales de riesgo.

Estado: radar_estado.json.gz (se guarda en una rama aparte, sin historial).
Salida: docs/data/radar.json
Uso:    python3 radar.py [--desde AAAA-MM-DD]   (solo la primera vez, para cargar historial)
Solo usa la biblioteca estándar de Python 3.9+.
"""
import gzip, json, os, sys, time, urllib.request, collections
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "radar_estado.json.gz")
OUT = os.path.join(HERE, "docs", "data", "radar.json")
RPC = os.environ.get("ELYSIUM_RPC", "https://rpc.elysium.kinetiq.xyz")

TOPIC_TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TOPIC_INIT = "0xdd466e674ea557f56295e2d0218a125ea4b4f0f6f3307b95f85e6110838d6438"   # Uniswap v4 Initialize
TOPIC_MODLIQ = "0xf208f4912782fd25c7f114ca3723a2d5dd6f3bcc3ac8db5af63baa85f711d5ec"  # Uniswap v4 ModifyLiquidity
ZERO32 = "0x" + "0" * 64
ZERO = "0x" + "0" * 40
DEAD = "0x000000000000000000000000000000000000dead"
WHYPE = "0xba876237b0f021a6c6d852d6c26e107997cc5e81"
USDC = "0xb47c4c8f73f009cc0c0d3f92b388d13e293f0b65"
BASES = {ZERO, WHYPE, USDC}
POSM = "0x1d1c51b9d07fd27d36412a2b66cc23d19eb3e518"  # Uniswap v4 Positions NFT (pools creados a mano)

# Nombres conocidos de los contratos por los que se crean los pools. Los que no estén acá
# se muestran por su dirección abreviada.
LABELS = {
    POSM: "Uniswap v4 (direct)",
    "0x38d3ef3a06d18fa3286fb5deafe611be725fcd15": "Montra",
    "0x9c73d179b2911e89a4edc47cfd78765990bc6761": "Eleos",
    "0x63f6a8a8d0257c0363251a50cde8a8b1046e4d19": "Ascend",
}

TRACK_DAYS = 8          # días que se sigue cada token
FREEZE_H = 25           # horas a partir de las que se cierra la cohorte de un token
SERIAL = 5              # lanzamientos en 7 días a partir de los que un creador es "en serie"
ADDR_CHUNK = 100
WORKERS = int(os.environ.get("RADAR_WORKERS", "4"))
POOL = ThreadPoolExecutor(max_workers=WORKERS)


# ------------------------------------------------------------------ RPC
CALLS = [0]


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for i in range(7):
        CALLS[0] += 1
        try:
            req = urllib.request.Request(RPC, body, {"content-type": "application/json", "user-agent": "pulso-elysium-radar/0.1"})
            out = json.load(urllib.request.urlopen(req, timeout=90))
            if "error" in out:
                msg = str(out["error"]).lower()
                if "rate" in msg or "429" in msg or "too many" in msg:
                    time.sleep(2 * (i + 1)); continue
                raise RuntimeError(out["error"])
            return out["result"]
        except RuntimeError:
            raise
        except Exception:
            time.sleep(2 * (i + 1))
    raise SystemExit("El RPC no responde: " + method)


def get_logs(frm, to, topics, address=None):
    """getLogs con partición automática cuando el rango devuelve demasiados resultados."""
    out, a, span = [], frm, to - frm + 1
    step = span
    while a <= to:
        b = min(a + step - 1, to)
        q = {"fromBlock": hex(a), "toBlock": hex(b), "topics": topics}
        if address:
            q["address"] = address
        try:
            r = rpc("eth_getLogs", [q])
        except RuntimeError:
            if step <= 50:
                raise
            step //= 4; continue
        if len(r) >= 10000 and step > 50:
            step //= 4; continue
        out += r
        a = b + 1
        step = min(step * 2, span)
    return out


def block_ts(n):
    return int(rpc("eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)


def find_block(ts, lo, hi):
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if block_ts(mid) < ts: lo = mid
        else: hi = mid
    return hi


def erc20_text(addr, selector):
    try:
        r = rpc("eth_call", [{"to": addr, "data": selector}, "latest"])
        b = bytes.fromhex(r[2:])
        if len(b) >= 64:
            n = int.from_bytes(b[32:64], "big")
            s = b[64:64 + n].decode("utf8", "replace")
        else:
            s = b.rstrip(b"\0").decode("utf8", "replace")
        s = "".join(ch for ch in s if ch.isprintable()).strip()
        return s[:32] or None
    except Exception:
        return None


def h2i(x):
    return int(x, 16) if x and x != "0x" else 0


# ------------------------------------------------------------------ estado
def load_state():
    if os.path.exists(STATE):
        with gzip.open(STATE, "rt") as f:
            return json.load(f)
    return None


def save_state(st):
    tmp = STATE + ".tmp"
    with gzip.open(tmp, "wt") as f:
        json.dump(st, f, separators=(",", ":"))
    os.replace(tmp, STATE)


def label(via):
    if via in LABELS:
        return LABELS[via]
    return via[:6] + "…" + via[-4:]


# ------------------------------------------------------------------ proceso
def process(st, frm, to, t_frm, t_to):
    bph = (to - frm) / max(1, (t_to - t_frm)) * 3600 if to > frm else st["bph"]
    st["bph"] = bph = 0.8 * st.get("bph", bph) + 0.2 * bph if st.get("bph") else bph
    ts_of = lambda b: int(t_frm + (b - frm) * (t_to - t_frm) / max(1, to - frm))

    # 1) emisiones nuevas (mint): sirven para distinguir tokens nuevos de tokens viejos
    rm = st["recent_mints"]
    for l in get_logs(frm, to, [TOPIC_TRANSFER, ZERO32]):
        if len(l["topics"]) != 3:
            continue
        tok = l["address"]; b = h2i(l["blockNumber"])
        if tok in st["tokens"] or tok in st["old"]:
            continue
        e = rm.setdefault(tok, [0, b, b])
        e[0] += 1; e[2] = b
        if e[0] > 3:
            st["old"][tok] = 1; rm.pop(tok, None)
    horizon = to - int(6 * bph)
    for tok in [t for t, e in rm.items() if e[2] < horizon]:
        rm.pop(tok)

    # 2) pools nuevos: registran un token si es nuevo de verdad
    new_tokens = []
    inits = get_logs(frm, to, [TOPIC_INIT])
    need = []
    for l in inits:
        c0 = "0x" + l["topics"][2][-40:]; c1 = "0x" + l["topics"][3][-40:]
        tok = c1 if (c0 in BASES and c1 not in BASES) else c0 if (c1 in BASES and c0 not in BASES) else None
        if tok and tok not in st["tokens"] and tok not in st["old"] and tok in rm:
            need.append(l["transactionHash"])
    txs = dict(zip(need, POOL.map(lambda h: rpc("eth_getTransactionByHash", [h]), need)))
    for l in inits:
        c0 = "0x" + l["topics"][2][-40:]; c1 = "0x" + l["topics"][3][-40:]
        if c0 in BASES and c1 not in BASES: tok = c1
        elif c1 in BASES and c0 not in BASES: tok = c0
        else: continue
        pid = l["topics"][1]; b = h2i(l["blockNumber"])
        hooks = "0x" + l["data"][2:][128 + 24:192]
        st["pms"][l["address"]] = 1
        if tok in st["tokens"]:
            t = st["tokens"][tok]
            if pid not in t["pools"]:
                t["pools"].append(pid); t["ex"] = sorted(set(t["ex"]) | {hooks})
                st["pools"][pid] = tok
            continue
        if tok in st["old"] or tok not in rm:
            continue
        tx = txs.get(l["transactionHash"]) or rpc("eth_getTransactionByHash", [l["transactionHash"]])
        via = tx.get("to") or ZERO
        st["tokens"][tok] = {
            "lb": b, "lt": ts_of(b), "via": via, "cr": tx["from"], "pools": [pid], "ex": sorted({hooks, via, l["address"]}),
            "mb": rm[tok][1], "n": 0, "nt": 0, "lastb": b, "hb": {}, "bal": {}, "liq": [0, 0], "frozen": False,
        }
        st["pools"][pid] = tok
        new_tokens.append(tok)
        rm.pop(tok, None)

    # tokens registrados en este tramo pero emitidos antes: se completan sus transferencias previas
    for tok in new_tokens:
        t = st["tokens"][tok]
        if t["mb"] < frm:
            apply_transfers(st, get_logs(t["mb"], frm - 1, [TOPIC_TRANSFER], tok), bph)

    # 3) transferencias de los tokens seguidos y activos
    active = [tok for tok, t in st["tokens"].items() if not t.get("dormant")]
    chunks = [active[i:i + ADDR_CHUNK] for i in range(0, len(active), ADDR_CHUNK)]
    for res in POOL.map(lambda c: get_logs(frm, to, [TOPIC_TRANSFER], c), chunks):
        apply_transfers(st, res, bph)

    # 4) liquidez agregada y retirada en sus pools
    for l in get_logs(frm, to, [TOPIC_MODLIQ]):
        tok = st["pools"].get(l["topics"][1])
        if not tok or tok not in st["tokens"]:
            continue
        d = l["data"][2:]
        delta = int(d[128:192], 16)
        if delta >= 2 ** 255:
            delta -= 2 ** 256
        liq = st["tokens"][tok]["liq"]
        liq[0 if delta > 0 else 1] += abs(delta)
    return bph


def apply_transfers(st, logs, bph):
    for l in logs:
        if len(l["topics"]) != 3 or len(l["data"]) < 66:
            continue
        t = st["tokens"].get(l["address"])
        if not t:
            continue
        f = "0x" + l["topics"][1][-40:]; to = "0x" + l["topics"][2][-40:]; v = int(l["data"][2:66], 16)
        b = h2i(l["blockNumber"])
        t["n"] += 1
        pms = st["pms"]
        trade = f in pms or to in pms          # compra o venta contra un pool
        if trade:
            t["lastb"] = max(t["lastb"], b)
            hr = int((b - t["lb"]) / bph) if b >= t["lb"] else 0
            if hr < 48 and not t["frozen"]:
                t["hb"][str(hr)] = t["hb"].get(str(hr), 0) + 1
            ah = str(int(b / bph))
            rec = t.setdefault("rec", {})
            rec[ah] = rec.get(ah, 0) + 1
            ex = set(t["ex"]) | {ZERO, DEAD, POSM}
            if f in pms and to not in ex:
                t["nt"] += 1                   # compra: el token sale del pool hacia una billetera
        bal = t.setdefault("bal", {})
        if f != ZERO:
            bal[f] = str(int(bal.get(f, "0")) - v)
        bal[to] = str(int(bal.get(to, "0")) + v)


def finalize(st, latest, now_ts):
    bph = st["bph"]
    day_of = lambda ts: datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
    pms = set(st["pms"])
    for tok in list(st["tokens"]):
        t = st["tokens"][tok]
        age_h = (latest - t["lb"]) / bph
        if not t["frozen"] and age_h >= FREEZE_H:
            traded = t["nt"] > 0
            alive24 = sum(t["hb"].get(str(h), 0) for h in range(18, 24)) >= 3
            life_h = (t["lastb"] - t["lb"]) / bph
            died2 = traded and life_h < 2
            if t["lt"] >= st["since"]:
                c = st["cohorts"].setdefault(day_of(t["lt"]), {})
                for key in ("ALL", t["via"]):
                    e = c.setdefault(key, [0, 0, 0, 0])
                    e[0] += 1; e[1] += traded; e[2] += died2; e[3] += alive24
            t["frozen"] = True; t["life"] = round(life_h, 2); t["traded"] = traded; t["alive24"] = alive24
            t.pop("hb", None)
        cur = int(latest / bph)
        if t.get("rec"):
            t["rec"] = {k: v for k, v in t["rec"].items() if int(k) > cur - 7}
        if t["frozen"] and (latest - t["lastb"]) / bph > 48:
            t["dormant"] = True
            t.pop("bal", None)
        if age_h > TRACK_DAYS * 24:
            for pid in t["pools"]:
                st["pools"].pop(pid, None)
            st["tokens"].pop(tok)
    # cohortes viejas fuera
    cut = day_of(now_ts - 60 * 86400)
    for d in [d for d in st["cohorts"] if d < cut]:
        st["cohorts"].pop(d)


def concentration(t, pms):
    bal = t.get("bal") or {}
    ex = set(t["ex"]) | {ZERO, DEAD, POSM} | pms
    holders = sorted((int(v) for k, v in bal.items() if k not in ex and int(v) > 0), reverse=True)
    held = sum(holders)
    if not held:
        return 0, 0
    return round(sum(holders[:10]) / held * 100, 1), len(holders)


def build_output(st, latest, now_ts):
    bph = st["bph"]
    pms = set(st["pms"])
    toks = st["tokens"]
    day_of = lambda ts: datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")

    # creadores en serie (7 días)
    week = [t for t in toks.values() if now_ts - t["lt"] <= 7 * 86400]
    by_cr = collections.Counter(t["cr"] for t in week)
    serial = {c for c, n in by_cr.items() if n >= SERIAL}

    last24 = [(k, t) for k, t in toks.items() if now_ts - t["lt"] <= 86400]
    cur = int(latest / bph)
    recent = lambda t: sum(v for k, v in (t.get("rec") or {}).items() if int(k) > cur - 6)
    active_now = sum(1 for t in toks.values() if now_ts - t["lt"] >= 86400 and recent(t) >= 3)

    # cohortes completas por día
    days = []
    for d in sorted(st["cohorts"]):
        day_end = int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()) + 86400
        if day_end + FREEZE_H * 3600 > now_ts:
            continue
        e = st["cohorts"][d].get("ALL")
        if not e or not e[0]:
            continue
        days.append({"dia": d, "lanzamientos": e[0], "nunca_operados_pct": round((e[0] - e[1]) / e[0] * 100, 1),
                     "murieron_2h_pct": round(e[2] / e[0] * 100, 1), "activos_24h_pct": round(e[3] / e[0] * 100, 1)})
    days = days[-14:]

    # por launchpad, últimos 7 días completos
    agg = collections.defaultdict(lambda: [0, 0, 0, 0])
    last7 = {x["dia"] for x in days[-7:]}
    for d in last7:
        for via, e in st["cohorts"][d].items():
            if via == "ALL":
                continue
            a = agg[via]
            for i in range(4): a[i] += e[i]
    lives = collections.defaultdict(list)
    for t in toks.values():
        if t.get("frozen") and t.get("traded"):
            lives[t["via"]].append(t["life"])
    pads = []
    other = [0, 0, 0, 0]
    for via, e in list(agg.items()):
        if e[0] < 100:
            for i in range(4): other[i] += e[i]
            agg.pop(via)
            lives["otros"].extend(lives.get(via, []))
    if other[0]:
        agg["otros"] = other
    for via, e in sorted(agg.items(), key=lambda kv: (kv[0] == "otros", -kv[1][0])):
        lv = sorted(lives.get(via, [])) or [0]
        pads.append({"contrato": "" if via == "otros" else via, "nombre": "otros" if via == "otros" else label(via), "lanzamientos": e[0],
                     "nunca_operados_pct": round((e[0] - e[1]) / e[0] * 100, 1),
                     "activos_24h_pct": round(e[3] / e[0] * 100, 1),
                     "vida_mediana_min": round(lv[len(lv) // 2] * 60)})

    # lista: los lanzamientos de las últimas 24 h con más movimiento
    cache = st.setdefault("names", {})
    rows = []
    for tok, t in sorted(last24, key=lambda kt: (-recent(kt[1]), -kt[1]["nt"]))[:15]:
        if tok not in cache:
            cache[tok] = [erc20_text(tok, "0x95d89b41"), erc20_text(tok, "0x06fdde03")]
        sym, name = cache[tok]
        top10, holders = concentration(t, pms)
        liq_added, liq_removed = t["liq"]
        pulled = liq_added > 0 and liq_removed / liq_added >= 0.8
        idle_h = round((latest - t["lastb"]) / bph, 1)
        flags = []
        if t["cr"] in serial: flags.append("serial_creator")
        if holders >= 10 and top10 >= 70: flags.append("concentrated")
        if pulled: flags.append("liquidity_removed")
        if idle_h >= 1: flags.append("inactive")
        rows.append({"token": tok, "simbolo": sym, "nombre": name, "launchpad": label(t["via"]),
                     "edad_h": round((now_ts - t["lt"]) / 3600, 1), "transferencias": t["n"], "transferencias_6h": recent(t), "tenedores": holders,
                     "top10_pct": top10, "lanzamientos_creador_7d": by_cr[t["cr"]], "sin_movimiento_h": idle_h, "senales": flags})
    for tok in [k for k in cache if k not in toks]:
        cache.pop(tok)

    week_n = len(week) or 1
    out = {
        "actualizado_utc": datetime.fromtimestamp(now_ts, timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "seguimiento_desde": datetime.fromtimestamp(st["since"], timezone.utc).strftime("%Y-%m-%d"),
        "resumen": {
            "lanzamientos_24h": len(last24),
            "activos_ahora": active_now,
            "nunca_operados_24h_pct": round(sum(1 for k, t in last24 if now_ts - t["lt"] >= 3600 and t["nt"] == 0)
                                            / max(1, sum(1 for k, t in last24 if now_ts - t["lt"] >= 3600)) * 100, 1),
            "creadores_en_serie_7d": len(serial),
            "pct_lanzamientos_de_creadores_en_serie_7d": round(sum(n for c, n in by_cr.items() if c in serial) / week_n * 100, 1),
            "lanzamientos_7d": len(week),
        },
        "por_dia": days,
        "por_launchpad": pads,
        "tokens": rows,
    }
    if days:
        out["resumen"]["ultimo_dia"] = days[-1]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


def main():
    t0 = time.time()
    latest = h2i(rpc("eth_blockNumber", []))
    now_ts = block_ts(latest)
    st = load_state()
    if st is None:
        desde = None
        if "--desde" in sys.argv:
            desde = sys.argv[sys.argv.index("--desde") + 1]
        since = int(datetime.strptime(desde, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()) if desde else now_ts - 2 * 3600
        start = find_block(since - 3 * 3600, 1, latest)   # 3 h antes, para ver las emisiones previas
        st = {"since": since, "last_block": start - 1, "last_ts": block_ts(start - 1), "bph": 0, "recent_mints": {}, "old": {},
              "tokens": {}, "pools": {}, "pms": {}, "cohorts": {}, "names": {}}
        print("Primera ejecución: historial desde", datetime.fromtimestamp(since, timezone.utc), "bloque", start)

    # se procesa en tramos de ~1 hora para que la carga inicial avance de a poco
    frm = st["last_block"] + 1
    step = int(st["bph"] or 18000)
    while frm <= latest:
        to = min(frm + step - 1, latest)
        t_to = block_ts(to)
        process(st, frm, to, st["last_ts"], t_to)
        st["last_block"], st["last_ts"] = to, t_to
        finalize(st, to, t_to)
        frm = to + 1
        steps = st.get("_steps", 0) + 1
        st["_steps"] = steps
        if steps % 6 == 0:
            save_state(st)
        if time.time() - t0 > 1200:
            save_state(st); print("Corte por tiempo; sigue en la próxima ejecución"); break
        if os.environ.get("RADAR_VERBOSE"):
            print(datetime.fromtimestamp(t_to, timezone.utc).strftime("%m-%d %H:%M"), "tokens", len(st["tokens"]), "llamadas", CALLS[0], flush=True)
    save_state(st)
    out = build_output(st, st["last_block"], st["last_ts"])
    save_state(st)
    print("Radar listo:", out["resumen"], "| llamadas", CALLS[0], "| %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
