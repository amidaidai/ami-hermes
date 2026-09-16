"""品种身份归一必须只有一份实现（口径单点 tv_symbols）。

背景：2026-09-16 黄金 TV 口径由 OANDA:XAUUSD 切到 TVC:GOLD。切换时
``auto_card._norm_symbol_for_cache`` 与 ``source_health.canonical_symbol``
各自自带一份 strip 前缀的副本没跟着改 —— ``TVC:GOLD`` 被归成 ``GOLD``，
与期望的 ``XAUUSD`` 不等，后果是：

* XAU 卡门2「TV现场确认」恒为红灯（数据其实新鲜、行动格完整）；
* 管线完成度审计判「TV主周期可用=False」（同一张卡 ① 表却显示 TV 现场，自相矛盾）；
* ``audit_preflight`` 的 tv_live_XAUUSD.json 行恒 FAIL，预检退出码恒 1。

本文件把「同一身份必须处处一致」钉成回归测试：以后再加归一实现必须先过这里。
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auto_card
import source_health
import tv_five_tf_contract
import tv_symbols
from tv_data_bridge import _norm_symbol_for_cache as bridge_norm

GOLD_SPELLINGS = ("XAUUSD", "XAU/USD", "XAU_USD", "GOLD", "TVC:GOLD",
                  "OANDA:XAUUSD", "FOREXCOM:XAUUSD", "FX_IDC:XAUUSD")


def test_every_gold_spelling_normalizes_to_one_identity():
    for raw in GOLD_SPELLINGS:
        keys = {
            "tv_symbols": tv_symbols.norm_identity(raw),
            "auto_card": auto_card._norm_symbol_for_cache(raw),
            "tv_data_bridge": bridge_norm(raw),
            "source_health": source_health.canonical_symbol(raw),
            "five_tf_contract": tv_five_tf_contract._canonical_symbol(raw),
        }
        assert set(keys.values()) == {"XAUUSD"}, f"{raw} 归一不一致: {keys}"


def test_non_gold_identities_stay_distinct():
    # 换口径不得把 BTC 和 XAU 合成一个身份（跨品种污染是老事故）
    assert auto_card._norm_symbol_for_cache("BINANCE:BTCUSDT.P") == "BTCUSDT"
    assert source_health.symbol_matches("BTCUSDT", "BINANCE:BTCUSDT.P") is True
    assert source_health.symbol_matches("XAUUSD", "BINANCE:BTCUSDT.P") is False
    assert source_health.symbol_matches("BTCUSDT", "TVC:GOLD") is False


def test_binance_gold_contract_is_not_merged_into_spot():
    # 合约 ≠ 现货：Binance XAUUSDT 合约 artifact 用裸写法，不得被并进 XAUUSD
    assert auto_card._norm_symbol_for_cache("XAUUSDT") != "XAUUSD"
    assert source_health.symbol_matches("XAUUSD", "XAUUSDT") is False


def test_gold_cache_passes_card_identity_gate(tmp_path=None):
    """真实形态的 XAU 缓存（symbol=TVC:GOLD）必须通过卡面门禁判定。"""
    from datetime import datetime, timedelta

    cache = {
        "timestamp": (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds"),
        "symbol": "TVC:GOLD",
        "fresh": True,
        "stale": False,
        "poc": 4286.088,
        "identity_valid": True,
        "action_table_complete": True,
    }
    status = auto_card._tv_cache_status(cache, "XAUUSD", max_age_minutes=5)
    assert status["usable"] is True, status
    # 反侧（BTC 期望）仍必须被品种门拦下
    assert auto_card._tv_cache_status(cache, "BTCUSDT", max_age_minutes=5)["usable"] is False


def test_preflight_level_identity_check_accepts_new_gold_spelling(tmp_path=None):
    """audit_preflight 走的 source_health 路径也必须认 TVC:GOLD。"""
    import json
    import tempfile
    from datetime import datetime, timezone

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tv_live_XAUUSD.json"
        path.write_text(json.dumps({
            # 显式 UTC：source_health 把无时区时间戳按 UTC 解释，本地时写会被判 8 小时偏差
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "symbol": "TVC:GOLD",
            "last_price": 4321.95,
            "fresh": True,
        }, ensure_ascii=False), encoding="utf-8")
        result = source_health.inspect_json_file(
            path, max_age_hours=2, expected_symbol="XAUUSD")
        assert result["identity_valid"] is True, result
        assert result["fresh"] is True, result
