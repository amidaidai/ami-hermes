from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pipeline_router import cron_sources, pipeline_summary


def test_crypto_cron_sources_match_real_cache_filenames():
    assert cron_sources("BTCUSDT") == [
        "dune_cache",
        "deribit_options",
        "x_sentiment",
        "qlib_factors",
        "liquidation_pressure",
    ]


def test_noncrypto_pipeline_descriptions_do_not_claim_crypto_sentiment():
    summary = pipeline_summary("XAUUSD", "full")
    assert "FG(加密)" not in summary
    assert "CGTrending" not in summary
    assert "BTC-SPX-XAU-DXY" not in summary
    assert "x_search黄金/XAU实时情绪" in summary
    assert "XAU-DXY-SPX-US10Y" in summary


def test_stock_pipeline_declares_stock_specific_data_matrix():
    summary = pipeline_summary("AAPL", "full")
    assert "公司/行业/财报事件" in summary
    assert "AAPL-SPX-NDX-VIX" in summary
