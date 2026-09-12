#!/usr/bin/env python3
"""Keep BTC five-timeframe TV and source snapshots fresh without delivery."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "scripts"))


def btc_five_tf_status() -> dict:
    from tv_five_tf_contract import load_five_tf_snapshot
    # The job runs every 20 minutes; the production contract tolerates 30.
    # Threshold must stay **below** the cron interval, otherwise the tick that
    # should refresh sees age≈20 < 22 and skips, and the snapshot is left to
    # expire past the 30-minute contract for ~10 minutes every cycle.
    return load_five_tf_snapshot("BTCUSDT", data_dir=DATA, max_age_minutes=18.0)


def source_snapshot_status() -> dict:
    from source_health import inspect_json_file
    return inspect_json_file(
        DATA / "source_snapshot_BTCUSDT.json",
        max_age_hours=0.75,
        expected_symbol="BTCUSDT",
    )


def run_collector() -> int:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "keylevels_collect.py")],
        cwd=str(ROOT), timeout=420,
    )
    return int(result.returncode)


def refresh_source_snapshot() -> bool:
    try:
        from trading_system import source_snapshot
        payload = source_snapshot("BTCUSDT")
        return isinstance(payload, dict) and bool(payload.get("time"))
    except Exception as exc:
        print(f"BTC SourceSnapshot刷新失败: {type(exc).__name__}: {exc}", file=sys.stderr)
        return False


def main() -> int:
    # 交互式分析租约：分析期间不切用户正在看的图。让路一轮不会让快照过期
    # （阈值 18 分 < cron 20 分 < 合同 30 分），比硬闯读出一张空表划算。
    # 若已发布缓存已经不可用，让路必须对调度器可见，不能把 17h 过期记成 ok。
    from tv_data_bridge import analysis_lease_status
    five = btc_five_tf_status()
    source = source_snapshot_status()
    lease = analysis_lease_status()
    if lease.get("active"):
        print(f"↷ BTC五周期续航本轮让路：交互式分析进行中（剩 {lease.get('remaining_seconds')}s）")
        if bool(five.get("usable")) and bool(source.get("fresh")):
            return 0
        print(
            f"⚠ 让路时缓存已不可用 five={five.get('reason')} source={source.get('reason')}",
            file=sys.stderr,
        )
        return 1
    need_five = not bool(five.get("usable"))
    need_source = not bool(source.get("fresh"))
    if not need_five and not need_source:
        return 0
    if need_five and run_collector() != 0:
        print(f"BTC五周期续航失败: {five.get('reason', '不可用')}", file=sys.stderr)
        return 1
    if need_source and not refresh_source_snapshot():
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())