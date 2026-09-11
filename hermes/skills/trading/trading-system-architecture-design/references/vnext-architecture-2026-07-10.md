# vNext 架构决策记录：决策闭环为中心（2026-07-10）

## 背景
用户要求：设计以决策闭环为中心的下一版系统架构，避免把全部逻辑塞进 Pine。

## 现有系统痛点审计

| 模块 | 现状 | 核心问题 |
|------|------|----------|
| Pine 指标 | SVP + HALDRO 全在 TV Pine | 逻辑全塞进 Pine，改动要重发布、无法回测、无法单测 |
| 市场体制 | skill 内 4 类（趋势/震荡/收敛/爆发） | 缺方向维度（牛/熊/震荡），未联动仓位乘数，ADX 只测强度不测方向 |
| 风控 | risk_constitution.py（单文件 700+ 行） | 体制乘数表在 skill 里写死，日/周回撤模式硬编码，Protections 与回测不联动 |
| 回测 | backtest_runner.py（5模型+真实成本+WFO） | 只跑固定模型，**不跑**体制分类器、风控护栏、GO/NO-GO 闸门 |
| 自动卡 | auto_card.py（采集→模型→双指标→GO/NO-GO→渲染） | 全链路耦合在单脚本，Pine 数据、Python 模型、风控、闸门混在一起 |
| 闸门 | go_nogo_gate.py（8门）+ signal_validators.py（2门） | 仅在 auto_card 尾部调用，**回测未覆盖**闸门逻辑 |
| 多源融合 | signal_confluence.py（Orion+QLib+Deribit→评分→方案） | 仅 BTC、仅作战室用，未纳入主决策闭环 |
| TV MCP | 只读 Data Window | 无法写 Pine 变量、无法回测 Pine 逻辑、缓存易过期 |

## 目标架构：决策闭环为中心

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        决策闭环 Decision Loop (Python)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  数据层   │→ │  特征层   │→ │  体制层   │→ │  策略层   │→ │  闸门层   │      │
│  │ Data     │  │ Feature  │  │ Regime   │  │ Strategy │  │ Gate     │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
│       │            │            │            │            │                  │
│       ▼            ▼            ▼            ▼            ▼                  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    风控宪法 Risk Constitution (单一真相源)             │   │
│  │  仓位公式、止损带、Protections、回撤降级、相关性、频率限制、冷却       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      执行/记录/复盘层 Execution & Review               │   │
│  │  trade_plan → order → fill → review → model_stats → governance       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ 仅拉指标数值（不含逻辑）
                        ┌───────────┴───────────┐
                        │   Pine 指标层          │
                        │  (TV MCP Read-Only)    │
                        │  SVP / HALDRO / CVD    │
                        │  VWAP / EMA / ATR      │
                        └────────────────────────┘
```

### 核心原则
1. **Pine 只输出数值**（SVP 结构位、HALDRO 组合/OI/CVD/确认、VWAP/EMA/ATR/ADX），**不输出方向/入场/止损/状态机**
2. **所有决策逻辑在 Python**（体制分类、模型评分、风控、闸门、执行方案）
3. **单一真相源**：`risk_constitution.py` = 仓位/止损/护栏/降级的唯一实现；回测、实盘、复盘**共用同一套代码**
4. **字段契约先行**：每层输入输出用 TypedDict/Pydantic 定义，跨层不共享原始 dict

## 字段契约（6 个核心契约）

详见 SKILL.md「字段契约标准」一节。

## GO/NO-GO 八闸门（硬闸门，回测必须复现）

| # | 闸门 | 通过条件 | 红灯动作 | 数据源 |
|---|------|----------|----------|--------|
| 1 | 数据新鲜度 | `data_grade ∈ {A,A-,B}` ∧ `age < 60s` | NO-GO | MarketSnapshot |
| 2 | TV 现场确认 | SVP/HALDRO 实时读取成功 ∧ 方向不冲突 | NO-GO | TVIndicators |
| 3 | R:R 底线 | `rr ≥ 2.0` | NO-GO | CandidatePlan |
| 4 | 事件窗口 | 非重大数据前60分后30分 | NO-GO | MacroSnapshot.news |
| 5 | 风控护栏 | `Protections.check_all(symbol) == True` | NO-GO | RiskConstitution |
| 6 | 样本/WFO | `samples ≥ 20` ∧ `WFO_eff ≥ 0.5` | 降级 B 观察 | ModelStats |
| 7 | 双指标共振 | SVP方向 = HALDRO方向 ∨ HALDRO不适用 | NO-GO(A级) | TVIndicators |
| 8 | 组合暴露 | 相关性 ≤ 0.7 ∧ 组合风险 ≤ 15% | NO-GO | CorrelationMatrix |

> 黄灯不拦截仅降级/记录；任一红灯 = 硬 NO-GO。

## 各市场副驾驶映射（HALDRO 替代/增强）

| 市场 | 主驾驶 | 副驾驶 | 备注 |
|------|--------|--------|------|
| BTC/ETH | SVP | HALDRO完整版 + Binance OI/Funding/Taker/LS比 + Deribit + ETF + Dune + COT | 全源验证 |
| 山寨币 | SVP | HALDRO简版 + BTC方向压制因子 + 流动性等级分流 | 中/低流动性降级 OI 权重 |
| XAU/黄金 | SVP | 无加密副指标 → Jin10/Gold-API/DXY/US10Y/KillZone | 宏观驱动为主 |
| 外汇/股指 | SVP | VWAP/Volume/宏观/事件/相关性 | 弱化 CVD/OI/Funding |

> 实现：`FeatureBuilder.build(symbol, asset_class)` 根据资产类自动组装副驾驶特征，**不在 Pine 里写分市场逻辑**。

## 实施顺序（6 周 MVP）

| 周 | 交付物 | 验收标准 |
|----|--------|----------|
| 1 | `contracts/` 包 + `FeatureBuilder` | 所有层输入输出可序列化，单测 100% 通过 |
| 2 | `regime_classifier_v2.py` | 6 体制映射表与仓位乘数一致，`regime_backtest.py` 接入分栏统计 |
| 3 | `risk_constitution_v2.py` | 仓位公式单一入口，Protections 可独立单测，参数热更 |
| 4 | `models/*.py` (6固定模型) | 各模型为纯函数 `model_xxx(fv) → CandidatePlan\|None`，可独立回测 |
| 5 | `gate_engine.py` | 8 闸门可组合、可复现、回测逐根 K 复跑 |
| 6 | `decision_loop.py` + 回测集成 | 同一代码跑实盘/回测，WFO overfit_score < 15 |
| 7+ | `auto_card_v2.py` 实盘接入 | ≤300 行，与回测卡字段完全一致 |

## Definition of Done（验收标准）

| 维度 | 指标 | 通过线 |
|------|------|--------|
| 契约 | Pydantic model 覆盖所有层，`mypy --strict` 通过 | 0 error |
| 体制 | 6 体制与社区 2×3 矩阵一致，乘数表在单一配置文件 | 回测分栏统计 `regime_backtest.py` 通过 |
| 风控 | 单笔≤1%、日回撤 2%/5% 双模式、周回撤 10%、连亏 3 停、Protections全覆盖 | `risk_constitution_v2.py` 单测 100% |
| 回测 | 同一 `decision_loop` 跨实盘/回测，WFO overfit_score < 15 | `walk_forward.py` 输出达标 |
| 闸门 | 回测逐根 K 复跑 8 闸门，通过率、拦截原因可审计 | `gate_engine.py` 有回测模式 |
| 实盘 | `auto_card_v2.py` ≤300 行，仅做：采集→`decision_loop.run()`→渲染→推送 | 与回测卡字段完全一致 |
| Pine | 代码**仅含指标计算**，无 `if direction then entry` 逻辑 | `pine-indicator-audit` 扫描 0 业务逻辑 |

## 关键文件清单（新建/重构）

```
D:/Hermes agent/
├── contracts/
│   ├── __init__.py
│   ├── market_snapshot.py
│   ├── feature_vector.py
│   ├── regime_output.py
│   ├── candidate_plan.py
│   └── gate_verdict.py
├── scripts/
│   ├── feature_builder.py
│   ├── regime_classifier_v2.py
│   ├── risk_constitution_v2.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── vwap_bounce.py
│   │   ├── vah_reclaim.py
│   │   ├── val_reclaim.py
│   │   ├── poc_rejection.py
│   │   ├── liquidity_sweep.py
│   │   └── breakout_accept.py
│   ├── gate_engine.py
│   ├── decision_loop.py
│   ├── backtest_runner_v2.py
│   ├── auto_card_v2.py
│   └── tv_data_bridge.py
├── data/
│   ├── regime_multipliers.json
│   └── risk_constitution.json
└── tests/
    ├── test_contracts.py
    ├── test_regime_classifier.py
    ├── test_risk_constitution.py
    ├── test_models.py
    ├── test_gate_engine.py
    └── test_decision_loop_backtest.py
```

## 常见坑与规避

| 坑 | 症状 | 规避 |
|----|------|------|
| **Pine 反渗透业务逻辑** | Pine 里出现 `if direction then entry` | 代码扫描：`pine-indicator-audit` 定期跑，业务关键字 0 容忍 |
| **契约漂移** | 回测/实盘字段不一致 | `contracts/` 单一源头，CI 强制 `mypy` + 序列化往返测试 |
| **体制乘数双份** | skill 里一份、代码里一份 | 仅 `data/regime_multipliers.json` 一份，代码读取 |
| **风控参数硬编码** | 改参数要改代码重部署 | 全部迁移到 `data/risk_constitution.json`，热更 |
| **回测不跑闸门** | 实盘被闸门拦、回测却显示盈利 | `backtest_runner_v2` 必须逐根 K 复跑 `gate_engine` |
| **副驾驶写死在 Pine** | 换市场要改 Pine 重发布 | `FeatureBuilder` 按 `asset_class` 动态组装 |
| **决策循环耦合采集** | `auto_card.py` 4000+ 行全耦合 | `auto_card_v2.py` 仅做：采集 → `decision_loop.run()` → 渲染 |

## 关键决策点（需用户确认）

| 决策项 | 推荐选项 A | 备选 B | 决策记录 |
|--------|------------|--------|----------|
| 体制分类器落地 | 独立 Python 模块 `regime_classifier_v2.py`，回测/实盘共用 | 留在 skill 里，通过 `skill_manage` 调用 | ☑ A（本架构文档已落地） |
| 风控参数存储 | `data/risk_constitution.json`（热更） | 环境变量/配置文件 | ☑ A |
| Pine 指标迁移 | 先不动 Pine，TV MCP 只读数值；vNext 只把**新指标**写 Python | 逐步把 SVP/HALDRO 移植到 Python（需 TV 数据源） | ☑ A |
| 回测引擎 | 复用 `backtest_runner.py` 成本模型，替换策略调用为 `decision_loop` | 重写回测引擎 | ☑ A |
| 实盘入口 | `auto_card_v2.py` 彻底精简为「采集→决策闭环→渲染」 | 保留 `auto_card.py` 逐步剥离 | ☑ A |

---

*本文档为架构决策记录（ADR），后续实施中如有偏离需更新此文档并同步相关 skill。*