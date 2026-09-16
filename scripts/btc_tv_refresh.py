#!/usr/bin/env python3
"""Keep BTC five-timeframe TV and source snapshots fresh without delivery.

## 两个阈值必须分开（2026-09-16 修正）

- **触发口径 12 分**（`btc_five_tf_status`）：决定「本轮要不要去刷」。它必须远小于
  cron 间隔，否则会跳过刷新、把快照拖到合同线外。
- **合同口径 30 分**（`five_tf_contract_status`）：生产合同能容忍的最大年龄。
  **让路算不算失败，看的是这个口径**，不是触发口径。

修前把两者混用：只要缓存越过 12 分触发线，任何让路（交互式分析进行中、共享图表锁
被占、采集子进程早期退出）都被记成 cron 失败。实测 2026-09-16 12:07 / 13:27 / 16:07
三轮失败时缓存年龄分别是 1054s / 1056s / 1053s（≈17.5 分）—— **远在 30 分合同内**，
是假失败。现在：合同内让路 → exit 0（可见但不计失败）；越过让路上限（24 分）或连续
让路达 3 轮 → exit 1（真失败，绝不允许把过期数据记成 ok）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "scripts"))

CONTRACT_MAX_AGE_MIN = 30.0     # 生产合同（tv_five_tf_contract 默认值）
YIELD_MAX_AGE_MIN = 24.0        # 让路上限 = 0.8 × 合同：留一轮给「下一轮必须刷成功」
YIELD_STREAK_LIMIT = 3          # 连续让路轮数上限（20 分 × 3 ≈ 1 小时）
YIELD_STATE = DATA / "btc_tv_refresh_yield_state.json"
COLLECT_DIAGNOSTIC = DATA / "keylevels_collect_diagnostic.json"
# 采集子进程「让路」退出码，必须与 keylevels_collect.DEFER_EXIT_CODE 一致
# （tests/test_btc_tv_refresh_yield.py 里有断言钉住这个契约）。
_DEFER_EXIT = 7

TZ = timezone(timedelta(hours=8))


def btc_five_tf_status() -> dict:
    """触发口径（12 分）：本轮要不要去刷五周期快照。"""
    from tv_five_tf_contract import load_five_tf_snapshot
    # The job runs every 20 minutes; the production contract tolerates 30.
    #
    # 2026-09-14 实测校正：原阈值 18 分假设「写入与 tick 对齐」，但采集本身
    # 要 ~3 分钟，写入实际落在 tick 后 ~3 分钟 → 下一个 tick 看到 age≈13-17 < 18
    # 就跳过 → 再下一个 tick 才刷 → 快照会跨过 30 分钟合同约 6 分钟（实测
    # 04:44 出现 age=32min 的 FAIL，cron 却记 ok）。
    # 正确关系：阈值 ≤ 间隔 − 采集耗时 − 余量 = 20 − 3.3 − 1 ≈ 15.7。
    # 取 12 分：每个 tick 都会判定需要刷新，age 峰值 ≈ 23 分 < 30 分合同。
    return load_five_tf_snapshot("BTCUSDT", data_dir=DATA, max_age_minutes=12.0)


def five_tf_contract_status() -> dict:
    """合同口径（30 分）：让路判定的唯一依据（与触发口径分开，别再用 12 分判失败）。"""
    from tv_five_tf_contract import load_five_tf_snapshot
    return load_five_tf_snapshot("BTCUSDT", data_dir=DATA, max_age_minutes=CONTRACT_MAX_AGE_MIN)


def source_snapshot_status() -> dict:
    from source_health import inspect_json_file
    # 同上：触发阈值必须让「下一 tick」愿意刷新。
    # 采集耗时 ~3.3 分 → 下一 tick 实测年龄 ≈ 16.7 分，故阈值必须 < 16.7。
    # 原 0.75h=45 分（甚至 0.3h=18 分）都过松：会累积到 ~37-65 分，
    # 前者超过 30 分钟合同、后者撞上看门狗 0.6h 阈值 → 都是自造噪声。
    # 0.25h=15 分 → 每 tick 刷新，峰值 ≈ 23 分，三方口径（合同/看门狗/触发）一致。
    return inspect_json_file(
        DATA / "source_snapshot_BTCUSDT.json",
        max_age_hours=0.25,
        expected_symbol="BTCUSDT",
    )


def last_collect_stage() -> str:
    """采集诊断文件里的最后阶段 —— 失败时一行定位「死在哪一步」。"""
    try:
        payload = json.loads(COLLECT_DIAGNOSTIC.read_text(encoding="utf-8"))
        return f"{payload.get('stage') or '?'}({payload.get('status') or '?'})"
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "?"


def run_collector() -> tuple[int, str]:
    """跑采集子进程，返回 (退出码, 诊断文件最后阶段)。"""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "keylevels_collect.py")],
        cwd=str(ROOT), timeout=420,
    )
    return int(result.returncode), last_collect_stage()


def refresh_source_snapshot() -> bool:
    try:
        from trading_system import source_snapshot
        payload = source_snapshot("BTCUSDT")
        return isinstance(payload, dict) and bool(payload.get("time"))
    except Exception as exc:
        print(f"BTC SourceSnapshot刷新失败: {type(exc).__name__}: {exc}", file=sys.stderr)
        return False


def chart_lock_available(wait: float = 60.0) -> bool:
    """共享图表锁是否可用（拿一下立刻放，只探测不占用）。

    **为什么需要**：本作业的采集子进程自己要抢 `tv_data_bridge.tv_collection_lock`
    （timeout=180）。若此刻 XAU 同步正持锁，子进程会空等两轮再以「未发布新快照」退出，
    于是每轮都被记成 cron 失败（实测 2026-09-15 11:08/11:28/11:49 连续 incident）。
    先探测的好处：抢不到就**体面让路**（exit 0），既不改子进程、也不制造假失败。
    注意探测与子进程抢锁之间仍有窗口（不是原子操作），所以让路判定不能只看锁 ——
    真正的兜底是「合同内让路、超限即失败」（见 resolve_yield）。
    锁模块自身异常一律当作「可用」——不能让探测把续航堵死。
    """
    try:
        from tv_data_bridge import tv_collection_lock
    except Exception:
        return True
    try:
        with tv_collection_lock(timeout=wait):
            return True
    except TimeoutError:
        return False
    except Exception:
        return True


def _read_yield_state() -> dict:
    try:
        payload = json.loads(YIELD_STATE.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _write_yield_state(streak: int, result: str) -> None:
    try:
        from atomic_json import atomic_write_json
        atomic_write_json(YIELD_STATE, {
            "streak": int(streak), "last_result": result,
            "last_ts": datetime.now(TZ).isoformat(timespec="seconds"),
        })
    except Exception:
        pass            # 记账失败不能把续航本身拖挂


def resolve_yield(reason: str, contract: dict, *, loud: bool = False) -> int:
    """让路判定：缓存仍在合同内 → 0（可见让路）；越过让路上限或连续让路超额 → 1。

    这是「让路不是失败」与「绝不把过期数据记成 ok」两条规则的交叉点：
    - age ≤ YIELD_MAX_AGE_MIN 且 streak < YIELD_STREAK_LIMIT → 让路（0）
    - age > YIELD_MAX_AGE_MIN 或 streak ≥ YIELD_STREAK_LIMIT → 失败（1）
    - age 未知（快照缺失/不可读）→ 失败（不确定就不能说新鲜）
    """
    age_seconds = contract.get("age_seconds")
    age_min = (age_seconds / 60.0) if isinstance(age_seconds, (int, float)) else None
    streak = int(_read_yield_state().get("streak") or 0) + 1
    over_age = age_min is None or age_min > YIELD_MAX_AGE_MIN
    over_streak = streak >= YIELD_STREAK_LIMIT
    age_txt = "未知" if age_min is None else f"{age_min:.1f}分"
    if not (over_age or over_streak):
        _write_yield_state(streak, "yielded")
        print(f"↷ {reason}")
        print(f"   五周期缓存 age={age_txt} ≤ 让路上限 {YIELD_MAX_AGE_MIN:.0f}分"
              f"（生产合同 {CONTRACT_MAX_AGE_MIN:.0f}分）· 连续让路 {streak}/{YIELD_STREAK_LIMIT} 轮"
              f" → 不计失败，下一轮补刷")
        return 0
    _write_yield_state(streak, "failed")
    why = f"age={age_txt} 超让路上限 {YIELD_MAX_AGE_MIN:.0f}分" if over_age else \
          f"连续让路 {streak} 轮 ≥ {YIELD_STREAK_LIMIT}"
    print(f"⚠ {reason}", file=sys.stderr)
    print(f" ⚠ 且{why} → 计失败（不能让过期数据被读成新鲜）", file=sys.stderr)
    if loud:
        print(f"   最后采集阶段：{last_collect_stage()}", file=sys.stderr)
    return 1


def main() -> int:
    from tv_data_bridge import analysis_lease_status
    five = btc_five_tf_status()            # 触发口径：要不要刷
    source = source_snapshot_status()
    lease = analysis_lease_status()
    contract = five_tf_contract_status()   # 合同口径：让路算不算失败
    if lease.get("active"):
        if bool(five.get("usable")) and bool(source.get("fresh")):
            _write_yield_state(0, "ok")
            print(f"↷ BTC五周期续航本轮让路：交互式分析进行中（剩 {lease.get('remaining_seconds')}s）"
                  f"· 数据仍在触发线内")
            return 0
        return resolve_yield(
            f"BTC五周期续航本轮让路：交互式分析进行中（剩 {lease.get('remaining_seconds')}s）",
            contract)
    need_five = not bool(five.get("usable"))
    need_source = not bool(source.get("fresh"))
    if not need_five and not need_source:
        _write_yield_state(0, "ok")
        return 0
    # 后台任务互斥：抢不到共享图表锁 → 让路一轮（是「排队」，不是「失败」）
    if not chart_lock_available():
        return resolve_yield("BTC五周期续航本轮让路：共享图表锁被其它后台任务占用", contract)
    if need_five:
        rc, stage = run_collector()
        if rc == _DEFER_EXIT:
            return resolve_yield("BTC五周期续航本轮让路：采集子进程让路（交互式分析/锁）", contract)
        if rc != 0:
            # 采集没跑完：可能是被抢图/中断，也可能是真错。判定权交给合同口径，
            # 但把 rc 和最后阶段一起打出来，下次发生能一行定位。
            print(f"BTC五周期续航未完成刷新: 采集 rc={rc} · 最后阶段 {stage}", file=sys.stderr)
            return resolve_yield(f"BTC五周期续航未完成刷新（采集 rc={rc}·{stage}）", contract,
                                 loud=True)
    if need_source and not refresh_source_snapshot():
        return 1
    _write_yield_state(0, "ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
