# contracts 包模板文件（可直接复制为正式代码）

## 1. contracts/__init__.py
```python
"""Contracts package for Tangxi vNext Decision Loop.

All layer interfaces defined as TypedDict with `extra="forbid"` for strict validation.
"""

from .market_snapshot import MarketSnapshot, TVIndicators, BinanceData, MacroSnapshot, NewsEvent
from .feature_vector import FeatureVector, RegimeLabel, VolRegime, DataGrade
from .regime_output import RegimeOutput, RiskProfile, CVDDivergence
from .candidate_plan import CandidatePlan, Direction
from .gate_verdict import GateResult, FinalVerdict, GateStatus

__all__ = [
    "MarketSnapshot", "TVIndicators", "BinanceData", "MacroSnapshot", "NewsEvent",
    "FeatureVector", "RegimeLabel", "VolRegime", "DataGrade",
    "RegimeOutput", "RiskProfile", "CVDDivergence",
    "CandidatePlan", "Direction",
    "GateResult", "FinalVerdict", "GateStatus",
]
```

## 2. contracts/market_snapshot.py
```python
from typing import TypedDict, Literal, NotRequired
from datetime import datetime

class TVIndicators(TypedDict, extra="forbid"):
    # SVP 主指标
    svp_vah: float
    svp_val: float
    svp_poc: float
    svp_vwap: float
    svp_band1_high: float
    svp_band1_low: float
    svp_band2_high: float
    svp_band2_low: float
    svp_w_vwap: float
    svp_m_vwap: float
    # HALDRO 副指标
    haldro_composite: float
    haldro_oi_trend: float
    haldro_cvd_trend: float
    haldro_confirmation: float
    haldro_htf_bias: Literal["bull", "bear", "neutral"]
    # 基础指标
    ema_9: float
    ema_21: float
    ema_34: float
    ema_55: float
    atr_14: float
    adx_14: float
    cvd: float
    cvd_slope: float

class BinanceData(TypedDict, extra="forbid"):
    spot_price: float
    futures_oi: float
    oi_change_pct: float
    funding_rate: float
    taker_buy_ratio: float
    taker_sell_ratio: float
    long_short_ratio: float

class MacroSnapshot(TypedDict, extra="forbid"):
    dxy: float
    us10y: float
    etf_flow_btc: float  # B单位
    cot_commercial_net: float
    options_pcr: float
    options_maxpain: float
    news_event: NotRequired[NewsEvent]

class NewsEvent(TypedDict, extra="forbid"):
    event_name: str
    event_time: int  # UTC ms
    impact: Literal["high", "medium", "low"]
    blackout_before_min: int  # 前N分钟禁做
    blackout_after_min: int   # 后N分钟禁做

class MarketSnapshot(TypedDict, extra="forbid"):
    symbol: str
    ts: int  # UTC ms
    price: float
    ohlcv: dict[str, list[float]]  # {"o":[], "h":[], "l":[], "c":[], "v":[]} 多周期
    tv_indicators: TVIndicators
    binance: BinanceData
    macro: MacroSnapshot
    news: NewsEvent | None
```

## 3. contracts/feature_vector.py
```python
from typing import TypedDict, Literal
from datetime import datetime

RegimeLabel = Literal[
    "bull_calm", "bull_normal", "bull_vol",
    "bear_calm", "bear_normal", "bear_vol",
    "range_calm", "range_normal", "range_vol"
]

VolRegime = Literal["calm", "normal", "volatile", "extreme"]

DataGrade = Literal["A", "A-", "B", "C", "D"]

class FeatureVector(TypedDict, extra="forbid"):
    # 结构位相对价格（ATR归一化）
    dist_vwap_atr: float
    dist_poc_atr: float
    dist_vah_atr: float
    dist_val_atr: float
    # 趋势/动量
    ema_stack: Literal["bull", "bear", "mixed"]
    adx: float
    adx_rising: bool
    # 订单流
    cvd_slope: float
    taker_ratio: float
    oi_change_pct: float
    funding_rate: float
    ls_ratio: float
    # 宏观/体制
    regime: RegimeLabel
    vol_regime: VolRegime
    btc_corr: float
    # 质量
    data_grade: DataGrade
    snapshot_age_sec: float
```

## 4. contracts/regime_output.py
```python
from typing import TypedDict, Literal
from .feature_vector import RegimeLabel

RiskProfile = Literal["conservative", "normal", "aggressive"]
CVDDivergence = Literal["bullish", "bearish", "none"]

class RegimeOutput(TypedDict, extra="forbid"):
    regime: RegimeLabel
    position_multiplier: float
    allowed_models: list[str]
    risk_profile: RiskProfile
    cvd_divergence: CVDDivergence
    notes: str
```

## 5. contracts/candidate_plan.py
```python
from typing import TypedDict, Literal

Direction = Literal["long", "short"]

class CandidatePlan(TypedDict, extra="forbid"):
    model_id: str
    direction: Direction
    entry: float
    stop: float
    targets: list[float]
    rr: float
    confidence: float
    regime_fit: bool
    features_used: dict[str, float]  # 关键特征值，用于复盘追溯
```

## 6. contracts/gate_verdict.py
```python
from typing import TypedDict, Literal
from .candidate_plan import CandidatePlan

GateStatus = Literal["green", "yellow", "red"]

class GateResult(TypedDict, extra="forbid"):
    gate_name: str
    status: GateStatus
    reason: str

class FinalVerdict(TypedDict, extra="forbid"):
    go: bool
    plan: CandidatePlan | None
    gates: list[GateResult]
    risk_usd: float
    leverage: int
    cooldown_minutes: int
    verdict_text: str
```

## 使用示例（单测中验证）

```python
# tests/test_contracts.py
import json
from contracts import MarketSnapshot, FeatureVector, RegimeOutput, CandidatePlan, FinalVerdict

def test_contract_serialization_roundtrip():
    """所有契约必须支持 JSON 序列化往返，extra=forbid 禁止多余字段"""
    
    # 1. MarketSnapshot
    snap = MarketSnapshot(
        symbol="BTCUSDT",
        ts=1720000000000,
        price=65000.0,
        ohlcv={"o": [64900]*100, "h": [65100]*100, "l": [64800]*100, "c": [65000]*100, "v": [100]*100},
        tv_indicators={...},  # 完整填充
        binance={...},
        macro={...},
        news=None,
    )
    json_str = json.dumps(snap)
    restored = json.loads(json_str)
    assert restored["symbol"] == "BTCUSDT"
    
    # 2. FeatureVector
    fv = FeatureVector(
        dist_vwap_atr=0.3, dist_poc_atr=0.8, dist_vah_atr=1.2, dist_val_atr=-1.1,
        ema_stack="bull", adx=25.0, adx_rising=True,
        cvd_slope=0.05, taker_ratio=1.1, oi_change_pct=0.02, funding_rate=0.0001, ls_ratio=1.2,
        regime="bull_normal", vol_regime="normal", btc_corr=1.0,
        data_grade="A", snapshot_age_sec=5.0,
    )
    assert FeatureVector(**json.loads(json.dumps(fv))) == fv
    
    # 3. RegimeOutput
    ro = RegimeOutput(
        regime="bull_normal", position_multiplier=1.5,
        allowed_models=["VWAP反抽", "突破接受", "POC拒绝", "动量延续"],
        risk_profile="normal", cvd_divergence="none", notes=""
    )
    assert RegimeOutput(**json.loads(json.dumps(ro))) == ro
    
    # 4. CandidatePlan
    cp = CandidatePlan(
        model_id="VWAP反抽", direction="long", entry=65000, stop=64500, targets=[65500, 66000],
        rr=2.0, confidence=0.78, regime_fit=True,
        features_used={"dist_vwap_atr": 0.3, "cvd_slope": 0.05}
    )
    assert CandidatePlan(**json.loads(json.dumps(cp))) == cp
    
    # 5. FinalVerdict
    fv = FinalVerdict(
        go=True, plan=cp,
        gates=[{"gate_name": "data_freshness", "status": "green", "reason": "数据A级·0.5h新鲜"}],
        risk_usd=2.5, leverage=10, cooldown_minutes=0,
        verdict_text="✅ GO · 绿灯8/8"
    )
    assert FinalVerdict(**json.loads(json.dumps(fv))) == fv

if __name__ == "__main__":
    test_contract_serialization_roundtrip()
    print("✅ All contracts pass roundtrip serialization test")
```