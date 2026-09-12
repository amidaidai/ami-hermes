#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""副指标（AggVol / HALDRO）字段采集回归 —— 2026-09-12。

## 历史缺陷

`tv_data_bridge.read_indicators()` 里有一行：

    if not _is_main_study(study):
        continue

它把**副指标研究整段丢弃**。后果：缓存 `data/tv_live.json` 的 indicators
里从来没有 `composite` / `haldro_valid_code` / `coverage_exchanges` /
`lsr` / `cvd_anchor_value`，于是卡片长期显示「副指标待刷新」「Composite 待刷新」，
副指标的确认/降级/否决能力被事实上摘掉。

实测（2026-09-12）：图上确实有第三个研究
`Volume Aggregated Spot & Futures`，28 个字段齐备 —— 数据在，只是被过滤掉了。

## 修复契约（本文件锁死）

1. 副研究**只**贡献契约 `DW_ALIASES_SUB` / `LEGACY_DW_ALIASES_SUB` 声明的键。
2. 副研究**不得**写入任何主指标字段（主/副隔离不变）。
3. 副研究**不得**写入证据标志（`mcp_evidence_*` / `mcp_location_valid` 等）。
4. 非副指标研究（随便一个第三方指标）不得注入 SUB 字段。
5. 主研究优先：`setdefault` 保证主研究已有的键不被副研究覆盖。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tv_data_bridge as bridge

MAIN_NAME = "SVP+ICT+VWAP+CVD"
SUB_NAME = "Volume Aggregated Spot & Futures"
FOREIGN_NAME = "Some Random Indicator"


def _payload(main=None, sub=None, foreign=None):
    studies = [{"name": MAIN_NAME, "values": main or {
        "VAH Price": 77328.5, "VAL Price": 77223.5, "POC Price": 77242.75,
        "S VWAP": 77261.0, "MCP Grade Code": 2, "MCP Side Code": 0,
    }}]
    if sub is not None:
        studies.append({"name": SUB_NAME, "values": sub})
    if foreign is not None:
        studies.append({"name": FOREIGN_NAME, "values": foreign})
    return {"success": True, "symbol": "BINANCE:BTCUSDT.P", "studies": studies}


def _read(monkeypatch, data):
    monkeypatch.setattr(bridge, "_tv_json", lambda *a, **k: data)
    return bridge.read_indicators("BINANCE:BTCUSDT.P")


SUB_REAL = {
    "Composite": -11,
    "HALDRO Valid Code": 2,
    "CVD Value": -138.3,
    "Coverage Exchanges": 5,
    "Coverage Spot": 5,
    "Coverage Perp": 4,
    "Volume Ratio": 1.27,
    "HALDRO Risk Code": 128,
    "OI Agreement %": 50,
    "HALDRO Flow Pack (OI*100+CVD*10+SP)": 92,
    "CVD Anchor Value": -138.3,
    "Confirm Score": 1,
}


def test_sub_study_fields_are_collected(monkeypatch):
    """核心回归：副指标字段必须落盘（否则卡面永远「副指标待刷新」）。"""
    ind = _read(monkeypatch, _payload(sub=SUB_REAL))
    assert ind["composite"] == -11
    assert ind["haldro_valid_code"] == 2
    assert ind["cvd_value"] == -138.3
    assert ind["coverage_exchanges"] == 5
    assert ind["coverage_spot"] == 5
    assert ind["coverage_perp"] == 4
    assert ind["volume_ratio"] == 1.27
    assert ind["haldro_risk_code"] == 128
    assert ind["oi_agreement_pct"] == 50
    assert ind["haldro_flow_pack"] == 92
    assert ind["cvd_anchor_value"] == -138.3
    assert ind["confirm_score"] == 1


def test_main_fields_still_collected(monkeypatch):
    """修副指标不能破坏主指标采集。"""
    ind = _read(monkeypatch, _payload(sub=SUB_REAL))
    assert ind["vah_price"] == 77328.5
    assert ind["val_price"] == 77223.5
    assert ind["poc_price"] == 77242.75
    assert ind["s_vwap"] == 77261.0
    assert ind["mcp_grade_code"] == 2


def test_sub_study_cannot_write_main_fields(monkeypatch):
    """主/副隔离：副研究即使带主指标同名字段也不得写入主键。"""
    ind = _read(monkeypatch, _payload(
        main={"VAH Price": 77328.5, "S VWAP": 77261.0},
        sub={"VAH Price": 99999.0, "S VWAP": 88888.0, "POC Price": 77777.0,
             "Composite": -11},
    ))
    assert ind["vah_price"] == 77328.5, "主研究已有时，副研究不得覆盖"
    assert ind["s_vwap"] == 77261.0
    assert "poc_price" not in ind, "主研究没有的字段，副研究也不得补进主键"
    assert ind["composite"] == -11


def test_sub_study_cannot_leak_evidence_flags(monkeypatch):
    """副研究不得建立图表证据 —— evidence 只能来自主研究的校验解码器。"""
    ind = _read(monkeypatch, _payload(sub={
        "Composite": -11,
        "MCP Evidence Pack": 202609121234,
        "MCP Location Valid": True,
        "MCP Trigger Confirmed": True,
        "MCP Bar Closed": True,
        "MCP Evidence Version": 20260905,
    }))
    assert ind["composite"] == -11
    assert not any(k.startswith("mcp_evidence_") for k in ind)
    assert "mcp_location_valid" not in ind
    assert "mcp_trigger_confirmed" not in ind
    assert "mcp_bar_closed" not in ind


def test_foreign_study_cannot_inject_sub_fields(monkeypatch):
    """第三方指标不得冒充副指标（否则图上涨任何带 Composite 的研究都能污染裁决）。"""
    ind = _read(monkeypatch, _payload(foreign={
        "Composite": 999, "CVD Value": 888, "Coverage Exchanges": 7,
    }))
    assert "composite" not in ind
    assert "cvd_value" not in ind
    assert "coverage_exchanges" not in ind


def test_sub_absent_does_not_crash(monkeypatch):
    """图上没有副研究时不得报错，也不得凭空造字段。"""
    ind = _read(monkeypatch, _payload())
    assert ind["vah_price"] == 77328.5
    assert "composite" not in ind


def test_sub_only_payload_still_yields_sub_fields(monkeypatch):
    """只有副研究、没有主研究时，副字段仍应被采（主字段为空）。"""
    data = {"success": True, "symbol": "BINANCE:BTCUSDT.P", "studies": [
        {"name": SUB_NAME, "values": {"Composite": 31, "Coverage Exchanges": 5}},
    ]}
    ind = _read(monkeypatch, data)
    assert ind["composite"] == 31
    assert ind["coverage_exchanges"] == 5


def test_is_sub_study_matches_known_names():
    assert bridge._is_sub_study({"name": SUB_NAME}) is True
    assert bridge._is_sub_study({"name": "AggVol v13"}) is True
    assert bridge._is_sub_study({"name": "HALDRO 副指标"}) is True
    assert bridge._is_sub_study({"name": MAIN_NAME}) is False
    assert bridge._is_sub_study({"name": FOREIGN_NAME}) is False
    assert bridge._is_sub_study({}) is False
