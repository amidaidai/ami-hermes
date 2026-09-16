"""CoinLobster 外部验证层：读侧三态与卡面读数（合同 §二.六）。

读侧判定必须与采集侧分开：
  - 采集时写死的 payload["usable_as_live"] = 上游数据是否实时
  - 读侧 state = 工件采集距今多久（≤25 新鲜 / 25–90 陈旧 / >90 或缺失不可用）
这些用例锁住三件事：陈旧必须带年龄、不可用不许占位、非 BTC 不许拿 BTC 冒充。
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import coinlobster_collector as cc  # noqa: E402


def _write(tmp_path, monkeypatch, *, minutes_ago, status="live", payload=None):
    art = tmp_path / "coinlobster_snapshot.json"
    ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    art.write_text(json.dumps({
        "_source_contract": {"version": 1},
        "_source_id": cc.SOURCE_ID,
        "_source_status": status,
        "_source_timestamp": ts.isoformat(),
        "payload": payload if payload is not None else {
            "liquidations": {"total_usd": 466_000_000, "long_share_pct": 89,
                             "dominant_side": "long"},
            "funding": {"per_venue": [
                {"exchange": "Kraken Futures", "rate_pct_8h": 0.0202},
                {"exchange": "OKX", "rate_pct_8h": 0.0053},
            ]},
            "usable_as_live": True,
        },
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(cc, "ARTIFACT", art)
    return art


def test_fresh_artifact_reads_live_and_gives_numbers(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, minutes_ago=2)
    payload, age, state = cc.read_state()
    assert state == "live" and age is not None and age < cc.READ_FRESH_MINUTES
    text, state2 = cc.read_evidence("BTC")
    assert state2 == "live"
    assert "级联 $466M" in text and "多单占89%" in text
    assert "0.0202~0.0053%" in text
    # 新鲜态不许多余的年龄噪声
    assert "分前" not in text


def test_stale_artifact_still_gives_numbers_but_must_carry_age(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, minutes_ago=40)
    _, _, state = cc.read_state()
    assert state == "stale"
    text, state2 = cc.read_evidence("BTC")
    assert state2 == "stale"
    assert "级联 $466M" in text          # 照样给数
    assert "分前" in text and "仅背景" in text   # 但必须自报年龄


def test_expired_artifact_is_unavailable_and_takes_no_space(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, minutes_ago=cc.READ_STALE_MINUTES + 10)
    _, age, state = cc.read_state()
    assert state == "unavailable" and age > cc.READ_STALE_MINUTES
    assert cc.read_evidence("BTC") == ("", "unavailable")


def test_missing_artifact_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "ARTIFACT", tmp_path / "nope.json")
    assert cc.read_state() == ({}, None, "unavailable")
    assert cc.read_evidence("BTC") == ("", "unavailable")


def test_non_live_envelope_is_unavailable_even_when_timestamp_is_new(tmp_path, monkeypatch):
    """信封自报 unavailable（采集全失败）时不许因为时间新就当新鲜。"""
    _write(tmp_path, monkeypatch, minutes_ago=1, status="unavailable")
    assert cc.read_state()[2] == "unavailable"
    assert cc.read_evidence("BTC") == ("", "unavailable")


def test_non_btc_symbol_never_borrows_btc_numbers(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, minutes_ago=1)
    assert cc.read_evidence("XAUUSD") == ("", "unavailable")
    assert cc.read_evidence("ETHUSDT") == ("", "unavailable")


def test_degraded_and_non_live_upstream_are_flagged_in_text(tmp_path, monkeypatch):
    payload = {
        "liquidations": {"total_usd": 100_000_000, "long_share_pct": 60,
                         "dominant_side": "short"},
        "funding": {"per_venue": [{"exchange": "Binance Futures", "rate_pct_8h": 0.01}]},
        "usable_as_live": False,
        "degraded_tools": ["funding_matrix:empty_per_venue"],
    }
    _write(tmp_path, monkeypatch, minutes_ago=1, payload=payload)
    text, state = cc.read_evidence("BTC")
    assert state == "live"
    assert "空单占60%" in text
    assert "部分降级" in text
    assert "上游非实时" in text


def test_missing_liquidation_total_is_unavailable(tmp_path, monkeypatch):
    """没有清算总数就没有这条读数 —— 不许只拿费率凑一行。"""
    _write(tmp_path, monkeypatch, minutes_ago=1,
           payload={"liquidations": {}, "funding": {"per_venue": []}})
    assert cc.read_evidence("BTC") == ("", "unavailable")
