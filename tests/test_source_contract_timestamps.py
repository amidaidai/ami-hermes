"""数据源契约字段对齐的回归测试（2026-09-13）。

背景：`cmc_quote` / `cmc_global` 一直返回**实时且完整**的数据，却因为时间戳键名
（CMC 用 `last_updated`）不在契约认得的集合里（`updated_epoch/updated_at/timestamp/ts/time/updated`），
`payload_timestamp()` 返回 None → 被判定 `unavailable(missing_timestamp)`。
结果是一份活数据在多源验证表里常年显红 —— 典型的「可见降级在喊狼」。

本组测试锁死：凡是我们接线进契约的采集器，其载荷必须能被 `payload_timestamp()` 解析出时间。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import multi_source_collector as m  # noqa: E402
from source_health import TIMESTAMP_KEYS, payload_timestamp  # noqa: E402

CMC_QUOTE_RESP = {
    "data": {
        "BTC": {
            "cmc_rank": 1,
            "last_updated": "2026-09-13T14:02:00.000Z",
            "quote": {"USD": {
                "price": 76837.16, "market_cap": 1_500_000_000_000,
                "volume_24h": 15_000_000_000, "percent_change_24h": -0.7,
                "percent_change_7d": -4.1, "market_cap_dominance": 58.8,
            }},
        }
    }
}

CMC_GLOBAL_RESP = {
    "data": {
        "last_updated": "2026-09-13T14:02:59.999Z",
        "btc_dominance": 58.84, "eth_dominance": 12.1,
        "active_cryptocurrencies": 12000,
        "quote": {"USD": {"total_market_cap": 2_600_000_000_000,
                          "total_volume_24h": 90_000_000_000}},
    }
}


def _no_cache(monkeypatch):
    """绕过磁盘缓存，直接跑 fetch() 构造逻辑。"""
    monkeypatch.setattr(m, "_cached", lambda key, fetch, ttl=120: fetch())


def test_cmc_quote_payload_has_contract_timestamp(monkeypatch):
    _no_cache(monkeypatch)
    monkeypatch.setattr(m, "_fetch", lambda url, headers=None, **kw: CMC_QUOTE_RESP)

    payload = m.cmc_quote("BTC")

    assert payload_timestamp(payload) is not None, (
        f"契约时间戳解析失败；载荷键={sorted(payload)}，契约认={TIMESTAMP_KEYS}")
    # 行情字段必须还在（别为了时间戳把数据弄丢）
    assert payload["price"] == 76837.16
    assert payload["dominance"] == 58.8


def test_cmc_global_payload_has_contract_timestamp(monkeypatch):
    _no_cache(monkeypatch)
    monkeypatch.setattr(m, "_fetch", lambda url, headers=None, **kw: CMC_GLOBAL_RESP)

    payload = m.cmc_global()

    assert payload_timestamp(payload) is not None, (
        f"契约时间戳解析失败；载荷键={sorted(payload)}，契约认={TIMESTAMP_KEYS}")
    assert payload["btc_dominance"] == 58.84


def test_cmc_fear_greed_still_has_timestamp(monkeypatch):
    """恐慌贪婪本来就有 timestamp —— 别在改动中退化。"""
    _no_cache(monkeypatch)
    # 真实 API 的字段是 value / update_time / value_classification，
    # 且 update_time 是 ISO 字符串（实测 2026-09-13）—— 按真实形态造 fixture。
    monkeypatch.setattr(m, "_fetch", lambda url, headers=None, **kw: {
        "data": {"value": 61, "value_classification": "Greed",
                 "update_time": "2026-09-13T13:53:10.028Z"}})

    payload = m.cmc_fear_greed()

    assert payload_timestamp(payload) is not None


def test_cmc_quote_status_is_live_when_data_is_fresh(monkeypatch):
    """完整契约接线：带时间戳的新鲜载荷必须被判 live，而不是 unavailable。"""
    _no_cache(monkeypatch)
    monkeypatch.setattr(m, "_fetch", lambda url, headers=None, **kw: CMC_QUOTE_RESP)
    # 不走源级熔断/缓存状态文件
    monkeypatch.setattr(m, "_read_source_state", lambda: {})

    payload = m.cmc_quote("BTC")
    # 签名是 attach_source_contract(payload, source_id, *, symbol=...)
    from source_contract import attach_source_contract
    # status 由调用方声明（契约设计如此：status or "unavailable"）；
    # 这里模拟采集器成功路径 —— 关键是带时间戳的 live 载荷不能因缺时间戳被降级。
    wired = attach_source_contract(payload, "cmc", status="live", symbol="BTCUSDT")

    status = (wired.get("_source_contract") or {}).get("status")
    assert status == "live", f"期望 live，实得 {status}：{wired.get('_source_contract')}"
