---
name: risk-management-system
description: "棠溪交易风控系统 v2.0 — 仓位计算(固定分数/Kelly×体制乘数)、ATR夹层止损、Protections(StoplossGuard/Cooldown/MaxDrawdown)、动态回撤降级、波动率自适应、相关性限制、组合温度、亏损冷却、C级连击停止。对接 risk_constitution.py, position_sizer.py, hard_stop.py, correlation_matrix.py"
version: 2.0.0
author: 安禾
tags: [risk, risk-management, position-sizing, ATR, stop-loss, drawdown, protections, Kelly, correlation, cooling-off]
---

# 风控系统 v2.0 — Risk Management

## 核心脚本

| 脚本 | 功能 |
|------|------|
| `risk_constitution.py` | 风险宪法 — 仓位+Protections+回撤降级+体制乘数 |
| `position_sizer.py` | 固定分数仓位 + 波动率自适应 + 体制乘数 |
| `hard_stop.py` | ATR夹层止损 + 硬停 + 执行日志 |
| `correlation_matrix.py` | 跨品种相关性矩阵 |
| `readiness_report.py` | 48h上线前就绪报告 |

## 仓位公式（v2.1 单一口径）

```
基础风险 = min(净值 × 1% × 回撤乘数 × 波动乘数, 净值 × 1%, 10U)
最终风险 = 基础风险 ÷ 执行体制风险除数
仓位数量 = 最终风险 ÷ |入场价 - 止损价|

风险除数示例：
  趋势正常 = 1.0
  平衡/待确认 = 1.25-1.5
  收敛 = 1.5（等待突破接受）
  扩张/高波 = 2.0或更高
  禁做 = 0（直接拦截，不参与除法）
```

**风险除数越大，仓位越小。** 必须先执行1%/10U硬上限，再做体制缩小；否则低波动放大与体制除数的先后顺序会破坏比例。方向背景不直接改变风险除数。

## 组合风控（v2.0 新规则）

### 相关性限制
- 新仓与现有持仓相关性 > 0.7 → 仓位 × 0.5
- BTC-ETH 相关性 0.85 → 同向持仓自动减半

### 组合温度
- 组合总风险 = Σ(各仓位风险%)
- > 15% → 跳过新仓
- > 25% → 强制减仓至 20%

### 亏损冷却
| 触发 | 动作 |
|------|------|
| 单笔亏 > 1.5% | 冷却 5 分钟 |
| 连续 2 个 C 级 | 当日禁做 (X) |
| 当日亏 > 3% | 当日停止 |
| 连续 3 笔亏损 | 仓位减半 + 强制复盘 |

## 原有规则（继续保留）

- **固定分数**: MAX_RISK_PER_TRADE_PCT = 1%
- **波动率自适应**: vol_multiplier = clamp(0.5, avg_ATR/current_ATR, 1.5)
- **ATR止损夹层**: 0.5×ATR ≤ 止损 ≤ 2.5×ATR
- **Protections**: StoplossGuard + CooldownPeriod + MaxDrawdown
- **动态回撤降级**: DD>5%→0.75×, >8%→0.5×, >12%→0.25×, >15%→0.1×, >20%→暂停

## vNext 架构集成点（2026-07-10 决策闭环架构落地）

在「决策闭环为中心」的 vNext 架构中，风控宪法重构为 **单一真相源** `scripts/risk_constitution_v2.py`，**回测/实盘共用同一套代码**。

### 字段契约（统一入口）

```python
# scripts/risk_constitution_v2.py

from contracts.risk import RiskInputs, RiskOutputs, ProtectionState

def evaluate_risk(inputs: RiskInputs) -> RiskOutputs:
    \"\"\"
    单一入口：所有风控判断（仓位、止损带、Protections、降级、相关性、频率、冷却）
    回测、实盘、复盘三端调用同一函数，保证一致性。
    \"\"\"
    ...

# RiskInputs（TypedDict）
class RiskInputs(TypedDict):
    account_balance: float
    atr: float
    regime_multiplier: float          # 来自 RegimeOutput.position_multiplier
    risk_profile: RiskProfile         # "conservative" | "normal" | "aggressive"
    entry_price: float
    stop_price: float
    target1_price: float
    symbol: str
    current_positions: list[Position] # 含 symbol, direction, size, entry
    risk_state: RiskState             # 日/周盈亏、连亏数、未复盘数、交易频率、最后止损时间
    protections_state: ProtectionState # StoplossGuard/Cooldown/MaxDrawdown 状态
    has_major_news: bool
    volatility_24h_pct: float

# RiskOutputs（TypedDict）
class RiskOutputs(TypedDict):
    allowed: bool
    risk_usd: float                   # 最终风险金额（经所有守卫）
    risk_tier: RiskTier               # "normal" | "light" | "half" | "blocked"
    position_size: float              # 最终仓位（币量）
    stop_valid: bool                  # 止损是否在 0.5-2.5 ATR 夹层内
    violations: list[str]             # 违规项（供闸门/审计）
    cooldown_minutes: int
    protections_passed: bool
    drawdown_multiplier: float        # 回撤降级乘数（0.1-1.0）
```

### 仓位计算（单一公式，无分支）

```python
def position_size(inputs: RiskInputs) -> float:
    \"\"\"
    仓位 = (净值 × 基础风险% × 回撤乘数 × 体制乘数⁻¹ × 波动自适应乘数) ÷ (ATR × 止损ATR倍数)
    \"\"\"
    base_risk_pct = CONSTITUTION["MAX_RISK_PER_TRADE_PCT"]  # 1%
    dd_mult = compute_drawdown_multiplier(inputs["risk_state"])
    vol_mult = volatility_adaptive_multiplier(inputs["atr"], inputs.get("avg_atr"))
    regime_mult = inputs["regime_multiplier"]  # 0 表示禁做
    if regime_mult == 0:
        return 0.0
    risk_usd = inputs["account_balance"] * base_risk_pct * dd_mult * vol_mult / regime_mult
    # 硬上限：1% 净值 & 10U
    risk_usd = min(risk_usd, inputs["account_balance"] * 0.01, 10.0)
    stop_atr_mult = (inputs["entry_price"] - inputs["stop_price"]) / inputs["atr"]
    return risk_usd / (inputs["atr"] * stop_atr_mult)
```

### Protections（可独立实例化、单测、持久化）

```python
class Protections:
    \"\"\"Freqtrade-style: StoplossGuard + CooldownPeriod + MaxDrawdown\"\"\"
    def __init__(self, state: ProtectionState = None): ...
    def check_all(self, symbol: str, current_bar: int) -> tuple[bool, list[str]]: ...
    def on_stoploss(self, symbol: str, bar: int): ...
    def on_loss(self, bar: int): ...
    def advance_bar(self): ...
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "Protections": ...
```

- 状态持久化：`data/protections_state.json`（监控重启不丢失）
- 回测时逐根 K 线 `advance_bar()` 复跑，保证与实盘一致

### 配置热更

`data/risk_constitution.json` 修改后无需重启，`evaluate_risk` 每次调用读取（或 60s 缓存）。

### 闸门层集成（GO/NO-GO 门5）

```python
# gate_engine.py
def check_protections_gate(inputs: RiskInputs) -> GateResult:
    risk_out = evaluate_risk(inputs)
    if not risk_out["protections_passed"]:
        return GateResult(status="red", reason="; ".join(risk_out["violations"]))
    if not risk_out["allowed"]:
        return GateResult(status="red", reason=risk_out["violations"][0])
    return GateResult(status="green", reason="风控宪法通过")
```

### 回测验证

`backtest_runner_v2.py` 调用 `evaluate_risk` 逐笔复跑，**产出的逐笔交易与实盘风控逻辑位级一致**。
