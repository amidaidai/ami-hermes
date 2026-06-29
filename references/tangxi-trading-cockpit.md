# 棠溪交易驾驶舱总控 v9.6

本文件是棠溪交易系统的唯一流程总控。分析卡、监控、skill、脚本和复盘都以这里为准；旧模板仅作历史参考。当前权威输出模板：`references/master-template-v68.md` v9.6（表格驾驶舱 · SVP v10 · 多资产）。

## 一、驾驶舱模块

| 模块 | 职责 | 主文件/能力 |
|---|---|---|
| 数据驾驶舱 | 多源采集、数据定级、新鲜度判断 | TV MCP、Binance、FinanceKit、Jin10、Web/X、CoinGecko、Polymarket、ETF Flow、Dune 链上、COT 报告 |
| 结构驾驶舱 | 定方向、价值区、关键位、扫线、VWAP/EMA/CVD | TV主指标 SVP+ICT+VWAP+EMA+CVD |
| 订单流驾驶舱 | 验证现货/永续、OI、CVD、Taker、Funding、期权 PCR/MaxPain | TV副指标、Binance OI/Taker/Funding、Deribit 期权 |
| 执行驾驶舱 | A/B/C/X 状态机、确认入场、失效、目标 | auto_card、render_tv_card、render_v8 |
| 风控驾驶舱 | R:R、仓位、日损、连亏、事件禁做、复盘样本 | risk_state、strategy_model_stats、strategy_governance |
| 监控驾驶舱 | 关键位接近/突破、自动推送、心跳、watchdog | 行情守望、watchdog、monitor_levels |
| 复盘驾驶舱 | 计划、触发、成交、平仓、复盘、模型升降权 | trade_plans/events/reviews、strategy_model_stats |
| 体制驾驶舱 | 趋势/震荡/收敛/爆发分类、跨资产相关性、降级信号 | regime_classifier、correlation_matrix、ADX/VHV/CVD背离 |

## 一·补、Cron 数据源 ⊂ 驾驶舱映射

| Cron 任务 | 驾驶舱模块 | 验证用途 |
|---|---|---|
| BTC 关键位同步 (4h) | 监控 | 关键位刷新，Monitor levels 数据来源 |
| Orion 全市场雷达 (30min) | 数据 | 广度扫描异动候选 + 跨交易所验证 |
| XAUUSD 监控 (5min) | 监控 | 黄金关键位/阶段/信号推送 |
| ETF Flow 刷新 (4h) | 数据 | 现货 ETF 流入流出 → BTC 方向性验证 |
| Dune 链上刷新 (2h) | 订单流 | BTC 链上流入流出 → 中长期趋势验证 |
| COT 报告刷新 (周六) | 数据 | 商业/投机持仓 → 中长期方向验证 |
| Deribit 期权刷新 (15min) | 订单流 | PCR/MaxPain → 期权市场情绪验证 |
| BTC 守护看门狗 (5min) | 监控 | 零 token 多因子评分 ≥8 推送 |
| SkillMCP/审计/备份/OR同步 | 运维 | 不直接参与交易验证 |

## 二、正式手动分析流程

触发词：分析BTC、分析XAU、现在呢、多周期看一下。

必须流程：

```text
① 确认品种映射
② TV MCP现场确认 chart_get_state/health，不得默认相信缓存
③ 多周期读取 D/4h/1h/15m/5m 的主指标行动格、关键位、labels/lines、必要时副指标/OI
④ 外部验证：Binance、FinanceKit/CoinGecko、Jin10、Web/X、F&G、Depth
⑤ 分层裁决：TV主指标定结构，副指标和Binance做验证，事件/风险做降级
⑥ full截图：必须含价格轴、主指标行动格、副指标/OI/CVD窗格
⑦ 输出卡：结论先行 → 多周期表 → 关键位矩阵 → 交叉验证 → 执行方案
```

正式分析不能静默使用过期 `tv_dmi_cache.json`。缓存只可作降级证据，必须标注年龄和来源。

## 三、高周继承、低周实时

| 周期 | 角色 | 更新 | 用途 |
|---|---|---|---|
| D | 大背景 | 日线收线 | 大结构、风险环境 |
| 4h | 方向 | 4h收线 | 定多空主线和市态 |
| 1h | 结构 | 1h收线 | 价值区、关键位、过滤4h |
| 15m | 执行 | 加密实时 | BTC/ETH主执行周期 |
| 5m | 触发 | 触发时切换 | XAU和精确入场确认 |

原则：高周期是约束，低周期是触发；不能切一个周期就换一套独立计划。

## 四、双指标裁决规则

```text
主指标 = 主驾驶：结构、方向、关键位、进场、止损、目标、R:R、磁吸
副指标 = 副驾驶：现货/永续、OI、CVD流向、量能、爆仓/踩踏
Binance = 外部验证：价格、OI历史、Funding、Taker、多空比
Deribit 期权 = 情绪验证：PCR(C/P比)、MaxPain、大额期权异动
ETF Flow = 现货方向：净流入/流出 → BTC 中期方向参考
Dune 链上 = 长期验证：BTC 交易所流入/流出趋势
COT 报告 = 结构验证：商业空投/投机多投 → 周线方向
Jin10/宏观 = 天气和路况：事件窗口、DXY/US10Y、风险偏好
体制分类 = 趋势/震荡/收敛/爆发 → 策略风格切换依据
跨资产相关性 = BTC-Gold-DXY 联动 → 风险偏好/避险模式
```

裁决：

| 情况 | 动作 |
|---|---|
| 主A + 副强 + Binance顺向 | A机会，可执行 |
| 主A + 副不配 | 降B，等确认 |
| 主B/C + 副强 + 贴关键位 | 给确认型入场 |
| 主X + 副强 | 不直接做，写解除条件 |
| TV与Binance冲突 | 标冲突，降级 |
| 情绪与结构冲突 | 情绪只提醒，不覆盖结构 |
| 期权PCR极度偏离 + 结构顺向 | 升级信号置信度(PCR是增强非主导) |
| ETF持续流出 + BTC技术多 | 降B，ETF流向与结构冲突时降级 |
| 体制=收敛 + 主A突破 | 降B，收敛区突破需二次确认 |
| Dune链上大量流出交易所 + 任何方向 | 增强多头偏向(长线因素，非短线触发) |
| COT商业净空增加 + 技术多 | 降级，商业持仓反向时提高警觉 |

## 五、A/B/C/X 状态机

### A：可执行

可写入场、止损、目标、仓位，但仍必须满足：
- R:R ≥ 1:2
- 数据新鲜
- 事件窗口未禁做
- risk_state允许
- TV主线与订单流不硬冲突

### B：确认型计划

B可以给入场，但必须写成“确认后入场”，不得写成无条件现价执行。

模板：

```text
B等待 · 偏多/偏空
确认入场：满足{触发条件}后，回踩/反抽{价区}执行
确认：{收线条件} · {CVD/Taker条件} · {关键位接受/拒绝}
止损：{结构外/扫点外/ATR夹层}
目标：{磁吸/VA另一侧/POC/VWAP}
R:R：1:{n}，不足1:2则仅观察
当前：未确认，不挂单/不执行
```

### C：试探型计划

C可以给入场，但必须比B更轻、更严格：
- 只允许轻仓/半仓
- 必须二次确认
- 必须写清“解除C→B/A”的条件
- 失败即撤，不摊平

### X：禁做/观察

X不输出可执行入场，只输出：
- 观察价
- 解除X的条件
- 重新评估触发
- 风险原因

## 六、R:R硬规则

- 任意可执行方向 R:R < 1:2：不得作为执行方案。
- B/C 若R:R不足，可以保留为“观察/重算方向”，但不能写入“入场+止损+止盈”执行块。
- A 若R:R不足，必须降为X禁做或重算目标/止损。

## 七、各市场流程

### BTC/ETH主流加密

必须用：TV主指标 + 副指标 + Binance OI/Funding/Taker/多空比 + FinanceKit/CoinGecko + F&G + Depth + Jin10/宏观。

执行周期：4h/D背景，1h结构，15m执行，5m触发。

### 山寨币/HYPE/TAO/ONDO

先分流动性等级：
- 主流：可按BTC流程
- 中流动性：OI/Depth权重降低，BTC方向作为压制
- 低流动性：不主动推A，只给观察/触发

### XAU黄金

不用加密副指标作主依据。必须用：TV主指标、Jin10 quote、gold-api、Yahoo GC=F/MGC=F代理、DXY、US10Y、Jin10日历、伦敦/纽约KillZone。

执行周期：D/4h背景，1h结构，15m辅助，5m执行。

### 外汇/股票/指数

主看结构、VWAP、宏观、事件、成交量；弱化CVD/OI，不套加密Funding/Taker。

## 八、数据新鲜度硬闸

正式卡必须显示：
- TV来源：实时/缓存/缺失
- TV时间：北京时间
- Binance/OI/Taker时间或采集时间
- 关键位更新时间
- 截图时间

硬规则：
- TV缓存超过10分钟：不得静默覆盖正式卡。
- TV缓存品种不匹配：不得使用。
- 关键位超过有效期：必须降级或重算。
- 监控heartbeat超过2分钟：报告监控异常。

## 九、监控驾驶舱

```text
正式分析 → 写 monitor_levels
行情守望10s轮询 → 接近/突破 → 数据质量/风控/模型确认 → 推送对应话题 → 写events → 必要时触发完整TV分析
```

话题：BTC 386，XAU 385，山寨/默认 416，报告 846。

## 十、复盘驾驶舱

```text
分析卡 → trade_plans
触发 → trade_events
成交 → 成交记录
平仓 → 成交复盘
统计 → strategy_model_stats
治理 → strategy_governance
下一张卡引用样本/胜率/平均R
```

样本不足时不得升权；未复盘过多时降仓或禁做。
