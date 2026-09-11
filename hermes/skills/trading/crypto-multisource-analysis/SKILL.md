---
name: crypto-multisource-analysis
description: 多资产驾驶舱 v9.6 — TV五层(1D/4h/1h/15m/5m)·Binance衍生品·CoinGecko Pro·宏观(SPX/VIX/DXY/金十/Poly/FG)·X实时情绪(x_search)·cron_read捷径(不重跑·读data/)·CVD/Depth·跨资产相关(corr)·黄金专属(gold_macro:GLD/GDX/TIP)·外汇专属(forex_rate:利差/央行)·GO/NO-GO下单七问闸门(go_nogo_gate)·QLib30因子·告警去重·IP-ban回退·17cron零token。步数:加密10/黄金8/外汇7/股票8/期货6。
category: trading
---

# Crypto Multi-Source Cross-Verification Analysis

触发词：`^分析 (BTC|ETH|SOL|加密|币)` 或 `[Tang Xi] 分析...`

## 自动加载技能（每次分析前）
1. `binance-trading` — 知悉所有币安MCP工具
2. `crypto-onchain-flow` — 链上分析框架（OI/多空比/费率/Taker/鲸鱼）
3. `market-regime-classifier` — ADX趋势强度/波动率/行情分类
4. `orion-screener-radar` — 全市场预筛选（604品扫描），提供异动候选清单供深入分析

## 执行纪律（2026-06-29 用户纠正 · 铁律级）

**驾驶舱不是摆设。** 用户明确要求每次分析必须按驾驶舱协议系统执行，不是跳步出结论。

### 四档驾驶舱模式（2026-08-28 用户确认 · 重排 · L1 轻量为默认档）

**档位唯一权威**：`scripts/pipeline_router.py` 的 `ANALYSIS_TIERS` 与 `resolve_tier()` 关键词表。对用户展示中文档位：**轻量档**（内部 L1 / `quick`）、**标准档**（L2 / `standard`）、**完整档**（L3 / `full`）、**监控档**（MON / `monitor`）。本节的档位名与触发词必须与代码一致；对不上时**以代码为准并立刻回来改本节**（2026-09-11 收敛：此前技能写「扫一下/状态」= 标准档而 router 不认，请求被静默降成轻量档）。查看当前权威表：`python -c "import sys;sys.path.insert(0,'scripts');import pipeline_router as r;print(r.tier_table())"`

用户说不同关键词，自动切换执行深度。**不需要用户记模式名。** L1 是默认——用户日常只想"看一眼现"时不再跑重活。**用户明确要求：保质量的前提下快而简。**

⚠ **铁律（2026-07-01 用户纠正 · 仍有效）**：含「**分析**」关键词触发**完整**模式时，即使是对同一品种的即刻后续请求，也绝不可降级为轻量/快速。用户说「分析BTC」就是完整10步，不因刚出过卡而简化。

| 中文档位 | 用户说的 | 内部映射 | 自动触发 | 跑什么 | 调用数 | 耗时 |
|:--:|---------|:--:|---------|---------|:--:|:--:|
| **轻量档** | `看下BTC` / `看下XAU` / `看一眼`（默认） | L1 / `quick` | ⚡ 轻量 | 行动格 table + quote 现价 + 一张截图（加密另加衍生品 curl） | **~5** | ~30s |
| **标准档** | `现在呢` / `更新` / `扫一下` — 追踪类 | L2 / `standard` | 🔀 标准 | 轻量档 + 上下邻居周期只读行动格结论行 + 关键位表 | ~8 | ~1.5min |
| **完整档** | `分析` / `分析BTC` / `分析XXX` | L3 / `full` | 🔍 完整 | router full mode（全管线） | 全量 | ~3min |
| **监控档** | 仅事件系统触发 | MON / `monitor` | 🛰 监控 | 仅事件发现，不出方向卡 | 事件驱动 | 按事件 |
| — | `深度分析` / `出完整卡` | 🔍 完整 | router full mode | 全量 | ~3min |

**常见失败模式（2026-07-01 记录 · 仍适用）**：用户说「分析BTC」时误判为追踪更新而走快速/L1。**这是错误的。**「分析」=完整硬开关。若用户想快，会说「看下」「现在呢」「看一下」而非「分析」。2026-08-28 新增：「看下X」= L1 轻量（区别于「分析X」=完整）。

**自动档位识别（2026-08-28 用户确认 · 无需用户说档位名）**：
按用户**话里的关键词**自动定档，优先级从高到低：
1. 含「**分析**」「**深度**」「**出完整卡**」→ **L3 完整**（硬开关，不因刚出过卡而降级）
2. 含「**看下**」「**看一眼**」「**扫一眼**」→ **L1 轻量**
3. 含「**现在呢**」「**更新**」「**扫一下**」「**状态**」→ **L2 标准**
4. **无动词**（只说「BTC」「XAU」或裸品种名）→ 默认 **L1 轻量**（最新报价+行动格+截图），若用户接着追问再升级
5. **歧义/会话开头无上下文** → 默认 **L1 轻量**，同时标注"如需完整请说 分析"；绝不默认上 L3 全管线
规则口诀：**「分析」=重，「看下」=轻，无动词=轻量起步，带"为什么/为啥"先补 lines/labels 精确位再答**。

**L1 轻量卡模板（默认 · 2026-08-28 固化）**：
```
0. [防抢图·必做] 声明分析租约，让后台续航让路：
   python scripts/tv_analysis_lease.py start --minutes 10 --symbol BINANCE:BTCUSDT.P
   （出卡后 end；忘了也会自然过期，TTL 上限 30 分钟。tv_screenshot 会自动续期。）
   没这一步时后台 btc_tv_refresh/xau_tv_sync 会在读图中途切走图表 —— 行动格读成空表。
1. 读主指标 行动格 pine_tables（唯一文字真理源：位置/结论/方向/结构/磁吸/现位）
2. quote_get 拉实时现价（一切价格裁决，不信 study_values close）
3. capture_screenshot(region="full") 主执行周期截图（BTC 15m / XAU 5m）
4. [加密] 衍生品 curl 批量：OI变化 + 资金费率 + 大户/全局多空比 + Taker（方向票）
输出：首行截图 → 一句话裁决(品种·价·方向·时间) → 行动格核心(表格) → 关键位矩阵(小表) → 多源交叉验证(小表) → 1句裁决 + 缺失备注
```
**L1 必须保留**：主指标行动格（唯一真理源）· quote现价（裁决漂移）· 主周期截图（人眼判结构）· 加密衍生品（OI/费率/多空/Taker 方向票）。**跳过的**：逐层 `study_values` 大字段、逐层 `lines/labels` 全量、多周期每层 sleep 重拉。`lines/labels` 精确关键位只在用户问"为啥/为何"时才读。

**L2 标准 = L1 + 邻居周期结论行**：主周期读取后，只读上下相邻周期（如 L1=15m 则补 4h/5m，L1=5m 则补 1h/15m）的 pine_tables 行动格「结论行」，不做逐层 study_values/labels 全量；再加关键位矩阵与两源验证。方向一致性判断仍靠主指标行动格 + 邻居结论行。

**L3 完整 = router full mode**（原全管线，加密10步/黄金8步等）。

**完整模式（v9.5 补齐·2026-06-29）**：
```
加密: tv→binance→cg_pro→macro→x_sent→cron_read→cvd→depth→corr→card (10步)
黄金: tv→macro→x_sent→cron_read→cvd→corr→gold_macro→card (8步)
外汇: tv→macro→x_sent→cron_read→corr→forex_rate→card (7步)
股票: tv→macro→x_sent→cron_read→corr→fmp→options_chain→card (8步)
期货: tv→macro→x_sent→cron_read→corr→card (6步)
```

**补齐的三步（2026-06-29）**：
- `x_sent`：独立步骤，x_search实时X情绪 + 恐贪 + CG热搜（不依赖cron落盘）
- `gold_macro`：黄金专属，TIP/GLD/GDX/白银比/央行储备
- `forex_rate`：外汇专属，利差/央行窗口/Carry Trade基础

**输出格式统一**：MEDIA截图首行 → v9.9手机驾驶舱卡 → 管线审计。v9.9权威见 `D:/Hermes agent/references/master-template-v68.md`：首屏必须结构位前置（上方结构｜⚖现价｜下方结构），完整卡固定 4 表（①周期体温/多周期定位、②关键位/结构关键位、③多源验证/双指标、④最推荐方案），快速模式也必须保留 1D/4h/1h/15m/5m、SVP主驾驶、HALDRO副驾驶和订单流三行，不允许跳层。

### 驾驶舱表格格式铁律（2026-07-02 用户多次纠正 · P0）

用户说「分析BTC/分析XAU」时，不只是跑数据源，还必须按**驾驶舱固定表格格式**输出；不能用散文、Step流水账、只写快速更新、只写道歉或自创模板。若不是完整管线，必须在卡尾逐项备注缺失原因。

**输出档位铁律（2026-08-29 用户两次纠正「太繁琐」· 三 skill 已统一）：**
- **默认 = 手机三表速读版**：①方向速览表（现价+五周期方向）→ ②关键位矩阵表 → ③一句触发/裁决。手机一屏读完，增量信息压到一句话或省略。
- **完整 8 表**（下方固定顺序）只在用户明确说「完整 / 深度 / 出完整卡」时才出。
- 「分析BTC / 分析XAU」= 采集走完整 10 步管线（不可跳步），但**输出呈现**默认仍是三表速读版。

**完整 8 表固定顺序（仅完整档使用，不可省略）：**
1. `MEDIA:<新截图>` 必须首行；截图为TV full窗口，含价格轴与CVD/副指标窗格。
2. 首句自然语言直给裁决：`↑/↓/○/× 品种 价格 · 结论 · 中文时间`。
3. **当前基本情况首屏表**：在流程审计前先给手机端最需要的现状，表头固定为 `当前基本情况 | 数据`，至少包含 `刚发生什么`、`贴近结构`、`最大问题`、`明确推荐`、`禁做`。这是手动Telegram分析卡的首屏速读层，先让棠溪知道当前行情和动作，再看完整驾驶舱数据。
4. `驾驶舱流程/管线完成情况` 表：步骤、模块、状态、备注；加密完整10步为 `tv → binance → cg_pro → macro → x_sent → cron_read → cvd → depth → corr → card`。
5. `多周期定位` 表：列固定为 `周期 | SVP | 副指标 | Composite | 价 vs VWAP`；必须含 1D/4h/1h/15m/5m 五层。
6. `关键位矩阵` 表：列固定为 `方向 | 价位 | 性质 | 距现价`。
7. `多源交叉验证` 表：列固定为 `维度 | 数值 | 方向`。
8. `矛盾点` 表：列固定为 `矛盾 | 多头 | 空头 | 裁决`。
9. `最推荐方案` 表：只给一个 `⭐主推`，包含触发、入场、止损、目标、仓位/等级、R:R；`🔁备选` 只能作为主推失效路径，禁止 A/B 同权菜单。
10. `评分/裁决` 表：模块分、总分、主方向、当前动作、失效条件。
11. `完整性备注` 表：对10步逐项标 ✅/⚠️/❌；凡未完成必须写明原因（如 x_search不可用→web替代、corr数据不足、CG Pro阻断），禁止假装完整。

**禁止事项：**
- 禁止只用文字段落代替表格。
- 禁止把管线步骤散落在正文里而不做「驾驶舱流程」表。
- 禁止先说“怪我/抱歉”后仍不改格式；用户要的是执行，不是解释。
- 禁止省略截图或把MEDIA放到正文后面。
- **禁止因上一轮中断/截图未完成就要求用户再发“继续/重来”。** 如果用户已经下达过分析任务且当前会话仍可调用工具，必须主动续跑缺失步骤（至少：切回目标品种→校验TV状态→补截图→补Binance/宏观/x_sent/depth→出完整卡）。只有工具权限完全不可用或必须用户选择时才提问。

### 中断续跑协议（2026-07-03 用户纠正）
当分析中途因为网关、工具链、截图或上下文压缩中断，用户随后说「继续」或问「为什么不继续」时，按以下方式处理：
1. 不道歉拖延、不让用户重发指令；直接恢复任务。
2. 先用 `chart_get_state` 校验当前 symbol；若不是目标品种，立即 `chart_set_symbol`，再校验一次。
3. 若上轮截图未落地或不是本轮时间戳，必须补 `capture_screenshot(region="full")`，MEDIA仍放最终回复首行。
4. 已采集的数据可复用但要补齐缺口；不确定新鲜度时宁可重读执行周期与Binance关键数据。
5. 完整卡的「驾驶舱流程」表必须标注哪些步骤是续接、哪些步骤重新采集、哪些步骤降级。
6. 最终仍必须给明确A/B首选，不用“等确认”作为主结论。

实战复盘与恢复清单见 `references/interrupted-analysis-resume-2026-07-03.md`。

### 必做：6市场全管线执行

用户覆盖6类资产：🪙加密 | 🥇贵金属 | 💱外汇 | 📈股票 | 📊期货 | 📋期权

每次分析前必跑 `pipeline_router.route_pipeline(symbol, mode)` 确定应执行步骤：
加密 BTC/ETH/SOL：10步（tv→binance→cg_pro→macro→x_sent→cron_read→cvd→depth→corr→card）
黄金 XAU/USD：8步（tv→macro→x_sent→cron_read→cvd→corr→gold_macro→card）
外汇 EUR/USD等：7步（tv→macro→x_sent→cron_read→corr→forex_rate→card）
股票 AAPL/TSLA：8步（tv→macro→x_sent→cron_read→corr→fmp→options_chain→card）
期货 ES/CL：6步（tv→macro→x_sent→cron_read→corr→card）
- 期权：3步（tv→options_chain→card）

### 全市场五层周期规则（2026-06-29 用户纠正 · 铁律级 · 2026-07-08 补 1D）

全市场统一五层框架 **1D→4h→1h→15m→5m**（注意是 **1D** 不是 D；用户 2026-07-08 明确要完整五周期，先漏 1D 后纠正补回）。不可跳层。截图切到该品种的**主执行周期**截 full。

| 市场 | 品种例 | 五层周期 | 主执行（截图） | 理由 |
|------|--------|----------|:--:|------|
| 🪙 加密 | BTC/ETH/SOL | 1D→4h→1h→15m→5m | **15m** | 24×7，15m平衡噪音与信号 |
| 🥇 贵金属 | XAU/XAG | 1D→4h→1h→15m→5m | **5m** | 棠溪指定，快进快出风格 |
| 💱 外汇 | EURUSD/GBPJPY | 1D→4h→1h→15m→5m | **15m** | 24×5，节奏接近加密 |
| 📈 股票 | AAPL/TSLA/NVDA | 1D→4h→1h→15m→5m | **1h** | 有缺口·盘中流动性分段 |
| 📊 期货 | ES/NQ/CL | 1D→4h→1h→15m→5m | **15m** | ES 23h流动性·对标加密节奏 |
| 📋 期权 | 跟随标的 | 跟随标的 | 跟随标的 | 标的主周期=期权主周期 |

**1D周期特殊处理**：1D 用 OHLCV summary（日线宏观背景），不读SVP指标（SVP在1D上渲染不完整）。TV `set_timeframe` 参数用 `"1D"` 或 `"D"`（TV 两者都接受，实测 `chart_set_timeframe({"timeframe":"1D"})` 返回成功）。4h/1h/15m/5m 四层全读 study_values + pine_tables + labels + lines。
**相邻周期冲突硬门**：周期一致性验证覆盖 1D≠4h / 4h≠1h / 1h≠15m / 15m≠5m 任一相邻反向即否决交易（见 `signal_validators.tf_alignment` / `tf_alignment_tv`）。

### ⚡ TV MCP 多周期方向读取铁律（2026-07-08 实战固化）

周期一致性验证（作战室/auto_card 用）优先走 **TV MCP 真实路径**（非 Binance REST 降级），每周期独立读取：

- **每周期独立 MCP 会话**：TV Desktop CDP 在单会话里连续切周期会断连（`Connection closed`），改为「开→切品种→切周期→等加载→读→关」每周期一个会话（`fetch_tv_mcp` + `asyncio.run` 循环，周期列表 `("1D","240","60","15","5")`）。
- **必须等加载完再读**：`set_timeframe` 后 `await asyncio.sleep(3)` 等 SVP/VWAP/CVD 指标完全加载，再 `data_get_ohlcv(summary=True)` 读方向，否则读到陈旧/空数据。
- **OHLCV summary 是 JSON 不是文本**：TV 返回 `{"success":true,"change_pct":"-2.09%",...}`，方向判定必须用 `json.loads` 取 `change_pct` 字段（旧正则匹配 `change%` 文本会全部返回 0 → 误判"全空"）。`_dir_from_ohlcv_summary()` 已按此修复。
- **端口探测降级**：`socket.connect_ex(("127.0.0.1",9222))!=0` → TV Desktop 未带 `--remote-debugging-port=9222` 启动 → 自动降级 Binance REST（`tf_alignment`）。TV Desktop 启动方式（清理 Electron env 避免 `--remote-debugging-port` 被拒）：`node -e "import('tools/tradingview-mcp/src/core/health.js').then(m=>m.launch({port:9222,kill_existing:true}))"`。
- **时段符号**：TV 周期字符串 1D=`"1D"`、4h=`"4h"`、1h=`"1h"`、15m=`"15"`、5m=`"5"`（分钟用纯数字，避免 `"5m"` 被误解释成异常高周期）；Binance REST 对应 `1d/4h/1h/15m/5m`。

### 常见失败模式（不要再犯）

| 失败模式 | 表现 | 正确做法 |
|---------|------|---------|
| 跳步出卡 | TV→Binance→直接出卡，跳过cg_pro/dune/deribit/x_sent等10步 | 严格按router返回的步骤列表逐一执行 |
| 含「分析」关键词走快速模式 | 用户刚看完全量卡，接着说「分析BTC」时降级为追踪更新 | 铁律：含「分析」二字=完整模式硬开关，不论时间间隔 |
| 漏调CoinGecko Pro | Key在代码里但分析时不调cg_categories/cg_coin_detail | 加密分析Step 4必须调CG Pro。CG Pro Bridge stdin模式不便→直接用`python scripts/coingecko_collector.py` |
| 漏调x_search | cron有定时采集但手动分析时不调 | x_search已恢复为独立步骤(x_sent)。x_sentiment_collector.py双落盘，cron_read也可读data/x_sentiment.json |
| **x_search一声放弃** | tool_call('x_search')失败后直接说不可用 web_search替代 | 先调用x_search一次再判断。在Telegram平台上x_search实际可用（2026-06-30验证），不要预判不可用。真的失败了再走排查协议；若返回 `personal-team-blocked:spending-limit`，属于额度/订阅阻断，不要重复调用，按 `references/x-search-quota-and-degraded-sentiment-2026-07-03.md` 降级为本地x_sent+web源并在审计表标⚠️ |
| 重分析漏X情绪 | 用户纠正后重新分析时又跳过x_sent | 每次输出分析卡（包括重分析/跟踪更新）前做一次x_sent检查：若前次输出无X情绪行，必须补调x_search或web_search。在出卡验证清单最前加一项「x_sent已执行」。|
| 忘切多市场 | 用加密思维分析黄金/外汇/股票 | 先跑router确认资产类别，用对应管线 |
| 只跑TV不出交叉验证 | 只看TV行动格，不调Binance OI/费率/多空比 | 衍生品三件套必须取齐 |
| 4h指标初始空 | 切4h后study_values只有Volume | 等12s总时长(8s+4s重试)，不要仅看第一次空就放弃 |
| ETF Flow虚挂 | router仍包含etf_flow步骤 | 跳过此步，用Dune+稳定币替代。标注「ETF Flow: SoSoValue被封·Dune替代」 |
| Jin10 flash参数错 | `keywords`参数MCP不接受 | 用`keyword`(单数)参数，或用`list_flash`分页 |
| TV MCP直接调用失败 | `mcp_tradingview_chart_set_timeframe` not found | 必须用`tool_call(name='mcp_tradingview_...', arguments={...})` |
| **TV MCP不可用仍出卡** | TV MCP server unreachable（MCP进程崩溃）时跳过TV步骤继续分析 | **TV MCP是所有分析的前提，不可用=中止，不能跳过**。用户明确「TVmcp是必须的」。修复流程：①`tv_launch(kill_existing=true)`尝试重启 → ②若返回ClosedResourceError/MCP不可达，表明MCP server进程崩溃，等~60s让Hermes auto-retry → ③再次`tv_launch(kill_existing=true)` → ④`health_check`确认api_available → ⑤继续分析 |

### 管线完成度审计（2026-06-30 用户要求 · 铁律级）

用户明确要求：「重新来一次完整的，不是完整的要备注」。每次完整分析完成后，在出卡前输出一个 **管线完成度审计表**，每步骤标注 ✅/❌/⚠️ 并附原因，让用户一目了然知道执行了什么、跳过了什么、为什么。

> v9.6 起 `auto_card()` 已内置审计表输出：启动时自动跑 `route_pipeline()` 打印路由，出卡前自动输出 Markdown 审计表（见 Step 6 管线完成度审计段）。

#### 完成度审计表格式

```
| 步骤 | 状态 | 备注 |
|:---|:---:|:---|
| 1. TV 五层 | ✅ | 1D/4h/1h/15m/5m 全量 + FVG框 + 截图 |
| 2. Binance | ✅ | OI/多空比/费率/Taker 全部 |
| 3. CG Pro | ❌ | API 网络阻断（private network）· 跳过 |
| 4. Macro | ⚠️ | DXY确认·VIX数据不精确 |
| 5. x_sent | ⚠️ | x_search不可用·web搜索替代（非X实时源） |
| 6. cron_read | ✅ | Dune+Deribit+x_sentiment 全部 |
| 7. CVD | ✅ | TV内置各周期 |
| 8. Depth | ✅ | curl直取（web_extract被阻断） |
| 9. Corr | ❌ | FinanceKit返回数据不足·跳过 |
| 10. Card | ✅ | 见下 |
```

#### 常见步骤失败与降级路径

| 步骤 | 常见失败 | 降级/处理 |
|:---|:---|:---|
| CG Pro (Step 3) | web_extract 被网络策略阻断（private network） | 尝试 terminal+curl 直取 CoinGecko API；若curl也被阻断，跳过并标注「CG Pro: 网络阻断」 |
| x_search (Step 5) | 工具在当前环境不可用 | **三层检查协议**：① `tool_search('x_search')` 搜不到 → ② `grep x_search config.yaml` 确认已配置 → ③ 检查 `platform_toolsets.{当前平台}` 是否包含 x_search。若配置了但当前平台没挂载，用 `delegate_task` 派到 CLI 工具集（CLI 通常有 x_search）尝试代理调用；若 delegate 也不行，最后回退 web_search 并标注「web源·非X实时」+ 附上排查过程说明 |
| Correlation (Step 9) | FinanceKit 返回 "Could not fetch data for enough symbols" | 跳过并标注「FinanceKit相关性不可用」 |
| Depth (Step 8) | web_extract 被阻断（Binance API私有网络） | 改用 `terminal('curl -s "https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=20"')` 直取 |
| Binance MCP (Step 2) | Binance MCP server unreachable 或 ClosedResourceError | 用 curl 直取 Binance REST API：24h统计`fapi/v1/ticker/24hr`、OI`fapi/v1/openInterest`、费率`fapi/v1/premiumIndex`、K线`fapi/v1/klines`、多空比`futures/data/topLongShortPositionRatio`、Taker`futures/data/takerlongshortRatio`。若 curl 也返回 Cloudflare 403（fapi 全线 Cloudflare 封禁），用 **TV 副指标 Volume Aggregated OI/Composite 数据做衍生品替代**，同时 spot api.v3/depth 通常仍可用。标注「Binance MCP不可用·fapi CF 403·TV副指标替代」 |
| 金十 MCP | MCP 未运行或未配置 | 跳过并标注「金十MCP不可用」 |

Depth 数据通过 curl 获取示例：
```bash
curl -s "https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=20" | python -c "
import sys,json; d=json.load(sys.stdin)
bids=[float(b[0])*float(b[1]) for b in d['bids'][:5]]
asks=[float(a[0])*float(a[1]) for a in d['asks'][:5]]
print(f'Bid墙(前5): {sum(bids):,.0f} USD')
print(f'Ask墙(前5): {sum(asks):,.0f} USD')
print(f'买卖比: {sum(bids)/sum(asks):.2f}')
"
```

### v9.5 缺口闭合（2026-06-29 本轮全部修复）

| 缺口 | 状态 | 修复时间 | 实现 |
|------|:--:|:--:|------|
| x_sent 无本地落盘 | ✅ 已闭合 | 2026-06-29 | `x_sentiment_collector.py` 双落盘(hermes data + 项目 data/x_sentiment.json) |
| forex_rate 步骤丢失 | ✅ 已闭合 | 2026-06-29 | `pipeline_router.py` 恢复 forex_rate 为活跃步骤(asset=forex) |
| gold_macro 丢失 | ✅ 已闭合 | 2026-06-29 | `pipeline_router.py` 恢复 gold_macro 为活跃步骤(asset=gold) |
| 快速模式丢X情绪 | ✅ 已闭合 | 2026-06-29 | quick mode 全部市场加回 x_sent 步骤 |

### v9.6 已闭合缺口（2026-06-30 全方位修复 · R1+R2）

#### v9.6 准确度硬化补丁（2026-07-06）

| 闸门 | 铁律 | 验证 |
|------|------|------|
| 数据新鲜度 | `auto_card()` 启动必须刷新/标记 `source_snapshot_{symbol}.json`；`go_nogo_gate` 读取真实 `_snapshot_age_h`，禁止用默认24h假值 | `python scripts/data_freshness_watchdog.py` 必须0过期；BTC/XAU snapshot <1h |
| 守望刷新 | `行情守望.py` 即使无有效监控价位，也必须每5分钟刷新 BTC/XAU SourceSnapshot；过期价位不能阻断数据刷新 | `data/monitor_heartbeat.json` fresh，`source_snapshot_BTCUSDT/XAUUSD.json` fresh |
| R:R硬底线 | GO/NO-GO 只看主线计划 `rr_a/rr1`，不是取A/B最大值；主线 R:R<1:2 必须 `NO-GO·rr_ratio`，即使反向 `rr_b`>2 也不能显示 GO | `python scripts/auto_card.py BTCUSDT` 若模板审计报 `rr1<2.0`，GO/NO-GO 必须同步红灯 |
| 跨资产情绪隔离 | CoinGecko社区面板、BTC/crypto Polymarket、BTC x_sent 缓存只用于加密；XAU/外汇/股票改用本品种热点/宏观/金十/COT，禁止把BTC情绪灌进非加密卡 | `python scripts/auto_card.py XAUUSD` 输出应含“非加密跳过BTC/crypto预测市场桥/不采用BTC缓存” |
| Windows输出安全 | 渲染器 `stdout/stderr.reconfigure()` 必须捕获 `OSError/ValueError`，避免 cron/管道句柄异常导致出卡中断 | `python -m py_compile scripts/render_v8.py` |
| 正式分析前置修复 | 用户说“分析BTC/分析XAU”触发完整模式时，若 TV CDP 断连、`data_freshness_watchdog.py` 报 source snapshot / tv_live / heartbeat 过期、或行情守望心跳停滞，不准直接用缓存出卡；必须先修运行态，再跑完整卡 | `tv_launch(kill_existing=true)` → `tv_health_check` → `python scripts/p0_refresh_all.py` → `python scripts/watchdog.py` 或重启守望 → `python scripts/tv_live_dump.py --verbose` → `python scripts/auto_card.py BTCUSDT` |

### 完整分析运行态预检（2026-07-07实战固化）

含“分析”关键词=完整模式硬开关。完整卡启动前先做运行态闸门，不把“工具故障/缓存过期”当作行情结论：
1. `route_pipeline(symbol, "full")` 打印并确认应执行步骤。
2. `tv_health_check`；若 CDP 失败，立即 `tv_launch(kill_existing=true, port=9222)`，再 health check。
3. 跑 `python scripts/data_freshness_watchdog.py`；若 BTC/XAU snapshot、`tv_live.json`、`tv_dmi_cache.json`、`monitor_heartbeat.json` 过期，先 `python scripts/p0_refresh_all.py`，必要时启动/修复 `watchdog.py`/`行情守望.py`。
4. `chart_set_symbol` 到目标品种，主周期（加密15m/黄金5m）截图前先刷新 `python scripts/tv_live_dump.py --verbose`。
5. 只有上述恢复后再跑 `auto_card.py {symbol}`，最终卡的完整性备注写明“已修复TV/守望/快照后重新出卡”。

回归命令：`python -m py_compile scripts/auto_card.py scripts/render_v8.py scripts/行情守望.py scripts/data_freshness_watchdog.py scripts/watchdog.py scripts/pipeline_router.py scripts/go_nogo_gate.py && python -m pytest -q`，随后实跑 `python scripts/auto_card.py BTCUSDT` + `python scripts/auto_card.py XAUUSD` 验证管线和闸门一致。详细复盘与探针见 `references/analysis-accuracy-hardening-2026-07-06.md`。

| 缺口 | 状态 | 修复 |
|------|:--:|------|
| 孤儿脚本闲置(6引擎~2,000行) | ✅ 已闭合 | `scripts/orphan_integration.py` 统一接口，接入 auto_card ⑦段 |
| 复盘率3.2% | ✅ 已闭合 | `scripts/batch_review.py` + `auto_review_cron.py` → 复盘率100% |
| Stock-API MCP零调用 | ✅ 已闭合 | A股stock-api MCP + 美股yfinance回退 `scripts/stock_quote.py` |
| pipeline_router未入auto_card | ✅ 已闭合 | auto_card Step 0 动态路由 + Step 6 管线审计表 |
| 评分引擎未接入 | ✅ 已闭合 | `scoring_engine.score_setup()` 接入 auto_card ⑧段 |
| VWAP/EMA/CVD引擎未接入 | ✅ 已闭合 | `vwap_ema_cvd_engine.vwap_ema_cvd_summary()` 接入 auto_card |
| 回测引擎无CLI入口 | ✅ 已闭合 | `backtest_runner.py` 新增 argparse CLI + 快速测试模式 |
| 外汇/期货/期权管线未验证 | ✅ 已闭合 | 5类市场管线全部路由验证通过 |
| 黄金缺金十/COT常态化 | ✅ 已闭合 | `scripts/jin10_gold_bridge.py` + `scripts/cot_bridge.py` → 金十日历/快讯 + COT持仓每周注入XAU分析卡 |
| forex_rate步骤无实战代码 | ✅ 已闭合 | `scripts/forex_rate.py` → 24外汇品种利差+央行窗口+Carry Trade，auto_card自动调用 |
| options_chain步骤无实战代码 | ✅ 已闭合 | `scripts/options_chain.py` → BTC/ETH走Deribit、美股走yfinance，auto_card自动调用 |
| liquidation/qlib/stablecoin无落盘 | ⚠️ 持续缺口 | cron stdout→TG无本地JSON，cron_read读数受限 |

**核心铁律：router返回的步骤列表，缺一步不算完成分析。**

### Cron-Read 捷径（v9.5 · 避免重复采集）

17个cron每30min自动采集：Deribit 期权OI、Dune 链上数据、X 情绪、QLib 因子、清算压力、稳定币供应、COT 持仓。**手动分析时无需重新运行这些脚本**——直接读取最新的 cron 输出文件：

- 完整协议：`references/cron-read-protocol.md`
- 双落盘模式：`references/dual-write-pattern.md`（x_sentiment已迁移，liquidation/qlib/stablecoin待迁移）

| 脚本 | 最新输出文件 | 读取方式 |
|------|-------------|---------|
| deribit_options.py | `data/deribit_options.json` | `read_file` → 提取 C/P比/MaxPain/总OI |
| dune_collector.py | `data/dune_cache.json` | `read_file` → 提取 BTC流/CEX净流 |
| cot_collector.py | `data/cot_data.json` | `read_file` → 提取投机净多/空 |
| qlib_factors.py | cron stdout (TG:846) | 读取上次推送或 `terminal('python scripts/qlib_factors.py --line')` |
| liquidation_collector.py | cron stdout (TG:846) | 同上 |
| stablecoin_collector.py | cron stdout (TG:846) | 同上 |
| x_sentiment_collector.py | cron stdout (TG:846) | 同上；或直接调 `x_search` 获取实时 |

**读取时效判断**：文件 mtime < 60min → 直接使用，标注「cron缓存·{时间}」。>60min → 重新运行脚本。

优化后完整模式从 ~14步 缩减到 ~8步（tv→binance→cg_pro→macro+jin10+poly+fg→cron_read→cvd→card），不丢失任一数据维度。

## 管线原则（不裁剪指标 · 分层治理 · 优先免费源）

用户明确否决"固定核心因子/减少指标"。本 skill 的优化方向是：**数据源全量保留，靠层级裁决和输出收敛解决噪音，不靠删源。**

- **采集不减配**：TV、Binance、OI/多空比/Funding/主动买卖、Depth wall、金十、恐惧贪婪、CoinGecko、X/web情绪都尽量执行。
- **TV双指标为主驾驶+副驾驶**：主指标(SVP+ICT+VWAP+CVD，标题不含EMA但源码含EMA9/21/34/55、FVG/HTF FVG、MCP Data Window)定结构、方向、位置、计划、失效、磁吸目标；副指标(Volume Aggregated Spot & Futures)定OI价仓、会话CVD、覆盖率/单所主导、合约占比、量能、爆仓、运动真假。外部源用于确认、挑战、降级和补盲。
- **副指标仅加密有效**：副指标内部 `isCryptoA = syminfo.type=='crypto'`，挂黄金/外汇/股指时其行动格自动罢工显示"非加密品种/请看主指标判定"。本 skill 只用于加密，故副指标全程有效、必采；但若误用到非加密品种，**只读主指标行动格 v2，跳过副指标采集**。
- **多源职责分层**：结构定方向，订单流定质量，衍生品定续航/拥挤，Depth/SVP定价位，事件时间定能否交易，情绪只做反指/仓位微调。
- **冲突不删源**：多源冲突时输出"矛盾点→主倾向→等待条件→失效条件"，不把任一源静默丢弃。源优先级权重(结构35%>聪明钱30%>宏观25%>情绪10%>事件5%)、多周期共振计数(≥4/6入场)、相邻周期冲突=不交易硬门、支撑真伪确认(吸收/OI/扫单收回)、跨市场领先链与反向极值阈值 —— 完整方法论见 `references/community-validation-methodology-2026.md`(17+社区源)。轧空冲顶期主副指标冲突（主禁追·副偏多共振→两路均收敛为等待）的特定裁决路径见 `references/squeeze-aftermath-pattern.md`(2026-06-30 GASUSDT 实盘案例)。
- **输出可短**：后续跟踪只写3-5行，但底层仍按需要读取全源或至少刷新TV+订单流+OI。
- **截图必有**：每轮输出（含"现在呢"快速更新）必须附带TV截图。用户明确要求"要有截图，都要有截图"。价格移动≥0.3%或行动格等级变化时一定截新图。MEDIA放首行。
- **主线程不变**：跨更新的一致性是生命线。每次出卡/更新时，在开篇用一句话固化当前主线逻辑（如"4h空势内反弹已结束，等反抽到VWAP附近确认再空"），后续数字更新不推翻主线，只补充变化。用户问"为什么变"时，展示主线程没变但数字自然更新的对照。
- **来源可证**：输出中的每条结论应能在对话中追溯到具体数据源调用。用户问"有没有用我的能力"时应能逐条列出MCP调用和数据源，不自证造数。
- **优先免费/免费额度源**：新增数据源时，优先选免费 API / 免费 tier / 公开页面抓取。付费源（CoinGlass $29+/月、Nansen $几百/月）仅在用户明确要求时接入。当前免费管线：SoSoValue(ETF)、Dune(链上40req/min)、Polymarket(Gamma公开)、CG Pro(用户已有Key)、Pyth(免费Hermes)、alternative.me(恐惧贪婪)。
- **全周期强制刷新（2026-06-28 用户纠正）**：用户说"多周期看一下"时，必须读取全部三个周期（4h背景继承→1h结构确认→15m实时执行），不能只刷当前TF。每个周期独立读取 study_values + pine_tables + labels + lines，不能一个周期的数据代表所有周期。高周期继承后标注"继承自{N}根前K线"，低周期标注"实时读取"。
- **时区铁律（2026-06-28 用户纠正）**：棠溪使用北京时间（BJT, UTC+8）。所有分析卡、告警、截图说明中的时间戳均为BJT。TV截图显示UTC时间，必须在文字描述中转换为BJT。
- **X情绪验证（2026-06-28 用户要求·2026-06-28 审计升级·2026-06-30 铁律：重分析/跟踪更新也必补）**：作为多渠道验证的标准步骤。**优先使用 `x_search` 工具（grok-4.20-non-reasoning，90s超时，2次重试）获取 X/Twitter 实时情绪**，提取方向(bullish/bearish/neutral)、强度、大V观点。写入分析卡独立行。X 情绪不覆盖结构方向，只作验证和挑战。若 x_search 不可用，回退 web_search 并标注「web源·非X实时」。

## 本机能力接入图（2026-06-27 审计 → 2026-06-28 v8.5 更新）

权威参考：`references/tangxi-capability-map.md`。多资产覆盖详情：`references/multi-asset-capability-matrix.md`。

本机已确认可用（2026-06-27 更新）：
- TV MCP：78工具，负责图表、双指标、截图、Pine读写。CDP断连恢复：`tv_launch(kill_existing=true)` → 等8-10s。MCP server崩溃恢复（ClosedResourceError）：等~60s auto-retry → `tv_launch(kill_existing=true)`，详见 `references/tv-mcp-crash-recovery-2026-06-30.md`。
- Binance MCP：15工具，负责价格/K线/OI/Funding/Taker/多空/账户/下单能力；默认只分析，不自动交易。
- FinanceKit MCP：17工具，负责 CoinGecko/股票/期权/市场概览/相关性/风险指标。
- Jin10 MCP：8工具，负责金十行情、财经日历、快讯/新闻。
- CoinGecko Pro Key：**已全面灌注**（2026-06-28，4个脚本）→ 全速500req/min + 板块轮动/流动性评分/交易所量验证
- ETF Flow（SoSoValue）：**已接入**（`etf_flow_collector.py`）→ 免费抓取 BTC ETF 日净流入流出 + 信号判定
- Dune Analytics（链上）：**已接入**（`dune_collector.py`）→ BTC全网流入/CEX净流/稳定币供应，免费 40req/min
- CFTC COT 持仓：**已接入**（`cot_collector.py`）→ 外汇/金属/股指/能源投机持仓，每周五更新
- Deribit 期权 OI：**已接入**（`deribit_options.py`）→ BTC/ETH C/P比+MaxPain，公开API免费
- DeFiLlama 稳定币 API：**已接入**（`stablecoin_collector.py`，cron `5f7192fd9029` 每2h）→ 385稳定币实时供应量，免费公开，写入TG:846。
- **QLib 因子库**：**已接入**（`qlib_factors.py`，cron `fd78e36de132` 每30min）→ 30个技术因子·多空评分·注入分析卡。
- **告警去重模块**：**已部署**（`alert_dedup.py`）→ MD5去重·已注入4个cron脚本。
- **IP-ban回退链**：**已完成**（`fallback_chain.py`）→ 三级回退(代理→直连→本地缓存)·预置加密/黄金/外汇回退源。
- **交易执行桥接**：**已上线**（`trade_exec_bridge.py`，cron `2bcc03c1f524`）→ 信号→trade_events.jsonl。
- Web情绪：DDGS/Brave/Exa/Tavily/Firecrawl 已具备；已升级4层降级链 Brave→Exa→Tavily→DDGS。
- Polymarket：**已接通**（polymarket_bridge.py → auto_card.py）→ Fed/衰退/CPI/加密ETF 预测概率自动写入卡片。
- 外部能力扫描：已完成 cryptoskills.dev + 公开市场审计 → 见 `references/external-capability-scan-2026-06-28.md`。
- X/Twitter：**x_search 工具已配置**（模型 `grok-4.20-non-reasoning`，90s超时，2次重试，xAI OAuth 已登录）。分析时**优先调 `x_search` 获取 X 实时情绪**，不可用时回退 `web_search` 并标注「web源·非X实时」。见 Step 6。
- Telegram：已配置，关键推送必须重试+落盘。
- **R1 修复新增**（2026-06-30）：`orphan_integration.py`（6孤儿引擎统一接口）+ `batch_review.py`（复盘率100%）+ `auto_review_cron.py`（cron复盘）+ `stock_quote.py`（股票报价→yfinance）+ `p0_refresh_all.py`（数据新鲜度恢复）
- **R2 桥接模块新增**（2026-06-30）：`jin10_gold_bridge.py`（金十黄金日历+快讯）+ `cot_bridge.py`（COT黄金持仓解析）+ `forex_rate.py`（24外汇品种利差+央行窗口）+ `options_chain.py`（BTC→Deribit/美股→yfinance期权链）—— 全部接入 auto_card 自动调用

当前缺口：
- ~~`fallback_providers: []` 为空；主模型无自动降级链。~~ → **已修复（2026-06-29）**：降级链已配置 deepseek→openrouter→xai-oauth，custom:api-direct.ccapi.us 已删除（未验证连通性）。
- ~~web 工具当前按配置单 provider 执行~~ → 降级脚本 `web_fallback_chain.py` 已存在但 cron no_agent 脚本不自动遍历。
- 链上专业数据缺 CryptoQuant/Glassnode/Nansen/Arkham 结构化源。
- **外部能力扫描已完成**（2026-06-28）：cryptoskills.dev / browse.sh / 全网免费API —— 详细对比见 `references/external-capability-scan-2026-06-28.md`。免费源已穷尽：SoSoValue(ETF)、Dune(链上)、COT(CFTC)、Deribit(期权)已全部接入。
- ~~CoinGlass 全所衍生品需付费 $29/mo，暂不接入。~~ → **Coinglass MCP 已移除（2026-06-29）**：无 API Key，401 未授权，从 MCP 配置删除。
- 实时鲸鱼追踪需付费（Glassnode/CryptoQuant/Santiment），暂不接入。
- **脚本路径分裂（2026-06-29 发现）**：21 个关键脚本（data_gatherer, multi_model_engine, model_checklist 等）只在 `hermes/scripts/`，不在 `scripts/`。`auto_card.py` 通过 sys.path 解决了 import，但 AI 按 SKILL.md 执行 `python scripts/xxx.py` 会失败。手动分析时注意路径前缀。
- **盘前 GO/NO-GO 闸门缺失（2026-06-29 社区对标 → 2026-06-29 晚已落地）**：分析卡输出后、下单前缺 7 问硬检查闸门。**已实现**：`scripts/go_nogo_gate.py`（v9.6），七门（数据新鲜/TV现场/R:R/事件/Protections/样本WFO/组合暴露），已接入 `auto_card.py` 渲染层，输出追加到完整卡尾部。详见 `tangxi-system-audit/references/community-best-practices-2026.md`。
- **交易执行质量评分缺失（2026-06-29 社区对标）**：入场后 A/B/C 执行评级缺失，复盘率仅 3.5%（12/342）。

### v9.4 已闭合缺口（2026-06-29 第二轮）

| 缺口 | 状态 | 实现 |
|------|:--:|------|
| x_sent虚挂 | ✅ 已闭合 | `x_sentiment_collector.py` + cron `d6247e06ac30` 每30min |
| 爆仓/清算数据 | ✅ 已闭合 | `liquidation_collector.py` (OI×价格联动) + cron `5db6dd683b1d` 每30min |
| DeFiLlama稳定币 | ✅ 已闭合 | `stablecoin_collector.py` + cron `5f7192fd9029` 每2h |
| 数据新鲜度告警 | ✅ 已闭合 | `data_freshness_watchdog.py` + cron `155082fc5e34` 每15min |
| DMI引擎接线 | ✅ 已闭合 | `pipeline_integration.py` 已import `dmi_decision.compute_dmi()` |
| QLib 30因子库 | ✅ 已闭合 | `qlib_factors.py` + cron `fd78e36de132` + 注入card「因子行」 |
| 告警去重 | ✅ 已闭合 | `alert_dedup.py` + 注入4脚本 |
| IP-ban回退链 | ✅ 已闭合 | `fallback_chain.py` (3级回退:代理→直连→缓存) |
| 五层架构执行层 | ✅ 已闭合 | `trade_exec_bridge.py` + cron `2bcc03c1f524` |
| Cron总数 | 13→19 | +6 no_agent cron 零token |

### v9.4 剩余缺口（2026-06-29）

**已有但未接入管线的引擎（10个孤岛，~4,800行）**：|
| trading_system.py | 980 | 交易执行系统 v9.5 | ✅ 已桥接(trade_exec_bridge) |
| risk_constitution.py | 739 | 风险宪法·Kelly·熔断 | ✅ 已接入(auto_card动态import) |
| five_model_matcher.py | 569 | 五模型入场匹配 | 未接 |
| scoring_engine.py | 511 | 14分机器评分引擎 v1 | ✅ 已接入(auto_card ⑧段) |
| vwap_ema_cvd_engine.py | 476 | VWAP/EMA/CVD综合引擎 | ✅ 已接入(auto_card Step 1后) |
| cvd_analyzer.py | 367 | CVD综合分析器 | ✅ 已接入(orphan_integration) |
| orderflow_absorption.py | 294 | 订单流吸收/分布检测 | ✅ 已接入(orphan_integration) |
| render_tv_card.py | 497 | TV卡渲染引擎 | 未接 |
| backtest_runner.py | 713 | 回测引擎(含过拟合检测) | ⚠️ CLI可用·未入cron |
| regime_backtest.py | 301 | 行情回测引擎 | 未接 |
| **dmi_decision.py** | **368** | **DMI决策引擎** | **✅ 已接线** |

对标源：VLDB 2024 学术论文（5类数据源框架）+ Quant 2.0 专业架构 + Freqtrade/SuperAlgos 社区标杆 + r/algotrading + awesome-blockchain-crypto-api（315+服务目录）+ awesome-crypto-mcp（100+ MCP服务器）+ DeFiLlama公开API实测。

**第二轮深度审计（2026-06-29）**：Vibe-Trading(14.7k★) 对标 + Pine v6升级评估 + 知乎五层架构对标 + 警报治理社区标准。详见 `references/community-audit-2026-06-29-round2.md`。

**声明虚挂（已全部闭合）**：
- ~~`x_sent` X情绪~~：✅ 已闭合 — `x_sentiment_collector.py` + cron `d6247e06ac30` 每30min
- `cg_pro` CoinGecko Pro：Orion 的 CG 交叉验证全部失败（CG Pro tickers 端点返回 400），非 Orion 场景可用但需确认端点兼容性。

**免费数据源尚未接入**：
- **爆仓/强平数据**：Binance `GET /fapi/v1/forceOrders` 需认证（已有Key）。清算集群是最强支撑/阻力位（社区共识），当前驾驶舱完全缺失。**期货强制平仓需认证，现货无公开端点。**
- **DeFiLlama 稳定币 API**：**已实测可用**（`stablecoins.llama.fi/stablecoins?includePrices=true`），385个稳定币实时供应量数据，USDT $184.85B / USDC $73.77B。**尚未接入驾驶舱或任何 cron。**
- **稳定币供应 Dune 替代**：原 Dune 查询 4159727 可能失效，DeFiLlama 可作免费替代。

**已有但未接入管线的能力（引擎孤岛 — 2026-06-29 深度审计发现）**：

**23,114行Python总代码，11个引擎。DMI已接线·执行层已桥接·QLib因子已注入。剩余9个孤岛~4,800行**：

| 隐藏引擎 | 行数 | 功能 | 状态 |
|------|:--:|------|:--:|
| trading_system.py | 980 | 交易执行系统 v9.5 | ✅ 已桥接(trade_exec_bridge) |
| risk_constitution.py | 739 | 风险宪法·Kelly·熔断 | 未接 |
| five_model_matcher.py | 569 | 五模型入场匹配 | 未接 |
| scoring_engine.py | 511 | 14分机器评分引擎 v1 | ✅ 已接入(auto_card ⑧段) |
| vwap_ema_cvd_engine.py | 476 | VWAP/EMA/CVD综合引擎 | ✅ 已接入(auto_card Step 1后) |
| cvd_analyzer.py | 367 | CVD综合分析器 | ✅ 已接入(orphan_integration) |
| orderflow_absorption.py | 294 | 订单流吸收/分布检测 | ✅ 已接入(orphan_integration) |
| render_tv_card.py | 497 | TV卡渲染引擎 | 未接 |
| backtest_runner.py | 713 | 回测引擎(含过拟合检测) | 未接 |
| regime_backtest.py | 301 | 行情回测引擎 | 未接 |
| **dmi_decision.py** | **368** | **DMI决策引擎** | **✅ 已接线** |

- **回测引擎**：`backtest_runner.py`（713行）含过拟合检测、真实手续费、时段过滤、权益曲线。`regime_backtest.py`（301行）含行情回测。两者均不接入分析流程，不为信号提供历史胜率背书。
- **复盘助手**：`trade_journal.py`（52行）存在但未与 cron 每日复盘联动。
- **4个空wrapper**：position_sizer/event_ban_live/session_strategy/triple_confirm 各仅2行 import，无实际逻辑。

**架构层面缺失**：
- **数据新鲜度自动告警**：无 cron 监控数据文件过期（上次发现 6 个文件过期 6-9 天零告警）。数据管道可靠性比模型更重要（Quant 2.0 共识）。
- **告警去重/限流**：15个 cron 按固定频率推送，无「条件不变则静默」的去重逻辑。若市场连续8小时平静，BTC看门狗发96条消息。若闪崩，3个cron同时触发刷屏。需实现状态机去重模式（btc_daemon已有雏形）。
- **跨资产相关性矩阵**：未计算 BTC-ETH-SOL-XAU-SPX 之间的滚动相关性，无法预警系统性风险传导。
- **交易执行管线（OMS）**：只有风控 skill，无下单/仓位/滑点/成交率追踪的自动化管线。`trading_system.py`（980行）存在但未接入 cron。

## 闲置能力盘点（回答"有没有用上全部能力"必读）

判断能力是否真接通：能力图是声称，**auto_card.py 实际 import 才是事实**。审计法、15项已接通能力、孤儿脚本整合进度见 `references/idle-capability-audit.md`。**6个孤儿脚本已于2026-06-30通过 `orphan_integration.py` 接入管线**，详见 `references/bridge-module-architecture.md`。R2桥接模块（金十/COT/外汇/期权）架构见同文件。第一优先级永远是激活已写好的能力，而非写新代码。

## auto_card 缓存消费铁律（2026-06-28 审计修复）

`auto_card.py` 读 `data/tv_dmi_cache.json` 时，过期/品种不匹配会把 `cache` 置 `None`。**所有 `cache.get()`/`"key" in cache` 必须在 `if cache is not None:` 块内**，否则过期缓存触发 `'NoneType' object has no attribute 'get'`，TV数据被整体跳过 → 卡片静默退化成纯 Binance API（用户多次纠正的失败模式）。修复：进入 not-None 块先给 `grade/treatment/...` 设默认值防 possibly-unbound；`_tv_pine` 注入和 `tv_grade` 派生全部内缩进块内。

**TV缓存保鲜缺口**：当前无 recurring cron 刷新 `tv_dmi_cache.json`（刷新任务是 once+disabled）。盯盘前必须确认缓存新鲜（<10分钟）。CDP 9222 断连时 `fetch_tv_data.cjs` 也不可用——手动分析须先 `tv_launch` 拉起 TradingView Desktop 再走 MCP 直连，不能依赖陈旧缓存。

## 热点扫描 / 市场概览（触发词：「看看热点的」「有什么流动好的」「扫一下市场」）

当用户要求快速扫描当前市场热点、流动性好、趋势/涨幅突出的品种时，用以下轻量级管线（非完整8步分析）：

### 数据采集

1. **CoinGecko Trending API**（最快、最准的趋势快照）：
   ```
   curl -s "https://api.coingecko.com/api/v3/search/trending"
   ```
   返回 Top 15 搜索热度币种 + Top 6 热门类别。注意：
   - 小市值 meme 币经常占据前列（如 The Black Bull/XMAQUINA），不一定有深度
   - 关注 `market_cap_rank` 字段过滤大盘币（rank ≤ 100 的才算有流动性）
   - 交叉参考 `score` 字段（越低越热）

2. **CoinGecko Market Data**（按成交量排序 = 流动性最好）：
   ```
   curl -s "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=volume_desc&per_page=30"
   ```
   返回按 24h 成交量降序排列的币种。这是判断流动性的最佳单一数据源。

3. **Binance Market Update**（Binance 官方市场总结）：
   ```
   web_search(query='"binance" "market update" date')
   或
   web_extract("https://www.binance.com/en/square/post/...")
   ```
   Binance 每日发布涨跌幅前几名，能反映交易所真实交易热度。

### 输出格式

用 Markdown 表格分三块：

| 区块 | 内容 |
|------|------|
| **大盘概况** | BTC/ETH 价格+24h%，总市值 |
| **流动性最好** | Top 10-15 by 24h成交量，含价格和涨跌幅 |
| **热门异动** | |24h%|>5% 且成交量>$10M 的品种 |

表格列：币种、价格、24h%、成交量。

### 注意事项

- 用户说「流动性好」= 按 24h 成交量排序，不是按市场热度
- 用户说「热点」= 按 CoinGecko Trending 或涨幅排序
- 山寨币（非 BTC/ETH/SOL）需要额外关注成交量是否真实（RSPCX 等异常大成交量通常是数据错误）
- 分析产出后用户可以挑选感兴趣的品种，再走完整的 8 步管线深入分析
- 免费 API（无需 Key）适用于 quick scan，正式分析仍需 TV MCP 全源

### 筛选后跟进（multi-coin TV scan）

用户从扫描结果中挑选几个感兴趣的品种后，进入**多品种快速 TV 扫描**阶段——它介于「市场概览」和「单币完整8步分析」之间：

1. **验证币安合约可用性**：用 `fapi/v1/exchangeInfo` 或 `fapi/v1/ticker/24hr` 检查目标币种是否在 Binance Futures 上市。若有 `get_price` 失败但 OI/多空比接口正常，是期货独占品种。

2. **批量采集 24h 统计**：`fapi/v1/ticker/24hr?symbols=[...]` 一次调用获取多个币种的最新价、24h涨跌幅、24h成交量。优先筛选成交量>$10M 的品种。

3. **逐一切 TV 扫盘**（每币种约 30-40s）：
   1. `chart_set_symbol("BINANCE:XXXUSDT.P")` → 等 5s
   2. `chart_get_state` 确认 symbol 正确
   3. `data_get_study_values` → SVP 的 VWAP/EMA/VAH/VAL/POC
   4. `data_get_pine_tables` → 行动格（13 行：位置/结论/方向/路径/风控/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位）
   5. `data_get_ohlcv` → 最新 K 线确认价格位置

4. **快速评估标准**（每个币种 3-5 行浓缩）：
   - EMA 排列方向（9>21>34>55=多头 ✅ 反=空头 ❌ 混乱=震荡）
   - 价格 vs VWAP（溢价=偏贵 折价=偏便宜，超±2σ=极端）
   - 行动格结论（等空/等多/已进场/禁做）
   - 成交量趋势（Volume Aggregated 的缩量/放量占比）

5. **对比表格 + 推荐排序**（Markdown 表，列：币种/价格/24h%/成交量/EMA/价vsVWAP/行动格/评价）

6. **关键注意事项**：
   - TV chart 是全局单例——每次切品种前先 `chart_get_state` 确认当前是啥，避免跨会话数据污染
   - 遍历多个币种后 SVP 指标可能返回 stale 旧品种数据 → 切回已知品种再切回刷新
   - 不要为每个币种做完整 8 步（太慢），只抓最关键的 3-4 个数据源
   - 用户说"全部拉一遍"时需要效率优先——不必每个都截图，只截最终推荐的

## SVP 行动格解读（快速参考）

读取 `data_get_pine_tables(study_filter="SVP+ICT+VWAP+CVD")` 后，参照 `references/svp-action-grid-states.md` 匹配结论等级（A=可执行 / B=等待有倾向 / C=冲突观望 / X=禁做）。**结论含⚠冲突 或 观望+进场=等触发+止损=— 三联确认 = C级 → 不推送。**

### 核对（check）行解读（2026-06-30 新增）

SVP v10 行动格新增「核对」行，例如 `HTF✓ EMA✓ CVD✓ 位置✓ 位移✗ 溢折✓ ADR✓ OI✓`。每个符号对应 DMI 引擎的一个检查项，全部 ✓ 才允许 A 级方向，有 ✗ 则限制到 B 级或更低：

| 检查项 | 含义 | 通过条件 |
|:---|:---|:---|
| HTF✓ | 高周期方向一致 | 4h/D 方向与当前周期一致 |
| EMA✓ | EMA 排列方向支持 | EMA9<21<34<55(空) 或 9>21>34>55(多) |
| CVD✓ | CVD 方向配合 | 卖压支持做空 或 买压支持做多 |
| 位置✓ | 价格在关键位附近 | 接近 VAH/VAL/POC 等主要价值区 |
| 位移✓ | 有 displacement 确认 | K线强势推进（≥1.8x 均量） |
| 溢折✓ | 溢价/折价合理 | 不过度偏离 VWAP |
| ADR✓ | ADR 未耗尽 | 日波动幅度未触及 ADR 边界 |
| OI✓ | OI 方向配合 | OI 变化支持当前方向判断 |
| 深折价✗ | 深度折价警告 | 价格远低于 VWAP（>2σ）→做空受限 |

**实用规则**：核对行 7/8 ✓ 以上 → B+ 可轻仓；8/8 ✓ → A 可执行；≤5/8 ✓ → 降级观望。核对行标记为 `—` 表示该周期 SVP 未渲染核对行（D/15m 常出现），此时以相邻更高周期核对行为参考。

### 多周期副指标交叉对比（2026-06-30 实战发现）

Volume Aggregated 副指标的信号、结论、持仓行会随周期变化，**必须每个周期独立读取**，不能用一个周期的副指标代表全部：

| 周期 | 信号 | 持仓 | 量能 | 操作 | Composite |
|:---:|:---|:---|:---|:---|:---:|
| 1D/4h | 🟡 偏空·2/4共振 | ▼多头平仓(去杠杆) | ▼缩量·86%⚠ | 别追空,等反弹 | −21 |
| 1h | 🟡 偏空·2/4共振 | ▼多头平仓(去杠杆) | ▼缩量·79%⚠ | 别追空,等反弹 | −21 |
| 15m | 🟡 偏空·3/4共振 | ⚡新空进场 | ▼缩量·88%⚠ | 缩量,等放量再做 | −31 |
| 5m | 🟢 偏空·4/4共振 | ⚡新空进场 | ▲放量·90%⚠ | A空=可做 | −41 |

**关键变化点**：
- 持仓行从「多头平仓(去杠杆)」变为「新空进场」→ 卖压从存量去杠杆切换到增量新空
- 量能从「缩量」变为「放量」→ 做空动能增强
- 信号强度从 2/4 升至 4/4 共振 → 微周期空头确认增强
- Composite 从 −21 恶化至 −41 → 越短周期空头越强烈
- **执行TF副指标否决权（2026-06-30 GASUSDT 实战）**：结构-TF(4h)副指标说「A多/可做」但执行-TF(15m)副指标说「降级/放弃」时，**执行-TF副指标结论覆盖结构-TF**。副指标信号随周期递减（4h🟢→15m🟡→5m🔴）时以执行-TF为否决票；信号递增（5m🟢→15m→4h🔴）时以结构-TF为方向参考但执行-TF决定具体操作。详见 `references/squeeze-aftermath-pattern.md` Phase 2。

### ⚠ TV MCP 工具调用方式（2026-06-29 发现·铁律）

TV MCP 工具**必须使用 `tool_call` 调用**，不能直接作为函数调用。`tool_search` 能找到它们，`tool_describe` 能描述它们，但直接调用会报 "Tool not found"。

```python
# ❌ 错误：直接调用 → Tool 'mcp_tradingview_chart_set_timeframe' does not exist
mcp_tradingview_chart_set_timeframe(timeframe="D")

# ✅ 正确：通过 tool_call 调用
tool_call(name="mcp_tradingview_chart_set_timeframe", arguments={"timeframe": "D"})
tool_call(name="mcp_tradingview_data_get_study_values", arguments={})
tool_call(name="mcp_tradingview_data_get_pine_tables", arguments={"study_filter": "SVP"})
tool_call(name="mcp_tradingview_data_get_ohlcv", arguments={"summary": True})
tool_call(name="mcp_tradingview_capture_screenshot", arguments={"region": "full"})
tool_call(name="mcp_tradingview_data_get_pine_labels", arguments={})
tool_call(name="mcp_tradingview_data_get_pine_lines", arguments={})
```

此规则适用于**所有 MCP 工具**（TV、Binance、Jin10、FinanceKit），无一例外。无论 MCP 工具名前缀 `mcp_tradingview_*`、`mcp_binance_*`、`mcp_jin10_*`、`mcp_financekit_*`，全部必须通过 `tool_search` 先搜索名字 → `tool_call` 调用，不能直接写函数名调用。

## 多周期读取已知陷阱

1. **SVP 主指标不在所有周期渲染（依赖指标版本+布局）**：SVP 指标在 4h 和 15m 上有完整 study_values（VWAP/EMA/POC/VAH/VAL），在 1h 上**可能**只输出副指标数据（SVP plot 不渲染），但也可能返回完整 SVP 数据 — 取决于用户 TV 布局加载的 SVP 指标版本。
   - **7.5s-12s 重试策略**：切到 1h 后等 8s，读 study_values，若 SVP plot 值缺失（VWAP/EMA 不在 study_values 内），不要放弃 — 先读 pine_tables（行动格始终独立渲染），再等 3s 重读 study_values。若第二次仍无 SVP 值，标注"继承4h背景，无SVP 1h独立数据"。
   - **但 `pine_labels` 和 `pine_lines` 始终可用**：即使 study_values 不含 SVP 数据，`data_get_pine_labels` 和 `data_get_pine_lines` 在 1h 上仍会返回会话级关键位（周日亚高/亚低、周六高/纽低、POC/VAH/VAL 等）。标签上的关键位对判断当前位置是否靠近重要区间很有价值。**不要因为 study_values 为空就跳过 labels/lines 读取** — 在所有周期上都读它们。
   - **1h 有 SVP 数据时的交叉验证**：若 1h 返回 VWAP/EMA/POC/VAH/VAL 且数量级匹配（非 stale），与 4h 数据对比：若两 TF 的 VWAP 方向一致则结构确认，若背离则标注结构冲突。例（2026-06-28 实盘）：1h study_values 包含 S VWAP `61,065` + EMA9-55 + POC/VAH/VAL，与 4h 的 VWAP `63,465`、VAL `59,404` 比较，确认全周期偏空结构。
   - **prices label 标注**：1h 和 4h 的 pine_labels 可能包含空文本标签（`text: ""`）但有关键价位。这些是 ICT 会话级标签（周六高/周日亚低等），来自 SVP 指标的独立 label 体系，不同于 study_values 的 VAH/VAL。必须同时收集两类：study_values 的 VAH/VAL/POC 用于统计定位，pine_labels 的会话标签用于结构判断。

2. **`chart_set_timeframe` 参数名与分钟周期写法**：TV MCP 此工具参数名为 `timeframe`（字符串），不是 `resolution`。传错报 `Invalid arguments for tool chart_set_timeframe`。
   - 分钟周期优先用纯数字字符串：15m 用 `"15"`，5m 用 `"5"`。实战发现 `"5m"` 可能被 TradingView/CDP 误解释成异常高周期，导致 OHLCV 只剩很少K线、标签出现跨年月数据；若5m返回 bar_count 异常小或时间戳跨度离谱，立即改用 `chart_set_timeframe({"timeframe":"5"})` 重读。
   - 4h/1h 可继续用 `"4h"` / `"1h"`；D 用 `"D"`。

3. **独立 OI 研究可能缺失（不仅山寨，BTC/ETH 也取决于布局）**：用户的 TV 布局可能不加载独立 Open Interest 研究，而是用 Volume Aggregated Spot & Futures 替代 OI 功能。实测（2026-06-28）BTC 布局为 SVP + Volume + Volume Aggregated（无独立 OI 窗格）。**不要在分析前假设 BTC/ETH 一定有 OI 研究**。处理：
   - Volume Aggregated Spot & Futures 内已含 OI 价仓四象限数据（`▲新多进场/⚡新空进场/▼多头平仓`），可作为 OI 信号替代。
   - 读取 `chart_get_state` 的 studies 列表检查 study name 是否含 "Open Interest"。若无独立 OI 研究，也可以读取 `pine_tables` 时检查 study_count——如果调用返回非 Volume 研究的 table 只有 2 个（主指标 + Volume Aggregated），同样可确认无独立 OI 研究。
   - 在分析卡中标注 OI 数据来源（"副指标 Volume Aggregated"）。

4. **⚡ Binance MCP `get_price` 可能对期货独占品种返回 Invalid symbol**：部分山寨币只在 Binance Futures 上市（无现货交易对），`get_price` 使用现货 API 端点，返回 HTTP 400 Invalid symbol。但同一 symbol 的 `get_open_interest_history`、`get_long_short_ratio`、`get_funding_rate_history` 等期货端点正常返回。处理：
   - 价格来源降级链：TV study_values VWAP/OHLCV close → Binance `get_klines` 取最新 K 线 close → CoinGecko 兜底。
   - 不因 `get_price` 失败就跳过整个 Binance 交叉验证——OI/多空比/费率等衍生品数据仍可走期货端点正常采集。
   - 分析卡中标注价格来源（如"价格来自 TV OHLCV，Binance 现货无此品种"）。

5. **中小市值山寨分析的特殊考量**：
   - TV 研究加载可能比 BTC/ETH 少（无独立 OI 窗格），但主指标 SVP+VWAP+EMA+CVD 和副指标 Volume Aggregated 始终可用。
   - 多空比对山寨币同样是可靠的反指信号（如 2.1x 多/空 = 极高偏多→警惕多头踩踏），因合约市场规模小，大户方向更具操纵性。
   - 恐惧贪婪指数 18-20 在极度恐惧时，山寨币的反弹弹性通常大于蓝筹，但下行滑点风险也更高。
   - 成交量缩量在非蓝筹品种上更常见，不代表与蓝筹相同的信号强度；需与同品种历史成交量对比判断。

5b. **⚡ 小市值山寨 SVP 渲染模式（2026-06-29 实战）**：
中小市值山寨（MC<$100M、CG rank>300）的 SVP 渲染模式与蓝筹显著不同。以下是在 INUSDT 上实测的 TF-by-TF 渲染表：

| 周期 | SVP study_values | SVP pine_labels/lines | 行动格 | 副指标 | 可用性 |
|:--:|:--:|:--:|:--:|:--:|:--:|
| D | ✅ OHLCV only | ❌ | ❌ | ❌ | **仅宏观背景** |
| 4h | ❌ | ✅ POC/VAH/VAL/ICT标签 | ❌ | ❌ | **标签可用·无VWAP/EMA** |
| 1h | ❌ | ❌ | ❌ | ❌ | **全无（继承4h）** |
| **15m** | **✅ VWAP/EMA/POC/VAH/VAL** | **✅ 完整** | **✅ 行动格** | **✅ Volume Aggregated** | **🎯 唯一执行层** |
| 5m | ❌ | ❌ | ❌ | ❌ | **噪音层** |

**关键发现**：15m 是中小市值山寨的**唯一承载层**——VWAP、EMA排列、行动格、副指标全在该周期。这与 BTC/ETH（4h 和 15m 均有完整 SVP）完全不同。

**但 GASUSDT（中市值，~$80M MC）的渲染表现优于 INUSDT（小市值）**，在多个周期上均有完整数据：

| 周期 | INUSDT（小市值） | GASUSDT（中市值） |
|:--:|:--|:--|
| D | ❌ SVP不渲染 | ✅ SVP完整(VWAP/EMA/POC/VAH) |
| 4h | ❌ study_values空，标签可用 | ✅ 完整SVP+行动格+副指标 |
| 1h | ❌ 全无 | ⚠ 无SVP但有副指标 |
| 15m | ✅ 完整 | ✅ 完整 |
| 5m | ❌ 噪音 | ✅ 完整SVP+行动格+副指标 |

**实用含义**：市值越大的山寨，SVP 覆盖层数越多。不要用一个山寨的渲染模板套全部。分析前先从 `chart_get_state` 确认 studies 实际返回情况，再决定哪些周期的数据可信。

**实用含义**：
- 不要因为 4h/1h 无 SVP 数据就认为指标失效 → 聚焦 15m，它承载了全部分析权重
- 4h 的 pine_labels 仍有价值——POC/VAH/VAL 标签提供中周期价值区参考，但无 EMA/VWAP 趋势数据
- 主周期截图仍用 15m（加密默认），按标准五层流程执行但标注「SVP 仅 15m 渲染」
- 若 15m 的 action grid 明确（如"ADR耗尽 慎追多"），综合采纳，不因高周期无数据而降级
- **"ADR耗尽 + CVD不配 + 慎追多"三重警告对山寨特别有效**——山寨 ADR 耗尽后追涨的回撤速度比蓝筹快 2-3 倍

5c. **⚡ 小市值山寨数据源退化链（2026-06-29 实战）**：
小市值山寨在多个数据源上会退化或失败，需提前预知降级路径：

| 数据源 | 蓝筹（BTC/ETH） | 小市值山寨 | 降级路径 |
|:--|:--|:--|:--|
| Binance `get_price` | ✅ 正常 | ❌ Invalid symbol（期货独占） | TV OHLCV close → CoinGecko |
| Binance `get_klines` | ✅ 正常 | ❌ Invalid symbol | TV study_values VWAP |
| Binance OI/LS/Funding | ✅ 正常 | ✅ 正常（期货端点） | 直接使用·不加价源 |
| FinanceKit correlation | ✅ 正常 | ❌ "Could not fetch data" | 跳过·标注不可用 |
| Depth walls | ✅ 有支撑/压力墙 | ❌ 无显著墙 | depth_wall返回空数组 → 正常 |
| QLib 因子 | ✅ BTC有 | ❌ 仅BTC | 以BTC方向作市场情绪参考 |
| SVP 全周期 | 4h+1h+15m 多周期 | 仅15m | 聚焦15m执行层 |
| 恐惧贪婪 | ✅ 全市场 | ✅ 全市场 | 不受影响 |
| Deribit期权 | ✅ BTC/ETH | ❌ 无 | 跳过 |

**黄金准则**：数据退化不等于不分析。每项失败都应有标注+降级路径，在分析卡中注明「数据源退化·降级路径：{替代源}」。不可因数据退化跳过整个步骤。

6. **⚡ TV 跨会话符号污染（2026-06-28 实战，2026-06-30 再次实战确认）**：TV MCP 的 chart 是**全局单例**——不同分析会话/步骤之间共享同一个 TV 图表页面。如果前一个分析切换了品种（如 BTCUSDT.P），后续分析没有显式 `chart_set_symbol` 就读取 study_values，会拿到旧品种的数据且**不报错**（数据数量级不同但格式正确）。

> **副指标颜色前缀歧义**：Volume Aggregated 子指标信号行的 🔴/🟡 前缀是**预警等级**而非方向指示。`🔴偏多` = 该方向不可靠的红色警告，不是看多信号。详见 `references/volume-aggregated-color-semantics.md`。该文件对 10 因子评分中的 Factor 3（MTF Alignment）和 Factor 5（Sub-indicator Verdict）的准确打分至关重要。
   - **检测方法**：每次读取 `study_values` 后，将 VWAP/EMA 值与 web 搜索确认的当前价格比较。若数量级不匹配（如 HYPE ~$62 变成 BTC ~$60,000），说明 symbol 已被其他会话切换。
   - **修复**：`chart_get_state` 确认当前 symbol → 若不对则 `chart_set_symbol` 重切 → 等 5s 后重读。
   - **预防**：每个分析会话开始时，第一步先 `chart_get_state` 记录当前 symbol（不要假设是上次设置的）。完成分析后不必要将 symbol 切回 BTC，下一个会话自己会检查。
   - **此问题与「切换品种后 indicators 返回 stale 旧品种数据」是不同的 bug**：stale 是 `chart_set_symbol` 后 indicators 未刷新；跨会话污染是没有 `chart_set_symbol` 直接读，读到的是另一个分析的品种数据。

7. **⚡ TV `data_get_study_values` 返回过期数据（2026-07-04 实战）**：图表会话闲置超时后（跨日线、长时间不操作），`study_values` 可能返回旧日期的 VWAP/POC/VAL/VAH，即使实际价格已大幅变动。**不信任单次 study_values 读取**——必须交叉对比 Binance 实时价格和 K 线。强制刷新：1D→4h→1h→5m→15m 全周期循环后重读。详见 `references/tv-data-staleness-and-refresh.md`。

## 新上线代币分析（近期上线币安 ≤30天）

当用户要求分析**近期上线币安的新币**时，在标准 8 步管线基础上补充：

### 基础信息验证

| 检查项 | 方法 | 重要性 |
|--------|------|--------|
| 币安上线日期 | 搜索 `"{coin}" "Binance" listing` | 高—新币波动特征不同 |
| 多交易所覆盖 | 搜索 `"{coin}" Upbit OR Bybit OR OKX` | 中—流动性广度 |
| 基本面/叙事 | 搜索 `"{coin} crypto what is"` | 中—了解驱动逻辑 |
| 代币解锁 | 搜索 `"{coin} tokenomics"` | 低—但影响抛压判断 |

### 新币分析特有原则

1. **价格发现期**：上线首周通常「爆拉→剧烈回调→区间整理」。不要把 VAH/VAL 当牢固支撑阻力，新币 SVP 关键位每天大幅漂移。
2. **高成交量为正常现象**：新币 100-300% 成交量/市值比正常，非出货信号。
3. **多空比反指意义更强**：合约深度浅，大户易操纵。2x+ 多空比既是反指也说明流动性池不足以支撑大规模清算。
4. **1h/4h VWAP 参考价值大于 15m**：新币日内 VWAP 易被单根大K线拉偏。价远低于 1h VWAP 不一定代表超卖——可能是上线初期爆拉拉高后 VWAP 未更新。
5. **X 情绪验证对叙事币尤其重要**：新币叙事驱动力强于技术面。
6. **计划需主动更新**：新币价格波动剧烈，第一版计划可能几小时内失效。价格超出原入场区 >3% 时自动调整入场/止损/目标。

### 分析卡特殊标注

添加一行「新币信息」：上线日期·交易所·叙事·注意事项。

## 条件入场监控 cron 模式

当用户要「到入场价先分析再告诉我」「失效也提醒」时使用。

### 适用场景
- 已有完整方案（入场/止损/目标），价格未到需等待
- 到入场区需先 TV MCP 分析条件是否满足
- 条件不满足时静默（不发消息）
- 跌破止损需发失效通知

### 实现步骤

1. **创建 agent cron**（非 no_agent — 需推理+TV MCP）：
   ```
   cronjob(action='create', name='XXX入场监控',
     skills=['crypto-multisource-analysis','binance-trading'],
     schedule='every 2m', deliver='origin', workdir='D:\\Hermes agent')
   ```

2. **Prompt 必含**：品种/入场区/止损/目标、状态文件路径、失效条件、目标条件、入场检查流程、初始状态。

3. **状态文件** `data/{coin}_monitor_state.json`：
   ```json
   {"triggered":false,"invalidated":false,"done":false,"entry_analyzed":false,"plan_version":1,"last_check_price":0,"last_check_time":"","last_check_note":"","reason":""}
   ```

4. **计划自动更新**（用户说「自动更新」时）：
   - 价格超出原定入场区 >入场区宽度 30% 时，自动产生新版计划
   - 标记 `plan_version: N+1`，理由写入 state
   - 推送给用户新计划摘要（新入场区/止损/目标）

5. **行为规则**：
   - 仅三种情况发消息：触发入场·失效·目标完成
   - 条件不满足 → 完全静默，只记 reason 到 state
   - TV MCP 连不上 → 标记跳过不消息
   - 不主动截 TV 图（频率高浪费 token）

### 陷阱
- cron `enabled_toolsets` 不要限制 MCP 工具（MCP 不属于 toolsets）→ 会丢失 TV/Binance MCP
- 用户可能手动更新计划 → `cronjob(action='update')` 更新 prompt + 重置 state

## v9.6 六市场流程与社区对照（2026-06-29）

当用户问"各个市场分析流程、用了什么能力、什么 skill、搜索了什么、怎么做、还能怎么优化"时，直接参考 `references/v96-six-market-flow-community-map.md`。该文件记录了本轮使用的 skill、TV/Web/X/Terminal 能力、六市场 full/quick 流程、以及 TradingView/Freqtrade/Nautilus/Bookmap/Reddit/X 对照后的 P0/P1/P2 优化方向。

### 新增架构（2026-06-29 晚·本轮落地）

| 新增项 | 说明 | 参考 |
|--------|------|------|
| TV实时数据注入 | tv_live.json + tv_dmi_cache.json 双缓存 → auto_card D周期不再"待刷新" | `references/tv-live-injection-architecture.md` |
| Orion LLM cron恢复 | 四层验证+LLM解读·9-23每30min·~$0.50/月 | `references/orion-llm-cron-verification.md` |
| GO/NO-GO七问闸门 | 数据新鲜/TV现场/R:R/事件/Protections/样本WFO/组合暴露 → 已接入auto_card渲染 | `scripts/go_nogo_gate.py` |
| 量价健康度行 | 多源交叉验证表新增 吸收·扫荡·位移 字段 | `scripts/render_v8.py` |
| XAU klines真实数据 | gold-api+金十24h高/低 → 推算VAH/VAL/POC | `hermes/scripts/auto_card.py` |
| predicted_grade | A/B/C/D预测评级自动写入每笔trade_plan | `hermes/scripts/auto_card.py` append_trade_plan |
| 双缓存架构 | tv_live.json(agent现场) > tv_dmi_cache.json(cron) | `references/tv-live-injection-architecture.md` |
| tv_data_bridge升级 | cron输出新增poc/vah/val/action_grid/fresh字段 | `scripts/tv_data_bridge.py` |

### 管线步骤（v9.5 精简·2026-06-29）

**核心变化**：14步→8-9步。cron已经每30分钟在跑的数据(dune/deribit/x/qlib/liq/stablecoin)分析时不再重跑脚本，改为直接读取最近cron输出文件。金十/Poly/FG合并到macro一步。

### Step 0 — 资产识别 + 智能路由（必须执行，不可跳过）

**铁律：分析前先跑 router，按返回的步骤列表逐一执行，缺一步不算完成。**

从 v9.6 开始，`auto_card()` 已内置此功能：启动时自动调用 `route_pipeline(symbol, "full")` 并打印路由摘要，出卡前自动输出 **管线完成度审计表**（✅/⚠️ 标注每步状态）。手动分析时仍需调用：

```python
from scripts.pipeline_router import route_pipeline, pipeline_summary, timeframe_info
steps = route_pipeline(symbol, mode="full")
tfinfo = timeframe_info(symbol)
print(f"{symbol} [{tfinfo['main']}] {len(steps)}步: {steps}")
# 逐步骤执行：tv → binance → cg_pro → macro → cron_read → cvd → depth → corr → card
```

Router 自动根据资产类别跳过不适用步骤：
加密 BTC/ETH/SOL：10步（tv→binance→cg_pro→macro→x_sent→cron_read→cvd→depth→corr→card）
黄金 XAU/USD：8步（tv→macro→x_sent→cron_read→cvd→corr→gold_macro→card）
外汇 EUR/USD等：7步（tv→macro→x_sent→cron_read→corr→forex_rate→card）
股票 AAPL/TSLA：8步（tv→macro→x_sent→cron_read→corr→fmp→options_chain→card）
期货 ES/CL：6步（tv→macro→x_sent→cron_read→corr→card）
- 期权：3步（tv→options_chain→card）

### Step 0b — 五层时间框架规则（铁律·每市场不同主周期）
```
加密24×7，流动性集中在亚/欧/美重叠时段:
  亚洲早盘 00-06 BJT → 低流动性·降级
  亚欧重叠 06-12 BJT → 正常
  欧美重叠 16-22 BJT → 高流动性·优先
  周末 周六-周日     → 低量·警惕假突破
```
时段判定写入分析卡「环境」段。低流动性+ADX<20→减仓50%或跳过。

### Step 0c — 五层时间框架规则（铁律·2026-06-29 全市场统一）

**所有市场统一使用 1D→4h→1h→15m→5m 五层全周期扫描，仅主周期（截图）不同。**

| 市场 | 品种 | 五层 | 主周期(截图) | 理由 |
|------|------|:--:|:--:|------|
| 🪙 加密 | BTC/ETH/SOL | 1D/4h/1h/15m/5m | **15m** | 24×7·15m平衡噪音与信号 |
| 🥇 贵金属 | XAU/XAG | 1D/4h/1h/15m/5m | **5m** | 快进快出·5m主执行 |
| 💱 外汇 | EURUSD/GBPJPY… | 1D/4h/1h/15m/5m | **15m** | 24×5·15m与加密节奏一致 |
| 📈 股票 | AAPL/TSLA/NVDA | 1D/4h/1h/15m/5m | **1h** | 有跳空·1h更可靠 |
| 📊 期货 | ES/NQ/CL | 1D/4h/1h/15m/5m | **15m** | 23h流动性·15m同步加密 |
| 📋 期权 | 跟底层 | 跟底层 | 跟底层 | 跟着标的走 |

**使用方法**：`timeframe_info(symbol)` 返回 `{layers, main, screenshot, rationale}`。

**SVP指标在非加密品种上的行为**：主指标SVP在黄金/外汇/股票上行动格不认（副指标罢工显示"非加密品种"），但VWAP/EMA/POC/VAH/VAL/labels/lines依然有效。非加密品种只读主指标，跳过副指标采集。

**XAU TV 现行口径（2026-07-11，覆盖旧限制）**：生产 `SVP+ICT+VWAP+CVD` 已可在 `OANDA:XAUUSD` 的 1D/4h/1h/15m/5m 五层输出 VWAP/EMA/CVD/MCP质量/POC/VAH/VAL 等 Data Window 字段；必须真实读取，不得再按“XAU只截图、Pine无数据”降级。HALDRO 在非加密上保持 `Valid Code=0`、`CVD Quality Code=4`，只能显示“不适用”，不得参与冲突或方向裁决。`xau_tv_sync.py` 用结构化 OHLCV JSON 的倒数第二根已闭柱，周期参数固定 `5/15/60/240`；禁止用全文正则抓末尾数字。刷新通用缓存用 `tv_live_dump.py --symbol OANDA:XAUUSD --verbose`；`tv_data_bridge` 必须先切图并用 `chart_get_state` 校验目标 symbol，禁止把当前XAU值强贴成BTC缓存。

### Step 1 — 加载技能
自动加载：`binance-trading` + `crypto-onchain-flow` + `market-regime-classifier`

### Step 2 — TV MCP 主分析
1. `tv_health_check` → 如不通则 `tv_launch(kill_existing=true)` → 等8s重试
2. 若 `tv_launch` 返回 ClosedResourceError 或「MCP server unreachable」→ **MCP server进程已崩溃**。不能连续重试——等~60s让Hermes auto-retry恢复MCP连接后，再调 `tv_launch(kill_existing=true)`。完整恢复流程见 `references/tv-mcp-crash-recovery-2026-06-30.md`。
3. （完整 CDP 恢复流程见 `tangxi-system-audit` → `references/tv-mcp-cdp-recovery.md`）
2. `chart_get_state` → 确认品种（如 `BINANCE:BTCUSDT.P`）和已加载指标
3. **全周期强制刷新（2026-06-29 用户纠正·五层）**：必须依次读取 1D→4h→1h→15m→5m，不可跳过任一周期。加密主执行=15m（截图15m），贵金属主执行=5m（截图5m），其他市场(外汇/股票/期货)看流动性选主周期截图。
   - 先切D：读OHLCV summary（日线宏观结构背景），等15-30s
   - 再切4h：读 study_values + pine_tables + labels + lines，等8-12s
   - 再切1h：同上流程，等8s
   - 再切15m：同上流程，等15-30s
   - 最后切5m：同上流程，等15-30s
   - 切回主执行周期 → **先 `ui_fullscreen` 确保窗口最大化** → 再 `capture_screenshot(region="full")`

#### ⚡ data_get_pine_boxes — 读取 FVG 框（2026-06-30 实战发现）

TV MCP 有 `mcp_tradingview_data_get_pine_boxes` 工具，直接读取 Pine Script `box.new()` 画的FVG缺口框。

```python
tool_call(name="mcp_tradingview_data_get_pine_boxes",
  arguments={"study_filter": "SVP"})
# 返回 {zones: [{high, low}, ...]} 每个zone是FVG框的上下边界
```

**铁律：不要自己从OHLCV算FVG。** 定版主指标（`outputs/pine_20260905/SVP_audit_fixed17_20260910.pine`，3557 行，sha256[:24]=68a34fc3）已内置完整FVG引擎。2026-06-30实测证明手动算的FVG与指标实际画的框位置/区间完全不同。FVG相关参数见输入区L110-L124：FVG_HTF_ALIGN（只留顺HTF方向）、FVG_REQUIRE_DISP（需位移确认）、FVG_SHOW_CE（画50%中点入场线）、SHOW_HTF_FVG（高周期FVG确认）。

#### ⚡ 双指标 pine_tables 读取铁律（2026-06-30 实战纠正）

加密分析时只调一次 `data_get_pine_tables` 不够——**主指标和副指标各有独立的行动格表格**，必须分别读：

```python
# 分别读取两个指标的行动格
tool_call(name="mcp_tradingview_data_get_pine_tables",
  arguments={"study_filter": "SVP+ICT+VWAP+CVD"})
  # → 主指标 13 行：位置/结论/方向/路径/风控/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位

tool_call(name="mcp_tradingview_data_get_pine_tables",
  arguments={"study_filter": "Volume Aggregated"})
  # → 副指标：信号(含颜色前缀)/结论/高周/持仓/OI/CVD/量能/占比/爆仓/操作
  #   颜色前缀解读 → references/volume-aggregated-color-semantics.md
```

**仅读主指标、跳过副指标表格的后果**（2026-06-30 实测）：
- 副指标 Composite 分数跨TF变化（4h=-21 → 15m/5m=+21）在分析卡中缺失
- 副指标操作行（降级/放弃 / 不追,等回调对齐）丢失
- 多空拥挤评估只看到数值看不到文本结论

**执行纪律**：每个周期的 pine_tables 读取必须包含两调用（主 filter=SVP，副 filter=Volume Aggregated）。

Step 3 — Binance MCP 交叉验证（并行执行）

**⚠ 所有 Binance MCP 工具必须通过 tool_call 调用**（同 TV MCP 规则，见上文「MCP 工具调用方式」）。
```
tool_call(name="mcp_binance_get_price", arguments={"symbol":"BTCUSDT"})  → 价格核对
tool_call(name="mcp_binance_get_klines", arguments={"symbol":"BTCUSDT", "interval":"15m", "limit":10})  → K线数据核对
tool_call(name="mcp_binance_get_open_interest_history", arguments={"symbol":"BTCUSDT", "limit":5})  → OI趋势（增/减）
tool_call(name="mcp_binance_get_long_short_ratio", arguments={"symbol":"BTCUSDT"})  → 大户多空比 ⚠反指信号
（全局多空比也可通过 `tool_search` 搜索后调用）
tool_call(name="mcp_binance_get_funding_rate_history", arguments={"symbol":"BTCUSDT", "limit":3})  → 资金费率趋势
tool_call(name="mcp_binance_get_taker_volume", arguments={"symbol":"BTCUSDT", "limit":5})  → Taker买卖比
```

### Step 4 — CoinGecko / FinanceKit 补充

**CoinGecko Pro Key 已全面激活**（`CG-tkuaqHxNbpTQ92HgpvEc4QXY`，2026-06-28 已灌注 4 个脚本）。Pro Key 解锁 500req/min + 以下新增端点：

```python
# 主路径 — FinanceKit MCP：
mcp_financekit_crypto_price(coin="bitcoin")
  → 24h/7d变动、市值、ATH跌幅
mcp_financekit_crypto_top_coins(n=10)
  → Top10排名 + BTC山寨轮动检测
mcp_financekit_crypto_trending()
  → 热搜币种
mcp_financekit_market_overview()
  → SPX/VIX/NASDAQ/DOW + Risk-on/off分类（BTC相关性参考）

# 新增 Pro 端点 — multi_source_collector：
cg_categories()        → 板块/分类24h涨幅排名（资金轮动检测）
cg_coin_detail("bitcoin") → 流动性评分/社区/开发者/Coingecko评分
cg_exchange_volumes("bitcoin") → BTC交易所成交量明细（真假量检测·信任评分）
```

#### ⚠ CG Pro curl 返回 None 空字段（2026-07-08 实战）

`curl -s "https://pro-api.coingecko.com/api/v3/coins/bitcoin?x_cg_pro_api_key=CG-...&..."` 可能返回 **HTTP 200 但 `market_data` 全为 `None`**（price/24h%/mcap 解析出来全是 None），而非网络阻断。此时**不要**误判为「已采集」或直接标⚠️跳过——先走本 step 的 **FinanceKit MCP 主路径**补数：

```python
tool_call(name="mcp_financekit_crypto_price", arguments={"coin": "bitcoin"})
  # → 24h/7d变动、市值、ATH跌幅（CG Pro 数据经 FinanceKit 代理更稳）
tool_call(name="mcp_financekit_crypto_top_coins", arguments={})
  # → Top10 + 山寨轮动检测
tool_call(name="mcp_financekit_crypto_trending", arguments={})
  # → 热搜币种
```

**正确降级顺序**：① FinanceKit MCP `crypto_price/top_coins/trending` → ② 若 MCP 也空，再试 `curl pro-api` 兜底 → ③ 两者皆空才标 `⚠️ CG Pro: 端点返回空·跳过`。**curl 仅作最后兜底，不是首选**。手动分析时若已用 curl 拿到 None，务必补一次 FinanceKit MCP 调用再下结论，避免 CG Pro 维度整段缺失。

### Step 5 — 金十 MCP（重大事件检查）
```
mcp_jin10_list_calendar()  → 本周财经日历（利率决议/CPI/NFP）
mcp_jin10_search_flash(keywords=["BTC","Bitcoin","加密"])
  → 近期快讯
```

### Step 5 附注 — 已并入 cron_read 的数据源汇总（v9.6 压缩）

以下数据源已由 17 个 cron 每 30 分钟自动采集并落盘，**手动分析时不重跑脚本**，直接读 `data/` 下最新文件。各源状态与注意事项：

| 数据源 | 状态 | cron 输出路径 | 频率 | 注意事项 |
|--------|------|---------------|------|----------|
| Polymarket 预测市场 | ✅ 已接入 | 并入 macro 步骤 | 实时 | Gamma API 免费公开，`polymarket_bridge.py` 已接入 auto_card |
| BTC ETF Flow | ❌ 已移除 | — | — | SoSoValue 被 Cloudflare 封禁，2026-06-29 删 cron；由 Dune CEX净流 + DeFiLlama 稳定币双源替代 |
| Dune 链上数据 | ✅ 已接入 | `data/dune_cache.json` | 2h | 免费 40req/min；数据有缓存延迟，非实时 tick 级；CEX 净流出=积累 / 净流入=抛压 |
| CFTC COT 持仓 | ✅ 已接入 | `data/cot_data.json` | 每周五 | 3 天延迟，中长周期判断用，不用于日内；杠杆基金净多=投机偏多 |
| Deribit 期权 OI | ✅ 已接入 | `data/deribit_options.json` | 15min | 公开 API 免费；C/P比>1.5 偏多 / <0.7 偏空；MaxPain 是理论磁吸位非硬支撑 |
| 跨资产相关性 corr | ✅ 已接入 | 实时调用 FinanceKit | 实时 | `correlation_matrix.symbols` 必须传逗号分隔字符串（非 list）；返回 `Data unavailable` 时标注「以F&G+金十+价格结构替代」，禁止编造相关系数 |

**cron 输出过期（>30分钟）时**：跳过该源，在卡中标注「cron输出过期·跳过」。不重跑脚本（浪费API额度）。

### Step 6 — X/Twitter 实时情绪验证（x_search优先）

**主路径 — x_search 实时（2026-06-28 已配置可用）：**
```
x_search("$BTC crypto sentiment today bullish bearish")
  → 模型: grok-4.20-non-reasoning，90s超时，2次重试
  → 提取方向(bullish/bearish/neutral)、强度、大V观点
  → 写入分析卡交叉验证区：来源 | 情绪 | 解读
```

**降级路径 — web_search（x_search 不可用时）：**
```
web_search(query='"$BTC" OR "#BTC" sentiment crypto 2026')
  → 提取X上的大V观点、市场情绪方向
  → 标注「web源·非X实时」
```

**铁律**：X 情绪不覆盖结构方向，只作验证和挑战。若 x_search 返回情绪与 TV 结构矛盾，标注⚠并等待确认。

**输出格式**：X 情绪分析（含 LLM cron 推送）必须使用 `xau-analysis-format` §⑫ 的 3 表格式（行情全景·多源交叉验证·关键位预案），禁止自由发挥格式。

#### ⚠ x_search 可用性检查协议（2026-06-30 用户纠正·铁律级）

当 x_search 第一步调用失败时，**不要直接说「不可用」降级 web_search**。用户有 Grok 就一定不要放弃太快。按以下顺序逐级排查，完成后把当前层级写到分析卡备注里：

| # | 层级 | 检查方法 | 备注 |
|:-:|:---|:---|:---|
| 1 | tool_search注册 | tool_search 搜 x_search — 看返回的 tools 列表 | 若搜到但调不了→检查 toolsets 限制 |
| 2 | config存在性 | grep x_search: config.yaml 确认已配置 | 不存在→用户没配·回退 web_search |
| 3 | platform_toolsets | 查 config.yaml 中 platform_toolsets.{当前平台} 是否含 x_search | **常见根因**：Telegram 平台可能未挂载 |
| 4 | delegate_task代理 | 若当前平台没挂载但配置存在 → delegate_task(toolsets=[x_search,web]) 派到有 x_search 的平台 | delegate 也失败→第5层 |
| 5 | web_search降级 | web_search 替代，标注「web源·非X实时」并附排查摘要 | 永远不静默降级 |

#### ⚠ 工具集变更需要重启会话\n\nHermes 的工具集在会话启动时加载。修改 `config.yaml` 的 `platform_toolsets` 后，当前会话**不会自动获得新工具**。必须：\n- Telegram/Discord 等网关渠道：发 `/reset` 启动新会话\n- CLI 渠道：退出后重新运行 `hermes`\n- 不需要重启 Hermes gateway 本身——gateway 会为新会话加载新配置\n\n**排查输出示例**：\n```\nx_sent ⚠ 三层检查：①tool_search搜不到→②config有x_search→③platform_toolsets.telegram无x_search\n→ 修复：config添加x_search到telegram后发 /reset\n→ 修复后验证：tool_search('x_search') 能搜到\n\n注意：hermes config set 写数组类型会变成YAML字符串字面量（'[''item1'', ''item2'']'），\n必须用 Python+Pyyaml 或直接编辑 config.yaml。详见 references/hermes-config-yaml-array-pitfall.md\n```

### Step 7 — 恐惧贪婪情绪
```
web_extract(urls=["https://api.alternative.me/fng/"])
  → 恐慌贪婪指数（0-100）→ 市场情绪判断
```

### Step 8 — 输出分析卡
格式：MEDIA截图首行 → 驾驶舱五层汇总表 → 多周期定位（1D/4h/1h/15m/5m） → 关键位矩阵 → 多源交叉验证 → 矛盾点 → 预案
完整模板见 `references/cockpit-card-template-v2.md`（2026-06-29 实战验证·8区块·表格驱动）。
所有数据源必须在卡中标明来源，不遗漏。

### Cron 脚本输出格式（v9.4 铁律）

## Cron 脚本输出格式（v9.4 铁律 · 2026-07-01 更新）

**所有 no_agent cron 脚本的输出必须使用 Markdown 表格**，禁止单行文本作为主格式。

LLM cron（如 X 情绪分析、Orion 分析）必须使用 `xau-analysis-format` §⑫ 的 3 表格式。详见详见 `xau-analysis-format` skill。

no_agent 脚本输出格式详见 `references/output-format.md`。

### Cron 推送静默开关模式（2026-08-31 棠溪偏好 · 铁律级）

棠溪会**针对特定 cron 推送主动表达"不要发了"**。COT 报告、XAU TV 现场卡、行情守望重启告警等都曾被要求静默。每次都改 `deliver: origin/all → local` 不够——本地落盘仍跑，只是"我不再想看到这张 TG 卡"。

**模式要点**：

| 关键 | 落地 |
|---|---|
| 开关载体 | `data/<script_name>_no_push.json` 标志文件，**不污染脚本逻辑不污染 cron 配置** |
| 优先级 | 环境变量 `<SCRIPT>_NO_PUSH=1` > 标志文件存在 > 正常推送 |
| 触发分支 | 脚本读 `if NO_PUSH_FLAG.exists() or os.environ.get("..._NO_PUSH")=="1": 静默 + print "⏸ 推送已关闭" else: 推 TG` |
| 恢复方式 | 删 `data/<script>_no_push.json` 单文件即恢复，无需改 cron/prompt/code |
| 行为 | cron 仍跑、落盘仍写、缓存仍刷；**仅屏蔽最终 `push_tg_rich` 调用** |
| 适用 | 用户对某张 TG 卡反复表达"不要发了"时新建；新加 collector 脚本预留 `NO_PUSH_FLAG` 探测 |

**为什么不用 cron 改 `deliver: local`？** 因为 `deliver: local` 是**全部静默**（脚本不跑或跑完不进 TG），而棠溪要的是"数据继续采、缓存继续刷、只不发那张卡"。标志文件能精确切断"采集→推送"这一条链，其他都保留。

**为什么不用 cron `update` 注入环境变量？** `cronjob update` 在 `no_agent=true` 任务上**无法设置环境变量**（沙箱白名单限制），必须改用代码/文件层开关。详见 `references/cron-update-toolset-pitfall.md`。

**已应用**：XAU TV 五层现场（`data/xau_tv_no_push.json` 关闭 846 频道推送）；COT 报告（`cot_collector.py` 自身本就 `deliver: local`，无需开关）；行情守望重启（`monitor/market_watchdog.py` 已 `paused`）。

### X情绪LLM分析 cron 特殊格式（v2.0 · 2026-07-03）

X情绪LLM分析 cron（job_id: c6ad11110a80）使用 **3 表全驱动格式**，与 `xau-analysis-format` §⑫ 对齐。详见 `references/x-sentiment-cron-output-format.md`。

3 张表覆盖：行情全景 → 多源交叉验证 → 关键位预案。
关键差异：x_sent 需要同时展示 BTC 短期空头与中长期看多的对立共识，不可合并；必须使用 x_search + web_search 多源交叉填写第2张表。

- 单指标报告：指标 | 数值 | 解读 三列表
- 多品种报告：品种 | 数据 | 信号 三列表
- 因子报告：类别 | 因子 | 方向 三列表
- 方向箭头：↑看多 ↓看空 →中性
- Telegram 真表格必须走 Bot API 10.1 RichMarkdown/sendRichMessage；表格前不要紧贴 standalone `表1 · xxx` 标题行

已应用：x_sentiment / liquidation / qlib_factors / stablecoin / orion

## Cron Push Scoring Rubric
For cron job push decisions, use the standardized 10-factor scoring rubric in `references/cron-push-scoring-rubric.md`. Score ≥ 7 + direction clear (not X/conflict) → push to topic 386 with screenshot. Score < 7 → output a **brief analysis summary showing the work**, then conclude — never be literally silent. The user needs to see key findings to debug decisions. Format: 3-5 concise sentences covering current price, SVP grade/action grid, scoring breakdown, and verdict. Example after score < 7: "BTC 60,103 · 4h bearish VWAP 63,462 · 15m flat at VWAP. SVP: 等空反抽(C). OI +0.16%, LS 2.12x long (crowded). Multi-factor score 5.4/10. Direction not actionable — no push."

**实战参考**：`references/push-decision-workflow-btc.md`（2026-06-28 落地）包含完整的 BTC 数据采集序列、10 因子评分表（含评分逻辑和阈值）、主副指标冲突判定（同TF打架/跨TF矛盾/三联确认C级），以及现场数据快照 + 评分结果 + 决策推理。

**多源交叉验证模板**：`references/multi-source-cross-verify-template.md`（2026-06-30 实战定型）包含 7 源验证清单、衍生品一致性判据矩阵、Taker主动买卖模式表、多周期EMA方向裁决表、「矛盾点」段写作规则。适用于用户要求「再核实一下，多方面核实」的场景。

**⚠ 截图铁律**：每轮输出（包含"现在呢"快速更新）必须带新截图。用户明确要求"要有截图，都要有截图"。价格移动≥0.3%或行动格/DMI等级变化时必须截图。截图放MEDIA首行。

## 验证清单
- [ ] **Router已执行：所有路由步骤逐一跑完（非跳步）**
- [ ] TV pine_tables含主指标+副指标双表行动格（主结论/副信号+操作）
- [ ] 副指标(Volume)表已读（加密必读）
- [ ] Binance价格与TV价差<0.3%
- [ ] OI/多空比/费率 三件套已写入分析卡
- [ ] Taker买卖比已取（对比CVD方向一致性）
- [ ] CoinGecko Pro：板块轮动(cg_categories) + 流动性评分(cg_coin_detail) + 交易所量验证(cg_exchange_volumes)
- [ ] 宏观风险：SPX/VIX/DXY 已写入
- [ ] Polymarket 事件概率已取（Gamma API，跳过时标注）
- [ ] ETF Flow 已取（SoSoValue，日净流+信号）
- [ ] Dune 链上数据已取（BTC流/CEX净流）
- [ ] COT 持仓已取（投机方向，非加密品种）
- [ ] Deribit 期权 OI 已取（C/P比+MaxPain，加密期权）
- [ ] 金十日历已查（重大事件标注）
- [ ] X情绪已通过 x_search 采集（优先），不可用时降级 web_search 并标注来源
- [ ] 恐惧贪婪已取
- [ ] QLib 因子信号已取（SIGNAL_SCORE·SIGNAL_BIAS）
- [ ] DMI ADX 已注入
- [ ] **模式判断正确**：含「分析」=完整模式，含「现在呢/更新/看一下」=快速模式，不因刚出过卡而降级
- [ ] 截图full窗口（含价格轴+CVD）
- [ ] MEDIA截图已附在消息首行
- [ ] 所有时间戳为BJT（UTC+8）
- [ ] 跟踪更新时已有新截图（不重发旧截图）

## ⚠ Cron脚本代理回退模式（2026-06-29 实战验证）

cron环境与直接终端环境的代理配置可能不同，导致HTTP请求在cron中SSL握手超时或连接失败。**所有面向no_agent cron的Python脚本必须使用双策略回退**（系统代理→直连）：

```python
def _fetch(url, timeout=10):
    """代理回退HTTP GET — cron与直接环境通用"""
    for proxy_handler in [None, {}]:  # proxy → direct
        try:
            if proxy_handler:
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler(proxy_handler))
            else:
                opener = urllib.request.build_opener()
            req = urllib.request.Request(url, headers={"User-Agent": "H/1"})
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception:
            continue
    return None
```

已应用于：`orion_screener_radar.py`(fetch_orion)、`liquidation_collector.py`(fetch_force_orders)、`stablecoin_collector.py`(_fetch)。创建新cron脚本时重用此模式。

## ⚡ 股票期货产品分析（MUUSDT 模式 · 2026-06-29 实战）

Binance Futures 上架的股票期货（如 MUUSDT=Micron Technology、DELLUSDT 等）与加密合约的关键差异：

| 数据源 | 加密 (BTC/ETH/HYPE) | 股票期货 (MUUSDT) | 处理 |
|:--|:--|:--|:--|
| Binance `get_price` | ✅ 正常 | ❌ Invalid symbol | TV OHLCV close 或 `fapi/v1/ticker/price` 直取 |
| Binance OI/LS/Funding | ✅ 正常 | ✅ 正常 | 同加密端点可用 |
| Volume Aggregated | ✅ 正常 | 显示0%/0% | 跳过副指标，只读主指标 |
| SVP 行动格 | ✅ 完整 | ✅ 完整 | VWAP/EMA/VAH/VAL/POC 正常 |
| 副指标有效 | ✅ 是 | ❌ 不适用 | 不读副指标结论 |
| 恐惧贪婪 | ✅ 全市场 | ✅ 但参考意义↓ | 股票期货跟大盘更紧 |
| 美股盘后流动性 | — | ⚠ 大幅下降 | 盘后价差大，波动易放大 |
| OI/Funding 解读 | 可用 | 可用但规模较小 | 衍生品深度不如加密 |

**实操规则**：
- `get_price` 失败不卡住——走 `fapi/v1/ticker/price?symbol=MUUSDT` 直取或 TV OHLCV close
- OI/多空比/费率仍可正常读取并写入分析卡
- 副指标 Volume Aggregated 显示 0%/0% 是正常行为——不是数据错误，跳过不读
- SVP 主指标行动格正常，依赖它判断方向
- 标注「股票期货·非加密·副指标不可用」到分析卡顶行
- 注意美股交易时段（BJT 21:30-04:00）和盘后流动性差异

## ✅ Telegram RichMarkdown 真表格（2026-07-03 定版）

Telegram 普通 `sendMessage`/`parse_mode=MarkdownV2` 不支持管道表真渲染，但 Bot API 10.1 `sendRichMessage` + `rich_message.markdown` 可以把标准 Markdown 管道表解析为 `RichBlockTable`。正式推送要求：
- 走 `sendRichMessage`，不走普通 `sendMessage`。
- 表格前不要紧贴 standalone `表1 · xxx` 标题行。
- 回执检查 `rich_message.blocks[type=table]`。
- 不用图片表格、代码块伪表、普通管道符文字冒充。

每次用户要求"查监控/查任务/cron有问题"时，执行 cron 健康审计：
1. `cronjob(action='list')` 拿全量
2. 逐项判：error/timeout/silent/disabled/deliver缺失
3. 检查输出文件密度和质量
4. 对照采集器清单确认无缺失 cron（见 `references/cron-architecture-v9.md`）
5. LLM cron 每 ≤2min → 建议转 no_agent 脚本省 token
6. `deliver: origin` 的 job 可能静默丢包，验证用户是否实际收到
7. 守护进程存活检查：`cat data/monitor_heartbeat.json` + `cat data/.btc_daemon_heartbeat.json` — 两者都必须 status=running 且时间 <5分钟
8. 完整架构见 `references/cron-architecture-v9.md`
9. 资源消耗审计见 `references/resource-consumption-audit.md`

### 守护进程 vs Cron（v9.0 架构）

**守护进程**（必须存活，cron 看门狗守护）：
- `行情守望.py` — 实时多品种推送监控 → heartbeat: `data/monitor_heartbeat.json`
- `btc_daemon.py` — BTC 零 token 多因子评分 (≥8推TG:386) → heartbeat: `data/.btc_daemon_heartbeat.json`

**看门狗 cron**：
- `BTC守护看门狗` — 每5min检查 btc_daemon heartbeat，stale>120s 自动重启

**关键教训（2026-06-29）**：监控心跳停在 2026-06-28 15:06 达 14 小时未被发现。LLM cron BTC高频分析虽在跑但每月消耗 $33 token。真正的零 token 守护进程 `btc_daemon.py` 早已存在但停止运行。审计时必须先查守护进程存活，再查 cron。

### 多市场时间框架速查
完整速查表见 `references/multi-market-timeframe-quick-ref.md`。`pipeline_router.timeframe_info(symbol)` 一键获取。

## cron_read 数据源现状
详见 `references/cron-read-source-inventory.md`。x_sent 已双落盘(data/x_sentiment.json)·liquidation/qlib/stablecoin 仍仅cron stdout无本地落盘，读取前检查文件是否存在。

## 智能路由

分析多资产品种前，用 `scripts/pipeline_router.py` 确定适用步骤：  
驾驶舱角色速查（分层裁决+市场路由）见 `references/cockpit-role-breakdown.md`。
```python
from pipeline_router import route_pipeline, pipeline_summary
steps = route_pipeline("XAUUSD", mode="full")  # 返回8步（跳过加密专属）
steps = route_pipeline("BTCUSDT", mode="quick") # 返回4步核心+卡
```
加密专属（Binance/CG Pro/Dune/Deribit/FG/CVD/depth）自动跳过非加密资产。
