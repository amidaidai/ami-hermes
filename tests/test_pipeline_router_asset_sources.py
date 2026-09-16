from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pipeline_router import cron_sources, pipeline_summary


def test_crypto_cron_sources_match_real_cache_filenames():
    """清算源 2026-09-15 换血：liquidation_pressure（cron 已退役）→ liquidation_flow。

    liquidation_flow 只覆盖 BTC/ETH，所以走 ``CRON_SOURCES_BY_SYMBOL`` 按品种追加，
    不写进 crypto 通用清单 —— 否则分析 SOL 时会拿 BTC 的清算缓存冒充已消费。
    """
    # coinlobster（2026-09-16 外部验证层）同样是 BTC 口径，走 BY_SYMBOL 追加。
    assert cron_sources("BTCUSDT") == [
        "dune_cache",
        "deribit_options",
        "x_sentiment",
        "qlib_factors",
        "liquidation_flow",
        "coinlobster",
    ]
    assert "liquidation_pressure" not in cron_sources("BTCUSDT")
    assert cron_sources("SOLUSDT") == [
        "dune_cache",
        "deribit_options",
        "x_sentiment",
        "qlib_factors",
    ]
    assert "coinlobster" not in cron_sources("SOLUSDT")
    assert "coinlobster" not in cron_sources("XAUUSD")
    # 摘要展示必须走 cron_source_file 映射：源名 ≠ 文件名，
    # 曾把 x_sentiment 显示成不存在的 data/x_sentiment.json。
    summary = pipeline_summary("BTCUSDT", "full")
    assert "data/x_sentiment_context.json" in summary
    assert "data/x_sentiment.json" not in summary
    assert "data/liquidation_flow.json" in summary


def test_noncrypto_pipeline_descriptions_do_not_claim_crypto_sentiment():
    summary = pipeline_summary("XAUUSD", "full")
    assert "FG(加密)" not in summary
    assert "CGTrending" not in summary
    assert "BTC-SPX-XAU-DXY" not in summary
    assert "x_search黄金/XAU实时情绪" in summary
    assert "XAU-DXY-SPX-US10Y" in summary


def test_index_and_option_summaries_do_not_claim_crypto_sentiment():
    """index/option 曾回退到通用（加密口径）文案：SPX500 的 corr 写成 BTC-SPX-XAU-DXY。"""
    for symbol in ("SPX500", "AAPL240119C150"):
        summary = pipeline_summary(symbol, "full")
        assert "FG(加密)" not in summary, symbol
        assert "CGTrending" not in summary, symbol
        assert "BTC-SPX-XAU-DXY" not in summary, symbol


def test_stock_pipeline_declares_stock_specific_data_matrix():
    summary = pipeline_summary("AAPL", "full")
    assert "公司/行业/财报事件" in summary
    assert "AAPL-SPX-NDX-VIX" in summary
