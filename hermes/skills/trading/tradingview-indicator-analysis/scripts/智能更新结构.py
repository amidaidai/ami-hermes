#!/usr/bin/env python3
"""智能更新结构 v1.0 — 根据刷新队列用纯脚本重算近端监控位。"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path("D:/Hermes agent")
DATA = ROOT / "data"
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import trading_system as ts

LEVELS_FILE = DATA / "monitor_levels.json"
REFRESH_FILE = DATA / "structure_refresh_requests.jsonl"
PLAN_LOG = DATA / "trade_plans.jsonl"


def now() -> datetime:
    return datetime.now().astimezone()


def now_iso() -> str:
    return now().isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows) + ("\n" if rows else ""), encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def plan_id(symbol: str) -> str:
    return f"{symbol}-{now().strftime('%Y%m%d-%H%M')}"


def expires(minutes: int) -> str:
    return (now() + timedelta(minutes=minutes)).isoformat()


def level_conf(grade: str, score: int, label: str, basis: list[str], missing: list[str] | None = None) -> dict[str, Any]:
    return {"grade": grade, "score": score, "label": label, "basis": basis, "missing": missing or ["TradingView成交量复核", "订单流确认"], "method": "智能结构更新v1"}


def round_price(symbol: str, value: float) -> float:
    if symbol.endswith("USDT"):
        return round(value, 2 if value < 10000 else 1)
    if symbol == "XAUUSD":
        return round(value, 1)
    return round(value, 3)


def build_levels(symbol: str, price: float) -> list[dict[str, Any]]:
    if symbol == "XAUUSD":
        return [
            {"name": "R1_reclaim_accept", "display_name": "阻1·近端收复接受位", "level": round_price(symbol, price * 1.0018), "side": "resistance", "type": "breakout_accept", "action": "突破并回踩不破才按延续；高杠杆不追第一根", "priority": "high", "condition": "near_or_breach", "expires": "120m", "valid_until": expires(120), "invalid_if": f"5m close below {round_price(symbol, price * 0.999)}", "status": "active", "level_confidence": level_conf("B", 73, "近端结构", ["金十实时价重算", "近端突破接受", "失效线明确"], ["TradingView复核", "美元/美债事件确认"])},
            {"name": "R2_extension", "display_name": "阻2·上方延伸压力位", "level": round_price(symbol, price * 1.0038), "side": "resistance", "type": "breakout_accept", "action": "只看放量突破后的回踩确认，不追高", "priority": "medium", "condition": "near_or_breach", "expires": "240m", "valid_until": expires(240), "invalid_if": f"15m close below {round_price(symbol, price * 1.001)}", "status": "active", "level_confidence": level_conf("C", 66, "延伸位", ["当前价上方延伸", "用于防追高", "等待复核"], ["TradingView复核", "时段成交确认"])},
            {"name": "S1_vwap_retest", "display_name": "支1·近端回踩确认位", "level": round_price(symbol, price * 0.9982), "side": "support", "type": "vwap_reclaim_filter", "action": "回踩守住才考虑顺势；跌破接受转等待", "priority": "high", "condition": "near_or_breach", "expires": "120m", "valid_until": expires(120), "invalid_if": f"5m close below {round_price(symbol, price * 0.9965)}", "status": "active", "level_confidence": level_conf("B", 72, "近端回踩", ["金十实时价重算", "近端支撑", "失效线明确"], ["TradingView VWAP复核", "美元/美债确认"])},
            {"name": "S2_sweep_reclaim", "display_name": "支2·扫低回收位", "level": round_price(symbol, price * 0.995), "side": "support", "type": "sweep_reclaim", "action": "刺破快速收回才看回收；跌破接受不逆势", "priority": "medium", "condition": "near_or_breach", "expires": "240m", "valid_until": expires(240), "invalid_if": f"15m close below {round_price(symbol, price * 0.992)}", "status": "active", "level_confidence": level_conf("C", 66, "扫损备份", ["下方扫流动性位", "备份支撑", "等待确认"], ["TradingView复核", "时段成交确认"])},
        ]
    # crypto/default
    return [
        {"name": "R1_reclaim_accept", "display_name": "阻1·近端收复接受位", "level": round_price(symbol, price * 1.002), "side": "resistance", "type": "breakout_accept", "action": "突破并回踩不破才考虑顺势；假突破不追", "priority": "high", "condition": "near_or_breach", "expires": "90m", "valid_until": expires(90), "invalid_if": f"5m close below {round_price(symbol, price * 0.998)}", "status": "active", "level_confidence": level_conf("B", 74, "近端结构", ["实时价重算", "突破接受模型", "失效线明确"])},
        {"name": "R2_upper_extension", "display_name": "阻2·上方延伸压力位", "level": round_price(symbol, price * 1.006), "side": "resistance", "type": "breakout_accept", "action": "放量突破后只做回踩确认，不追第一根", "priority": "medium", "condition": "near_or_breach", "expires": "180m", "valid_until": expires(180), "invalid_if": f"15m close below {round_price(symbol, price * 1.001)}", "status": "active", "level_confidence": level_conf("C", 66, "延伸位", ["实时价上方延伸", "用于防追高", "待订单流确认"])},
        {"name": "S1_retest", "display_name": "支1·近端回踩确认位", "level": round_price(symbol, price * 0.998), "side": "support", "type": "retest", "action": "回踩守住才考虑顺势；跌破说明接受失败", "priority": "high", "condition": "near_or_breach", "expires": "120m", "valid_until": expires(120), "invalid_if": f"5m close below {round_price(symbol, price * 0.995)}", "status": "active", "level_confidence": level_conf("B", 73, "近端回踩", ["实时价重算", "近端支撑", "失效线明确"])},
        {"name": "S2_sweep_reclaim", "display_name": "支2·扫流动性回收位", "level": round_price(symbol, price * 0.992), "side": "support", "type": "sweep_reclaim", "action": "刺破后快速收回才看回收；跌破接受不逆势", "priority": "medium", "condition": "near_or_breach", "expires": "1d", "valid_until": expires(24 * 60), "invalid_if": f"15m close below {round_price(symbol, price * 0.988)}", "status": "active", "level_confidence": level_conf("C", 66, "扫损备份", ["实时价下方扫损", "备份支撑", "待CVD确认"])},
    ]


def update_symbol(raw: dict[str, Any], symbol: str, reasons: list[str] | None = None) -> dict[str, Any]:
    block = raw.setdefault("symbols", {}).setdefault(symbol, {})
    price_probe = ts.template_price(symbol)
    price = price_probe.get("price") or block.get("price_at_analysis")
    if not isinstance(price, (int, float)) or price <= 0:
        raise RuntimeError(f"{symbol} 无可用实时价格")
    pid = plan_id(symbol)
    block.update({
        "plan_id": pid,
        "analysis_cycle": "智能更新 · 近端结构重算 · 等5m确认 · 旧位降权",
        "price_at_analysis": float(price),
        "updated": now_iso(),
        "monitor_enabled": True,
        "needs_structure_refresh": False,
        "refresh_reason": "",
        "levels": build_levels(symbol, float(price)),
        "smart_update": {"time": now_iso(), "source": price_probe.get("source"), "quality": price_probe.get("quality"), "confidence": price_probe.get("confidence"), "reasons": reasons or []},
    })
    append_jsonl(PLAN_LOG, {"time": now_iso(), "schema": "trade_plan_v1", "plan_id": pid, "symbol": symbol, "state": "B等待", "score": 7, "model": "智能结构更新", "direction": "等待", "entry": None, "stop": None, "targets": [], "risk_usd": ts.template_risk_limit(symbol), "tags": ["智能更新", "近端结构", "等待确认"], "source": price_probe})
    return block


def pending_symbols(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for row in rows:
        if row.get("status") != "pending" or not row.get("symbol"):
            continue
        out.setdefault(row["symbol"], []).extend(row.get("reasons") or [])
    return out


def main(argv: list[str]) -> None:
    raw = read_json(LEVELS_FILE, {"schema": "monitor_levels_multi_v1", "symbols": {}})
    rows = read_jsonl(REFRESH_FILE)
    targets = argv[1:] or list(pending_symbols(rows))
    if not targets:
        print("无待智能更新品种")
        return
    reasons_by_symbol = pending_symbols(rows)
    updated: list[str] = []
    for symbol in targets:
        update_symbol(raw, symbol, reasons_by_symbol.get(symbol, []))
        updated.append(symbol)
    raw["updated"] = now_iso()
    write_json(LEVELS_FILE, raw)
    for row in rows:
        if row.get("symbol") in updated and row.get("status") == "pending":
            row["status"] = "done"
            row["done_time"] = now_iso()
    write_jsonl(REFRESH_FILE, rows)
    print("智能更新完成：" + "、".join(updated))


if __name__ == "__main__":
    main(sys.argv)
