# contracts/__init__.py
"""
字段契约包 - 所有层的输入输出 Schema 定义
使用 TypedDict + Pydantic v2 保证类型安全、序列化一致
"""

from .market_snapshot import MarketSnapshot, TVIndicators, BinanceData, MacroSnapshot, NewsEvent
from .feature_vector import FeatureVector, RegimeLabel, VolRegime, DataGrade, RiskProfile, CVDDivergence
from .regime_output import RegimeOutput
from .candidate_plan import CandidatePlan, Direction
from .gate_verdict import GateResult, GateStatus, FinalVerdict

__all__ = [
    "MarketSnapshot",
    "TVIndicators", 
    "BinanceData",
    "MacroSnapshot",
    "NewsEvent",
    "FeatureVector",
    "RegimeLabel",
    "VolRegime",
    "DataGrade",
    "RiskProfile",
    "CVDDivergence",
    "RegimeOutput",
    "CandidatePlan",
    "Direction",
    "GateResult",
    "GateStatus",
    "FinalVerdict",
]