#!/usr/bin/env python3
"""持仓监测 v1.0 — 自动检测 Binance 合约开仓/平仓，免去手动 成交记录.py。

设计（棠溪要求"真实成交记录更省事"）：
  - 轮询 Binance USDT 合约 positionRisk（签名 API）。
  - 与上轮持仓快照对比，检测三类状态变化：
      新开仓 (0 → 非0)         → ts.mark_trade_opened，风控闸门进入待复盘
      平仓   (非0 → 0)         → 估算已实现盈亏 → ts.record_trade_review 自动复盘
      反手   (多 ↔ 空)         → 先平旧仓复盘，再标记新开仓
  - 状态快照存 data/position_state.json，重启不丢。
  - no_agent 友好：有变化才 print（推送内容），无变化静默（零打扰）。

用法：
  python 持仓监测.py            # 单次检查（cron no_agent 每1-5m 调用）
  python 持仓监测.py --loop 30  # 自测：每30s 循环
"""
from __future__ import annotations

import argparse
import json
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DATA = ROOT / "data"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import trading_system as ts
import system_data_bridge as bridge

STATE_FILE = DATA / "position_state.json"
EVENT_LOG = DATA / "position_events.jsonl"


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_event(row: dict):
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def fetch_positions() -> dict:
    """返回 {symbol: {amt, entry, side, unrealized}} 仅含非零持仓。"""
    raw = bridge._sget("/fapi/v2/positionRisk")
    out = {}
    if not isinstance(raw, list):
        # _sget 出错返回 {"_e": ...}
        return {"_error": raw.get("_e", "unknown") if isinstance(raw, dict) else "bad response"}
    for p in raw:
        try:
            amt = float(p.get("positionAmt", 0) or 0)
        except (TypeError, ValueError):
            continue
        if abs(amt) < 1e-12:
            continue
        sym = p.get("symbol")
        out[sym] = {
            "amt": amt,
            "entry": float(p.get("entryPrice", 0) or 0),
            "side": "long" if amt > 0 else "short",
            "unrealized": float(p.get("unRealizedProfit", 0) or 0),
            "mark": float(p.get("markPrice", 0) or 0),
        }
    return out


def _side_zh(side: str) -> str:
    return "做多" if side == "long" else "做空"


def detect_changes(prev: dict, curr: dict) -> list[dict]:
    """对比两轮持仓，产出状态变化事件。"""
    events = []
    syms = set(prev) | set(curr)
    for sym in sorted(syms):
        if sym.startswith("_"):
            continue
        old = prev.get(sym)
        new = curr.get(sym)
        if not old and new:
            events.append({"kind": "open", "symbol": sym, "new": new})
        elif old and not new:
            events.append({"kind": "close", "symbol": sym, "old": old})
        elif old and new and old.get("side") != new.get("side"):
            events.append({"kind": "flip", "symbol": sym, "old": old, "new": new})
    return events


def handle_open(sym: str, new: dict, plan_id: str = "") -> str:
    ts.ensure_files()
    note = f"自动检测开仓 · {_side_zh(new['side'])} {abs(new['amt'])} @ {new['entry']:.2f}"
    ts.mark_trade_opened(sym, plan_id, note)
    _append_event({"time": ts.now_iso(), "kind": "open", "symbol": sym,
                   "side": new["side"], "amt": abs(new["amt"]), "entry": new["entry"]})
    return (f"🟢 {sym} · 自动检测开仓\n方向：{_side_zh(new['side'])}\n"
            f"数量：`{abs(new['amt'])}`\n入场：`{new['entry']:.2f}`\n"
            f"风控闸门：已记一笔待复盘，平仓后自动复盘")


def handle_close(sym: str, old: dict, exit_price: float = 0.0) -> str:
    """平仓：估算已实现盈亏 → 自动复盘。
    注意：positionRisk 平仓后拿不到出场价，用最后已知 mark 价估算（近似）。
    精确 PnL 需查 income/userTrades，此处提供自动近似复盘，棠溪可后续手动校正。"""
    ts.ensure_files()
    entry = old.get("entry", 0)
    amt = abs(old.get("amt", 0))
    px = exit_price or old.get("mark", 0) or entry
    # 多头：(出场-入场)*量；空头：(入场-出场)*量
    if old.get("side") == "long":
        pnl = (px - entry) * amt
    else:
        pnl = (entry - px) * amt
    review = {
        "time": ts.now_iso(),
        "symbol": sym,
        "model": "自动检测",
        "direction": _side_zh(old.get("side")),
        "entry": entry,
        "exit": px,
        "pnl_usd": round(pnl, 2),
        "note": "持仓监测自动平仓复盘（近似PnL·可手动校正）",
        "auto": True,
    }
    ts.record_trade_review(review)
    _append_event({"time": ts.now_iso(), "kind": "close", "symbol": sym,
                   "side": old.get("side"), "entry": entry, "exit": px, "pnl_usd": round(pnl, 2)})
    sign = "盈" if pnl >= 0 else "亏"
    return (f"🔵 {sym} · 自动检测平仓\n方向：{_side_zh(old.get('side'))}\n"
            f"入场：`{entry:.2f}` → 出场：`{px:.2f}`\n"
            f"估算盈亏：`{pnl:+.2f}U`（{sign}）\n已自动写入复盘，更新风控状态")


def run_once() -> str:
    prev = _read_json(STATE_FILE, {})
    curr = fetch_positions()
    if "_error" in curr:
        # 凭据/网络错误：静默，不覆盖上轮快照
        return ""
    msgs = []
    for ev in detect_changes(prev, curr):
        if ev["kind"] == "open":
            msgs.append(handle_open(ev["symbol"], ev["new"]))
        elif ev["kind"] == "close":
            msgs.append(handle_close(ev["symbol"], ev["old"]))
        elif ev["kind"] == "flip":
            # 反手：先平旧仓复盘，再标记新开仓
            msgs.append(handle_close(ev["symbol"], ev["old"], exit_price=ev["new"].get("entry", 0)))
            msgs.append(handle_open(ev["symbol"], ev["new"]))
    # 保存当前快照（去掉错误键）
    _write_json(STATE_FILE, {k: v for k, v in curr.items() if not k.startswith("_")})
    return "\n\n".join(msgs)


def main():
    ap = argparse.ArgumentParser(description="自动检测 Binance 合约开平仓")
    ap.add_argument("--loop", type=int, default=0, help="循环间隔秒数（0=单次）")
    args = ap.parse_args()
    if args.loop > 0:
        while True:
            out = run_once()
            if out:
                print(out, flush=True)
            time.sleep(args.loop)
    else:
        out = run_once()
        if out:
            print(out)


if __name__ == "__main__":
    main()
