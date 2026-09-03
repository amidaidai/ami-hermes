from pathlib import Path


DESKTOP = Path.home() / "Desktop" / "hermes下载文件"


def test_versioned_indicator_enhancements_exist_with_contract_fields():
    svp = list(DESKTOP.glob("SVP主指标_增强版_修正版_*.pine"))
    agg = list(DESKTOP.glob("AggVol副指标_增强版_*.pine"))
    assert svp and agg
    svp_text = svp[-1].read_text(encoding="utf-8")
    agg_text = agg[-1].read_text(encoding="utf-8")
    assert "MCP State Bus" in svp_text
    assert "txStateBus" in svp_text
    assert "txBarClosed" in svp_text
    assert "MCP ICT State" in svp_text
    assert "质量契约" not in agg_text
    assert "Estimated CVD Flag" not in agg_text
    assert "HALDRO Bar Closed" not in agg_text
    assert "HALDRO Coverage Quality Code" not in agg_text


def test_indicator_enhancements_do_not_add_execution_authority_to_aggvol():
    agg = sorted(DESKTOP.glob("AggVol副指标_增强版_*.pine"))[-1]
    text = agg.read_text(encoding="utf-8")
    assert "Entry Price" not in text
    assert "Stop Price" not in text
    assert "Target Price" not in text


def test_aggvol_lsr_is_a_single_crypto_only_confirmation_source():
    text = sorted(DESKTOP.glob("AggVol副指标_增强版_*.pine"))[-1].read_text(encoding="utf-8")
    assert "f_lsr_a()" in text
    assert "isCryptoA ? f_lsr_a() : na" in text
    assert "LSR" in text
    assert "LSR缺" in text


def test_final_svp_is_original_ict_complete_source_without_extra_state_bus():
    svp = DESKTOP / "SVP主指标_最终精简版_20260902.pine"
    text = svp.read_text(encoding="utf-8")
    assert "ICTLevel" in text
    assert "sweptHighRejected" in text and "sweptLowReclaimed" in text
    assert "MCP State Bus" not in text
    assert "MCP ICT State" not in text


def test_lsr_fix_uses_binance_perpetual_metric_suffix():
    text = (DESKTOP / "AggVol副指标_LSR修正版_20260902.pine").read_text(encoding="utf-8")
    assert "baseA + 'USDT.P_LSR'" in text
    assert "baseA + 'USDT_LSR'" not in text
