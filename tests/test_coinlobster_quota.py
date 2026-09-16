"""CoinLobster 额度自保回归（2026-09-16 实测：免费档 200 次/日打满后每轮都失败）。

背景：cron（core 2 次/轮，`9,29,49`=96 次/日）+ 分析入口按需深采（full 6 次/轮）
把免费额度吃满 → 之后每 30 分钟一轮 `全部工具失败` exit 1 → 持续铸造 incident、
把 `audit_preflight` 的 `Cron策略` 拖红。额度打满是**状态**不是故障。

本文件钉住的契约：
- 429 且为「当日额度用尽」→ `quota_cooldown` + exit 0 + 冷却 breaker（到次日 00:05）
- 冷却期内 → 不发起任何 RPC，仍写 quota_cooldown 工件并 exit 0
- 短时 429（无 daily 字样）→ 仍按失败上报（不用 cooldown 掩盖真问题）
- 非额度类全失败 → `unavailable` + exit 1（原行为不变）
- 当日额度不足一轮计划 → 按计划顺序保核心格，跳过项写进工件 `skipped_tools`（不静默削源）
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import coinlobster_collector as cc  # noqa: E402

TZ = cc.TZ


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """把工件/breaker/预算状态全部隔离到 tmp，绝不碰仓库 data/。"""
    monkeypatch.setattr(cc, "ARTIFACT", tmp_path / "coinlobster_snapshot.json")
    monkeypatch.setattr(cc, "QUOTA_BREAKER", tmp_path / ".quota_breaker.json")
    monkeypatch.setattr(cc, "BUDGET_STATE", tmp_path / ".budget.json")
    monkeypatch.setattr(cc, "load_key", lambda: "k")


def _run(monkeypatch, argv, rpc_results):
    """跑 collector.main()，RPC 结果由序列逐次弹出。"""
    seq = list(rpc_results)
    calls = []

    def fake_rpc(tool, params, key, timeout=30):
        calls.append(tool)
        return seq.pop(0) if seq else (False, "no more")

    monkeypatch.setattr(cc, "_rpc", fake_rpc)
    monkeypatch.setattr(cc.time, "sleep", lambda *_: None)
    monkeypatch.setattr(sys, "argv", ["coinlobster_collector.py", *argv])
    return cc.main(), calls


def _artifact():
    return json.loads(cc.ARTIFACT.read_text(encoding="utf-8"))


DAILY_429 = ('HTTP 429 {"jsonrpc":"2.0","error":{"code":-32029,'
             '"message":"Daily limit reached for this free account (200 calls a day)."}}')
SHORT_429 = 'HTTP 429 {"jsonrpc":"2.0","error":{"code":-32000,"message":"Too many requests"}}'


# ── 识别 ────────────────────────────────────────────────────────────────

def test_is_daily_quota_error_distinguishes_short_rate_limit():
    assert cc.is_daily_quota_error({"a": DAILY_429}) is True
    assert cc.is_daily_quota_error({"a": SHORT_429}) is False
    assert cc.is_daily_quota_error({"a": "-32029 daily"}) is True
    assert cc.is_daily_quota_error({"a": "HTTP 200 ok"}) is False
    assert cc.is_daily_quota_error({}) is False


# ── 当日额度打满 ────────────────────────────────────────────────────────

def test_daily_quota_exhausted_is_cooldown_not_failure(monkeypatch):
    rc, calls = _run(monkeypatch, ["--profile", "core"], [(False, DAILY_429), (False, DAILY_429)])
    assert rc == 0, "额度打满不能记 cron 失败（否则每 30 分钟一条 incident）"
    env = _artifact()
    assert env["_source_status"] == "quota_cooldown"
    assert env["_source_cached"] is False        # 没有旧工件可保留 → 不能谎称有缓存
    assert calls == ["market_liquidations", "funding_matrix"]   # 第一轮确实试过了
    brk = json.loads(cc.QUOTA_BREAKER.read_text(encoding="utf-8"))
    assert datetime.fromisoformat(brk["until"]) > datetime.now(TZ)


def test_breaker_short_circuits_without_any_rpc(monkeypatch):
    monkeypatch.setattr(cc, "arm_quota_breaker", cc.arm_quota_breaker)
    cc.arm_quota_breaker("seed")
    rc, calls = _run(monkeypatch, ["--profile", "core"], [])
    assert rc == 0 and calls == [], "冷却期内不得再打 RPC（省额度、省日志）"
    assert _artifact()["_source_status"] == "quota_cooldown"


def test_expired_breaker_does_not_block_collection(monkeypatch):
    cc.QUOTA_BREAKER.write_text(json.dumps({
        "until": (datetime.now(TZ) - timedelta(minutes=1)).isoformat(timespec="seconds")}),
        encoding="utf-8")
    rc, calls = _run(monkeypatch, ["--profile", "core"], [(True, {}), (True, {})])
    assert rc == 0 and calls, "过期的冷却不能继续拦采集"


def test_short_rate_limit_still_fails_loudly(monkeypatch):
    rc, _ = _run(monkeypatch, ["--profile", "core"], [(False, SHORT_429), (False, SHORT_429)])
    assert rc == 1, "短时限流不是额度打满，不能被 cooldown 吞掉"
    assert _artifact()["_source_status"] == "unavailable"
    assert not cc.QUOTA_BREAKER.exists()


# ── 额度记账与削源可见性 ────────────────────────────────────────────────

def test_budget_trim_keeps_plan_order_and_discloses_skipped(monkeypatch):
    """当日只剩 1 次额度、计划 2 个 → 只打第一个，跳过的写进工件。"""
    cc.BUDGET_STATE.write_text(json.dumps(
        {"date": datetime.now(TZ).strftime("%Y-%m-%d"), "calls": cc.DAILY_CALL_BUDGET - 1}),
        encoding="utf-8")
    rc, calls = _run(monkeypatch, ["--profile", "core"], [(True, {})])
    assert rc == 0
    assert calls == ["market_liquidations"], calls
    env = _artifact()
    assert env["skipped_tools"] == ["funding_matrix"], env
    assert env["_source_status"] == "live"


def test_degraded_note_survives_existing_contract_artifact(monkeypatch):
    """已有旧工件（带 `_source_contract`）时，降级注记必须保留、旧数据不能丢。

    实测坑：把旧工件直接回灌会被 `source_contract._raw_payload` 拆包成**旧 payload**，
    `degraded_note` 静默消失 —— 「可见降级」就失效了。测试必须覆盖「已有旧工件」这条路径。
    """
    seed = {"btc": {"price": 1}, "liquidations": {"total_usd": 5},
            "_source_status": "live", "_source_id": "coinlobster_snapshot",
            "_source_cached": False,
            "_source_contract": {"source_id": "coinlobster_snapshot", "status": "live",
                                 "timestamp": "2026-09-16T08:09:22+00:00",
                                 "payload": {"btc": {"price": 1}}, "error": None}}
    cc.ARTIFACT.write_text(json.dumps(seed), encoding="utf-8")

    rc, _ = _run(monkeypatch, ["--profile", "core"], [(False, DAILY_429), (False, DAILY_429)])
    assert rc == 0
    env = _artifact()
    assert env["_source_status"] == "quota_cooldown"
    assert env["btc"]["price"] == 1 and env["liquidations"]["total_usd"] == 5, "旧数据必须保留"
    assert "冷却到" in str(env.get("degraded_note")), f"降级注记丢失: {env}"
    assert env["_source_cached"] is True


def test_budget_exhausted_skips_whole_run_as_cooldown(monkeypatch):
    cc.BUDGET_STATE.write_text(json.dumps(
        {"date": datetime.now(TZ).strftime("%Y-%m-%d"), "calls": cc.DAILY_CALL_BUDGET}),
        encoding="utf-8")
    rc, calls = _run(monkeypatch, ["--profile", "core"], [])
    assert rc == 0 and calls == []
    env = _artifact()
    assert env["_source_status"] == "quota_cooldown"
    assert env["skipped_tools"] == ["market_liquidations", "funding_matrix"]


def test_successful_calls_are_counted(monkeypatch):
    _run(monkeypatch, ["--profile", "core"], [(True, {}), (True, {})])
    assert cc.calls_used_today() == 2


def test_budget_state_resets_on_new_day(monkeypatch):
    cc.BUDGET_STATE.write_text(json.dumps({"date": "2000-01-01", "calls": 999}), encoding="utf-8")
    assert cc.calls_used_today() == 0


# ── 既有行为不变 ────────────────────────────────────────────────────────

def test_stale_skip_and_normal_live_path_unchanged(monkeypatch):
    rc, calls = _run(monkeypatch, ["--profile", "core", "--if-stale-minutes", "0"], [(True, {}), (True, {})])
    assert rc == 0 and len(calls) == 2
    assert _artifact()["_source_status"] == "live"


def test_partial_failure_still_writes_live_with_partial_errors(monkeypatch):
    rc, _ = _run(monkeypatch, ["--profile", "core"], [(True, {}), (False, SHORT_429)])
    assert rc == 0
    env = _artifact()
    assert env["_source_status"] == "live"
    assert env["partial_errors"], "单工具失败必须留明细，不能静默"
