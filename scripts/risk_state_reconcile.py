#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""人工风险对账：用**显式输入**刷新 data/risk_state.json 的业务日期与账务字段。

为什么需要它
------------
`risk_state.json` 陈旧时系统只能一直显示「非真实额度 / 状态陈旧」——
因为没有任何生产者敢凭空造一个账户余额。这个工具把「人对账」这一步
变成显式动作：余额必须由使用者提供，日期由工具盖章为**当天（北京时间）**，
绝不回填、绝不猜、绝不读旧值当新值。

用法
----
    # 只看对账后的快照与状态（不写盘）
    python scripts/risk_state_reconcile.py --balance 500 --daily-pnl -3.5

    # 真正落盘（--write 才写；默认 dry-run）
    python scripts/risk_state_reconcile.py --balance 500 --daily-pnl -3.5 --write

安全约束
--------
- 必须显式给出 > 0 的 `--balance`，否则拒绝执行（不编造账户）。
- 只更新日期与账务字段，其余键（如 `last_unreviewed_trade`）原样保留。
- 不使用文件 mtime，不推断 PnL，不清空未复盘记录。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STATE_PATH = DATA_DIR / "risk_state.json"
TZ = timezone(timedelta(hours=8))

OWNED_FIELDS = (
    "date", "daily_realized_pnl", "daily_starting_balance",
    "weekly_realized_pnl", "weekly_starting_balance",
    "trades_count", "loss_streak", "max_loss_streak",
    "unreviewed_trade_count", "suspended", "suspend_reason",
    "trades_today", "last_loss_time",
)


def _read_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"❌ 现有 risk_state.json 不可读（{type(exc).__name__}）：拒绝覆盖，请先人工检查")
    return payload if isinstance(payload, dict) else {}


def build_snapshot(existing: dict, args: argparse.Namespace, today: str) -> dict:
    """合并后的新快照：日期=今天，账务=显式输入，其余键原样保留。"""
    snapshot = dict(existing)
    snapshot.update({
        "date": today,
        "daily_starting_balance": float(args.balance),
        "weekly_starting_balance": float(args.weekly_balance if args.weekly_balance is not None else args.balance),
        "daily_realized_pnl": float(args.daily_pnl),
        "weekly_realized_pnl": float(args.weekly_pnl),
        "trades_count": int(args.trades),
        "trades_today": int(args.trades),
        "loss_streak": int(args.loss_streak),
        "max_loss_streak": max(int(args.loss_streak), int(existing.get("max_loss_streak") or 0)),
        "unreviewed_trade_count": int(args.unreviewed),
        "suspended": bool(args.suspend),
        "suspend_reason": str(args.suspend_reason or ""),
        "reconciled_at": datetime.now(TZ).isoformat(),
        "reconciled_by": "manual_cli",
    })
    if args.last_loss_time:
        snapshot["last_loss_time"] = str(args.last_loss_time)
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="用显式输入对账 risk_state.json（默认只读预览）")
    parser.add_argument("--balance", type=float, required=True,
                        help="账户余额（USDT）。必填且 >0 —— 工具不编造账户")
    parser.add_argument("--weekly-balance", type=float, default=None, help="周起始余额，缺省同 --balance")
    parser.add_argument("--daily-pnl", type=float, default=0.0, help="当日已实现盈亏")
    parser.add_argument("--weekly-pnl", type=float, default=0.0, help="本周已实现盈亏")
    parser.add_argument("--trades", type=int, default=0, help="当日成交笔数")
    parser.add_argument("--loss-streak", type=int, default=0, help="当前连亏笔数")
    parser.add_argument("--unreviewed", type=int, default=None, help="未复盘笔数（缺省保留原值）")
    parser.add_argument("--suspend", action="store_true", help="标记暂停交易")
    parser.add_argument("--suspend-reason", default="", help="暂停原因")
    parser.add_argument("--last-loss-time", default="", help="最后一次止损的 ISO 时间戳")
    parser.add_argument("--write", action="store_true", help="真正写盘（默认 dry-run）")
    args = parser.parse_args(argv)

    if not (args.balance > 0):
        print("❌ --balance 必须 > 0：无法在不知道余额的情况下对账（禁止编造）", file=sys.stderr)
        return 2

    existing = _read_state()
    if args.unreviewed is None:
        args.unreviewed = int(existing.get("unreviewed_trade_count") or 0)
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    snapshot = build_snapshot(existing, args, today)

    carried = sorted(set(snapshot) - set(OWNED_FIELDS) - {"reconciled_at", "reconciled_by"})
    print(f"对账日期：{today}（北京时间）")
    print(f"账户余额：{snapshot['daily_starting_balance']:g} ｜ 当日盈亏：{snapshot['daily_realized_pnl']:g} "
          f"｜ 本周盈亏：{snapshot['weekly_realized_pnl']:g}")
    print(f"成交：{snapshot['trades_today']} 笔 ｜ 连亏：{snapshot['loss_streak']} ｜ 未复盘：{snapshot['unreviewed_trade_count']}")
    if carried:
        print(f"原样保留的其他键：{', '.join(carried)}")

    if not args.write:
        print("🟡 dry-run：未写盘。确认无误后加 --write")
        return 0

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_PATH.with_suffix(f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, STATE_PATH)
    print(f"✅ 已写入 {STATE_PATH}")

    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from risk_constitution import load_risk_state, risk_state_status
        print("状态复核：" + json.dumps(risk_state_status(load_risk_state()), ensure_ascii=False))
    except Exception as exc:  # pragma: no cover - 状态复核失败不影响本次对账
        print(f"⚠ 状态复核失败：{type(exc).__name__}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
