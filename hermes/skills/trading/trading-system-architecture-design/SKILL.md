---
name: trading-system-architecture-design
description: "决策闭环为中心的交易系统架构设计方法论 — 将 Pine 降级为指标计算器，所有判断/决策/风控/闸门/执行收归 Python 决策闭环。字段契约先行、单一真相源、回测实盘共用同一套 decision_loop。"
version: 1.0.0
author: 安禾
tags: [trading, architecture, decision-loop, regime, risk, backtesting, pine, system-design]
---

# 交易系统架构设计：决策闭环为中心

## 适用场景
- 设计/重构交易系统核心架构，避免把全部逻辑塞进 Pine Script
- 建立字段契约，实现回测与实盘共用同一套决策代码
- 拆解现有系统，识别耦合点，制定分层迁移计划

## 权威边界与历史方案说明（2026-09）

本文“Pine只输出数值、移除全部业务逻辑”属于历史迁移方案，不是当前已批准架构，不能据此擅自移除SVP行动格或执行授权。当前SVP主指标提供结构与交易授权；Python FinalVerdict做数据、风控与冲突闸门，不能凭自身评分把SVP等待/禁做升级为可执行。AggVol仅确认、降级或否决。用户仅手动交易，GO-A也不是自动下单授权。

人工B/C候选应与执行字段分开建模：用户允许展示清晰标注的人工候选Entry/Stop/Target，不代表GO-A；WAIT/NO-GO执行字段仍清空，X禁做不显示可操作候选。下文旧版“B/C最多只有candidate_entry”不是当前界面需求。数值门槛、体制数量、6周计划及文件清单均为历史设计示例，必须核对当前代码与验证样本，不视作已实现事实或收益保证。

## 核心原则

### 1. Pine 只做「指标计算器」
- **仅输出数值**：SVP 结构位、HALDRO 组合/OI/CVD/确认、VWAP/EMA/ATR/ADX
- **不输出业务逻辑**：无方向判断、无入场/止损/目标、无状态机、无模型评分
- TV MCP 仅作只读数据源，通过 `tv_data_bridge.py` 标准化为 `TVIndicators` 契约

### 2. 所有决策逻辑在 Python 决策闭环
```
MarketSnapshot → FeatureVector → RegimeOutput → CandidatePlan(s) → GateEngine → FinalVerdict
     │               │               │               │               │            │
  数据层           特征层           体制层           策略层           闸门层        裁决层
```
每层输入输出由 Pydantic `TypedDict` 定义，`extra="forbid"`，跨层不共享原始 dict。

### 3. 单一真相源
| 领域 | 真相源文件 | 覆盖范围 |
|------|-----------|---------|
| 仓位/止损/护栏/降级 | `risk_constitution_v2.py` | 回测、实盘、复盘共用 |
| 体制→乘数/白名单/画像 | `data/regime_multipliers.json` | 体制分类器、策略层、风控层 |
| 风控可调参数 | `data/risk_constitution.json` | 热更，无需重启 |
| 闸门规则 | `gate_engine.py` | 8 闸门可组合、可回测 |

### 4. 回测实盘共用同一套 `decision_loop`
- `backtest_runner_v2.py` 逐根 K 调用 `decision_loop.run(snapshot)`
- 产出逐笔交易 + 权益曲线 + 闸门通过率 + 体制分栏统计
- `auto_card_v2.py` 实盘入口仅做：采集 → `decision_loop.run()` → 渲染 → 推送

---

## 字段契约标准（6 个核心契约）

### 1. MarketSnapshot — 标准化行情快照
```python
class MarketSnapshot(TypedDict):
    symbol: str
    ts: int                          # UTC ms
    price: float
    ohlcv: dict[str, list[float]]    # 多周期 {"o":[], "h":[], "l":[], "c":[], "v":[]}
    tv_indicators: TVIndicators      # SVP/HALDRO/基础指标
    binance: BinanceData             # OI, funding, taker, ls_ratio
    macro: MacroSnapshot             # DXY, US10Y, ETF, COT, options
    news: NewsEvent | None           # 事件窗口
```

### 2. FeatureVector — 模型可直接用的特征向量
```python
class FeatureVector(TypedDict):
    dist_vwap_atr: float
    dist_poc_atr: float
    ema_stack: str                   # "bull" | "bear" | "mixed"
    adx: float
    cvd_slope: float
    taker_ratio: float
    regime: RegimeLabel              # 6 体制
    vol_regime: VolRegime
    data_grade: DataGrade
    snapshot_age_sec: float
```

### 3. RegimeOutput — 6 体制 + 仓位乘数
```python
class RegimeLabel(str, Enum):
    BULL_CALM = "bull_calm"
    BULL_NORMAL = "bull_normal"
    BULL_VOL = "bull_vol"
    BEAR_CALM = "bear_calm"
    BEAR_NORMAL = "bear_normal"
    BEAR_VOL = "bear_vol"
    RANGE_CALM = "range_calm"
    RANGE_NORMAL = "range_normal"
    RANGE_VOL = "range_vol"        # 禁做

class RegimeOutput(TypedDict):
    regime: RegimeLabel
    position_multiplier: float     # 2.5 / 1.5 / 1.0 / 0
    allowed_models: list[str]
    risk_profile: RiskProfile
    cvd_divergence: CVDDivergence
```

### 4. CandidatePlan — 未经闸门的候选方案
```python
class CandidatePlan(TypedDict):
    model_id: str
    direction: Direction
    entry: float
    stop: float
    targets: list[float]
    rr: float
    confidence: float
    regime_fit: bool
```

### 5. GateResult / FinalVerdict — 闸门裁决
```python
class GateResult(TypedDict):
    gate_name: str
    status: GateStatus             # "green" | "yellow" | "red"
    reason: str

class FinalVerdict(TypedDict):
    go: bool
    plan: CandidatePlan | None
    gates: list[GateResult]
    risk_usd: float
    leverage: int
    verdict_text: str
```

---

## GO/NO-GO 八闸门（硬闸门，回测必须复现）

| # | 闸门 | 通过条件 | 红灯动作 | 数据源 |
|---|------|----------|----------|--------|
| 1 | 数据新鲜度 | `data_grade ∈ {A,A-,B}` ∧ `age < 60s` | NO-GO | MarketSnapshot |
| 2 | TV 现场确认 | SVP/HALDRO 实时读取 ∧ 方向不冲突 | NO-GO | TVIndicators |
| 3 | R:R 底线 | `rr ≥ 2.0` | NO-GO | CandidatePlan |
| 4 | 事件窗口 | 非重大数据前60分后30分 | NO-GO | MacroSnapshot.news |
| 5 | 风控护栏 | `Protections.check_all() == True` | NO-GO | RiskConstitution |
| 6 | 样本/WFO | `samples ≥ 20` ∧ `WFO_eff ≥ 0.5` | 降级 B | ModelStats |
| 7 | 双指标共振 | SVP方向 = HALDRO方向 ∨ HALDRO不适用 | NO-GO(A级) | TVIndicators |
| 8 | 组合暴露 | 相关性 ≤ 0.7 ∧ 组合风险 ≤ 15% | NO-GO | CorrelationMatrix |

> 黄灯不拦截仅降级/记录；任一红灯 = 硬 NO-GO。

---

## FinalVerdict 与副驾驶权限不变量（2026-07-10）

- 最终执行状态固定为 `GO-A / WAIT / NO-GO`；B/C/X仅是指标等级、人工观察或禁做语义，不能成为执行裁决。渲染、告警、仓位和执行只能消费 FinalVerdict。
- `WAIT/NO-GO` 必须清空可执行 `entry/stop/target`，观察价另放 `watch_entry/watch_side`。渲染器需再次检查 `_final_verdict`，防止原始A级字段绕过闸门；不得把遗留原始 `entry` 回填为“触发价”。
- **最终裁决覆盖原始叙述**：`FinalVerdict=NO-GO` 且双指标冲突时，渲染器必须显示“主副强冲突”，绝不能继续展示缓存的“主副同向”。`WAIT/NO-GO`下，非B/C反的执行表触发价固定为`—`；B/C反最多展示明确标记的`candidate_entry`，不得带止损/目标执行指令。
- **SVP等待词是硬契约**：行动格任一字段含`⚠冲突`、`未收线`、`等收线`、`等解除`、`C等待`或`观望`，即使遗留等级为A，也必须降为`WAIT`并清空执行三件套。结构化状态码优先；文本门控仅作为旧指标/迁移期的fail-closed兼容层。
- HALDRO Valid Code：`0=无效，不得制造冲突`；`1=单源回退，只作弱确认，冲突时WAIT`；`2=聚合有效，强冲突可硬NO-GO`；非加密不套HALDRO。
- 区域A级不等于交易A级；位置、触发、订单流、R:R和风控仍可否决。
- 体制只选择模型，不决定方向；不得用固定VIX或演示波动率填充实时体制。
- 风险金额先受宪法1%/绝对金额上限约束，再由体制风险除数缩小；仓位层不得按旧confidence重新放大。
- 旧八闸门只保留诊断职责；若 `FinalVerdict.executable=false`，旧 `go_nogo_gate` 不得重新输出 GO。WAIT 与 NO-GO 必须分别显示，不能把等待误报成硬禁做。
- 跨层价格字段进入裁决前必须安全数值化；`等触发/待确认/—` 视为缺失值，不得直接 `float()`。影子记录仅在 entry/stop/target 三者均为正数时落盘。
- 实时体制优先消费闭柱 OHLCV。Binance原始K线数组必须丢弃最后一根未收柱；XAU TV同步使用结构化 `last_5_bars[-2]`，禁止正则抓JSON末尾数字。
- TV缓存写入必须执行“切目标symbol→chart state复核→读取→再次复核”；CLI `values --symbol` 不能被当作已经切图的证据。
- **TV实时指标与结构位必须分开选源**：当前柱的 POC/VAH/VAL 可能暂时为 `na/null`，但同一份 `tv_live` 的 HALDRO Valid Code、OI、CVD、Composite、EMA/MCP 仍然有效。不得用 `poc != null` 作为采用整个实时缓存的前置条件。先按 symbol+timestamp 门禁提升 Data Window/行动格为本轮权威；结构位缺失时再单独回退上一份同品种新鲜缓存。否则会把现场 `HALDRO Valid Code=2` 误降成 0，并错误写入 `haldro_invalid`。
- 影子记录必须保存可被同一 `resolve_final_verdict()` 直接回放的 `main/dual/regime/risk` 嵌套快照；旧扁平 JSONL 由兼容转换层读取。校准器同时接受 `regime="trend"` 与 `regime={"code":"trend"}`；样本不足门槛只报告样本数，不输出概率。
- **Scheduled inference is a separate deployment boundary**: pin provider/model on every unattended analysis job; interactive model switching must not alter production routing. Keep the primary daily model and manual deep-review model separate, and verify the pin with a real cron run.
- **Market-data contracts precede model scoring**: normalize source, market type, timestamp, freshness, units and semantic validity before FeatureVector construction. A successful HTTP response or non-empty cache is not sufficient. Each collector must expose `live/cache/stale_cache/unavailable/quota_cooldown`; 429/额度耗尽进入约15分钟源级熔断，`stale_cache`不得列为本轮实时完成。
- **Options fields require semantic separation**: `max_pain` must mean minimum aggregate settlement payout, while `max_oi_strike` is only an OI concentration level; invalid/outlier values are excluded from gates.

完整实现模式、影子记录与常见陷阱见 `references/final-verdict-shadow-calibration-2026-07-10.md`。多资产缓存身份、共享TV图表锁、免费API熔断及指标上线验收清单见 `references/multi-asset-data-quality-and-pine-rollout.md`。
TV跨品种缓存门禁、闭柱特征、安全数值化与新旧shadow回放契约见 `references/tv-cache-final-verdict-shadow-contract-2026-07-11.md`。

---

## 各市场副驾驶映射（HALDRO 替代/增强）

| 市场 | 主驾驶 | 副驾驶 | 备注 |
|------|--------|--------|------|
| BTC/ETH | SVP | HALDRO完整版 + Binance OI/Funding/Taker/LS + Deribit + ETF + Dune + COT | 全源验证 |
| 山寨币 | SVP | HALDRO简版 + BTC方向压制 + 流动性分级 | 中/低流动性降级 OI 权重 |
| XAU/黄金 | SVP | 无加密副指标 → Jin10/Gold-API/DXY/US10Y/KillZone | 宏观驱动为主 |
| 外汇/股指 | SVP | VWAP/Volume/宏观/事件/相关性 | 弱化 CVD/OI/Funding |

实现：`FeatureBuilder.build(symbol, asset_class)` 自动组装，**不在 Pine 里写分市场逻辑**。

---

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

---

## Definition of Done（验收标准）

| 维度 | 指标 | 通过线 |
|------|------|--------|
| 契约 | Pydantic model 覆盖所有层，`mypy --strict` 0 error | ✅ |
| 体制 | 6 体制与社区 2×3 矩阵一致，乘数表单一配置源 | ✅ |
| 风控 | 单笔≤1%、日回撤双模式、周回撤10%、连亏3停、Protections全覆盖 | ✅ |
| 回测 | 同一 `decision_loop` 跨实盘/回测，WFO overfit_score < 15 | ✅ |
| 闸门 | 回测逐根 K 复跑 8 闸门，通过率/拦截原因可审计 | ✅ |
| 实盘 | `auto_card_v2.py` ≤300 行，仅做采集→决策→渲染→推送 | ✅ |
| Pine | 代码仅含指标计算，0 业务逻辑 | ✅ |

---

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

---

## 常见坑与规避

| 坑 | 症状 | 规避 |
|----|------|------|
| **Pine 反渗透业务逻辑** | Pine 里出现 `if direction then entry` | 代码扫描：`pine-indicator-audit` 定期跑，业务关键字 0 容忍 |
| **契约漂移** | 回测/实盘字段不一致 | `contracts/` 单一源头，CI 强制 `mypy` + 序列化往返测试 |
| **上游接口漂移（静默丢数据）** | 上游改行名/字段名，下游硬编码名单还停在旧版，**不报错只少一块数据** | 单一契约源 + 消费矩阵扫描；见 `references/upstream-interface-drift-audit-20260910.md` |
| **字段被折进另一行** | 下游那几个字段全变空但无报错 | 为合并行写结构化解析器把字段拆回来 |
| **行标签变成动态的** | 只认字面标签 → 其它态整个漏读 | 写 `ordered_*_rows()` 认全部变体 |
| **闸门塞进上游解析函数** | 裁决逻辑与数据解析耦合，无法单独测 | 新闸门一律挂在“裁决落定那一点”，单向保守化 |
| **体制乘数双份** | skill 里一份、代码里一份 | 仅 `data/regime_multipliers.json` 一份，代码读取 |
| **风控参数硬编码** | 改参数要改代码重部署 | 全部迁移到 `data/risk_constitution.json`，热更 |
| **回测不跑闸门** | 实盘被闸门拦、回测却显示盈利 | `backtest_runner_v2` 必须逐根 K 复跑 `gate_engine` |
| **副驾驶写死在 Pine** | 换市场要改 Pine 重发布 | `FeatureBuilder` 按 `asset_class` 动态组装 |
| **决策循环耦合采集** | `auto_card.py` 4000+ 行全耦合 | `auto_card_v2.py` 仅做：采集 → `decision_loop.run()` → 渲染 |
| **未识别资产类别 → 空管线** | 传入 `SPX500` / 标准期权代码，路由返回 **`[]`**（不是报错）→ 调用方不分析也不报错 | 每个资产类别在所有步骤的 `assets` 集合里都要有归属；路由尾部加 `assert steps`；给 `other` 配基础步骤集 |
| **未知档位静默降档** | `analysis_mode_spec("Fuuull")` 静静回落到 `quick` | Full 少跑十一步而卡面看不出 → 降级必须显式（返回 `mode_error`） |
| **兑底 stub 静默降级** | 契约/依赖 import 失败 → 字段全空、行名全空，卡面看似正常 | stub 置 `DEGRADED=True`，卡面的数据状态行必须把它说出来 |
| **口述规则未落到代码** | 用户早说过「option 跟随底层」，但代码里没实现 → 期权 `full` = **0 步** | 把用户口述的多市场规则当契约，落地后逐类跑一次矩阵验证（见下节） |

---

## 关键决策点模板（新项目启动时确认）

| 决策项 | 推荐选项 A | 备选 B | 记录决策 |
|--------|------------|--------|----------|
| 体制分类器落地 | 独立 Python 模块共用 | 留在 skill 调用 | ☐ A / ☐ B |
| 风控参数存储 | `data/risk_constitution.json` 热更 | 环境变量 | ☐ A / ☐ B |
| Pine 指标迁移 | 先不动，只读数值；新指标写 Python | 逐步移植 SVP/HALDRO | ☐ A / ☐ B |
| 回测引擎 | 复用成本模型，替换策略调用 | 重写引擎 | ☐ A / ☐ B |
| 实盘入口 | `auto_card_v2.py` 彻底精简 | 保留旧版本逐步剥离 | ☐ A / ☐ B |

---

## 监控触发与关键位契约（2026-08）

将实时关键位监控视为**事件发现层**，而不是交易信号层。唯一链路应为：

```text
TradingView候选位 → 人工审核 → keylevels_config.json（唯一批准源）
→ 单实例守护 → keylevel_cross事件 → quick分析调度器
→ 重新读取TV/实时衍生品 → FinalVerdict
```

必须遵守：
- `keylevels_candidates.json` 只是候选池；`keylevels_config.json` 才是批准监测配置。
- 历史 `monitor_levels.json` 只能作为兼容/审计缓存，不能被分析渲染器当作当前监测位来源。
- 价格穿越事件携带 `cross_direction=up/down`，这不是交易方向；兼容字段应为 `direction=neutral`。
- 事件至少包含 `event_type=keylevel_cross`、`event_class=price_cross_only`、`analysis_required=true`、`analysis_status=pending`、`config_revision`、`tv_symbol` 和关键位有效期。
- 调度器默认只调用 `auto_card --quick`，不自动下单、不自动推送；推送必须显式授权。成功/失败后把同一事件标记为 `analyzed/failed`，保留 `event_id` 防重复。
- 看门狗必须检查守护实例数量：0个重启，1个正常，多于1个先收敛，不能只判断“至少存在一个”。

高周期关键位采集必须覆盖 `D→4h→1h→15m→5m`，且每次切换周期后先验证 `chart_get_state` 的品种和周期，再读取线、标签、框和行动格，防止复用上一周期缓存。完整契约和验证样例见 `references/keylevel-monitor-contract-202608.md`。

## 上游输出接口漂移（2026-09 实案）

当上游是指标脚本/第三方服务而非自己的 `contracts/` 时，**“字段契约先行”具体长什么样**：

### 症状与根因

上游改版下游**不报错，只是静默少一块数据**。实案：主指标行动格 10 行 → 13 行，
下游行名清单未同步，两版只有 4 个名字重合 → **13 行只吃到 4 行**，
丢掉的恰是装着执行三件套/R:R 的「风控」行与装着主副一致性的「协同」行。

根因不是“忘了改”，而是**同一套字段名硬编码在 3 处**（桥接层别名表、卡片 DW 映射表、行键清单）。

### 四步处置（每步都要有可量化的产物）

| 步 | 做什么 | 产物 |
|---|---|---|
| 1 | 从**上游源码**（不是文档）导出完整输出接口 | DW 字段全量 + 行名全量 |
| 2 | 拿每个名字去仓库语料里搜“谁在读” | 消费矩阵：真消费 / 无人读 / 只被文档提到 |
| 3 | 与下游硬编码名单求交集 | “4 / 13” 这种损失数字 |
| 4 | 用**真实载荷**跑下游构造函数前后对比 | 进测试的期望值 |

**铁律：字段映射文档可能比上游落了两个大版本，不能当权威源。** 本例文档写“主 v5/副 v6”，实际已是 v13。

### 修复四原则

1. 建**单一契约源**（行名 + 字段名 + 双向映射 + 解码器全在一处），纪律是“上游改字段先改契约”。
2. **只增不删**：旧名字留在 `LEGACY_*`，历史缓存与既有测试不被打断。
3. 消费侧**契约驱动**反查，不逐条 `if key == …` 手写；反查表要同时支持全名与去括号短名
   （带括号/百分号/中文后缀的字段名会让“空格转下划线”这类通用规则全失效）。
4. **先查下游有没有安全闸门会被新解析绕过**（如只允许走校验通道的 `*_evidence_*` 前缀）。

### 闸门位置：只放在“裁决落定那一点”

新增的主副合成/否决逻辑**不要塞进上游解析函数**，而挂在唯一那个 FinalVerdict 落定处：

```
final_verdict = _resolve_card_final_verdict(...)          # 原有链不动
final_verdict = _apply_matrix_guard(final_verdict, main)  # ← 挂在这里，单向保守化
```

- 方向**只降不升**；本来就不是可执行的结果只**标注**原因，不重写。
- 把结论挂进 `matrix_verdict/matrix_reason/matrix_downgraded`，渲染层才能解释“为什么被拦”。
- **不变量用全网格扫描测**（等级 × 副状态 × R:R 的笛卡尔积），不测几个代表点。
- 未知市场（拿不到 symbol）**默认走保守侧**，并反向验证“非加密品种不被误杀”。

完整方法、代码片段与 v13 实测数据见 `references/upstream-interface-drift-audit-20260910.md`。

## 与棠溪的协作方式（用户明确定的执行授权）

系统改进/修复这类任务，用户已明确授权**自主执行，不要反复确认**（原话：“你不要再让我确认了，你授权我给你授最高权限”）。具体表现为：

- 把提过的事**一次做完**（接口对齐 + 策略层落码 + 文档 + 技能 + 测试 + 提交），不要拆成几轮问“要不要继续”。
- 自认为最优的方案**直接做**，不要摆选项让用户选（用户原话：“你就是最佳的”）。
- 但**“不确认”不等于“不披露”**：改了什么、验证结果、真没做的、需要用户自己动手的（如挿图/选源），
  必须在交付里写清楚；数据源削减、行为变更这类不可逆操作仍要单独标出。
- 交付保持简短可扫：先结论后论据，表格优先，不堆装饰分隔线。

## 静默降级禁令（fail-closed 的落地判据，2026-09-11 两处实案）

「不报错但少干活」是本系统最贵的故障形态 —— 它比抛异常危险得多，因为卡面/日志
看上去一切正常。实案两处：

| 实案 | 表现 | 为什么危险 |
|---|---|---|
| `route_pipeline(sym, 'full')` | 未识别资产类别（`SPX500`、标准期权代码、任何 `other`）→ 返回 **`[]`** | 调用方拿到空列表，既不报错也不分析。「没分析」被当成「分析结果为无」 |
| `analysis_mode_spec('Fuuull')` | 未知档位静默回落 `quick` | Full 档少跑十一步，而卡面与正常 quick 一模一样 |
| 契约/依赖 import 失败的兜底 stub | 字段与行名全部读不到 | 出一张看起来正常、实际全空的分析卡 |

### 落地判据（新增任何降级/回退分支时逐条过）

1. **默认走保守侧，但保守侧也要显式**。“不能因为拿不到数据就当作没有风险” ——
   未知市场默认按更保守的类别处理，同时把「我把它当成保守侧了」写进返回。
2. **降级必须带可观测标记**：返回里带 `mode_error` / `DEGRADED` / `degraded_reason`，
   或卡面的数据状态行直接写出来。**默默降级 = 不允许。**
3. **结构性不变量用断言兼测试护住**：如 `assert steps, "路由为空"`。
   「不可能发生」的状态要靠代码结构保证，不靠人工记得。
4. **档位契约必须互不相同**：写一条测试断言四档（Quick/Inherit/Full/Monitor）的 spec 不重样——
   否则哪天被谁改成同一个，没人会注意到。
5. **不确定档位名时宁可跑多不可跑少**：`route_pipeline` 遇未知 mode 按 `full` 处理，
   不按 `quick`。少跑步骤比多跑危险。

### 多资产路由的完备性矩阵（新增资产类别必须全登记）

一个新资产类别（如 `index`）或一个新的券种形式（如期权代码）要同时落进**四处**，
漏一处就会得到「该类品种无步骤 / 无主周期 / 无截图口径」的静默缺口：

| 位置 | 漏了会怎样 |
|---|---|
| 每个步骤的 `assets` 适用集合 | 该类别命中不到任何步骤 → 空管线 |
| `TF_RULES`（层/主周期/截图周期） | 退回默认周期，与用户约定不符 |
| `quick_map` / `mon_map` | quick 或 monitor 档直接空 |
| 代码里的识别规则（ticker 解析） | 识别不了 → 全落到 `other` |

**验收方式**：跑一张「资产 × 档位」矩阵表，断言每格都非空，并把主周期一起打出来。
本轮实测产出（修后）：``crypto 15m / gold 5m / forex 15m / stock 1h /
futures 15m / index 15m / option=跟随底层 / other 15m``，四档都非空。

**衍生品跟随底层**：期权（OSI/OPRA `AAPL240119C150`、OCC 空格补齐、Deribit
`BTC-29MAR24-60000-C`）应解析出 `underlying` + `underlying_class`，
按**底层**类别路由步骤与主周期，再强制补上期权链步骤（放在出卡之前）；
但 `monitor`（仅事件）档不得补 —— 补了就把「事件发现」变成了「一次分析」。

完整实案（三处静默降级、四处登记缺口、矩阵验收表）见
`references/silent-degradation-and-routing-completeness-20260911.md`。

## 相关技能

- `market-regime-classifier` — 体制分类器实现细节（需升级为 v2 6体制+乘数联动）
- `risk-management-system` — 风控宪法实现细节（需重构为 v2 单一真相源）
- `backtesting-suite` — 回测框架（需接入 decision_loop 与闸门复跑）
- `tangxi-trading-cockpit` — 现有驾驶舱流程总控（架构迁移参考）
- `spec-driven-development` — 规范先行，契约先行的方法论