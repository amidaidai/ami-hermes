---
name: tradingview-execution-card
description: TradingView 交易执行卡分析 — 默认低周期执行卡，高周期限时继承；仅在用户要求或关键位失效时刷新全周期。加密15m/黄金5m主执行。
---

> **同族导航** — 卡片组 4 个技能各司其职，别加载错 （同族入口：`tradingview-indicator-analysis`）
> · **本技能 `tradingview-execution-card`** = 低周期执行卡（加密 15m / 黄金 5m，高周期限时继承）
> · 同族其余：`tradingview-indicator-analysis`（入口 · 分析卡主流程（多品种多周期、叙事驱动、5 段模板））、`xau-analysis-format`（卡片格式细则（裁决措辞/周期标签/移动端布局））、`trading-card-generation`（卡片生成脚本（compact + full 双输出））
> · 组内改动请同步其余成员的触发词，避免同名族抢触发。


# TradingView 交易执行卡分析

对单一品种输出简洁交易执行卡。默认不每次全周期重扫：高周期继承最近上下文，重点刷新低周期执行/触发。适用于用户发送"分析 BTC"、"卡呀 BTC"等指令。

## 触发条件
- 用户说"分析 XXX"、"看看 XXX"、"扫描 XXX"、"卡呀 XXX"、"给我卡 XXX"
- 品种名支持：BTC/BTCUSDT, ETH/ETHUSDT, SOL, XAUUSD/GOLD/黄金, 或其他交易品种
- 默认模式是**低周期执行卡**：除非用户明确说"全面扫/全周期/刷新高周期"，否则不要每次跑完整 4h+1h+执行+触发流程
- **特例（2026-07-08确立）**：用户只说"分析BTC"（无"卡呀/看看"快捷词、无特指低周期）时，走**全周期完整卡**——五周期+D全扫 + 多源。完整模板与15步审计见 `references/btc-full-card-template.md`。

## 品种规则
- **加密**：15m 主执行、5m 触发、1h+4h+D 过滤（高周期缓存，低周期全量）
- **黄金**：5m 主执行、15m+1h+4h+D 过滤
- **其他品种**：默认 15m 主执行，4h+D 过滤

## 周期继承表（5m/15m/1h/4h/D 五周期 · 高周继承低周实时）
统一读取顺序，避免每次全扫。加密主执行=15m，黄金主执行=5m。

| 周期 | 角色 | 刷新策略 |
|---|---|---|
| D | 大背景/磁吸边界 | 继承到下一根 D 收盘；仅价格突破 D 关键位才刷 |
| 4h | 趋势过滤/HTF确认 | 继承到下一根 4h 收盘 |
| 1h | 中继背景/关键位 | 继承到下一根 1h 收盘；空表(study_count:0)标"继承4h" |
| 15m | 加密主执行 / 黄金过滤 | 加密每次全刷；黄金继承 |
| 5m | 黄金主执行 / 加密触发 | 主执行周期每次全刷 |

**继承失效条件（任一即提前刷新对应高周）**：价格突破/跌破继承的高周关键位、低周信号与继承高周明显冲突、距上次高周判断超过该周期一根 K。

## TradingView MCP 权限边界（免费账号硬约束）

用户使用 TradingView 免费账号。TV MCP 在本技能中只承担**当前盘面结构读取**，不得把高级付费能力写进完成度、驾驶舱能力或分析前提：

- **允许且必须聚焦**：切换品种/周期；读取 1D/4h/1h/15m/5m 当前结构；提取 POC/VAH/VAL/VWAP/EMA、FVG/OB/BRK/LV、BOS/CHoCH、流动性与溢价/折价位置；读取行动格、Data Window、labels/lines/tables；截取含价格轴和 CVD 窗格的全屏图。
- **必须结合用户指标，不看裸K**：SVP 主指标是全市场主驾驶，TV MCP必须读取其行动格、Data Window、框线与具体结构位；加密品种再读取 HALDRO 的 OI、估算CVD、覆盖率、Composite、Valid/Risk Code 作副驾驶验证。准确措辞是“TV MCP读取当前图表中的SVP，并在加密市场结合HALDRO”，不能简写成脱离指标的“只读结构位”。
- **禁止归入 TV MCP**：策略回测、Strategy Tester、K线回放、历史复盘、付费 footprint 等免费账号不具备或不需要的能力。
- **职责解耦**：若任务确需历史统计、回测或复盘，明确标为“本地 Python + 独立历史数据”，不得声称由 TV MCP 完成，也不得把本地统计能力混写进 TV MCP 验收表。
- **输出重点**：具体结构位与执行含义优先，不罗列免费账号不可用的能力。先回答“现在在哪、关键位是什么、如何触发、哪里失效”。
- **审计措辞**：验证 TV MCP 时只写“切图/结构位/行动格/Data Window/截图已验证”；不要写“回测/复盘已验证”。

### 免费账号 TV MCP 最小验收清单

| 验收项 | 通过标准 |
|---|---|
| 品种/周期 | `chart_get_state` 与目标一致 |
| 五周期结构 | 1D/4h/1h/15m/5m均有现场值或在有效继承期内 |
| 具体结构位 | 至少读出 POC/VAH/VAL/VWAP 及当前有效 FVG/OB 等区域 |
| 行动格/DW | 方向、入场、止损、目标、失效字段可解析；缺失须明示 |
| 截图 | full区域，含价格轴、主图结构和CVD窗格 |

## 副指标市场门控（加密双驾驶 / 黄金单主）
主指标(SVP+ICT+VWAP+CVD，标题不含EMA但源码含EMA9/21/34/55、FVG/HTF FVG、MCP Data Window)是全市场主驾驶，全程读。副指标(Volume Aggregated)**仅加密有效**：
- 它内部 `isCryptoA = syminfo.type=='crypto'`，挂黄金/外汇时行动格自动显示"非加密品种/请看主指标判定"——**采集会浪费时间且无意义**。
- **加密**：必采副指标——5家交易所聚合量能、聚合/回退OI、会话CVD、覆盖率/单所主导、合约占比、爆仓、Composite；与主指标行动格交叉验证运动真假。
- **黄金/外汇/股指**：**跳过副指标采集**，只读主指标行动格（13 行：位置/结论/方向/路径/风控/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位）和 MCP Data Window 兜底字段。

## 扫描模式

### 默认：低周期执行卡
用户只说"分析 XXX"、"看看 XXX"、"卡呀"时，默认走这个模式：
- **防抢图（必做·2026-09-11）**：分析开始先声明租约，让后台切图任务让路：
  `python scripts/tv_analysis_lease.py start --minutes 10 --symbol <TV符号>`；出卡后 `end`。
  没这一步时 `btc_tv_refresh` / `xau_tv_sync` / `keylevels_collect` 会在读图中途切走图表，
  表现是行动格突然读成空表、周期对不上（实测 2026-09-11 14:07 连抢两次）。
  TTL 上限 30 分钟，忘了 end 也会自然过期；`tv_screenshot.py` 会自动续期。

  ✅ **租约自锁已修（2026-09-14）**：此前租约生效期间 `keylevels_collect` 会判 `deferred`，分析挡住自己的五周期采集（超 30 分钟契约后源状态落 `TV五周期 unavailable`）。现在 auto_card 开跑自持租约（已有交互式租约则沿用不覆盖、收尾只释放自己声明的），并给自有采集子进程置 `TANGXI_ANALYSIS_OWNER=1` 放行；外部后台（btc_tv_refresh/xau_tv_sync/cron）不带该标记，照旧让路。排查口子：`data/keylevels_collect_diagnostic.json` 的 `analysis_owner:proceed`（自有放行）/ `lease:deferred`（外部让路）。
- **继承高周期**：在有效期内沿用最近一次 4h/1h 背景、关键位、方向判断；不要重新全扫。
- **继承有效期**：1h 背景默认继承到下一根 1h K 收盘；4h 背景默认继承到下一根 4h K 收盘。若价格突破/跌破继承关键位，提前刷新。
- **刷新执行周期**：加密刷 15m，黄金刷 5m；读取 table/labels/lines/study_values。
- **刷新触发周期**：加密刷 5m，黄金刷 1m/3m/5m（以当前图表可用为准）；读取 table/labels/study_values。
- **截图强制**：加密/XAU 每轮更新必须截图；执行周期刷新后立即 `capture_screenshot(region="full")`，必须含右侧价格轴、主图指标、行动格、底部CVD/OI/Volume窗格。
- **“现在呢”主动修复协议（2026-07-06）**：若 quick/auto_card 先显示 `TV实时注入未采用`、`tv_live/tv_dmi_cache 缓存过期`、或 `chart_get_state` CDP失败，不准直接用 stale 数据回答。必须立刻 `tv_launch(kill_existing=true)` → `tv_health_check` → `chart_set_symbol` → `chart_set_timeframe` → `tv_live_dump.py --verbose` 刷新 TV live → `capture_screenshot(region="full")` → 重新跑 `auto_card.py`，然后再给裁决。用户问“现在呢”要的是最新执行建议，不是解释工具故障。
- **X 情绪可选**：只有市场异动、用户要求、或结构与情绪明显冲突时才快速查；否则继承最近情绪。

### 全周期刷新
只有以下情况才全跑：
- 用户明确说"全面扫"、"全周期"、"刷新高周期"、"从4h重新看"。
- 距上次高周期判断很久，或价格突破/跌破上次 4h/1h 关键位。
- 当前低周期信号与继承高周期明显冲突，必须重新确认背景。
- **特例**：用户仅说"分析BTC"（无快捷词、无周期特指）→ 走全周期完整卡（见下方「全周期BTC完整卡」节）。

## 全周期BTC完整卡（RichMarkdown·2026-07-08生产版）

当用户说"分析BTC"（无特指低周期、非"卡呀/看看"快捷执行）时，走**全周期完整卡**：1D/4h/1h/15m/5m 五周期全扫 + Binance + 宏观 + X + 链上 + Deribit/Dune + Depth + Corr 多源。这是 2026-07-08 实测跑通的生产版，权威模板与15步审计见 `references/btc-full-card-template.md`。

**首屏版式（用户2026-07-06确认"差不多这个排版"，2026-07-08沿用）**：
```
2026年7月8日07：27 · BTC
一、现在在哪：15m在VWAP下方窄幅震荡，夹在`63,461`与`63,746`之间，偏弱但未破位
二、现在怎么做：不追空也不追多，等`63,300`回踩守住做A，或跌破`62,638`才切B空
```
**六段编号 + 真Markdown表格**（每段下接表，禁止假表格/宽表>3列）：
① 当前结构 ② 多周期定位 ③ 关键位矩阵 ④ 多源验证 ⑤ 执行方案 ⑥ 最终裁决

**v9.12 默认版式（2026-09-14 用户批准）**：`render_v96_card` 的默认输出已改为 ≤40 行精简骨架——首屏（品种/时间/时段/状态）→ `⭐主推`/`🔵主推 等确认`/`⚠️主推 禁做` 一行 → `结构：⚖现价 … · 🔴上 … · 🟢下 …` 一行 → ① 体温条+副读行 → ② 角色制关键位（并簇 ≤4 行 + 远端注脚）→ ③ 多源 4 行 + 源状态一行 → ④ 三列表 + 【裁决】/失效两行。**上面六段版式只在用户点名「按原分析卡/模板来」时使用**，两者不得混排。
**尾部强制**追加「完整性审计」表（15步管线 ✅/❌/⚠️ 备注），证明全周期全源已跑。

**关键规则**：
- 价格前带结构位（`VWAP 63,461`/`POC 63,746`/`周二纽低 62,638`），禁裸价堆砌
- AB预案完全对称：方向/入场+触发/止损+止盈/仓位+风险/失效/复查；R:R 诚实，不足标⚠不伪造
- 等级：A主推 / B备选 / C等待 / X禁做；当前震荡期多为 C
- 术语中文化：主动买卖 / OI→持仓 / 多空比 / 恐惧贪婪；VWAP/CVD/EMA/Funding/Spot保留英文
- 普通 assistant 回复只发 `MEDIA` 截图 + 一句裁决 + `rich_sent` 回执；完整表格卡**只**走 Bot API 10.1 RichMarkdown 到话题 `-1003733144325:386`，**禁止**把完整正文再复制到普通回复（否则Telegram降级成项目符号/假表格并重复）

**R:R 计算（出卡前跑）**：
```python
price=63632.01
entryA=63300; stopA=62630; t1=63800.07; t2=64234.1; t3=64691.9
for n,t in [('A_t1',t1),('A_t2',t2),('A_t3',t3)]: print(n, round((t-entryA)/(entryA-stopA),2))
entryB=62620; stopB=63150; bt1=61975.98; bt2=61297.0
for n,t in [('B_t1',bt1),('B_t2',bt2)]: print(n, round((entryB-t)/(stopB-entryB),2))
```

**TV截图渲染铁律**：`capture_screenshot(region="full")` 存到 `D:\Hermes agent\tools\radingview-mcp\screenshots\` → 必须 `cp` 到 `C:/Users/Administrator/.hermes-web-ui/upload/default/` 再引用（D盘不渲染）。

**推送**：`send_telegram_reliable('telegram:-1003733144325:386', text, parse_mode='RichMarkdown', timeout=20, retries=3, persist_on_fail=True)` → 期望回执 `True rich_sent`。

## 全周期分析流程（仅在需要刷新高周期时执行）


### Step 1: X 情绪预扫
- 优先用 x_search 扫 `{品种} sentiment today crypto/trading X twitter`；不可用时 fallback 到 web_search
- 提取情绪方向（偏多/偏空/中性/极端）+ 强度 + 是否有突发催化
- X 只作为情绪/催化过滤层，不替代 TradingView 多周期结构
- 耗时 ~30s

### Step 2: 高周期锚定
- 设置 TradingView 到 4h → 读决策表（data_get_pine_tables）+ 关键位（data_get_pine_labels + data_get_pine_lines）
- 切换到 1h → 同上
- 高周期关键位（POC/VAH/VAL/VWAP/ICT）继承到低周期上下文
- 如果 1h 决策表为空（显示"study_count: 0"），标注"继承4h背景"并仅用 4h 数据
- 耗时 ~60s

### Step 3: 执行周期深度
- 切换到执行周期 → 读决策表 + labels + lines + study_values（获取 VWAP/EMA/CVD 实时值）
- 截图（capture_screenshot, region="full"）→ 必须用 full 含价格轴和 CVD 副图
- 截图后立即 cp 到 `C:/Users/Administrator/.hermes-web-ui/upload/default/`（D盘源路径不渲染）
- 以 Pine 数据为主；截图/识图只做视觉核对，不作为唯一依据
- 耗时 ~40s

### Step 4: 触发周期快扫
- 切换到触发周期 → 读决策表 + labels
- 耗时 ~20s

### Step 5: 输出交易执行卡

格式跟 `tradingview-indicator-analysis` 同一设计语言。执行卡更短（≤7行），只保留最核心的：

```
**{品种} · {周期} · {等级}**
**{做多/做空/不做/等待} — {一句话原因}**

**关键位**
VWAP `{vwap}`  POC `{poc}`  VAH `{vah}`  VAL `{val}`

**结构**
上 {sweep_high}  下 {break_low}  目标 {target}

**执行**
{action} `{entry}`  止损 `{stop}`  目标 `{target}`

**失效**
{invalidation}

**禁做**
{dont_chase}
```

格式规则：
- Telegram 正式推送必须走 Bot API 10.1 `sendRichMessage` + `rich_message.markdown`；若使用表格，表格前不能紧贴 standalone `表1 · xxx` 标题行
- **棠溪BTC交易卡首屏版式（2026-07 用户校正）**：正式BTC/RichMarkdown卡的首屏不要用大表格开头，先用目录式速读层：
  ```text
  2026年7月6日21：37 · BTC
  一、现在在哪：{结构位置一句话}
  二、现在怎么做：{直接动作一句话}
  ① 当前结构
  ② 多周期定位
  ③ 关键位矩阵
  ④ 多源验证
  ⑤ 执行方案
  ⑥ 最终裁决
  ```
  后续每个编号段下面再接真Markdown表格。用户明确反馈“差不多这个排版”。
- **Telegram双通道规则**：正式交易卡正文只通过 Bot API 10.1 `sendRichMessage` + RichMarkdown 发到话题；普通 assistant 回复只放 `MEDIA` 截图 + 一句最终裁决 + `rich_sent` 回执。不要把完整表格正文再复制到普通回复里，否则Telegram会降级成项目符号/假表格并造成重复。
- 价格前必须带结构位，例如 `POC 61,873`、`VAL 61,334`、`VWAP 62,487`、`DO 63,617`、`周日低 62,410`；禁止裸价堆砌
- 下方表格第一列必须是侧重点标签：`【当前】/【脚下】/【防守】/【第一空点】/【主空区】/【失效】/【主动买卖】/【持仓】/【情绪】/【风控】`
- 禁止互动式提问或投票（如“你偏哪边 A/B/C”）；安禾必须基于TV/Binance/社区/宏观/用户指标验证后直接给裁决
- 非完整执行卡/告警推送优先压缩成首行结论 + 恰好3张≤3列 RichMarkdown 管道表
- 粗体标题 + `{grade}` 颜色 emoji（🟢A 🔵B 🟡C 🔴X）
- 结构线 VAH/POC/VWAP/VAL 必须粗体
- 价格全用反引号
- 禁止 `｜` 分隔、禁止 `⚡🔑📐` emoji 前缀
- ≤7 行，电报一屏
- 全周期 X → 只输出禁做 + 原因，不硬编入场/止损

## 日内止损止盈方法论（v6.9.11 硬件化）

**错误做法**：用固定百分比算止损止盈（如 BTC 3% 止盈）。3% 是周线/波段目标，不适用于 5m/15m 日内交易。

**正确做法** — ATR 夹层 + 关键位锚定：
1. **止损** = `max(ATR × 2, 当前价 × 0.3%)`，再夹到下一个有意义的结构位上方（空头）/下方（多头）
2. **止盈** = 下一个有意义的结构位（跳 0.3% 以内噪音）。0.3% 以内的关键位视为噪音跳过。
3. **R:R 底线**：若结构不支持 ≥1:2，**标注 ⚠R:R不足**，不伪造数字、不扩大止盈造假 R:R。
4. **兜底**：无结构位时用 0.8%（非 3%）兜底。

**代码参考**：`hermes/scripts/auto_card.py` → `_compact_card()` → `_meaningful_level_above()` / `_meaningful_level_below()` / `atr_stop`。详见 `references/intraday-stop-target-methodology.md`。

**陷阱**：
- BTC 紧致结构（价夹在 POC-VAL 之间 500 点）时 R:R 不达标是正常的——不是 bug，是市场不给机会。此时卡片应诚实标注而非编造远距离目标。
- CVD/Taker 方向决定 Plan A 优先方向（空头偏），Plan B 为反向备选。

## 卡片预案对称性铁律

**A 和 B 必须字段完全一致**，不可缩写备选方案。每条必须包含：
① 方向 ② 入场+触发 ③ 止损+止盈 ④ 仓位+风险 ⑤ 失效 ⑥ 复查 ⑦ 轨迹

错误示例（Plan B 缩水）：
```
B·多头：止损 63,552 止盈 65,787 R:R 1:4.9  ← 缺入场/仓位/风险/失效/复查
```

正确示例（对称）：
```
B·多头反弹（备选·反向确认）：
  触发：站回 VAL 64,136 + 15m 收线确认
  入场：64,200 ±50点 限价
  止损：63,552 止盈：65,787 R:R 1:4.9
  仓位：0.0017 BTC · 风险 0.68U
  失效：跌回 64,136 下方 + 15m 接受
  复查：入场后 15m × 3根
```

## 等级与计划规则
- **输出格式修正**：卡片里的首屏必须先给"做/不做、等哪里、失效位、禁做动作"；不要先展示模板本身或解释分析方法
- **A**：主计划。必须给入场、止损、目标、失效位；只在结构、关键位、量能/CVD 至少两项同向时给 A。
- **B**：轻仓/等待确认。必须给触发条件和失效位；不强行现价入场。
- **C反**：反转试探。只能靠近 VWAP/VAH/VAL/POC/扫点等关键位，小仓，必须写清反转确认条件。
- **C等待**：只给等待位和重新评估条件，不给入场价。
- **X**：不做。只写禁做动作、失效原因、重新评估条件；不要硬生成入场/止损/目标。

## 格式规范

- **设计语言继承** `tradingview-indicator-analysis`：无 `｜`、无装饰 emoji（仅方向用 📈📉⛔）、名前行后、纯纵向流
- **执行卡更短**：≤7 行，只放关键位 + 执行 + 失效 + 禁做
- **粗体规则**：结构线 VAH/POC/VWAP/VAL、方向结论、操作指令 必须粗体
- **价格代码**：全用反引号 `` `66,286` ``
- Telegram 主发，飞书备发（走 `feishu-analysis-card-sender`）

## 陷阱
- ⚠️ **TV CDP 连接故障恢复**：若 `tv_health_check` 返回 `api_available: false` 且 `target_url` 含 `tooltip/index.html`——MCP server 连到了 tooltip iframe（死窗口）而非 chart target。此时所有 data_ 工具都会报 `_activeChartWidgetWV is undefined`。**不要反复重试 data 工具**——它们无法自愈。正确修复：`tv_launch(kill_existing=true)` 重建连接→等5-8s→`tv_health_check` 确认 `api_available: true` 且 `target_url` 含 `tradingview.com/chart/`。2026-06-27 实测此模式恢复时间<10s。
- ⚠️ **行动格 + MCP Data Window 双通道（定版 2026-09-11）**：主指标当前行标是 `位置/结论/方向/路径/风控/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位`，等级嵌在`结论`里；同时源码末尾已恢复 `MCP Side/Grade/Setup/Entry/Stop/Target/CVD/Quality` Data Window导出。读取优先级：行动格文字 > MCP编码兜底 > 外部源校验；禁止再按“Data Window编码已移除/CVD不由指标导出”的旧假设处理。MCP实时分析必须分别读 `data_get_pine_tables(study_filter="SVP")` 与 `data_get_study_values`，自动脚本走 `auto_card.py`。回归测试：`tests/test_tv_action_panel_decode.py`、`tests/test_render_tv_card.py`。
- 1h 决策表可能为空（study_count:0），不报错，标注"继承4h背景"并仅用 4h 数据
- **截图渲染**：TradingView MCP 截图在 D 盘不渲染。必须 `cp` 到 `C:/Users/Administrator/.hermes-web-ui/upload/default/`，用该路径的 markdown image
- **Vision 模型**：识图配置通常为 auxiliary.vision.provider="auto"；如截图识别失败或 403，可临时改为 custom:api.yairouter.com + gpt-5.5 后重启会话/网关
- 切换到新周期后等待 2-3 秒再读数据，避免数据未加载
- CVD slope 负值=主动卖>买，正值=主动买>卖
- hermes config set CLI 在此环境不可用（uv trampoline），改配置用 Python: `python -c "import yaml; ..."` 直写 config.yaml
- 用户问颜色/指标元素含义时，查阅 `references/indicator-color-legend.md`
- ⚠️ **截图渲染**：capture_screenshot 保存到 `D:\\Hermes agent\\tools\\tradingview-mcp\\screenshots\\` 的图片在 Hermes Web UI 中**不会渲染**。必须立即 `cp` 到 `C:/Users/Administrator/.hermes-web-ui/upload/default/` 再引用该路径。引用格式：`![描述](<C:/Users/Administrator/.hermes-web-ui/upload/default/xxx.png>)` — 正斜杠 + 尖括号
- ⚠️ **截图区域**：必须 `region="full"`，`region="chart"` 不包含右侧价格轴和底部 CVD，用户看不到关键信息
- ⚠️ **TV CDP 连接故障恢复**：若 `health_check` 返回 `api_available: false`（连到了 tooltip iframe 而非 chart），用 `tv_launch(kill_existing=true)` 重建，等5-8s 确认 `api_available: true`。不要反复调 data 工具 — `_activeChartWidgetWV is undefined` 无法自愈。完整架构见 `crypto-multisource-analysis` skill 的 `references/decode-pipeline-architecture.md`。

## 参考文件
- `references/btcusdt-example-20260615.md`
- `references/btc-full-card-template.md` — 全周期BTC完整卡生产模板（2026-07-08实测·含15步审计）
- `references/decode-pipeline-architecture.md`
- `references/indicator-color-legend.md`
- `references/intraday-stop-target-methodology.md`
- `references/tv-cdp-action-panel-architecture.md`
