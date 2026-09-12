from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from indicator_source_audit import audit_sources
from tv_indicator_contract import ENTRY_VALID, HALDRO_STATE, NO_TRADE_BITS


def test_checked_in_indicator_sources_match_contract():
    result = audit_sources()
    assert result["ok"] is True
    assert result["contract"]["main_missing_plots"] == []
    assert result["contract"]["sub_missing_plots"] == []
    assert result["sources"]["svp"]["sha256"].startswith("68a34fc32da035880a0b332c")
    assert result["sources"]["aggvol"]["sha256"].startswith("c4c563ef4a08b77cb0ceb73f")


def test_indicator_machine_code_contract_is_explicit():
    assert ENTRY_VALID[-3] == "X禁做"
    assert ENTRY_VALID[2] == "可执行(B/C)"
    assert ENTRY_VALID[3] == "可执行(A)"
    assert HALDRO_STATE == {0: "S0未接/无效", 1: "S1支持多", 2: "S2支持空", 3: "S3冲突", 4: "S4降权"}
    assert NO_TRADE_BITS[16] == "R:R不足"
    assert NO_TRADE_BITS[1024] == "副指标冲突/降权"


def test_packed_machine_fields_round_trip():
    from tv_indicator_contract import (
        decode_contract_pack, decode_evidence_pack, decode_quality_code,
        decode_regime_pack, decode_struct_pack, decode_trigger_pack,
    )
    assert decode_trigger_pack(1203113) == {
        "triggerCode": 2, "age": 31, "fresh": True, "signalState": 0,
    }
    assert decode_regime_pack(10278) == {
        "regimeCode": 1, "preferredModelCode": 2, "confidence": 78,
    }
    assert decode_contract_pack(171011)["valid"] is True
    assert decode_contract_pack(171011)["marketCode"] == 1
    assert decode_evidence_pack(202609051111) == {
        "versionDate": 20260905, "direction": 0, "locationValid": True,
        "triggerConfirmed": True, "barClosed": True,
    }
    assert decode_struct_pack(823221) == {
        "fvgQuality": 82, "obCode": 31, "bosCode": 0, "liquidityCode": 0,
    }
    assert decode_quality_code(66)["cvdLowQuality"] is True
