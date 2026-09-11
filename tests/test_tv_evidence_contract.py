"""Evidence fixtures model the real data_get_study_values name/values envelope.

Read-only MCP observation: SVP+ICT+VWAP+CVD plus Volume/Aggregated studies;
values are strings (e.g. Execution Pack '100\u202fK'), no symbol/resolution/id.
New evidence values below are CONTRACT TEST INPUTS, not observed live output.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import tv_data_bridge as bridge

VERSION = 20260905


def payload(direction=1, location=1, trigger=1, closed=1):
    return {"success": True, "study_count": 3, "studies": [
        {"name": "Volume", "values": {"Volume": "95.43\u202fK"}},
        {"name": "SVP+ICT+VWAP+CVD", "values": {
            "MCP Execution Pack": "100\u202fK",
            "MCP Evidence Pack": str(VERSION * 10000 + (direction + 1) * 1000
                                     + location * 100 + trigger * 10 + closed),
            "MCP Evidence Bar Time": "1788652800000",
            "MCP Evidence Close Time": "1788667200000",
        }},
        {"name": "Volume Aggregated Spot & Futures", "values": {"HALDRO Valid Code": "0"}},
    ]}


def read(monkeypatch, data):
    monkeypatch.setattr(bridge, "_tv_json", lambda *a, **kw: data)
    return bridge.read_indicators("BINANCE:BTCUSDT.P")


def test_decode_contract_in_actual_transport_shape_without_inventing_identity(monkeypatch):
    result = read(monkeypatch, payload())
    assert result["mcp_evidence_version"] == VERSION
    assert result["mcp_evidence_direction"] == 1
    assert result["mcp_location_valid"] is True
    assert result["mcp_trigger_confirmed"] is True
    assert result["mcp_bar_closed"] is True
    assert result["mcp_evidence_bar_time"] == 1788652800000
    assert result["mcp_evidence_close_time"] == 1788667200000
    for key in ("symbol", "timeframe", "study_id"):
        assert "mcp_evidence_" + key not in result
    assert result["mcp_execution_pack"] == "100\u202fK"


@pytest.mark.parametrize("direction", [-1, 0, 1])
@pytest.mark.parametrize("flags", [(0, 0, 0), (1, 0, 1), (0, 1, 1), (1, 1, 1)])
def test_direction_and_explicit_false_flags(monkeypatch, direction, flags):
    result = read(monkeypatch, payload(direction, *flags))
    assert result["mcp_evidence_direction"] == direction
    assert [result[k] for k in ("mcp_location_valid", "mcp_trigger_confirmed", "mcp_bar_closed")] == list(map(bool, flags))


@pytest.mark.parametrize("pack", [None, "", 0, "0", True, -1, "NaN", float("inf"),
                                  "202.61\u202fB", "202609052111.1", "2.02609052111e11",
                                  "20260905211,1", 202609042111, 202609053111,
                                  202609052211, 202609052121, 202609052112, 2 ** 53])
def test_malformed_or_unsupported_pack_has_no_evidence(monkeypatch, pack):
    data = payload()
    data["studies"][1]["values"]["MCP Evidence Pack"] = pack
    result = read(monkeypatch, data)
    assert not any(k.startswith("mcp_evidence_") for k in result)
    assert "mcp_location_valid" not in result
    assert "mcp_trigger_confirmed" not in result
    assert "mcp_bar_closed" not in result


@pytest.mark.parametrize("foreign", ["Volume Aggregated Spot & Futures", "AggVol", "Not SVP", "SVPish"])
def test_foreign_studies_cannot_establish_evidence(monkeypatch, foreign):
    data = payload()
    data["studies"][1]["name"] = foreign
    data["studies"][1]["values"].update({
        "MCP Location Valid": True, "MCP Trigger Confirmed": True,
        "MCP Bar Closed": True, "MCP Evidence Version": VERSION,
    })
    result = read(monkeypatch, data)
    assert not any(k.startswith("mcp_evidence_") for k in result)
    assert not any(k in result for k in ("mcp_location_valid", "mcp_trigger_confirmed", "mcp_bar_closed"))


def test_foreign_study_cannot_overwrite_main_timestamps(monkeypatch):
    data = payload(-1, 0, 0, 0)
    data["studies"][2]["values"].update(payload()["studies"][1]["values"])
    data["studies"][2]["values"]["MCP Evidence Bar Time"] = "999"
    result = read(monkeypatch, data)
    assert result["mcp_evidence_bar_time"] == 1788652800000
    assert result["mcp_evidence_direction"] == -1
    assert result["mcp_location_valid"] is False


@pytest.mark.parametrize("bad", [None, 0, "0", False, "", "UNKNOWN", "null"])
def test_invalid_identity_stays_absent(monkeypatch, bad):
    data = payload()
    data.update(symbol=bad, resolution=bad)
    data["studies"][1]["id"] = bad
    result = read(monkeypatch, data)
    for field in ("symbol", "timeframe", "study_id"):
        assert "mcp_evidence_" + field not in result


@pytest.mark.parametrize("tf_field", ["resolution", "timeframe"])
def test_identity_comes_only_from_same_response_not_requested_symbol(monkeypatch, tf_field):
    data = payload()
    data.update(symbol="OANDA:XAUUSD")
    data[tf_field] = "240"
    data["studies"][1]["id"] = "6x1CZu"
    result = read(monkeypatch, data)
    assert result["mcp_evidence_symbol"] == "OANDA:XAUUSD"
    assert result["mcp_evidence_timeframe"] == "240"
    assert result["mcp_evidence_study_id"] == "6x1CZu"


@pytest.mark.parametrize("bad", [None, 0, "0", -1, True, "1.78T", "NaN", "1788652800000.5", 1788667200001])
def test_invalid_or_reversed_source_times_are_not_forwarded(monkeypatch, bad):
    data = payload()
    data["studies"][1]["values"]["MCP Evidence Bar Time"] = bad
    result = read(monkeypatch, data)
    assert "mcp_evidence_bar_time" not in result
    assert "mcp_evidence_close_time" not in result


def test_formula_titles_and_lossless_number_format(monkeypatch):
    data = payload()
    values = data["studies"][1]["values"]
    values["MCP Evidence Pack (version*10000+dir*1000+loc*100+trigger*10+closed)"] = "202,609,052,111.00"
    del values["MCP Evidence Pack"]
    values["MCP Evidence Bar Time (unix ms)"] = "1\u202f788\u202f652\u202f800\u202f000"
    del values["MCP Evidence Bar Time"]
    result = read(monkeypatch, data)
    assert result["mcp_evidence_version"] == VERSION
    assert result["mcp_evidence_bar_time"] == 1788652800000


@pytest.mark.parametrize("duplicate", ["study", "title"])
def test_ambiguous_evidence_fails_closed(monkeypatch, duplicate):
    data = payload()
    if duplicate == "study":
        data["studies"].append(payload(-1)["studies"][1])
    else:
        data["studies"][1]["values"]["MCP Evidence Pack (formula)"] = "202609050111"
    result = read(monkeypatch, data)
    assert "mcp_evidence_version" not in result
    assert "mcp_evidence_bar_time" not in result


@pytest.mark.parametrize("studies", [None, {}, [None], [{"name": "SVP", "values": []}],
                                     [{"name": "SVP", "values": {None: 1}}]])
def test_malformed_study_envelopes_do_not_crash(monkeypatch, studies):
    result = read(monkeypatch, {"success": True, "studies": studies})
    assert "mcp_evidence_version" not in result
