#!/usr/bin/env python3
"""P0 数据刷新：一次性刷新所有过期数据文件"""
import sys, json, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "scripts"))

TZ = timezone(timedelta(hours=8))
now = lambda: datetime.now(TZ).isoformat(timespec="seconds")

refresh_log = []

def log(msg, ok=True):
    status = "✅" if ok else "❌"
    print(f"{status} {msg}")
    refresh_log.append({"msg": msg, "ok": ok, "time": now()})

# ─── 1. source_snapshot_BTCUSDT + XAUUSD ───
print("=== 1. 刷新 source_snapshot ===")
try:
    from trading_system import source_snapshot
    # BTC
    btc_snap = source_snapshot("BTCUSDT")
    if btc_snap and btc_snap.get("quality"):
        # Already written by source_snapshot()
        log(f"BTC snapshot: quality={btc_snap.get('quality')}, price={btc_snap.get('price')}")
    else:
        log("BTC snapshot returned empty", ok=False)
    # XAU
    xau_snap = source_snapshot("XAUUSD")
    if xau_snap and xau_snap.get("quality"):
        log(f"XAU snapshot: quality={xau_snap.get('quality')}, price={xau_snap.get('xau')}")
    else:
        log("XAU snapshot returned empty", ok=False)
except Exception as e:
    log(f"source_snapshot failed: {e}", ok=False)

# ─── 2. protections_state.json ───
print("\n=== 2. 刷新 protections_state ===")
try:
    from risk_constitution import load_protections
    p = load_protections()  # creates default if missing
    (DATA / "protections_state.json").write_text(
        json.dumps(p, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    log(f"protections_state: OK ({type(p).__name__})")
except ImportError:
    try:
        # Fallback: create minimal
        d = {"schema": "protections_v1", "created_at": now(), "protections": {}}
        (DATA / "protections_state.json").write_text(json.dumps(d, indent=2))
        log("protections_state: created minimal default")
    except Exception as e:
        log(f"protections_state failed: {e}", ok=False)
except Exception as e:
    log(f"protections_state failed: {e}", ok=False)

# ─── 3. strategy_governance.json ───
print("\n=== 3. 刷新 strategy_governance ===")
try:
    from trading_system import default_governance
    g = default_governance()
    (DATA / "strategy_governance.json").write_text(
        json.dumps(g, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    log(f"strategy_governance: schema={g.get('schema')}")
except Exception as e:
    log(f"strategy_governance failed: {e}", ok=False)

# ─── 4. strategy_model_stats.json ───
print("\n=== 4. 刷新 strategy_model_stats ===")
try:
    from prediction_tracker import aggregate_stats
    stats = aggregate_stats()
    (DATA / "strategy_model_stats.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    log(f"model_stats: {len(stats)} models")
except Exception as e:
    log(f"model_stats failed: {e}", ok=False)

# ─── 5. btc_signal.json ───
print("\n=== 5. 刷新 btc_signal ===")
try:
    from btc_daemon import write_signal
    # Call with BTCUSDT and current context
    import trading_system as ts
    snap = ts.source_snapshot("BTCUSDT")
    price = snap.get("price") or snap.get("spot") or 0
    zone = "oversold" if price and float(price) < 60000 else "neutral"
    write_signal(zone, price)
    log(f"btc_signal: zone={zone}, price={price}")
except Exception as e:
    log(f"btc_signal failed: {e}", ok=False)

# ─── 6. 验证所有文件新鲜度 ───
print("\n=== 6. 新鲜度验证 ===")
for name in ["source_snapshot_BTCUSDT.json", "source_snapshot_XAUUSD.json",
             "protections_state.json", "strategy_governance.json",
             "strategy_model_stats.json", "btc_signal.json"]:
    path = DATA / name
    if path.exists():
        age_m = (time.time() - path.stat().st_mtime) / 60
        ok = age_m < 5
        log(f"{name}: {age_m:.0f}m old {'✓' if ok else '⚠ >5m'}", ok=ok)
    else:
        log(f"{name}: MISSING", ok=False)

print(f"\n{'='*50}")
print(f"刷新完成: {sum(1 for l in refresh_log if l['ok'])}/{len(refresh_log)} 项成功")
for l in refresh_log:
    print(f"  {'✅' if l['ok'] else '❌'} {l['msg']}")
