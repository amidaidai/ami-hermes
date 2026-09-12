#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交互式分析租约 CLI — 分析期间让后台切图任务让路。

背景
----
`tv_collection_lock` 只序列化**后台任务彼此**（BTC 关键位续航 / XAU 同步 /
到价触发）。对话里做分析时是直接调 TV MCP 读行动格 + 截图，不持这把锁，
后台续航照样按 cron 切周期 —— 实测 2026-09-11 14:07 读 5m 被 btc_tv_refresh
连抢两次，行动格整张读成空表。

用法
----
    python scripts/tv_analysis_lease.py start --minutes 10 --symbol BINANCE:BTCUSDT.P
    python scripts/tv_analysis_lease.py status
    python scripts/tv_analysis_lease.py end

行为契约
--------
- 租约**只影响后台切图任务的调度**：有效期内后台任务 defer 到下一轮，不改任何
  数据内容、不改裁决、不写缓存。
- TTL 上限 30 分钟；分析脚本崩溃也只是让后台晚一轮，不会永久锁死图表。
- `end` 幂等；忘了 end 也会自然过期。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if callable(_reconfigure):
        _reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="交互式分析租约（防后台抢图）")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="声明分析进行中")
    start.add_argument("--minutes", type=float, default=10.0, help="租约时长（上限30分钟）")
    start.add_argument("--note", default="", help="备注（写进租约文件，便于溯源）")
    start.add_argument("--symbol", default="", help="正在分析的品种，如 BINANCE:BTCUSDT.P")

    sub.add_parser("end", help="释放租约（幂等）")

    status = sub.add_parser("status", help="查看租约状态")
    status.add_argument("--quiet", action="store_true", help="只打印 active/expired 一行")

    sub.add_parser("guard", help="后台任务用：空闲退0，分析中退3")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from tv_data_bridge import (analysis_lease_status, begin_analysis_lease,
                                end_analysis_lease)

    if args.command == "start":
        payload = begin_analysis_lease(
            args.minutes, note=args.note, symbol=args.symbol)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "end":
        print(json.dumps(end_analysis_lease(), ensure_ascii=False))
        return 0

    status = analysis_lease_status()
    if args.command == "guard":
        return 3 if status.get("active") else 0

    if args.quiet:
        print("analysis" if status.get("active") else "idle")
        return 0
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())