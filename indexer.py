#!/usr/bin/env python3
"""
Pulso Elysium - indexador (etapa 1: salud de la red y flujo de capital)

Lee la red Elysium (chain 99901), su contrato de bridge en HyperEVM (chain 999)
y DefiLlama, y escribe data.json con series diarias y una foto del momento.

Uso:   python3 indexer.py            (actualiza data.json en esta carpeta)
Solo usa la biblioteca estandar de Python 3.9+.
Cada ejecucion agrega una foto nueva y completa los dias que falten.
"""
import json, os, sys, time, urllib.request
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data.json")

ELYSIUM_RPC = os.environ.get("ELYSIUM_RPC", "https://rpc.elysium.kinetiq.xyz")
HYPEREVM_RPC = os.environ.get("HYPEREVM_RPC", "https://rpc.hyperliquid.xyz/evm")

# --- Direcciones (documentacion oficial: elysium.kinetiq.xyz/docs/contract-addresses)
WHYPE = "0xbA876237B0F021A6c6D852d6c26E107997cC5E81"          # Elysium
USDC = "0xb47c4C8F73F009CC0C0d3f92B388d13E293F0B65"           # Elysium
ARBSYS = "0x0000000000000000000000000000000000000064"         # Elysium (retiros)
ARB_OWNER_PUBLIC = "0x000000000000000000000000000000000000006b"
BRIDGE_L1 = "0x503D572157113fAaaD4DbeD2647Bb10b949216B6"      # HyperEVM (custodia HYPE)
ROLLUP_L1 = "0x508C173dFe5F737B3493195Bf785d71fA76fD217"      # HyperEVM
SEQ_INBOX_L1 = "0x7f3Ff53aecB87261206ad3bDc27A88b6D8420fa6"   # HyperEVM

SEL_TOTAL_SUPPLY = "0x18160ddd"
SEL_NETWORK_FEE_ACCOUNT = "0x2d9125e9"
SEL_CONFIRM_PERIOD = "0x2e7acfa6"
SEL_WHITELIST_DISABLED = "0x12ab3d3b"
SEL_GET_VALIDATORS = "0xb7ab4db5"
SEL_BATCH_COUNT = "0x06f13056"
SEL_PAUSED = "0x5c975abb"
TOPIC_L2_TO_L1 = "0x3e7aafa77dbf186b7fd488006beff893744caa3c4f6f299e8a709fa2087374fc"

GENESIS_DAY = "2026-10-19"      # primer bloque de la red
PUBLIC_MAINNET_DAY = "2026-11-09"
LOG_CHUNK = 200_000

# Calendario de desbloqueos de KNTQ (fuente: The Edge Weekly #73 / AirdropAlert; verificar)
KNTQ_UNLOCK = {"first": "2026-11-27", "monthly_tokens": 12_920_000, "months": 24}
REVENUE_SPLIT = {"recompra_kntq": 0.50, "builders": 0.25, "tesoreria": 0.25}


# ---------------------------------------------------------------- utilidades
def _post(url, body, tries=6):
    data = json.dumps(body).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data, {"content-type": "application/json", "user-agent": "pulso-elysium/0.1"})
            out = json.load(urllib.request.urlopen(req, timeout=40))
            if isinstance(out, dict) and "error" in out:
                msg = str(out["error"].get("message", "")).lower()
                if "rate" in msg:
                    time.sleep(1.5 * (i + 1)); continue
                raise RuntimeError(out["error"])
            return out["result"]
        except RuntimeError:
            raise
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))
    raise RuntimeError("limite de consultas del RPC: " + url)


def rpc(url, method, params):
    return _post(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})


def get_json(url):
    try:
        req = urllib.request.Request(url, headers={"user-agent": "pulso-elysium/0.1"})
        return json.load(urllib.request.urlopen(req, timeout=40))
    except Exception as e:
        print("  aviso: no se pudo leer", url, "-", e, file=sys.stderr)
        return None


def h2i(x):
    return int(x, 16) if x and x != "0x" else 0


def call(url, to, data, block="latest"):
    return rpc(url, "eth_call", [{"to": to, "data": data}, block])


def day_str(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def day_end_ts(day):
    d = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
    return int(d.timestamp())


# ---------------------------------------------------------------- bloques
_ts_cache = {}


def block_ts(n):
    if n not in _ts_cache:
        _ts_cache[n] = h2i(rpc(ELYSIUM_RPC, "eth_getBlockByNumber", [hex(n), False])["timestamp"])
    return _ts_cache[n]


def last_block_before(ts, lo, hi):
    """Ultimo bloque con timestamp < ts, buscando entre lo y hi."""
    if block_ts(hi) < ts:
        return hi
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if block_ts(mid) < ts:
            lo = mid
        else:
            hi = mid
    return lo


# ---------------------------------------------------------------- principal
def main():
    state = {"days": {}, "snapshots": [], "withdrawals": {"last_block": 0, "by_day": {}}}
    if os.path.exists(DATA):
        with open(DATA) as f:
            state.update(json.load(f))

    latest = h2i(rpc(ELYSIUM_RPC, "eth_blockNumber", []))
    now = block_ts(latest)
    today = day_str(now)
    print("Elysium bloque", latest, "-", today)

    fee_account = "0x" + call(ELYSIUM_RPC, ARB_OWNER_PUBLIC, SEL_NETWORK_FEE_ACCOUNT)[-40:]

    # 1) series diarias leidas del historial de la cadena
    days = state["days"]
    d = datetime.strptime(GENESIS_DAY, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    lo = 1
    while d.strftime("%Y-%m-%d") <= today:
        day = d.strftime("%Y-%m-%d")
        closed = day < today
        if not (closed and days.get(day, {}).get("closed")):
            blk = last_block_before(day_end_ts(day), lo, latest) if closed else latest
            tag = hex(blk)
            days[day] = {
                "block": blk,
                "closed": closed,
                "fees_cum_hype": h2i(rpc(ELYSIUM_RPC, "eth_getBalance", [fee_account, tag])) / 1e18,
                "usdc_supply": h2i(call(ELYSIUM_RPC, USDC, SEL_TOTAL_SUPPLY, tag)) / 1e6,
                "whype_supply": h2i(call(ELYSIUM_RPC, WHYPE, SEL_TOTAL_SUPPLY, tag)) / 1e18,
            }
            print("  dia", day, "bloque", blk)
        lo = days[day]["block"]
        d += timedelta(days=1)

    # 2) retiros hacia HyperEVM (eventos L2ToL1Tx de ArbSys)
    w = state["withdrawals"]
    start = w["last_block"] + 1
    bounds = sorted((v["block"], k) for k, v in days.items())

    def day_of_block(b):
        for blk, k in bounds:
            if b <= blk:
                return k
        return today

    while start <= latest:
        end = min(start + LOG_CHUNK - 1, latest)
        logs = rpc(ELYSIUM_RPC, "eth_getLogs", [{"fromBlock": hex(start), "toBlock": hex(end),
                                                  "address": ARBSYS, "topics": [TOPIC_L2_TO_L1]}])
        for lg in logs:
            data = lg["data"][2:]
            value = int(data[64 * 4:64 * 5], 16) / 1e18     # callvalue = HYPE nativo retirado
            k = day_of_block(h2i(lg["blockNumber"]))
            e = w["by_day"].setdefault(k, {"count": 0, "hype": 0.0})
            e["count"] += 1
            e["hype"] += value
        start = end + 1
    w["last_block"] = latest

    # 3) foto del momento
    snap = {"ts": now, "block": latest, "fee_account": fee_account}
    snap["gas_gwei"] = h2i(rpc(ELYSIUM_RPC, "eth_gasPrice", [])) / 1e9
    snap["block_time_s"] = (now - block_ts(latest - 5000)) / 5000
    try:
        snap["bridge_hype"] = h2i(rpc(HYPEREVM_RPC, "eth_getBalance", [BRIDGE_L1, "latest"])) / 1e18
        time.sleep(1.2)
        vals = call(HYPEREVM_RPC, ROLLUP_L1, SEL_GET_VALIDATORS)
        time.sleep(1.2)
        snap["rollup"] = {
            "validators": int(vals[2 + 64:2 + 128], 16),
            "whitelist_enabled": h2i(call(HYPEREVM_RPC, ROLLUP_L1, SEL_WHITELIST_DISABLED)) == 0,
        }
        time.sleep(1.2)
        snap["rollup"]["confirm_period_blocks"] = h2i(call(HYPEREVM_RPC, ROLLUP_L1, SEL_CONFIRM_PERIOD))
        time.sleep(1.2)
        snap["rollup"]["paused"] = h2i(call(HYPEREVM_RPC, ROLLUP_L1, SEL_PAUSED)) == 1
        time.sleep(1.2)
        snap["rollup"]["batches"] = h2i(call(HYPEREVM_RPC, SEQ_INBOX_L1, SEL_BATCH_COUNT))
    except Exception as e:
        print("  aviso: HyperEVM no respondio -", e, file=sys.stderr)

    # 4) fuentes externas (DefiLlama)
    px = get_json("https://coins.llama.fi/prices/current/coingecko:hyperliquid,coingecko:kinetiq")
    if px:
        snap["hype_usd"] = px["coins"].get("coingecko:hyperliquid", {}).get("price")
        snap["kntq_usd"] = px["coins"].get("coingecko:kinetiq", {}).get("price")
    g0 = int(datetime.strptime(GENESIS_DAY, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    span = (datetime.strptime(today, "%Y-%m-%d") - datetime.strptime(GENESIS_DAY, "%Y-%m-%d")).days + 1
    hist = get_json(f"https://coins.llama.fi/chart/coingecko:hyperliquid?start={g0}&span={span}&period=1d")
    ext = state.setdefault("external", {})
    if hist:
        ext["hype_usd_by_day"] = {day_str(p["timestamp"]): p["price"] for p in hist["coins"]["coingecko:hyperliquid"]["prices"]}
    tvl = get_json("https://api.llama.fi/v2/historicalChainTvl/Elysium%20Kinetiq")
    if isinstance(tvl, list):
        ext["tvl_by_day"] = {day_str(p["date"]): p["tvl"] for p in tvl}
    chains = get_json("https://api.llama.fi/v2/chains")
    if chains:
        snap["tvl_usd"] = next((c["tvl"] for c in chains if c.get("chainId") == 99901), None)
    dex = get_json("https://api.llama.fi/overview/dexs/Elysium%20Kinetiq?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true")
    if dex:
        snap["dex_24h_usd"] = dex.get("total24h")
        snap["dex_by_protocol"] = sorted(
            ({"name": p["name"], "vol_24h": p.get("total24h") or 0} for p in dex.get("protocols", [])),
            key=lambda p: -p["vol_24h"])[:8]
    fees = get_json("https://api.llama.fi/overview/fees/Elysium%20Kinetiq?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true")
    if fees and fees.get("totalDataChart"):
        ext["llama_app_fees_by_day"] = {day_str(t): v for t, v in fees["totalDataChart"]}

    state["snapshots"].append(snap)
    state["snapshots"] = state["snapshots"][-2000:]
    state["meta"] = {
        "updated_ts": now, "genesis_day": GENESIS_DAY, "public_mainnet_day": PUBLIC_MAINNET_DAY,
        "kntq_unlock": KNTQ_UNLOCK, "revenue_split": REVENUE_SPLIT, "fee_account": fee_account,
    }
    with open(DATA, "w") as f:
        json.dump(state, f, indent=1)
    print("Listo:", DATA)


if __name__ == "__main__":
    main()
