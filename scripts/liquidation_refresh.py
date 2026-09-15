#!/usr/bin/env python3
"""清算双源刷新入口 —— 供 `no_agent` cron 调用（不推送，只写缓存）。

两源分工
--------
- `coinglass_web`：24h 清算堆积热图（相对刻度，非 USD）→ `data/coinglass_liq.json`，只覆盖 BTC
- `liquidation_flow`：逐笔强平事件（真实成交，名义为估算）→ `data/liquidation_flow.json`，覆盖 BTC/ETH

设计约束
--------
- 单源失败**不阻塞**另一源：各自写自己的缓存（含失败态）。
- **退出码语义（2026-09-15 修正）**：降级是状态、不是故障 —— 单源失败但另一源
  仍能供数（含「沿用上轮」）时退出码 0，降级明细进 stdout 供排查；**只有两源都
  不可用才算真失败**（exit 1）。此前单源降级也 exit 1，被 cron 记成 incident 噪声。
- 不推送任何消息：卡面/报告侧按需读缓存；避免与 TG 授权规则冲突。
- 静默友好：成功时只打印一行摘要，便于 cron 日志排查。
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = str(Path(__file__).resolve().parent)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import coinglass_web  # noqa: E402
import liquidation_flow  # noqa: E402


def main() -> int:
    problems: list[str] = []
    usable = 0          # 「能供数」的源数：live 或带「沿用上轮」的缓存都算

    try:
        rec = coinglass_web.refresh_cache("Binance_BTCUSDT")
        band = coinglass_web.liquidation_band_text("BTCUSDT")
        if rec["status"] != "live":
            problems.append(f"coinglass={rec['status']} {rec.get('error') or ''}".strip())
        else:
            usable += 1
        print(f"CoinGlass 热图: [{rec['status']}] {band}")
    except Exception as exc:  # 单源异常不得吞掉另一源
        problems.append(f"coinglass={type(exc).__name__}: {exc}")
        print(f"CoinGlass 热图: [unavailable] {type(exc).__name__}: {exc}")

    try:
        rec2 = liquidation_flow.refresh_cache(("BTC", "ETH"))
        coins = rec2.get("coins") or {}
        if rec2["status"] != "live":
            problems.append(f"okx={rec2['status']} {rec2.get('error') or ''}".strip())
        # 只要有一个品种有事件（本轮 live 或沿用上轮）就算该源可供给卡面
        if any((info or {}).get("events") for info in coins.values()):
            usable += 1
        summary = " | ".join(
            f"{coin}:{len((info or {}).get('events') or [])}笔"
            f"{'/沿用' if (info or {}).get('stale') else ''}"
            for coin, info in coins.items())
        print(f"OKX 逐笔强平: [{rec2['status']}] {summary}")
        for coin in ("BTC", "ETH"):
            print("  " + liquidation_flow.flow_text(coin))
    except Exception as exc:
        problems.append(f"okx={type(exc).__name__}: {exc}")
        print(f"OKX 逐笔强平: [unavailable] {type(exc).__name__}: {exc}")

    if problems:
        print("降级明细（不影响挂载，仅供排查）: " + " | ".join(problems))
    if usable:
        return 0
    print("两源均不可用")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
