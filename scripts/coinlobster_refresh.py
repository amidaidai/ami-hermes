#!/usr/bin/env python3
"""CoinLobster 外部验证层刷新入口 —— 供 `no_agent` cron 调用（不推送，只写缓存）。

分工
----
- `coinlobster_collector.py --profile core`：全市场清算级联 + BTC 逐所资金费率
  → `data/coinlobster_snapshot.json`（带 source_contract 五态信封）
- 每轮 2 次调用；cron 实排 `9,29,49`（每 30 分钟）= 48 轮/日 = 96 次/日，
  免费档 200 次/日的余量留给分析入口的按需深采（`--profile full`，6 次/轮）。

设计约束
--------
- **绝不推送**：只写缓存；卡面/报告侧按需读，避免与 TG 授权规则冲突。
- **降级是状态不是故障**：单工具失败仍写 live 信封并把明细放进 `partial_errors`；
  只有全部工具不可用才算真失败（exit 1，会被 cron 记 incident）。
- **额度打满也是状态**（2026-09-16）：服务端 429 且是「当日额度用尽」（code -32029 /
  `Daily limit reached` / `calls a day`）→ 归 `quota_cooldown`、写
  `data/.coinlobster_quota_breaker.json` 冷却到次日 00:05、**exit 0**（不阻塞、不刷 incident）。
  另外按 `COINLOBSTER_DAILY_BUDGET`（默认 200）做当日额度记账：剩余不够跑完整计划时
  按计划顺序保留核心格，被跳过的工具写进工件 `skipped_tools`（**不静默削源**）。
  短时 429（无 daily 字样）仍按失败上报，不用 cooldown 掩盖真问题。
- **配额自保**：`--if-stale-minutes 8` 让「cron 刚跑过」时按需调用直接跳过，
  不重复消耗额度。
- key 从 `MCP_COINLOBSTER_API_KEY` 或 hermes profile `.env` 读（cron 环境无 env 变量，
  回落是主路径）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS = str(Path(__file__).resolve().parent)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import coinlobster_collector as collector  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="CoinLobster 刷新入口（no_agent cron）")
    ap.add_argument("--profile", choices=("core", "full"), default="core",
                    help="core=清算级联+逐所费率（2 次，cron 用）；full=全量（6 次，按需）")
    ap.add_argument("--if-stale-minutes", type=float, default=8.0,
                    help="上次采集比这个值更新则直接跳过；0 = 强制采")
    args = ap.parse_args()

    saved_argv = sys.argv
    try:
        sys.argv = ["coinlobster_collector.py",
                    "--profile", args.profile,
                    "--if-stale-minutes", str(args.if_stale_minutes)]
        return collector.main()
    except Exception as exc:  # 采集器内部异常也要以非零退出码上报，别静默假绿
        print(f"CoinLobster 刷新异常: {type(exc).__name__}: {exc}")
        return 1
    finally:
        sys.argv = saved_argv


if __name__ == "__main__":
    sys.exit(main())
