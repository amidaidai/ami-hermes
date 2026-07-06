from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def test_master_template_contains_dual_indicator_section_and_five_timeframes():
    text = _text("references/master-template-v68.md")
    assert "### 双指标裁决" in text
    assert "HALDRO副驾驶" in text
    for tf in ["| D |", "| 4h |", "| 1h |", "| 15m |", "| 5m |"]:
        assert tf in text


def test_key_user_facing_scripts_do_not_emit_bjt_suffix():
    paths = [
        "scripts/auto_card.py",
        "scripts/x_sentiment_collector.py",
        "scripts/dune_collector.py",
        "scripts/liquidation_collector.py",
        "scripts/qlib_factors.py",
        "scripts/stablecoin_collector.py",
        "scripts/trade_exec_bridge.py",
        "scripts/engine_orchestrator.py",
        "scripts/go_nogo_gate.py",
    ]
    for rel in paths:
        text = _text(rel)
        assert "%Y-%m-%d %H:%M BJT" not in text, rel
        assert " BJT" not in text, rel
        assert "UTC" not in re.sub(r"#.*", "", text), rel


def test_go_nogo_copy_says_eight_gates():
    text = _text("scripts/go_nogo_gate.py")
    assert "下单前八问" in text
    assert "执行GO/NO-GO八问" in text
    assert '"max_score": 8' in text
    assert "GO/NO-GO七问" not in text


def test_monitor_subprocess_decoding_is_utf8_safe():
    text = _text("scripts/行情守望.py")
    assert 'capture_output=True, text=True, encoding="utf-8", errors="replace"' in text
    watchdog = _text("scripts/watchdog.py")
    assert 'text=True, encoding="utf-8", errors="replace"' in watchdog


def test_orion_report_format_has_exact_three_markdown_tables():
    text = _text("scripts/orion_screener_radar.py")
    assert "def build_report" in text
    # Three headers in normal branch plus three in empty branch are expected.
    for header in ["| 来源 | 状态 | 备注 |", "| 品种 | 数据 | 信号 |", "| 品种 | 判断 | 动作 |"]:
        assert header in text
    assert "表1 ·" not in text and "表2 ·" not in text and "表3 ·" not in text


def test_accuracy_gates_use_real_snapshot_freshness_and_xau_monitoring():
    auto = _text("scripts/auto_card.py")
    watchdog = _text("scripts/data_freshness_watchdog.py")
    monitor = _text("scripts/行情守望.py")
    assert "def _refresh_and_mark_snapshot" in auto
    assert 'engine_data["_snapshot_age_h"]' in auto
    assert '"source_snapshot_XAUUSD.json"' in watchdog
    assert "def maybe_refresh_source_snapshot" in monitor
    assert "expired monitor levels caused process_block() to return" in monitor


def test_cross_asset_sentiment_does_not_bleed_into_non_crypto_cards():
    auto = _text("scripts/auto_card.py")
    assert 'if asset == "crypto":\n        try:\n            from coingecko_collector import community_dashboard' in auto
    assert '非加密跳过CoinGecko加密社区面板' in auto
    assert '非加密跳过BTC/crypto预测市场桥' in auto
    assert '非加密不采用BTC缓存' in auto


def test_renderer_stdout_reconfigure_is_pipe_safe():
    render = _text("scripts/render_v8.py")
    assert "def _safe_reconfigure" in render
    assert "except (OSError, ValueError):" in render
    assert "_safe_reconfigure(sys.stdout)" in render
