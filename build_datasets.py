#!/usr/bin/env python3
"""Convierte data.json (salida de indexer.py) en las tablas que lee el tablero."""
import json, os
from datetime import datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__))
s = json.load(open(os.path.join(HERE, "data.json")))
out = os.environ.get("OUT") or os.path.join(HERE, "docs", "data"); os.makedirs(out, exist_ok=True)
code = open(os.path.join(HERE, "indexer.py")).read()
code2 = open(os.path.abspath(__file__)).read()
snap = s["snapshots"][-1]; ext = s["external"]; meta = s["meta"]
price = ext.get("hype_usd_by_day", {}); tvl = ext.get("tvl_by_day", {})
days = sorted(s["days"])

# ---- tabla diaria
bridge_by_day = {}
for sn in s["snapshots"]:
    if sn.get("bridge_hype") is not None:
        bridge_by_day[datetime.fromtimestamp(sn["ts"], timezone.utc).strftime("%Y-%m-%d")] = round(sn["bridge_hype"], 2)
rows = []; prev = 0.0
for d in days:
    v = s["days"][d]; p = price.get(d) or snap["hype_usd"]
    fee = v["fees_cum_hype"] - prev; prev = v["fees_cum_hype"]
    w = s["withdrawals"]["by_day"].get(d, {"count": 0, "hype": 0})
    rows.append({"dia": d, "parcial": not v["closed"], "bloque_cierre": v["block"],
                 "ingresos_hype": round(fee, 4), "ingresos_usd": round(fee * p, 2),
                 "ingresos_acum_hype": round(v["fees_cum_hype"], 4),
                 "usdc_en_red": round(v["usdc_supply"], 2), "whype_en_red": round(v["whype_supply"], 2),
                 "retiros_cantidad": w["count"], "retiros_hype": round(w["hype"], 2),
                 "tvl_usd": tvl.get(d), "hype_usd": round(p, 4), "hype_en_bridge": bridge_by_day.get(d)})
daily = [r for r in rows if r["dia"] >= "2026-11-05"]
closed = [r for r in daily if not r["parcial"]]
src = [{"label": "indexer.py", "value": code, "type": "code", "lang": "python"},
       {"label": "build_datasets.py", "value": code2, "type": "code", "lang": "python"},
       {"label": "Fuentes", "value": "RPC publico de Elysium (chain 99901), RPC publico de HyperEVM (chain 999), API de DefiLlama (TVL, precios, volumen DEX)"}]
json.dump({"rows": daily, "meta": src}, open(os.path.join(out, "diario.json"), "w"), ensure_ascii=False)

# ---- resumen (una fila)
last, before = closed[-1], closed[-2]
peak = max(closed, key=lambda r: r["ingresos_usd"])
run = closed[-3:]; run_usd = sum(r["ingresos_usd"] for r in run) / len(run)
cum_usd = sum(r["ingresos_usd"] for r in rows)
bridge_usd = snap["bridge_hype"] * snap["hype_usd"]; usdc = rows[-1]["usdc_en_red"]
bridged = bridge_usd + usdc; tvl_now = snap["tvl_usd"]
unlock_usd = meta["kntq_unlock"]["monthly_tokens"] * snap["kntq_usd"]
buy_month = run_usd * meta["revenue_split"]["recompra_kntq"] * 30
pub = [r for r in rows if r["dia"] >= meta["public_mainnet_day"]]
resumen = {
 "actualizado_utc": datetime.fromtimestamp(snap["ts"], timezone.utc).strftime("%Y-%m-%d %H:%M"),
 "ultimo_dia_cerrado": last["dia"],
 "ingresos_ultimo_dia_usd": last["ingresos_usd"], "ingresos_dia_previo_usd": before["ingresos_usd"],
 "cambio_ingresos_pct": round((last["ingresos_usd"] / before["ingresos_usd"] - 1) * 100, 1),
 "dia_pico": peak["dia"], "ingresos_pico_usd": peak["ingresos_usd"],
 "caida_desde_pico_pct": round((last["ingresos_usd"] / peak["ingresos_usd"] - 1) * 100, 1),
 "ingresos_acum_hype": round(rows[-1]["ingresos_acum_hype"], 2), "ingresos_acum_usd": round(cum_usd, 0),
 "ritmo_diario_usd": round(run_usd, 0),
 "hype_en_bridge": round(snap["bridge_hype"], 0), "hype_usd": round(snap["hype_usd"], 2),
 "hype_en_bridge_usd": round(bridge_usd, 0), "usdc_en_red": round(usdc, 0),
 "capital_puenteado_usd": round(bridged, 0), "tvl_usd": round(tvl_now, 0),
 "pct_en_protocolos": round(tvl_now / bridged * 100, 1), "capital_ocioso_usd": round(bridged - tvl_now, 0),
 "whype_en_red": round(rows[-1]["whype_en_red"], 0),
 "pct_hype_envuelto": round(rows[-1]["whype_en_red"] / snap["bridge_hype"] * 100, 1),
 "retiros_hype_desde_mainnet": round(sum(r["retiros_hype"] for r in pub), 0),
 "retiros_cantidad_desde_mainnet": sum(r["retiros_cantidad"] for r in pub),
 "retiros_ultimo_dia_hype": last["retiros_hype"],
 "kntq_usd": round(snap["kntq_usd"], 4), "desbloqueo_mensual_kntq": meta["kntq_unlock"]["monthly_tokens"],
 "primer_desbloqueo": meta["kntq_unlock"]["first"], "desbloqueo_mensual_usd": round(unlock_usd, 0),
 "recompra_mensual_estimada_usd": round(buy_month, 0),
 "cobertura_recompra_pct": round(buy_month / unlock_usd * 100, 1),
 "gas_gwei": snap["gas_gwei"], "tiempo_bloque_ms": round(snap["block_time_s"] * 1000),
 "volumen_dex_24h_usd": round(snap.get("dex_24h_usd") or 0, 0),
}
json.dump({"rows": [resumen], "meta": src}, open(os.path.join(out, "resumen.json"), "w"), ensure_ascii=False)

# ---- reparto teorico de ingresos acumulados
nombres = {"recompra_kntq": "Recompra y quema de KNTQ", "builders": "Builders", "tesoreria": "Tesorería de Kinetiq"}
rep = [{"destino": nombres[k], "porcentaje": int(v * 100), "hype": round(resumen["ingresos_acum_hype"] * v, 1),
        "usd": round(cum_usd * v, 0)} for k, v in meta["revenue_split"].items()]
json.dump({"rows": rep, "meta": src}, open(os.path.join(out, "reparto.json"), "w"), ensure_ascii=False)

# ---- riesgos de la red: supuestos de confianza leidos de los contratos en HyperEVM
r = snap.get("rollup", {})
blk = r.get("confirm_period_blocks") or 0
horas = round(blk / 3600, 1)  # HyperEVM produce ~1 bloque por segundo
val = r.get("validators")
thr = r.get("upgrade_threshold"); own = r.get("upgrade_owners")
multi = f"{thr} de {own} firmas" if r.get("upgrade_multisig") and thr and own else ("multisig" if r.get("upgrade_multisig") else "sin confirmar")
riesgos = [
 {"id": "secuenciador", "aspecto": "Ordenamiento (secuenciador)", "valor": "1 secuenciador",
  "nivel": "medio", "lectura": "Kinetiq / Conduit",
  "detalle": "Una sola entidad ordena todas las transacciones. Si se cae, la red se frena; podría demorar o censurar transacciones, y no hay protección contra MEV (Timeboost todavía no está activo)."},
 {"id": "validacion", "aspecto": "Validación del estado", "valor": (str(val) + " validador" + ("" if val == 1 else "es")) if val is not None else "sin dato",
  "nivel": "alto" if (val or 0) <= 1 or r.get("whitelist_enabled") else "ok", "lectura": "Rollup.getValidators() · validatorWhitelistDisabled()",
  "detalle": "Los validadores son los que pueden impugnar un estado falso de la red. Hoy hay un único validador y la lista está cerrada: la seguridad de los retiros depende de que ese operador sea honesto y no lo comprometan."},
 {"id": "datos", "aspecto": "Disponibilidad de datos", "valor": "Comité (AnyTrust)",
  "nivel": "medio", "lectura": "Documentación de Kinetiq",
  "detalle": "Un comité guarda los datos de las transacciones fuera de HyperEVM. Si el comité no firma, la red vuelve a publicar los datos completos en HyperEVM. Hay que confiar en ese comité."},
 {"id": "actualizaciones", "aspecto": "Actualización de los contratos", "valor": multi,
  "nivel": "medio", "lectura": "UpgradeExecutor · Safe " + "0xc030…61d0",
  "detalle": "El rollup, el bridge y el secuenciador se pueden actualizar. El permiso lo tiene un multisig que exige " + multi + "; no hay un plazo de espera en la cadena, así que un cambio se aplica apenas se junten las firmas."},
 {"id": "retiros", "aspecto": "Plazo de desafío de retiros", "valor": (f"~{horas:g} h" if blk else "sin dato"),
  "nivel": "info", "lectura": "Rollup.confirmPeriodBlocks()",
  "detalle": f"Un retiro de HYPE hacia HyperEVM iniciado ahora puede completarse recién dentro de unas {horas:g} horas ({blk:,} bloques). Es el tiempo durante el cual un validador puede impugnarlo.".replace(",", ".")},
 {"id": "pausa", "aspecto": "Estado operativo", "valor": "En pausa" if r.get("paused") else "Operativo",
  "nivel": "alto" if r.get("paused") else "ok", "lectura": "Rollup.paused()",
  "detalle": "Indica si el rollup está detenido en este momento. Operativo es lo normal."},
]
multi_en = f"{thr} of {own} signatures" if r.get("upgrade_multisig") and thr and own else ("multisig" if r.get("upgrade_multisig") else "unconfirmed")
EN_RISK = {
 "secuenciador": ("Transaction ordering (sequencer)", "1 sequencer",
   "A single party orders every transaction. If it goes down the chain stops; it could delay or censor transactions, and there is no MEV protection yet (Timeboost is not live)."),
 "validacion": ("State validation", (f"{val} validator" + ("" if val == 1 else "s")) if val is not None else "no data",
   "Validators are the ones who can challenge a false chain state. Today there is a single validator and the list is closed: the safety of withdrawals depends on that operator being honest and not compromised."),
 "datos": ("Data availability", "Committee (AnyTrust)",
   "A committee stores transaction data off HyperEVM. If it does not sign, the chain falls back to posting full data on HyperEVM. You have to trust that committee."),
 "actualizaciones": ("Contract upgrades", multi_en,
   "The rollup, bridge and sequencer contracts can be upgraded. The permission is held by a multisig that requires " + multi_en + "; there is no on-chain delay, so a change takes effect as soon as the signatures are collected."),
 "retiros": ("Withdrawal challenge period", (f"~{horas:g} h" if blk else "no data"),
   (f"A HYPE withdrawal to HyperEVM started now can only complete in about {horas:g} hours (" + f"{blk:,}".replace(",", ".") + " blocks). That is the window in which a validator can challenge it.")),
 "pausa": ("Operating status", "Paused" if r.get("paused") else "Operational",
   "Whether the rollup is halted right now. Operational is normal."),
}
for _x in riesgos:
    _x["aspecto_en"], _x["valor_en"], _x["detalle_en"] = EN_RISK[_x["id"]]
    _x["lectura_en"] = "Kinetiq docs" if _x["id"] == "datos" else _x["lectura"]
json.dump({"rows": riesgos, "meta": src}, open(os.path.join(out, "riesgos.json"), "w"), ensure_ascii=False)

# ---- serie horaria del HYPE en el bridge (fotos del indexador)
hor = [{"ts": sn["ts"], "hora_utc": datetime.fromtimestamp(sn["ts"], timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "hype_en_bridge": round(sn["bridge_hype"], 1)} for sn in s["snapshots"] if sn.get("bridge_hype") is not None]
json.dump({"rows": hor, "meta": src}, open(os.path.join(out, "horario.json"), "w"), ensure_ascii=False)
print(len(daily), "dias;", resumen["actualizado_utc"])
