from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import risk_constitution as rc


def test_adaptive_risk_usd_high_vol_reduces():
    # 高波动（ATR% = 4%）→ 仓位缩小，risk_usd < 基准
    r = rc.adaptive_risk_usd(account_balance=100.0, atr_pct=0.04, base_risk_pct=0.02)
    assert r["risk_usd"] < 2.0
    assert r["multiplier"] < 1.0
    assert r["regime"] == "高波动"


def test_adaptive_risk_usd_low_vol_increases_capped():
    # 低波动（ATR% = 0.5%）→ 仓位放大但受 max_mult 与单笔上限约束
    r = rc.adaptive_risk_usd(account_balance=100.0, atr_pct=0.005, base_risk_pct=0.02)
    assert r["risk_usd"] >= 2.0
    assert r["multiplier"] > 1.0
    # 单笔风险绝不超过账户 10%（本金100→上限10U）
    assert r["risk_usd"] <= 10.0


def test_adaptive_risk_usd_normal_vol_near_base():
    # 正常波动（ATR% ≈ 基准2%）→ 接近基准 risk_usd
    r = rc.adaptive_risk_usd(account_balance=100.0, atr_pct=0.02, base_risk_pct=0.02)
    assert abs(r["risk_usd"] - 2.0) < 0.5
    assert abs(r["multiplier"] - 1.0) < 0.2


def test_adaptive_risk_usd_hard_cap_10usd():
    # 极低波动也不得突破单笔 10U 硬上限
    r = rc.adaptive_risk_usd(account_balance=1000.0, atr_pct=0.001, base_risk_pct=0.02)
    assert r["risk_usd"] <= 10.0
    assert r["capped"] is True


def test_adaptive_risk_usd_zero_atr_safe():
    # ATR 为 0 / 缺失 → 回退基准，不崩
    r = rc.adaptive_risk_usd(account_balance=100.0, atr_pct=0.0, base_risk_pct=0.02)
    assert r["risk_usd"] == 2.0
    assert r["multiplier"] == 1.0
