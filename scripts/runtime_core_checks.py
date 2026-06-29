#!/usr/bin/env python3
"""
棠溪 · 核心模块测试套件 v1.1
覆盖: scoring_engine · risk_constitution · five_model_matcher · hard_stop · regime_classifier · backtest_runner · equity_tracker

运行: pytest scripts/test_core.py -v
"""

import sys, os, json, pytest
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


# ═══════════════════════════════════════════════════
# scoring_engine 测试
# ═══════════════════════════════════════════════════

class TestScoringEngine:
    def test_full_score_bearish(self):
        """偏空场景完整评分"""
        from scoring_engine import score_setup
        result = score_setup(
            symbol="BTCUSDT",
            tv_levels={"S VWAP": 64308, "EMA 9": 64066},
            cvd_value=-469, cvd_slope=-102.5, taker_ratio=0.7073,
            volume_ratio=0.85, cvd_quality="C",
            tf_consensus=3, tf_total=4,
            entry_price=64308, stop_price=64116, target1_price=63668,
            atr_value=450, risk_usd=2.03, account_balance=67.52,
            x_direction="bearish", cg_sentiment_pct=72, fear_greed=15,
        )
        assert result["total"] > 0
        assert result["total"] <= 14
        assert result["max_score"] == 14.0
        assert "symbol" in result
        assert "breakdown" in result
        # 检查每个维度的分数在范围内
        for key, bd in result["breakdown"].items():
            assert 0 <= bd["score"] <= bd["max"], f"{key} score out of range"
        assert result["total"] >= 5  # 至少中等评分

    def test_score_cvd_discount(self):
        """CVD C级应有折扣"""
        from scoring_engine import score_orderflow
        a = score_orderflow(cvd_value=-469, cvd_slope=-102, taker_ratio=0.7, cvd_quality="A")
        c = score_orderflow(cvd_value=-469, cvd_slope=-102, taker_ratio=0.7, cvd_quality="C")
        assert c["score"] < a["score"], "C级应低于A级"

    def test_score_rr_violation(self):
        """R:R不合格应检测"""
        from scoring_engine import score_risk
        good = score_risk(entry_price=64308, stop_price=64116, target1_price=63668)
        bad = score_risk(entry_price=64308, stop_price=64116, target1_price=64200)
        assert good["score"] > bad["score"], "R:R不合格应扣分"

    def test_score_blackout(self):
        """新闻黑窗期应禁止"""
        from scoring_engine import score_catalyst
        result = score_catalyst(blackout_active=True)
        assert result["score"] == 0
        assert "禁做" in result["details"][0]

    def test_score_extreme_fear(self):
        """极端恐慌应有信号"""
        from scoring_engine import score_sentiment
        result = score_sentiment(x_direction="bearish", x_strength="high",
                                  cg_sentiment_pct=72, fear_greed=15)
        assert result["score"] >= 1.5
        assert any("极度恐惧" in d for d in result["details"])


# ═══════════════════════════════════════════════════
# risk_constitution 测试
# ═══════════════════════════════════════════════════

class TestRiskConstitution:
    def test_normal_trade_allowed(self):
        """正常仓位应允许"""
        from risk_constitution import check_constitution, RiskState
        state = RiskState(daily_starting_balance=100)
        result = check_constitution("BTCUSDT", risk_usd=2.0, account_balance=100,
                                      entry_price=64000, stop_price=63800, target1_price=64400,
                                      atr_value=400, state=state)
        assert result["allowed"]

    def test_excessive_risk_blocked(self):
        """超大风险应拒绝"""
        from risk_constitution import check_constitution, RiskState
        state = RiskState(daily_starting_balance=100)
        result = check_constitution("BTCUSDT", risk_usd=10.0, account_balance=100,
                                      entry_price=64000, stop_price=63800, target1_price=64400,
                                      atr_value=400, state=state)
        assert not result["allowed"] or result["risk_tier"] != "常规"

    def test_consecutive_losses_suspend(self):
        """连续亏损3笔应暂停"""
        from risk_constitution import check_constitution, RiskState
        state = RiskState(loss_streak=3, daily_starting_balance=100)
        result = check_constitution("BTCUSDT", risk_usd=2.0, account_balance=100,
                                      state=state)
        violations = " ".join(result.get("violations", []))
        assert "亏损" in violations or result["risk_tier"] != "常规"

    def test_daily_drawdown_suspend(self):
        """日回撤5%应暂停"""
        from risk_constitution import check_constitution, RiskState
        state = RiskState(daily_realized_pnl=-5, daily_starting_balance=100)
        result = check_constitution("BTCUSDT", risk_usd=1.0, account_balance=95,
                                      state=state)
        violations = " ".join(result.get("violations", []))
        assert "回撤" in violations or not result["allowed"]

    def test_kelly_calculation(self):
        """Kelly仓位计算"""
        from risk_constitution import kelly_position_size
        result = kelly_position_size(win_rate=0.6, avg_win_r=2.0, avg_loss_r=1.0,
                                       account_balance=100)
        assert result["kelly_raw"] > 0
        assert result["suggested_risk_usd"] > 0
        assert result["suggested_risk_usd"] <= 100 * 0.03

    def test_kelly_no_data(self):
        """无数据时保守默认"""
        from risk_constitution import kelly_position_size
        result = kelly_position_size(win_rate=0, avg_win_r=0, avg_loss_r=0,
                                       account_balance=100)
        assert "样本不足" in result["method"]


# ═══════════════════════════════════════════════════
# five_model_matcher 测试
# ═══════════════════════════════════════════════════

class TestFiveModelMatcher:
    def test_vwap_rejection_short(self):
        """价格<VWAP + EMA空头 → 做空"""
        from five_model_matcher import vwap_rejection
        result = vwap_rejection(63980, 64308, 63988, 63668, 64066, 64266, -469, -102)
        assert result.direction == "short"
        assert len(result.setups) >= 1
        assert result.setups[0].entry > 63980  # 入场在VWAP上方

    def test_val_reclaim_long(self):
        """价格<VAL → 回收入场做多"""
        from five_model_matcher import val_reclaim
        result = val_reclaim(63600, 63985, 64308, 64684, -469)
        assert result.direction == "long"

    def test_breakout_accept_both_sides(self):
        """突破接受两种方向"""
        from five_model_matcher import breakout_accept
        long_r = breakout_accept(64600, 64500, "resistance", 450, 0)
        short_r = breakout_accept(63800, 64000, "support", 450, 0)
        assert long_r.direction == "long"
        assert short_r.direction == "short"

    def test_generate_all_returns_best(self):
        """全量运行返回最佳"""
        from five_model_matcher import generate_all_setups
        result = generate_all_setups(
            current_price=63980,
            vwap=64308, vwap_band1=63988, vwap_band2=63668,
            vah=64806, val=63985, poc=64684,
            ema9=64066, ema21=64266,
            recent_high=66192, recent_low=63696,
            atr=450, cvd_value=-469,
        )
        assert result["best_setup"] is not None
        assert len(result["matched_models"]) >= 1
        assert result["best_setup"]["confidence"] >= 70

    def test_rr_ratio_positive(self):
        """所有入场的R:R应≥0"""
        from five_model_matcher import generate_all_setups
        result = generate_all_setups(
            current_price=63980,
            vwap=64308, vwap_band1=63988, vwap_band2=63668,
            vah=64806, val=63985, poc=64684,
            ema9=64066, ema21=64266,
            recent_high=66192, recent_low=63696,
            atr=450, cvd_value=-469,
        )
        for s in result["all_setups"]:
            assert s["rr_ratio"] >= 0, f"{s['model']} R:R negative"


# ═══════════════════════════════════════════════════
# hard_stop 测试
# ═══════════════════════════════════════════════════

class TestHardStop:
    def test_position_size_short(self):
        """做空仓位计算"""
        from hard_stop import position_size
        result = position_size(entry=64000, stop=64500, risk_usd=2.0, leverage=100)
        assert "error" not in result
        assert result["quantity"] > 0
        assert result["margin"] > 0

    def test_position_size_long(self):
        """做多仓位计算"""
        from hard_stop import position_size
        result = position_size(entry=64000, stop=63500, risk_usd=2.0, leverage=100)
        assert result["quantity"] > 0

    def test_min_quantity_floor(self):
        """最小0.001 BTC"""
        from hard_stop import position_size
        result = position_size(entry=64000, stop=63999, risk_usd=0.01, leverage=100)
        assert result["quantity"] >= 0.001

    def test_dry_run_stop_loss(self):
        """模拟模式止损"""
        from hard_stop import execute_stop_loss
        result = execute_stop_loss("BTCUSDT", "short", 64283, 64510,
                                    risk_usd=2.03, dry_run=True)
        assert result["success"]
        assert len(result["orders"]) >= 2  # entry + stop

    def test_dry_run_with_targets(self):
        """模拟模式含止盈"""
        from hard_stop import execute_stop_loss
        result = execute_stop_loss("BTCUSDT", "short", 64283, 64510,
                                    risk_usd=2.03, target1=63637, dry_run=True)
        assert len(result["orders"]) >= 3  # entry + stop + tp1


# ═══════════════════════════════════════════════════
# regime_classifier 测试
# ═══════════════════════════════════════════════════

class TestRegimeClassifier:
    def test_low_vol_bear(self):
        """低波下跌分类"""
        from regime_classifier import classify_regime
        result = classify_regime(vix=18.5, btc_change_24h_pct=-2.9,
                                  btc_volatility_20d_pct=3.0, fear_greed=50)
        assert result.name.startswith("LOW_VOL")

    def test_extreme_fear_override(self):
        """极端恐慌应修正风险等级"""
        from regime_classifier import classify_regime
        result = classify_regime(vix=18.5, btc_change_24h_pct=-2.9,
                                  btc_volatility_20d_pct=3.0, fear_greed=15)
        assert "极度恐惧" in result.trading_implications[0] or result.risk_level == "extreme"

    def test_high_vol_bull(self):
        """高波上涨"""
        from regime_classifier import classify_regime
        result = classify_regime(vix=25, spy_change_pct=1.5, btc_change_24h_pct=5,
                                  btc_volatility_20d_pct=5.5)
        assert "HIGH_VOL" in result.name


class TestBacktestRunner:
    def test_import(self):
        """确保回测模块可导入"""
        from backtest_runner import run_backtest, format_result, BacktestResult
        assert BacktestResult is not None

    def test_ema_calc(self):
        """EMA计算正确"""
        from backtest_runner import calc_ema
        data = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        ema9 = calc_ema(data, 9)
        assert len(ema9) == 10
        assert ema9[-1] > 0

    def test_atr_calc(self):
        """ATR计算正确"""
        from backtest_runner import calc_atr
        highs = [105, 106, 107]
        lows = [95, 94, 93]
        closes = [100, 100, 100]
        atr = calc_atr(highs, lows, closes, 14)
        assert len(atr) == 3

    def test_vwap_calc(self):
        """VWAP计算正确"""
        from backtest_runner import calc_vwap
        h = [10, 10, 10]
        l = [8, 8, 8]
        c = [9, 9, 9]
        v = [100, 100, 100]
        vwap = calc_vwap(h, l, c, v)
        assert len(vwap) == 3
        assert abs(vwap[-1] - 9) < 0.1


class TestEquityTracker:
    def test_empty_reviews(self):
        """无复盘记录时返回起点"""
        from equity_tracker import build_equity_curve
        result = build_equity_curve(initial_balance=100, reviews=[])
        assert result["total_trades"] == 0
        assert result["current_balance"] == 100
        assert len(result["points"]) == 1

    def test_single_win(self):
        """单笔盈利"""
        from equity_tracker import build_equity_curve
        reviews = [{"plan_id": "test-1", "taken": True, "result_r": 2.0, "risk_usd": 10, "model": "VWAP反抽", "time": "2026-01-01", "test": False}]
        result = build_equity_curve(initial_balance=100, reviews=reviews)
        assert result["total_trades"] == 1
        assert result["wins"] == 1
        assert result["current_balance"] == 120

    def test_skip_test_trades(self):
        """跳过测试记录"""
        from equity_tracker import build_equity_curve
        reviews = [{"taken": True, "result_r": 5.0, "test": True, "plan_id": "test"}]
        result = build_equity_curve(initial_balance=100, reviews=reviews)
        assert result["total_trades"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
