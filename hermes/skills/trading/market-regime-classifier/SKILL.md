---
name: market-regime-classifier
description: "棠溪市场状态分类器 — ADX趋势强度、波动率状态(VHV)、行情类型(趋势/震荡/收敛/爆发)、CVD量价背离。零token规则引擎，帮助快速判断当前市场环境适合哪种模型。"
version: 1.0.0
author: 安禾
tags: [market-regime, trend, volatility, ADX, market-state, classification, BTC, XAU]
---

# 市场状态分类器 — Market Regime Classifier

帮助快速判断 BTC/XAU 当前是趋势、震荡、收敛还是爆发行情，选择对应模型。

## 两层体制不可混用（2026-07-10 修订）

短线系统应区分：

1. **方向背景**：1D/4h/1h 决定多、空或中性，可参考200MA/结构；
2. **执行环境**：闭柱特征分类为 `trend / balance / compression / expansion`，只负责选择模型，不决定方向。

实时执行体制禁止使用固定VIX或演示波动率。推荐特征：ADX、ATR14/ATR均值、EMA spread/ATR、20K VWAP穿越次数、20K VA停留率、位移/ATR、RVOL、VWAP距离。分类优先级：扩张→收敛→趋势→平衡；耗尽作为风险叠加位。

**风险乘数语义必须统一**：若公式是除法 `risk_usd / regime_multiplier`，高波动/扩张的乘数必须更大，不能把高波动写成1.0而平静写成2.5；否则仓位方向完全反了。低波动也不得突破风控宪法1%硬上限。方向×波动的9格矩阵可用于宏观画像，但不能替代短线执行环境分类。

## 三层分类体系

### ① 趋势强度（ADX）
| ADX | 状态 | 建议模型 |
|-----|------|---------|
| < 20 | 弱趋势/震荡 | POC拒绝·VWAP反抽·VAH/VAL回收 |
| 20-30 | 正常趋势 | 突破接受·VWAP回踩·关键位阻 |
| 30-40 | 强趋势 | 动量延续·EMA趋势（+辅助） |
| > 40 | 极强趋势（过热） | 反转准备·FVG回补·CHoCH提前挂 |

> 通过 TV MCP `data_get_study_values` 获取 ADX 值

### ② 波动率状态（Volatility Regime）
基于 ATR(14) 与 50周期均值的比率：

| ATR比率 | 状态 | 仓位调整 |
|---------|------|---------|
| < 0.7 | 低波动（收敛） | 1.5× 仓位（等待爆发）|
| 0.7-1.3 | 正常波动 | 1.0× |
| 1.3-2.0 | 高波动 | 0.5× （止损放宽）|
| > 2.0 | 极端波动 | 跳过（观望/微仓）|

> 通过 Binance MCP `get_klines(symbol, interval=15m, limit=64)` 计算 ATR

### ③ 量价背离（CVD Divergence）
| CVD vs 价格 | 含义 | 操作 |
|-------------|------|------|
| 价格↑ CVD↓ | 多头薄弱（隐退） | 勿追多，准备空 |
| 价格↓ CVD↑ | 空头薄弱（吸筹） | 勿追空，准备多 |
| 价格↑ CVD↑ | 健康上涨 | 可做多 |
| 价格↓ CVD↓ | 健康下跌 | 可做空 |

> 通过 TV MCP `data_get_study_values` 获取 CVD 状态

## 快速分类流程 (v2.0 6体制)

```python
# 从 TV MCP 获取数据流
state = classify_market(
    price=60500,      # 当前价格
    ma200=58000,      # 200MA
    adx=22,           # ADX(14)
    atr_ratio=0.85,   # ATR(14) / ATRAvg(50)
    cvd_divergence="none",
)
# 返回: {regime: "牛平静", models: [...], position_mult: 2.0, risk_level: "低"}
```

## 历史方向×波动画像（仅作背景标签，表中旧“仓位乘数”不得直接进入风险公式）

| 市场体制 | 仓位乘数 | BTC模型 | XAU模型 | 风控 |
|---------|---------|---------|---------|------|
| 牛平静 | 2.0 | VWAP回踩·突破接受·EMA趋势 | 突破接受·VWAP回踩 | 正常止损 |
| 牛正常 | 1.5 | VWAP回踩·EMA趋势·动量延续 | M_VWAP磁吸·动量延续 | 正常 |
| 牛波动 | 1.0 | 动量延续·FVG回补（快进快出） | FVG·关联套利（快进快出） | 宽止损(1.5ATR) |
| 熊平静 | 2.0 | POC拒绝·VAH空·CHoCH | POC拒绝·VAH空·美元关联 | 正常 |
| 熊正常 | 1.5 | CHoCH·扫流动性回收空 | CHoCH·扫流动性回收空 | 正常 |
| 熊波动 | 1.0 | 扫流动性空·FVG空（快进快出） | 扫流动性空（快进快出） | 宽止损(1.5ATR) |
| 震荡平静 | 2.5 | POC拒绝·VAH/VAL回收（高胜率） | POC拒绝·VAH/VAL回收 | 严格R:R |
| 震荡正常 | 1.5 | POC拒绝·VWAP反抽 | VWAP反抽·区间套利 | 正常 |
| 震荡波动 | 不交易 | X禁做（方向不明+高波动） | X禁做 | 跳过 |

**旧表仅保留历史画像含义，不可直接代入仓位公式。** 当前统一口径：`最终风险 = min(基础风险, 账户1%硬上限, 绝对金额上限) ÷ 执行体制风险除数`；波动越高，风险除数越大，仓位越小。

**例外规则**：
- ADX<20 且 ATR比突然扩张>1.25 → 减仓50%或观望（方向不明+高波动=最危险组合）
- CVD与价格背离 → 降一级（牛正常→牛平静仓位）

## 集成方式

```python
# 在 auto_card.py 中调用
regime = classify_market(adx, atr_ratio, cvd_status, price_vs_ema)
# 注入分析卡的"环境段"：
# ③ 市场状态：正常趋势 · 正常波动 · ADX 22
```

## 可用数据源
- **TV MCP**: `data_get_study_values` → ADX, CVD 实时值
- **Binance MCP**: `get_klines` → ATR 计算
- **本地**: `scripts/system_data_bridge.py` → enrich_engine_data()

## Pitfalls

- **4 类 vs 社区 6 体制（2026-06-29 社区对标发现）** — 当前分类只有趋势/震荡/收敛/爆发 4 类，缺方向维度。社区最佳实践（Market Regimes 2026）用 Price vs 200MA × ATR比值 = 6 类：牛平静/牛波动/熊平静/熊波动/震荡平静/震荡波动。建议升级时加 Price vs 200MA 作为第二维度。详见 `tangxi-system-audit/references/community-best-practices-2026.md`。
- **未联动仓位乘数（2026-06-29 社区对标发现）** — 分类后只映射策略模型，不联动仓位大小。社区公式：`仓位 = 账户风险% ÷ (ATR × 体制乘数)`，乘数从 2.0(平静)到 4.0(爆发)。建议与 `risk-management-system` 联动，在 `risk_constitution.py` 中加体制乘数查表。
- **缺 200MA 过滤** — 社区用 Price vs 200-day MA 定牛/熊方向，当前只用 ADX。ADX 测强度不测方向。可加 `get_klines(interval="1d", limit=200)` 计算 SMA200 作为方向维度。

## vNext 架构集成点（2026-07-10 决策闭环架构落地）

在「决策闭环为中心」的 vNext 架构中，体制分类器作为 **独立 Python 模块** `scripts/regime_classifier_v2.py` 存在，**不再依赖 skill 运行时**，实现回测/实盘共用同一套代码。

### 字段契约（FeatureVector → RegimeOutput）

```python
# 输入：FeatureVector（含 price, ma200, adx, atr_ratio, cvd_divergence 等）
# 输出：RegimeOutput（TypedDict）
class RegimeOutput(TypedDict):
    regime: RegimeLabel              # 9 体制枚举：bull_calm/bull_normal/bull_vol/bear_calm/bear_normal/bear_vol/range_calm/range_normal/range_vol
    position_multiplier: float       # 仓位乘数：2.5/1.5/1.0/0(range_vol=0)
    allowed_models: list[str]        # 该体制白名单模型
    risk_profile: RiskProfile        # "conservative" | "normal" | "aggressive"
    cvd_divergence: CVDDivergence    # "bullish" | "bearish" | "none"
    notes: str
```

### 9 体制映射表（单一配置源：`data/regime_multipliers.json`）

| regime_label | direction | vol_state | position_mult | allowed_models | risk_profile |
|---|---|---|---|---|---|
| bull_calm | bull | calm | 2.5 | VWAP反抽, VAH回收, VAL回收, 突破接受 | conservative |
| bull_normal | bull | normal | 1.5 | VWAP反抽, 突破接受, POC拒绝, 动量延续 | normal |
| bull_vol | bull | volatile | 1.0 | 动量延续, FVG回补, 扫流动性回收 | aggressive |
| bear_calm | bear | calm | 2.5 | POC拒绝, VAH空, VAL回收空, 突破接受空 | conservative |
| bear_normal | bear | normal | 1.5 | POC拒绝, VAH空, 扫流动性回收空, 动量延续空 | normal |
| bear_vol | bear | volatile | 1.0 | 扫流动性空, FVG空, 突破接受空 | aggressive |
| range_calm | range | calm | 2.5 | POC拒绝, VAH/VAL回收, VWAP反抽 | conservative |
| range_normal | range | normal | 1.5 | POC拒绝, VWAP反抽, VAH/VAL回收 | normal |
| range_vol | range | volatile | **0.0** | **无（禁做）** | — |

> **注意**：`range_vol` 位置乘数 = 0，直接在闸门层拦截（GO/NO-GO 门8：组合暴露/体制禁做）。

### 集成方式（vNext）

```python
# scripts/decision_loop.py 中
from regime_classifier_v2 import classify_regime
from feature_builder import build_feature_vector

def run_decision_loop(snapshot: MarketSnapshot) -> FinalVerdict:
    fv = build_feature_vector(snapshot)
    regime_out = classify_regime(fv)  # 纯函数，可回测逐根复跑
    # regime_out.position_multiplier 直接传给 risk_constitution_v2.position_size()
    # regime_out.allowed_models 过滤 models/*.py 候选
    # regime_out.risk_profile 选 risk_constitution_v2 风控画像
    ...
```

### 回测验证

- `regime_backtest.py` 接入 `classify_regime`，逐根 K 线产出 `regime_label`，分栏统计各模型在各体制下的期望值
- 样本 < 10 笔标注「样本不足·仅供参考」，不用于权重调整（铁律不变）

### 配置热更

`data/regime_multipliers.json` 修改后无需重启，`classify_regime` 每次调用读取（或加轻量缓存 60s），实现体制参数热更。

## 社区对标与升级建议（2026-06-29 联网审计）

### 6 体制模型（社区最佳实践 · Market Regimes 2026）

当前 4 类（趋势/震荡/收敛/爆发）缺少**方向维度**。社区标准是 2×3 矩阵：

| | 低波动(ATR比<0.75) | 正常波动(0.75-1.25) | 高波动(>1.25) |
|---|---|---|---|
| **Price > 200MA (牛)** | 牛平静 | 牛正常 | 牛波动 |
| **Price < 200MA (熊)** | 熊平静 | 熊正常 | 熊波动 |
| **反复穿越 200MA (震荡)** | 震荡平静 | 震荡正常 | 震荡波动 |

建议升级：在 ADX 之外加 `Price vs 200MA` 判定牛/熊/震荡方向。

### 体制 → 仓位乘数联动（Quant Checklist 2026）

分类后不仅映射模型，还应联动仓位大小：

```
仓位 = (账户净值 × 单笔风险%) ÷ (ATR × 体制乘数)

体制乘数：
  趋势平静 = 2.0    震荡平静 = 2.5
  趋势波动 = 3.0    震荡波动 = 3.5
  收敛/爆发 = 4.0 或不交易
```

体制越波动，乘数越大，仓位越小——自动适配风险。

### ADX<20 + 波动扩张 → 减仓 50%

社区机构共识：当 ADX<20（无趋势）且 ATR 比值突然扩张到 >1.25 时，市场处于方向不明确的高波动状态，应减仓 50% 或观望。
