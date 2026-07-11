from __future__ import annotations
import json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "tradingview-mcp" / "src" / "cli" / "index.js"
WORK = CLI.parents[3]


def run(*args: str) -> dict:
    cp = subprocess.run(["node", str(CLI), *args], cwd=WORK, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=60)
    if cp.returncode:
        raise RuntimeError(cp.stdout + cp.stderr)
    return json.loads(cp.stdout)


def wait_values(required: set[str], timeout_sec: int = 25) -> dict:
    deadline = time.time() + timeout_sec
    latest: dict = {}
    while time.time() < deadline:
        latest = run("values")
        names = {str(study.get("name")) for study in latest.get("studies", [])}
        if required.issubset(names):
            return latest
        time.sleep(1)
    return latest


def audit_symbol(symbol: str) -> dict:
    run("symbol", symbol)
    out = {"symbol": symbol, "timeframes": {}}
    required = {"SVP+ICT+VWAP+CVD", "Volume Aggregated Spot & Futures"}
    for tf in ("5", "15", "60", "240", "D"):
        run("timeframe", tf)
        state = run("state")
        actual_tf = str(state.get("resolution"))
        tf_ok = actual_tf == tf or (tf == "D" and actual_tf == "1D")
        if state.get("symbol") != symbol or not tf_ok:
            raise RuntimeError(f"chart mismatch: wanted {symbol} {tf}, got {state}")
        values = wait_values(required)
        names = [study.get("name") for study in values.get("studies", [])]
        if not required.issubset(set(map(str, names))):
            raise RuntimeError(f"indicator values incomplete for {symbol} {tf}: {names}")
        out["timeframes"][tf] = {"state": state, "values": values}
        print(f"{symbol} {tf}: studies={names}")
    return out


def main() -> int:
    output = {
        "BTCUSDT": audit_symbol("BINANCE:BTCUSDT.P"),
        "XAUUSD": audit_symbol("OANDA:XAUUSD"),
    }
    target = ROOT / "outputs" / "indicator-audit-20260710" / "tv_five_tf_named_scripts.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
