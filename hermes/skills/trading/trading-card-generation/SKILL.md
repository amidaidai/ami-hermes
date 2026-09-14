---
name: trading-card-generation
description: Generate BTC/XAU trading analysis cards (compact + full dual output) for 棠溪's manual decision cockpit. Covers ATR-based stop/target, symmetric AB plans, honest R:R, TradingView indicator integration, Telegram delivery. Load when user asks for card generation, analysis output, or trading plan formatting.
---

> **同族导航** — 卡片组 4 个技能各司其职，别加载错 （同族入口：`tradingview-indicator-analysis`）
> · **本技能 `trading-card-generation`** = 卡片生成脚本（compact + full 双输出）
> · 同族其余：`tradingview-indicator-analysis`（入口 · 分析卡主流程（多品种多周期、叙事驱动、5 段模板））、`tradingview-execution-card`（低周期执行卡（加密 15m / 黄金 5m，高周期限时继承））、`xau-analysis-format`（卡片格式细则（裁决措辞/周期标签/移动端布局））
> · 组内改动请同步其余成员的触发词，避免同名族抢触发。


# 棠溪交易分析卡生成 v8.0（叙事驱动·TV集成·无分隔线）

## 触发条件
- 生成 BTCUSDT 或 XAUUSD 分析卡
- 用户说"跑一下品种""出卡""分析一下"
- 需要推到 Telegram 的分析
- 模板/警报格式调整

## 核心原则

1. **系统=决策驾驶舱，不是自动交易。** 棠溪是最终踩油门的人。
2. **B/C等待不产生执行权。** 价格在关键位附近只给触发条件和人工观察候选，不渲染可执行Entry/Stop/Target；最终只有GO-A可执行。
3. **诚实 > 好看。** R:R不足标注⚠而非伪造数字。
4. **预案AB完全对称。** 方向/入场/止损/止盈/仓位/失效对称。
5. **手机优先。** 每行≤38字符，Telegram移动端不折行。
6. **社区驱动。** 格式以X/Twitter/Reddit/Telegram频道共识为基准。
7. **信息密度。** 删除冗余框架（五段标题/重复编号/自动规则），只保留可执行信息。
8. **唯一主推裁决。** 裁决层必须先给“最适合的第一推荐方案”，禁止把 A/B/X 像菜单一样平铺成同等选项；备选只作为主推失效后的路径，不得抢主推权重。

## 版本演进

| 版本 | 完整卡 | 极简卡 | 警报 | 特征 |
|------|--------|--------|------|------|
| v6.9 | 80+行 | 15行 | 20行 | 五段正文·10段头部 |
| v7.0 | ≤25行 | ≤10行 | ≤8行 | 社区驱动精简·三合一③行 |
| v7.1 | ≤20行 | ≤8行 | ≤6行 | 手机适配·每行≤38字 |
| v8.0 | ≤35行 | ≤8行 | ≤8行 | **叙事驱动·TV DMI集成·无分隔线·R1/R2/S1/S2/S3** |
| v9.10 | ≤35行 | ≤11行 | — | **排版精简：结构位去内部ID·订单流压缩·HALDRO精简·快速卡加裁决收尾** |
| v9.11 | ≤35行 | 20-25行 | — | **手机排版：首屏结论前置·结构/执行/验证三块窄表·每表≤3列·去重复标题** |
| v9.12 | **≤40行（正文）** | ≤25行 | — | **减法+角色化：删【现在】【做法】重复表·体温条替代周期表·关键位并簇→角色制≤4行·源状态压一行** |

**v9.11 Telegram手机排版铁律（2026-09-03）**：用户反馈“排版不好看”时，优先重排信息层级，不要继续堆字段。快速卡固定为：品种时间 → 方向/等级 → 加粗一句结论 → 现价（可含日高/日低/涨跌）→ 五周期体温 → 结构表 → 执行表 → 验证表 → 下一步/失效。每张表最多3列，表格前保留空行；禁止 `【章节】`、宽四列表、把 SVP/HALDRO/订单流压成一条长句。数据源状态应作为验证表中的一行，审计解释缩短为“裁决/辅助/降级/状态可见”。实现以 `scripts/render_tv_card.py::_render_push()` 为准，模板同步于 `D:/Hermes agent/references/master-template-v68.md`。

**v9.12 完整卡减法铁律（2026-09-14 用户批准「按建议推进」）**：完整卡从 ~120 行压到 ≤40 行，规则三条——① **并簇**：相邻 <0.15% 的结构位合成区间（`77,847`+`77,865` → `77,847–77,865` 阻力簇），不许逐位罗列；② **角色制**：② 只给 ≤4 行 `上沿阻力簇/近端转撑/主观察/失效·支撑带`，其余位与远端极值下沉表下「远端」注脚；③ **去重与上限**：删除与 ②/④ 重复的【现在】结构位表与【做法】决策摘要表，每表 ≤3 列、正文 ≤40 行、同一事实只写一遍。首屏 = ⭐主推行 + 结构夹层行（`结构：⚖现价 … · 🔴上 … · 🟢下 …`）；① 周期体温 = 一行体温条 + 一行副读（五周期与 ⭐主 标记必须全在）；③ 表下固定一行 `已入FinalVerdict：… ；仅展示/辅助：…`。`⭐` 只在 GO-A 可执行时点亮，等待/禁做沿用 `🔵主推 等确认` / `⚠️主推 禁做`。实现：`scripts/render_v96.py::render_v96_card`（v9.12 起），回归：`tests/test_card_v912_format.py`。用户点名「按原分析卡/模板来」时才回到六段版式。

**v8.0 关键变更**：
- 格式对标社区优秀分析卡（R1/R2/S1/S2/S3关键位·叙事结构·5段：①结构→②关键位→③量价→④方案→⑤评分）
- **禁止** `━━━━━━━━━━` 分隔线（用户明确要求）
- **禁止** `—— 你来选方向 ——` 结尾（用户明确要求）
- TV DMI 决策表实时注入 ③量价分析段，不再显示"需TV确认"占位符
- 渲染引擎：`scripts/render_v96.py`，调用 `render_v96_card()`（原 render_v8.py/render_v8_card 已于 2026-07-07 更名）

## Chinese Localization Rules (Confirmed 2026-06-22)

**Absolutely forbidden English terms in card body** (will get corrected — encoded as hard rules):
- `Silver Bullet` → `银弹窗口` or just `银弹`
- `Taker` → `主动买卖` (never standalone "Taker")
- `LS` / `Long Short` → `多空比`
- `OI` / `Open Interest` → `持仓`
- `F&G` / `Fear & Greed` → `恐惧贪婪`
- `KillZone` → use zone name directly: `亚洲`/`伦敦`/`纽约`/`盘外`
- `Premium` / `Discount` → `溢价` / `折价`
- `Outside` (KillZone) → `盘外`
- `Silver Bullet ❌` → `银弹窗口: 无`
- `False` / `True` in any context → never appear in cards

**Allowed English in cards:**
- VWAP, CVD, EMA, DXY, BTC, USDT — universal trading abbreviations
- R:R — standard notation
- Funding — user explicitly prefers English
- Spot/美元 — user explicitly prefers English

**Testing for English leaks:**
After generating any card, grep for `Silver Bullet`, `Taker`, `OI[^ ]`, `LS[^ ]`, `F&G`, `KillZone`, `Outside`:
```bash
grep -E "Silver Bullet|Taker|LS |OI |F&G|KillZone|Outside" data/auto_card_*.md || echo "0 English leaks"
```
All must return zero matches. If any appear, fix the source and regenerate.

## 社区基准（多源确认）

- **Telegram信号频道**: 4-6行（方向·入场·SL·TP·RR）
- **TradingView Alert**: 3-5行（品种·价格·信号·TF）
- **X/Twitter社区**: 6-8行（入场区间·2目标·有效期·RR）
- **机构Dashboard**: 8-12行（区间·SL·TP·仓位·失效）

详见 references/community-benchmarks.md

## v9.6 表格驾驶舱落地（2026-06-29）

当前权威模板为 `D:/Hermes agent/references/master-template-v68.md`；模板版本必须与渲染器和card schema一致，不能凭历史版本号判断完成。完整度步骤必须动态读取 `pipeline_router.route_pipeline()`，禁止硬编码旧的“10步”。旧 v8.0 叙事卡仅保留为历史说明；标准手动出卡必须输出五大表格区块：`多周期定位`、`关键位矩阵`、`多源交叉验证`、`执行预案`、`风控闸门`。

**棠溪BTC手动卡首屏排版（2026-07 用户校正）**：RichMarkdown正文首屏应先给目录式速读，不要先塞宽表。固定形状：
```text
2026年7月6日21：37 · BTC
一、现在在哪：急跌后的支撑墙上方
二、现在怎么做：不追空，等反抽
① 当前结构
② 多周期定位
③ 关键位矩阵
④ 多源验证
⑤ 执行方案
⑥ 最终裁决
```
正文每个编号段下面再接真Markdown表格。普通 assistant 回复不要复制完整表格正文，只回 `MEDIA` 截图 + 一句裁决 + `rich_sent` 回执；否则Telegram会把复制版降级成项目符号/假表格并造成重复。

渲染层落地记录见 `references/v96-table-cockpit-renderer.md`。关键经验：改模板不等于改渲染，必须同时跑 `python hermes/scripts/auto_card.py BTCUSDT` 和 `python hermes/scripts/auto_card.py XAUUSD`，并检查五大 marker 全存在。函数名已随文件一并更名（`render_v96_card()`），`auto_card.py` 走 `from render_v96 import render_v96_card`。

**全周期BTC完整卡（手动"分析BTC"场景）**：完整五周期+D的RichMarkdown卡模板与15步审计已落到 `tradingview-execution-card` skill 的 `references/btc-full-card-template.md`（未落地·勿引），由该 skill 管辖。本 skill 保留 v9.6 五大表格区块权威；两者首屏"一、二、…①-⑥"版式须保持一致（用户2026-07-06确认）。

**v9.6 GO/NO-GO 下单闸门（2026-06-29 新增）**：每张完整卡尾部自动追加七问硬闸门（数据新鲜度·TV现场·R:R·事件窗口·Protections·样本WFO·组合暴露）。任一红灯 → 卡片裁决 `✗ NO-GO`。闸门模块 `scripts/go_nogo_gate.py`，由 `auto_card.py` 在 `validate_card_rules()` 后自动调用。

**v9.6 predicted_grade 预测评级（2026-06-29 新增）**：每条 `trade_plans.jsonl` 记录自动写入 `predicted_grade` 字段（A/B/C/D）。评级逻辑：置信度≥0.6+R:R≥2.0+数据A级→A；置信≥0.3+R:R≥1.5→B；置信>0→C；禁做/门控否决→D。用于复盘时对照实际结果，评估预测质量。当前市场震荡期，多数卡评级为 C（置信低+门控否决）。

**XAU 数据源更新（2026-06-29）**：XAU 多周期 K 线不再使用 TV MCP 占位（OANDA:XAUUSD 上 SVP v10 不返 Pine 数据）。改用 gold-api 现货价 + 金十 24h 高/低 + 日内推算 VAH/VAL/POC。来源标注 `gold-api·金十 现货{N} | 24h高{N} 低{N}`。

**v9.6 表格密度警告（2026-07-08）**：`render_v96_card()` 当前产出 6-7 个表段，手机端阅读负担大。用户已明确偏好「最多 2 表 + emoji 短句」的精简版式。出卡时需要判断用户意图——用户要求"精简/追/快速看"时走 2 表模式，用户要求"全量分析"时才出完整 7 表卡。2 表格式详见 pitfall 28 和 `references/phone-friendly-2table-format.md`。

## 用户话内定档与 Telegram 双通道（2026-09-03）

### L1 轻量 BTC 实盘回传验收（2026-09-04）
用户说“看一下BTC”时，必须完成并回传以下最小闭环：TradingView 当前状态校验（`BINANCE:BTCUSDT.P`、15m、SVP+ICT+VWAP+CVD 与下方成交量/聚合窗格）→ 主指标行动格 → 实时报价 → Binance 衍生品方向票（Funding、持仓变化、多空比、主动买卖）→ **一张新全屏截图**。截图应首行返回，且视觉验收包含右侧价格轴与 CVD/成交量窗格。若主指标出现 `⚠冲突`、`等解除`、`观望` 或类似等待语义，唯一主推必须是“等待”，不得生成 Entry/Stop/Target，也不得用衍生品的短线偏多/偏空覆盖主指标裁决。没有持仓时明确写“无持仓”；过期 nPOC 只能作背景备注，不能作为执行位。轻量回复只保留现价、主指标结论、关键上下位、主要冲突与下一步，避免展开完整五周期管线或审计报告。

### 截图优先与画面—状态一致性（2026-09-04）
用户在跟踪更新中明确偏好“先放截图”，因此普通回复的顺序固定为：**第一行新截图 → 第二行一句话裁决 → 其余内容按需展开**。不要先输出解释、道歉或表格；用户若只说“先放截图”，只返回截图，不附分析正文。

截图不能只凭 `chart_get_state` 认定正确。TradingView MCP 的状态回读与实际截图可能短暂不同步；每次切换品种或周期后必须：
1. `chart_set_symbol/timeframe`；
2. 等指标重算完成（15–30秒）；
3. 再读 `chart_get_state` 与主指标行动格；
4. 生成新截图；
5. 对截图做视觉验收，确认左上角实际品种/周期、右侧价格轴、主指标及下方窗格；若视觉周期与状态不一致，丢弃该截图、重新切回目标周期并重截，禁止把错误周期截图发给用户。特别注意：工具返回的 quote、pine table 或 screenshot 可能出现跨品种/跨周期短暂错配；不能仅凭请求参数或返回 `success=true` 认定成功。视觉验收失败时，必须先恢复目标品种，再等待重算，重新读取状态、行动格和截图；在恢复完成前不得引用这轮错误数据。

连续跟踪更新时，关键位也必须重新绑定当前截图和当前报价：若行动格显示“过期”或截图/状态不同步，不得把旧关键位写成确定执行位；只保留为背景参考并明确标注。磁吸位/前低是分层观察区，不是“到了就买/卖”的指令：输出时必须同时给出最近结构位、下一级磁吸位和确认条件，不能把远端关键位写成当前唯一等待点。若价格已先触及最近结构位，应先更新近端反应，再决定是否继续看远端位。
这是分析卡生成的硬路由，优先于旧版“默认低周期/完整卡”描述：
- `看下/看一眼/快速过一遍`：轻量，只读主周期（BTC 15m、XAU 5m）截图、现价、主指标行动格和加密 Binance 方向票；不拉五周期。
- `现在呢/继续/接着看/更新`：标准，在轻量基础上只补相邻周期结论行；不升级为完整。
- `分析/全面/深度/完整卡`：完整，才跑 1D/4h/1h/15m/5m 全数据管线与多源验证。
- 仅品种名：默认轻量。严格按原话执行，禁止多跑，也禁止少跑。

Telegram 交付必须拆成两条独立消息：先用 `send_telegram_photo()` 发本轮新 TV 全屏主周期截图，再用 `send_telegram_reliable(parse_mode="RichMarkdown")` 发窄版文字卡；普通 assistant 回复只保留 `MEDIA:<截图>`、一句中文裁决和“已推卡”，不得复制表格。目标必须从当前会话的 chat/thread 元数据读取，不能凭记忆硬编码话题号。时间统一 `YYYY年M月D日 HH：MM`，裁决不确定时写“等待/不宜”，B/C 等待不生成入场、止损、目标。

## 价格到位提醒与“只提醒、不代判”（2026-09-04 用户校正）

当用户问“价格到了提醒我，让我自己看”时，意图是**价格触达通知**，不是让助手在触达前后自动替用户下单或给出新的方向裁决。提醒必须采用三段式：

> `BTC 到达 {价格/区域} 附近，请查看 {主周期} 图表。`

> `触发条件：查看结构/CVD/主指标；不代表自动做多或做空。`

> `未触发前：不追、不提前挂单。`

关键位应按“近端结构位 → 下一级磁吸位 → 远端观察位”分层设置，不能把远端位说成唯一等待点；每个提醒只负责把用户叫回图表，最终判断仍由用户自行完成。若用户没有明确要求自动交易，不生成或暗示 Entry/Stop/Target。

如果使用 TradingView 或后台监控创建提醒：
1. 先绑定当前已验证的品种、周期和报价；
2. 明确提醒方向（上穿/下穿/触达）及价格区间；
3. 消息内容只写“到位 + 请查看”，不写自动交易指令；
4. 创建后必须读取活动提醒列表或等价回执验证；
5. 创建失败或无法验证时，明确告诉用户“尚未设置成功”，绝不能说成已提醒。普通聊天本身不能主动在未来弹消息，除非存在已验证的后台任务/平台提醒。

## 完整档现场路由验收（2026-09-12）

用户话内「分析BTC」触发完整档时，不能把 `python scripts/auto_card.py BTCUSDT` 的默认输出当作完整管线证明。该入口实测可能仍打印 `quick` 并只审计 `tv → binance → card`。执行顺序必须是：

1. 先用 `pipeline_router.resolve_tier/route_pipeline(symbol, "full")` 验证档位和步骤；
2. 若 auto_card 输出的实际档位不是 `full`，不得把它的 quick 审计冒充完整审计；
3. 补跑缺失的五周期TV、Binance衍生品、CoinGecko/FinanceKit、宏观、x_search、深度、相关性等步骤；
4. 最终卡分别标注「现场完整采集」与「自动卡实际渲染档位」，数据源失败和旧缓存必须可见；
5. cron_read 文件必须先检查 mtime，超过60分钟标 `stale_cache/过期跳过`，禁止把旧文件写成实时证据。

这条验收规则与 `crypto-multisource-analysis` 的完整档管线互补；若两者出现冲突，以运行时 `pipeline_router` 和现场工具返回为准。复现与验收清单见 `references/full-tier-runtime-verification-2026-09-12.md`。

## 2026-09-12 用户纠正：原分析卡版式回归铁律

当用户说“按原分析卡/模板来”或明确否定自定义排版时，禁止继续设计新布局；必须回到 `master-template-v68.md` 与 `tradingview-execution-card/references/btc-full-card-template.md` 的六段版式，并保持首屏与段落顺序一致。

### BTC完整卡固定结构

1. 第一行：`YYYY年M月D日 HH：MM · BTC`。
2. 空一行后固定两句：
   - `一、现在在哪：` 当前价格相对**最近具名结构位**的位置；必须写结构名称（VAH/POC/VWAP/VAL/FVG/周高低等），不能只写“上沿/下方/争夺区”。
   - `二、现在怎么做：` 直接写动作与等待条件，不先解释模板，也不堆“当前情况/当前位置/执行路径”等重复标题。
3. 正文固定六段：`① 当前结构 ② 多周期定位 ③ 关键位矩阵 ④ 多源验证 ⑤ 执行方案 ⑥ 最终裁决`。
4. 每张表最多三列；表格字段短，结构名称和价格必须在同一行绑定动作含义。
5. 执行方案必须同时展示两个对称条件：`⭐A主推` 与 `🔁B备选`。每行都要包含触发条件、动作和**为什么**；推荐理由不得另起长段落漂移到表外。A/B不得平权，最终主推只出现一次。
6. 若主指标为冲突、等解除、观望或 C 等待：最终状态保持 WAIT/C，禁止渲染入场、止损、目标；方案只能写观察触发与失效条件。
7. 最终裁决必须放在正文最后，明确“最优方案 + 理由 + 当前是否执行”。
8. 执行方案必须显式包含“挂单方式”：GO-A时写条件单/限价单/触发单及入场、止损、目标、撤单条件；WAIT/C时只写“暂不挂单 + 触发条件”，不得把观察价伪装成已挂单或执行三件套。
9. A/B方案的推荐理由必须写在执行方案表的同一行，不另起长段落重复解释；格式固定为“方案 | 挂单方式 | 触发与动作/理由”。

### 位置绑定与语义校验

- 先比较现价与最近结构位，再写“现在在哪”。例如现价贴近 15m VAH 时，应写“15m VAH下方”，不能误写成“POC/S VWAP核心争夺区”；只有价格确实位于中轴区才这样描述。
- 远端磁吸位只能作为后续目标观察，不能替代最近结构位成为唯一等待点。
- 结构位名称使用人类可读中文：`15m VAH`、`15m POC`、`15m S VWAP`、`15m VAL＋4h POC`；不要只写“上沿/下沿/支撑位”。
- 方案理由优先来自主指标结构→多周期背景→持仓/CVD/主动买卖；副指标只能确认、降级或否决，不能覆盖 SVP 主驾驶。

本次回归示例与检查清单见 `references/original-card-layout-regression-2026-09-12.md`。

### 标准跟踪卡的相邻周期复核（2026-09-12）

`现在呢/继续/更新` 只补主周期的相邻结论，不升级完整卡；但每个相邻周期都必须单独做状态完整性检查：

1. 切换周期后先 `chart_get_state`，确认仍是目标品种；不要直接消费上一品种/上一周期的表格结果。
2. 若结构位价格数量级与 Binance/主周期明显不符，立即丢弃该周期结果，重设 `BINANCE:BTCUSDT.P` 后等待重算再读；错误尺度的数据不得写进卡。
3. `study_count:0` 或主指标表缺失时，只写“主指标未返回/数据不可用”；不得用副指标或旧缓存代替主指标方向。副指标只能作为辅助，并标明“主指标缺失”。
4. 现价必须重新绑定最近具名结构位：现价贴近 VAH 就写“VAH下方”，贴近 POC/VWAP 才写“中轴争夺”，不能沿用上一轮位置叙述。
5. 主指标出现“冲突/等解除/观望/C等待”时，卡面只能写 `⭐主推等待`；“A主推”只代表 GO-A 授权方案，不能把方案编号 A 当作评级。
6. 执行表必须包含“挂单方式”：WAIT/C 只写“暂不挂单+触发条件”；只有 GO-A 才能写条件单/限价单及入场、止损、目标、撤单条件。

## 出卡流程

### 1. 加载模板（必须·铁律）
```python
read_file("D:/Hermes agent/references/master-template-v68.md")
```
不经此步出卡=违规。模板是格式权威。

### 2. 数据采集 + 引擎运算
```bash
cd "D:/Hermes agent" && python scripts/auto_card.py BTCUSDT
cd "D:/Hermes agent" && python scripts/auto_card.py XAUUSD
```
约60-90秒。自动采集Binance+gold-api+金十+Polymarket+Grok+社区情绪。
VWAP/EMA/CVD由 `scripts/vwap_ema_cvd_engine.py` 本地计算（不依赖TV连接）。

### 3. 双卡输出（v7.1手机优先）
- 完整卡按用户档位输出；B/C等待不得因排版切换而泄露执行价格，只有GO-A才可显示执行三件套
- 极简卡 ≤8行（关键位±0.5%内触发）
- 警报 ≤6行（行情守望实时推送）

### 4. 推送到 Telegram
截图与文字卡分开；文字真表格必须走 `telegram_reliable.send_telegram_reliable(parse_mode="RichMarkdown")`，截图走照片通道。普通 `hermes send` 不算RichMarkdown验收。仅在用户明确授权时外发。

## 止损止盈算法 (_calc_stop_target_atr)

```
输入: price, direction("short"/"long"), klines, symbol
逻辑:
  1. ATR = klines[15m].atr 或 klines[5m].atr，fallback price×0.2%
  2. atr_stop_dist = ATR × 2.0（最小price×0.3%）
  3. 收集中周期结构位(15m/1h/4h): VAH/VWAP/POC/high/EMA21/EMA55
  4. 跳过噪音(距价<0.3%)
  5. 做空: stop=max(price+atr_stop, 最近阻力)  target=最近支撑
     做多: stop=min(price-atr_stop, 最近支撑)  target=最近阻力
  6. 无结构位兜底: stop=price×1.008/0.992  target=price×0.992/1.008
返回: {stop, target, rr, stop_reason, target_reason, atr}
```

## 🚨 Format Correction (2026-06-23)

**Two distinct card formats exist — use the right one per context:**

| Context | Format | Lines | When |
|---------|--------|:-----:|------|
| **Quick buzz alert** (daemon push) | Conversational·无编号·自然语言 | 3-5 | "BTC 62460跌到大底区,守住做多64K+" |
| **Full analysis card** (deep analysis) | **v8.0 叙事5段**·结构/关键位/量价/方案/评分 | 22-28 | When daemon score ≥8, or user asks for analysis |
| **Standard alert card** (Telegram push) | v4.2 压缩·①②③编号·≤38字/行 | 8-10 | Legacy — avoid for new development |

**当前canonical格式由master模板+实际渲染器共同定义。** v8.0仅是历史叙事格式；出卡前读取 `references/master-template-v68.md`（未落地·勿引），并以当前 `render_v96.py`/`render_tv_card.py` 实测输出为准。

## Format Iron Law (v4.2 — Telegram alert card, legacy)

**This format is DEPRECATED for full analysis cards. Keep it only for backward-compatible quick alerts.**

When outputting alert/push cards to Telegram/Feishu/Discord/local reports (vs long-form analysis cards), current user preference supersedes old no-table rules:

- **首行方向**：`↑做多`/`↓做空`/`○等待`/`×禁做` + 等级 + 价格
- **默认布局**：首行结论 + 恰好3张真实Markdown管道窄表 + 每表≤3列
- **禁**：假表格/文字对齐/4列以上宽表/长段落/尾注/markdown 加粗/说明文字/标题前缀
- **价格**：反引号 `65,042`
- **术语中文化**：Taker→主动买卖, OI→持仓, LS→多空比。VWAP/CVD/EMA/ADX/Funding/Spot保留英文
- **只输出卡片正文**：无 "检测报告" "分析" "注意" 等标题

旧版“禁表格/`|`”仅保留为历史记录，已被“手机窄Markdown表格”规则废弃。

示例（当前引擎输出）：
```
×禁做 X 65,057 · VWAP 64,551 · 23:13
① 方向：偏多 · 处理：延展禁追
   趋势 7/1 · 反转 5/2
② DMI ADX 34 · CVD +11,696 · 顺空确认
③ VWAP 64,551 — VAH 65,043 — VAL 63,841
④ 位置：VA内 · VWAP上方 · 主动买卖 1.16 · 持仓 101K
⑤ 延展禁追 · EMA 65,084/64,893 · 多头排列
```

## 出卡格式规范 (v4.2 棠溪偏好对齐) — 废弃旧v7.1/v8.0格式

### 完整告警卡（≤10行 · A级推送）

```
↑做多/↓做空/○等待/×禁做 {grade} {price} · VWAP {vwap} · {time}
① 方向：{bias} · 处理：{treatment}
   趋势 {trend_l}/{trend_s} · 反转 {rev_l}/{rev_s}
② DMI ADX {adx} · CVD {cvd} · {cvd_state}
③ {key_level_1} — {key_level_2} — {key_level_3}
④ 位置：{position} · 主动买卖 {taker} · 持仓 {oi}K
⑤ {treatment} · EMA {ema9}/{ema21} · {ema_state}
{suggested_action}
```

所有行：纯文本 · 无粗体 · 无emoji · 无表格 · 反引号价格 · 冒号对齐
◷ 06-21 22:15 · BTCUSDT · BINANCE · B

① B等待 · VWAP反抽 · 3/13 · 置信3/5
   共振·锚定·震荡

② 现价 `63884`
   高 `64200` 低 `63600` 日-1.20%
   4h空 · 1h震 · 15m拒 · 5m待

③ VWAP `63894` 下·1σ-2σ
   EMA 快空·慢空·强空排
   CVD 卖 · Taker sell · FG 35

④ 阻 `64200` POC `63900`
   VAH `64100` VAL `63700`
   支 `63500`
   失效 `64500` 执行 `63800`

—— 预案A · 空⚠优先 ——
⑤ 入场 `63600-64000` 限价
⑥ 止损 `64200` 结构位
   止盈 `63200` `62600` 1:2.5
⑦ 仓位 半仓 风险0.67U 100x
⑧ 失效 `64500` 复查3×15m

—— 预案B · 多备选 ——
⑨ 入场 `64200` 止损 `64200`
   止盈 `64800` 1:1.5⚠R:R
   仓位 半仓 风险0.67U

⑩ 闸门：数据✓ 风控✓ 执行✓
   心态✓ · 不到不执行
   决策：你来选方向——
```

### 极简卡（≤8行 · 价格锚关键位触发）

```
○等待 {bias} · VWAP {vwap}
现价 {price} · CVD {cvd} · TV {grade}
VAH {vah} — VWAP {vwap} — VAL {val} — POC {poc}
① 守VWAP上方做多看VAH
② 若破VWAP则转空看VAL

### 警报（≤8行 · A级推送）

```
↑做多/↓做空/○等待/×禁做 {grade} {price} · VWAP {vwap}
① 方向：{bias} · 处理：{treatment}
② DMI ADX {adx} · CVD {cvd} · {cvd_state}
③ {key_level_1} — {key_level_2} — {key_level_3}
④ 位置：{position} · 主动买卖 {taker} · 持仓 {oi}K
⑤ {treatment} · EMA {ema9}/{ema21}
```

禁粗体/禁说明文字/禁`—— 你来选方向 ——`。旧“禁表格”规则废弃：推送优先使用真Markdown管道窄表，每表≤3列，禁止假表格和宽表。

## 手机适配规则

1. **每行≤38字符** — Telegram移动端不折行
2. **②现价拆3行** — 价/高低日变/多周期
3. **③指标拆3行** — VWAP行/EMA行/CVD行
4. **④关键位拆4行** — 阻+POC/VAH+VAL/支/三线
5. **预案AB各拆2-3行** — 入场/止损止盈分两行
6. **⑩闸门拆2行** — 数据风控执行/心态
7. **去冒号** — `止损:` → `止损 `（省2字）
8. **空格替`·`** — 手机端更紧凑
9. **`_p()`去反引号** — `_fmt_price`自带\`，手机再包会双重
10. **Funding/Spot保持英文** — 用户偏好: `Funding 0.01%` 不用 `资金费率0.01%`·`Spot/美元` 不用 `现货/美元`·Kill Zone中文化但K线标签（VAH/VAL/CVD等）中文

## 每日学习 v2.0

全维度知识池，不限分类，对交易和系统有利即可。14题材·42条目·365天轮换：
策略·择时·订单流·量价·技术·风控·心理·宏观·链上·编程·运维·回测·社区·品种

详见 `scripts/daily_learn.py`。

## 数据源

### 价格与K线
- BTC: Binance futures (HMAC) + CMC spot + 金十
- XAU: gold-api.com + 金十 + Yahoo GC=F (期货-125→现货)

### 订单流与情绪
- CVD/Taker/OI/Funding: Binance HMAC API
- F&G: Alternative.me + Coingecko
- 社区情绪: Grok/X验证 + Polymarket
- 宏观: DXY/US10Y from Yahoo

### VWAP/EMA 本地引擎（v1.0）
不依赖TV连接。`scripts/vwap_ema_cvd_engine.py` 从K线本地计算：
- VWAP + 1σ/2σ 标准差带（对齐棠溪 Pine: VWAP_SD_MULT_1=1.0/2=2.0）
- EMA 9/21/34/55 + 趋势云（快云9/21·慢云34/55）
- CVD 吸收/背离检测（对齐 Pine: CVD_ABSORB_LEN=12等）
- 注入 auto_card 的 ③ 行
## 参考文件

- `references/card-format-quickref.md` — 卡片格式速查
- `references/tv-dmi-override.md` — TV DMI 决策表覆盖规范
- `references/community-benchmarks.md` — 社区信号格式基准（X/TG/TV/机构·多源确认）
- `references/tv-data-bridge.md` — TV数据桥架构（行情守望直连TV MCP·替代cron）
- `D:/Hermes agent/references/master-template-v68.md` — 出卡格式权威模板（每次出卡前必读）
- `references/btc-full-card-pointer.md` — 全周期BTC完整卡指针（管辖在 tradingview-execution-card skill）
- `references/telegram-richmarkdown-delivery.md` — TG RichMarkdown 真表格投递管线（hermes send 纯文本 vs telegram_reliable.sendRichMessage）
- `references/phone-friendly-2table-format.md` — 手机端精简 2 表卡格式（2026-07-08 用户偏好）
- `references/main-indicator-action-grid-is-authority.md` — **主指标行动格是唯一方向源**（2026-08-31 P0 纠错，必读）
- `references/telegram-mobile-layout-v911.md` — Telegram手机端分析卡排版规范、常见失败形态与回归检查项（2026-09-03）。
- `references/telegram-image-rendering-pitfalls.md` — **Telegram 图片渲染坑**（2026-08-31 出图尺寸/高度/边距实战）
- `references/pil-render-v5-pitfalls.md` — **PIL 渲染器 v5 实战坑**（2026-08-31 多元组表格/None列宽/Image.BICUBIC等）

## v7.5 新增模块

- `scripts/zh_locale.py` — 中文本地化统一翻译层
- `scripts/tv_screenshot.py` — TV截图管线（加密15m主·黄金5m主·右侧价格栏+CVD）
- `scripts/topic_router.py` — 话题路由器（BTC→386·XAU→385·山寨→416）
- `scripts/daily_learn.py` — 每日学习引擎（08:30·10+社区·三维度轮换）
- `D:/Hermes agent/scripts/vwap_ema_cvd_engine.py` — VWAP+EMA+CVD本地引擎 + CVD冰山检测 + 多资产相关性

## 10+ 社区融合源

ICT/X · Freqtrade · NautilusTrader · Bookmap · TradingView · Reddit r/algotrading · Reddit r/Forex · ForexFactory · DailyFX · Telegram信号社区 · Investopedia · gold-api.com

## 验证

```bash
python -m pytest tests/ -q --tb=short -k \"not test_watchdog_ratelimit\"
# 必须全绿（2026-09-11 基线 751 passed；数量会增长，别把旧数字当验收门槛）
```

## 即时追踪问法：方向与路径先行（2026-09-11）

用户问“现在什么情况/偏多还是空/路径是什么”时，先给单一裁决，再给条件路径，不要复述整张卡：

1. 第一行明确 `↑偏多`、`↓偏空` 或 `○观望/方向未确认`；主指标行动格出现冲突、未收线、等解除、观望时，不能被副指标或分析者推算覆盖，裁决必须保持等待。
2. 路径按“当前价附近最近结构位 → 下一关键位 → 远端磁吸位”书写，每一步同时写触发条件和失效/转向条件；价格已经触及近端位后，必须更新到下一级，不可继续把旧近端位当唯一观察点。
3. 下跌后接近前低/磁吸位时，明确“偏空但不追空”；反弹后接近VWAP/VAH时，明确“偏多背景未确认/偏空反抽观察”，避免把方向判断写成即时下单指令。
4. 任何 `S3/S4`、副指标冲突、OI/CVD背离或缩量状态，都只降低确认度；不得生成执行三件套。普通追踪卡只保留现价、主指标结论、关键上下位、冲突、下一步。
5. 每轮加密追踪仍须先核验 Binance 价格与签名只读链路，并确保 TV 当前品种/周期与截图一致。若图表被后台任务切到别的品种，先恢复 `BINANCE:BTCUSDT.P/15m`，重新读取状态、行动格和截图，再引用任何关键位。

## 普通行情更新的首屏与精简排版（2026-09-12 用户确认）

当用户只说“看一下BTC/看下BTC/现在呢”时，使用轻量跟踪卡，不要把完整分析报告或15步审计正文倾倒到普通聊天。固定交付顺序：

1. **第一行必须是本轮新TradingView全屏截图**（价格轴+CVD/成交量窗格）；
2. 第二行只给一句结论：方向、现价、动作、北京时间；
3. 后续只保留一张窄表或短表格：当前位、最近结构位、上下关键位、主要冲突、下一步；
4. 只保留一个`⭐唯一主推`，不把A/B/X平铺成菜单；
5. 用户未要求“全面/完整/分析”时，不展开五周期管线、完整性审计、长篇数据源清单；状态只写必要的`live/降级/不可用`；
6. `WAIT/NO-GO`时只写观察触发与失效条件，不渲染Entry/Stop/Target。

“排版好看”在这里优先意味着信息层级清楚、截图先行、短句和窄表，而不是增加装饰、标题或审计字段。若切换品种/周期后`chart_get_state`与数据读数短暂错配，必须丢弃错配结果并重读后再截图，绝不能把错误品种的指标写进卡面。

## 完整图表显示与分析卡一致性（2026-09-11 用户明确要求）

分析卡不能只读取 `data_get_pine_tables` 的文字行动格；必须结合TradingView整张现场图表显示后再裁决。完整视觉核对至少包括：K线趋势/实体与加速或衰竭、价格轴当前位置、价值区/POC/VAH/VAL、VWAP、FVG/OB/BOS/MSS/摆动高低点、主图结构、底部CVD/成交量/持仓窗格、放量或缩量、突破是否收线，以及图表画面与行动格是否一致。

输出顺序固定：`唯一⭐最推荐方案 → 方向 → 路径 → 关键位 → 执行/等待 → 失效条件`。不得只给一组平行可能性，也不得把“方向判断”与“执行授权”混为一谈。若SVP行动格为冲突/未收线/等解除/观望，主推必须是“等待”，但仍要明确当前偏多或偏空背景及触发路径；AggVol只能确认、降级或否决，不能覆盖SVP。

截图必须作为证据而非装饰：确认品种、周期、价格轴、主图和CVD/成交量窗格均为目标状态；若整图视觉结构与行动格或Binance数据冲突，先标出冲突并降级，不得机械引用单字段。

## 常见陷阱

1. **不加载模板就出卡** — 已多次被纠正。第一步永远是 read_file master-template。
2. **双重反引号** — `_fmt_price` 已自带反引号，v7.1手机格式用 `_p()` 去反引号后自行封装。忘用 `_p()` 会导致 `` `63,884` ``（双重）。
3. **手机行长超标** — 每行超38字符 → Telegram自动折行 → 手机阅读体验差。拆行规则见上方。
4. **AB不对称** — 预案B必须与A格式一致（入场/止损/止盈/仓位/风险），不能缩写。
5. **B等待留空止损止盈** — 即使B等待也算 `_calc_stop_target_atr()`。标注"等触发"但不留空。
6. **XAU K线未缩放** — GC=F期货需 -125 调整至现货。
7. **patch工具f-string吞转义** — 修改含 `f\"...\"` 双引号的Python代码时，`\"` 可能被错误转义。改用 execute_code 或 write_file。
8. **Watchdog `.poll()` 不可用** — Windows Popen 可能返回不完整对象，`.poll()` 抛 AttributeError。已在 watchdog v1.3 修复为 pid_alive fallback。
9. **VWAP/EMA数据缺时③行不渲染** — 无K线数据时跳过③，不显示空行。
11. **Cron agent模式≠no-agent** — agent模式在脚本rc≠0时LLM接管→生成诊断报告→全文投递TG→噪音。no-agent=脚本stdout直发·零token·静默。数据采集类cron必须用no-agent。详见 references/tv-data-bridge.md。
12. **TV数据≠必须通过cron采集** — TV MCP需agent上下文调用。v7.2架设tv_data_bridge.py：行情守望.py主循环每5分钟subprocess调TV CLI(tv values/tables/lines/quote)→直写tv_dmi_cache.json→零噪音。不依赖agent·不占token·不投递TG。
13. **TV推送仅A多/A空/X** — B/C等级变化静默不推送。置信度阈值：六指标全共振(A级)或结构冲突(X级)才够格。
14. **5分钟刷新有理** — DMI等级15分钟收线才变·但VWAP/EMA/CVD值每tick在动·关键位距离每秒变。5分钟不空转不遗漏。
15. **话题路由不匹配** — 确认BTC→386·XAU→385·山寨→416。发卡前用 `topic_router.get_target(symbol)` 查目标。
16. **中文Kill Zone** — 卡片中Kill Zone标签已全量中文化（Asia→亚洲盘·London→伦敦盘·NY AM→纽约上午盘·NY PM→纽约下午盘）。出卡时勿用英文Kill Zone名。
17. **VWAP/EMA本地引擎** — 不依赖TV连接。`vwap_ema_cvd_engine.py` 从K线本地计算。含CVD冰山检测和多资产相关性检查。
18. **渲染用display_name不用name** — `monitor_levels.json`每层有`name`(内部ID如R1_reclaim_accept)和`display_name`(人读中文如阻1·近端收复)。所有渲染路径必须优先display_name。v7.5已全量修复(479d55f)。
19. **双层前缀Bug** — 数据源(model_dir_text)已含"引擎判"时渲染器不得再加"引擎"→产生"引擎引擎"。直接使用数据源值即可。
20. **N/A → 中文兜底** — `_sr_level/_chase_ok/_exec_line`等工具函数返回N/A→必须中文化(待确认/—)。用户看到的必须是中文。
21. **模板多版本统一** — `references/master-template-v68.md`（未落地·勿引）、`card-render-rules.md`、`monitor-template.md` 三份模板的版本号（文件头）必须一致。改一个时必须同步另外两个。版本号不一致会导致出卡路线冲突。进一步以 `pipeline_router` 和 card schema 的机器版本为准，历史技能中的步数/版本号不具备运行时证明力。
22. **禁止 `━━━` 分隔线** — 用户2026-06-22明确反馈"不要这些"。v8.0叙事卡全删分隔线，用空行自然分段。
23. **禁止 `—— 你来选方向 ——`** — 用户2026-06-22明确反馈"这个不要"。已从auto_card(2处)和行情守望(1处)全删。
24. **TV数据必须实时注入，不可显示"需TV确认"** — 用户2026-06-22严厉反馈："我就是要你结合我的TV来一起分析，你居然要我自己看"。每次出卡前必须尝试读取TV MCP数据（DMI表+指标值），无法获取时才标注"TV暂不可用"。
25. **审计必须实测跑管线** — 静态扫描发现不了函数不存在/变量未定义这类动态错误。2026-06-22教训：`_near_key_level`和`qty_unit`两处致命bug在静态审计中完全漏过。审计铁律：语法检查→实测 `python scripts/auto_card.py BTCUSDT && python scripts/auto_card.py XAUUSD`。
26. **脚本 canonical 目录为 `scripts/`（2026-06-29）** — 23 个脚本曾在 `scripts/` 和 `hermes/scripts/` 双目录存在且版本发散。已统一：`scripts/` 为 canonical，`hermes/scripts/` 副本已删除。所有执行和引用必须用 `scripts/` 路径。
27. **TG 推送发 RichMarkdown 必须用 telegram_reliable，不能用 hermes send（2026-07-08 确认）** — `hermes send` 发送纯文本（`sendMessage`），不会解析 RichMarkdown 表格，TG 上只显示 `|` 竖线。正确的通路：调用 `scripts/telegram_reliable.py` 的 `send_telegram_reliable(parse_mode='RichMarkdown')`，它会走 Bot API 10.1 `sendRichMessage` 渲染真表格。`auto_card.py` 第 3573 行推送段当前用 `hermes_cli.main send`（纯文本），应切换为 `telegram_reliable.send_telegram_reliable(parse_mode='RichMarkdown')`。cron 的 no-agent 模式（stdout→hermes send）也无法走 RichMarkdown，需要脚本自行调用 telegram_reliable 推送。
28. **render_v96.py 7 张表手机端过密（2026-07-08 已修复）** — `render_v96_card()` 已从旧 6-7 表段（双指标裁决·多周期定位·关键位矩阵·多源验证·矛盾点·执行预案·风控闸门）改成手机优化版：`【现在】→【做法】→ ①周期体温(emoji单行) → ②关键位(1表) → ③多源一句话(emoji锚点) → ④执行(1表) → 【裁决】`。实测 BTC/XAU 核心卡约 28 行，手机一屏半；完整版存档可继续追加订单流/ICT等附录，但 TG 推送用紧凑卡。相关测试已同步：`test_card_render_locked.py`、`test_format_alignment.py`。
29. **两种卡两套渲染器，不要混用（2026-07-08 已落地）** — 棠溪系统两个独立渲染路径已完成手机优化：

    | 版本 | 渲染器 | 新格式 | 推送场景 |
    |:---|:---|:---|:---:|
    | **完整版** | `render_v96_card()` (`scripts/render_v96.py`) | 2表+emoji叙事，约28-35行 | `auto_card.py --push` 手动调 |
    | **快速版** | `_render_push()` (`scripts/render_tv_card.py`) | 1表+3行，约10-11行 | cron 自动推 |

    同步改动：`references/master-template-v68.md`（未落地·勿引） 升级为 v9.7；`auto_card.py` 推送段从 `hermes_cli.main send` 切到 `telegram_reliable.send_telegram_reliable(parse_mode="RichMarkdown")`；截图仍先用 gateway MEDIA 发送，卡片走 RichMarkdown 真表格。实测 `BTCUSDT` 管线 10/10、`XAUUSD` 管线 7/8（TV降级预期），TG 回执 `True rich_sent`。

30. **唯一主推裁决，不要菜单式 A/B/X 平铺（2026-07-08 用户纠正·已落地 v9.8）** — 用户明确指出“裁决应该是最最适合的方案，最推荐1，前面一堆方案很有问题”。执行表必须改为 `| 优先级 | 条件/触发价 | 动作 | R:R |`：第一行 `⭐主推 {方向}` 或 `🔵主推 等` 或 `⚠️主推 禁做`，第二行 `🔁备选` 只作为主推失效后的路径，第三行 `⚠️禁止`。禁止把 A/B/X 渲染成同等可选菜单。已同步 `render_v96.py`、`render_tv_card.py`、`master-template-v68.md` 和相关测试；实测 `19 passed` + BTC/XAU `auto_card.py` exit 0。

31. **v9.9 手机驾驶舱不能压掉能力（2026-07-08 用户纠正·已落地）** — 用户上传主/副指标源码后明确指出：不能为了好看丢掉主指标/副指标能力、结构位前置、多周期定位。新版权威模板 `references/master-template-v68.md`（未落地·勿引） 升级为 v9.9：首屏必须 `【现在】{上方结构} · 现价 · {下方结构}`；完整卡固定 4表：`①周期体温/多周期定位`、`②关键位/结构关键位`、`③多源验证/双指标`、`④最推荐方案`；快速卡也必须含结构位夹层、D/4h/1h/15m/5m体温、SVP行、HALDRO行和订单流行。`render_v96.py` 与 `render_tv_card.py` 已同步，`auto_card.py` 将 klines + dual_indicator 透传给快速卡；实测 `19 passed` + BTC/XAU `auto_card.py` exit 0。

32. **`auto_card.py` 推送段代码位置（2026-07-08 确认）** — `auto_card.py` Step 6 是 TG 推送段，必须位于主流程下，不能缩进到 `if is_compact:` 里；v9.9快速卡通常超过10行，若 push 被 compact 条件门控，`--push` 会静默不发。卡片必须调用 `telegram_reliable.send_telegram_reliable(parse_mode='RichMarkdown')`，并以 `rich_sent` 回执作为上线验证；截图可先走 `hermes_cli.main send MEDIA:`。Cron no-agent 模式的脚本（`btc_ref_levels_sync.py`、`monitor/btc_watchdog.py` 等）不能依赖 `hermes send`，必须自己调用 `telegram_reliable.send_telegram_reliable()` 并设 `deliver: local` 以阻止纯文本投递。

33. **SVP `?` 不是有效等级，必须回退 MCP Data Window（2026-07-08 v9.9补丁）** — TV缓存可能写出 `grade="?"` / `处理="?"`，但同一缓存的 `indicators` 已有 `mcp_side_code`、`mcp_grade_code`、`mcp_target_price`、`mcp_cvd_value`。渲染快速卡前必须把 `?` 当作未知值，允许 `_build_tv_main_data()` / `_apply_tv_dmi_override()` 用 `MCP Side Code` + `MCP Grade Code` 恢复 `X/A多/A空/B多/B空/C反多/C反空/C等待`，并用 `结论` 替代 `处理="?"`；否则真实卡会出现 `SVP ? ?`，等同于没有使用主指标。回归测试：`tests/test_svp_unknown_regression.py`。
34. **棠溪 TG 排版铁律（2026-07-08 终版）** — 推送 = **文字 RichMarkdown 表格卡 + 主周期图表截图**两条消息：先 `send_telegram_reliable(parse_mode='RichMarkdown')` 发文字卡（`rich_sent`），再 `send_telegram_photo()` 发主周期 TV 截图（`photo_sent`）。截图必须发「主周期」图表：加密 15m、贵金属 5m（见 `tv_screenshot.capture_analysis_setup`，BTC→BINANCE:BTCUSDT.P/15m，XAU→OANDA:XAUUSD/5m）。多周期按看盘顺序 **D→4h→1h→15m→5m**（自上而下，背景→执行层），主周期行标 `⭐主`。落地：`render_v96.py`/`render_tv_card.py` 用 `TF_ORDER=("D","4h","1h","15m","5m")`；`auto_card.py` 推送段先发文字卡后发图；`telegram_reliable.send_telegram_photo` 新增（Bot API sendPhoto multipart）；`master-template-v68.md` 已同步。
35. **`tv_screenshot` 子进程 ABI 坑（2026-07-08 踩过）** — hermes venv 的 mcp/pydantic_core 是 cp311 编译，主进程若是 3.12 则 `import mcp` 报 `No module named 'pydantic_core._pydantic_core'`。`capture_analysis_setup` 必须子进程调 venv 自带 `venv/Scripts/python.exe` 跑，且**清理继承的 PYTHONPATH/PYTHONHOME**（否则 venv 子进程仍会 ABI 崩）。`__main__` 直接调 `_capture`，绝不能调 `capture_analysis_setup`（会递归 spawn 自身）。

37. **主指标行动格是唯一方向源，禁止被分析者逻辑覆盖（2026-08-31 重大纠错）** — 用户明确指出"我的指标不是有很多东西吗？比如SVP，vwap，ema，ICT等等你全面看看图表"——期望的是**主指标 SVP+ICT+VWAP+CVD 行动格的自带结论**，而不是分析者用技术指标推算出的方向。**铁律**：当 `data_get_pine_tables` 行动格结论含 `⚠冲突` / `⚠未收线` / `C等待` / `等收线` / `等解除` 时，**必须输出 C 级等待 / ⚠冲突**，禁止改写为 A 级做多/做空。**反例（本次事故）**：1h 主指标行动格结论 = `副S4降权·仅候选 ⚠冲突 · 等解除·新`、`方向 = 观望`、`现位 = 待·反抽nPOC·等MSS↓·13:00定`——明确 C 级等待 + 13:00 定时；15m 主指标 = `⚠冲突 ⚠未收线 · 等收线`、`方向 = 偏多·条件2/10`——也是 C 级等待 + 13:00 定时。但出卡时硬给"★A 级做空（推荐）"——**直接违背主指标结论，是 P0 错误**。**正例**：原样引用"主指标 15m: ⚠冲突+⚠未收线 → C级等待"，多空双向触发条件分别列出（"触发多: 13:00定时后 MSS↑ + 站回VWAP + 收线"、"触发空: 跌破VAL + OI共识>80% + CVD转正"），**让用户根据后续行情自己判断**。**判定流程**：先读 `data_get_pine_tables` 主指标行动格 → 若结论字段含 ⚠/C/等/观望/冲突/未收线 中任一，**整张卡方向=C级等待**，不可降级为 A。副指标 Composite 跨周期矛盾（15m +21 vs 1h −21）也支持 C 级判定，但不能推翻主指标。详见 `references/main-indicator-action-grid-is-authority.md`。
38. **Telegram 图片预览框高度截切（2026-08-31 实战铁律）** — 用户手机 2160×3840 (9:16)。Telegram iOS/Android 客户端对**长宽比异常**的图片有"等比缩放显示到屏幕宽"的行为：① 高度 > ~2200px 的图，预览框只能显示上半部分（约 50-70%），下半部分被遮；② 宽度 > 1080px 的图，缩放后右侧留白多；③ 图本身是完整的（用 PIL crop 验证过），问题在客户端渲染策略。**解决方案**：① **宽 ≤ 1080px**（手机宽度），Telegram 不再横向撑满；② **高 ≤ 2000px**（预览框安全阈值），或使用 1080×2021 这种"手机宽+略高"的尺寸；③ **重要：先发图后发卡**——单图单独发，避免连续发图被压缩成小图；④ 不要嵌 TV 截图到分析卡内（用户多次明确"应该是两张照片，分开发"），**截图独立 + 分析卡独立两张**；⑤ 如果是 1920×3444 那种"准9:16长图"，Telegram 会**纵向裁切**到约 60% 高度——绿色推荐框/时间窗/下一步行全部丢失。**踩坑点**：调试时用 `Image.open().size` 看图尺寸没用（看到的是原始像素），要看 Telegram 端"消息预览框"的可见高度——通常手机端 = 屏幕高度 × 0.6。**图本身完整但客户端截切 = 用户的反馈是"看不到了"或"下面没有了"——这不是图的问题，是尺寸问题**。**实战可用尺寸**：1080×1613（v9.6 完整版）、1080×2021（手机宽 + 标准高度）、2160×3840（设备原生分辨率，但**Telegram 仍会预览裁切**）。详见 `references/telegram-image-rendering-pitfalls.md`。
40. **"好难看/信息不够"= 结构扩列（2026-08-31 v5 教训）** — 用户对 v4 卡片反馈"这个照片好难看，信息不够"。**根因不是视觉问题，是信息维度缺失**。视觉调色（红/绿/蓝填充、徽章、●色块）只解决"好看"；要解决"信息不够"必须**结构性扩列**，缺一不可：

    ① **TV 截图嵌入**（真实 K 线，360×280 缩略图放在信号矩阵左侧）——证明"现场看过盘"，替代虚构的 sparkline
    ② **多周期简表**（15m/1h/4h/1D × 结论 × 关键位 × 评级）——一行一周期，4 行结构
    ③ **监控检查单**（5-7 价位 × 含义 × 触发动作）——用户最关心的"到了 X 价位该做什么"
    ④ **A/B 方案并排对比**（左右双色块，入场/止损/目标对称）——不是 callout 文字，要可视化

    **铁律**：用户说"信息不够/难看/单薄/丰富一点"时，**默认走 v5 完整结构**（10 块版式：标题+徽章+4KPI+多周期+TV缩略信号矩阵+Binance票+监控检查单+A/B对比+风险条+callout），不要再做只调色不扩列的 v4 路线。`scripts/render_analysis_card.py` v5 已支持以上所有 10 块调用。**反例（本次事故）**：v4 调色后用户仍说"信息不够"——单纯改色是 P0 失误。

41. **PIL 渲染器 `_draw_table` 通用化坑（v5 实战·已修复）** — `scripts/render_analysis_card.py` 升级到 v5 时表格函数必须支持 **2/3/4 元组混用**（不同时段不同表）：

    - 2-tuple `(val, level)` — 表格只有"数值+评级"
    - 3-tuple `(label, val, level)` — 表格"维度+数值+评级"
    - 4-tuple `(price, meaning, action, level)` — 监控检查单"价位+含义+动作+评级"

    `_draw_table` 第一个 if 链必须用 `isinstance(cell, tuple) and len(cell)==N` 分支而不是 `tuple2 = (val, level); tuple3 = (lbl, val, level)` 这种 unpack，否则一列 4 元组就崩。**典型错误**：`val, level = cell` 收到 4 元组 → `ValueError: too many values to unpack (expected 2)`。**还有**：`col_w=[180, 200, None]` 这种带 `None` 的列宽不能直接传，必须在函数里替换为 `inner_w - sum(cw[:-1])` 或干脆不传 col_w 让函数均分。详见 `references/pil-render-v5-pitfalls.md`（待补）。

42. **v9.10 排版精简四件套（2026-07-11 落地）** — 用户要求"排版好看一些"，四项改动同时落地两个渲染器 + 模板：

    - **结构位「用法」列去内部ID**：`_level_kind()` 返回三元组 `(label, icon, use)`，`use` 用中文语义（`VWAP均价锚`/`VAH上沿阻力`/`VAL下沿支撑`/`POC密集区`），不再显示 `5mVWAP`/`1hVWAP` 等内部拼接名。
    - **订单流压缩**：`_multi_source_line()` 去掉 `cvd_quality`/`taker_ratio`/`haldro_confirm`/`kill_zone` 四个冗余字段，只保留 `CVD方向`/`主动方向`/`费率`/`恐贪`，行宽从 ~80 字压到 ~40 字。
    - **HALDRO 精简**：`_dual_short()` 中 `hal` 截断从 34 字缩到 24 字，去掉"配合主指标 A空 = 可做"等冗余后缀。
    - **快速卡加裁决收尾**：`_render_push()` 末尾加 `【裁决】{方向} · 主副指标已纳入 · 不追单`，双指标 SVP+HALDRO 合并为一行。模板 `master-template-v68.md` 同步升级 v9.10。

43. **Bloomberg 终端风格（v6/v7 实战·2026-08-31 落地）** — 用户对 v5 反馈"信息不够"被 pitfall 40 记录后，v6→v7 进一步走 Bloomberg/TradingView 终端化（Fortress / Vault 风格）。**铁律**：`scripts/render_analysis_card.py` 升级到 v7 时**数字用 Consolas 等宽**+**段间距加大**+**顶部状态条**+**去掉内嵌 TV 截图**——四件套缺一不可。
    - **数字字体 = Consolas**（`C:/Windows/Fonts/consola.ttf` + `consolab.ttf` 粗体）：数字/英文/标点走等宽，价格自动对齐。中文 = `msyh.ttc`（微软雅黑）+ `simhei.ttf`（黑体粗标题）。`consolai.ttf` 斜体备用。
    - **字号体系**：KPI 60 / 标题 42 / 表头 26（粗黑体）/ 标签 22 / 脚注 22。数字单独体系：等宽 26（普通）/ 26（粗体）。
    - **行高 = 60**（v4-v5 是 46-56，挤）。表头高度 50。段间距 22。
    - **顶部状态条**（`status=[(text, level), ...]`）：`TV✓ Binance✓ CoinGecko✓ ⏲ 下一根 15m 14m55s 🕐 资金费 00:12:43`——横排蓝底小框，宽度内紧凑放 5-6 项；触发时高亮 warn 色，倒计时走 white。
    - **不要嵌 TV 截图到分析卡**——用户 2026-08-31 明确"这个截图好垃圾，要分开"。正确做法：**先发一张全屏 TV 主周期截图（含价格轴+CVD），再发一张分析卡 PIL PNG，两条消息分开推 TG**。嵌入版（v5 `_draw_tv_thumb` 360×280 缩略图）已在 v7 弃用，函数已删。
    - **配色深底高对比**：`#0E0E12` 底 / `#2563EB` 蓝表头 / `#4ADE80` 绿 / `#EF4444` 红 / `#F59E0B` 橙。**深色填充色要够暗才看得出**：`RED_BG = #3A0808`（不是 #1F0707，#1F0707 在黑底上看不出）/`GRN_BG = #062812`/`BLU_BG = #0B1F3A`。**踩坑**：v4 用 #1F0707 视觉模型识别为"只有黑底+红边"，v5 改 #3A0808 才"深红底+红框"。

44. **PIL 渲染器 v6/v7 表格契约必须统一（2026-08-31 教训）** — v5→v7 升级时 `_draw_table` 反复出 ValueError 4 次，根因是**调用方传入元组长度不统一**：
    - 2-tuple `(val, level)`：mini_tf 早期 / 简化
    - 3-tuple `(label, val, level)`：binance / 信号矩阵
    - 4-tuple `(price, meaning, action, level)`：monitor 监控检查单
    **铁律**：调用前先看自己字段数，传 `[(p, m, a, lv), ...]` 还是 `[(l, v, s), ...]`。`_draw_table` 的 if 链必须 `isinstance(cell, tuple) and len(cell)==N` 分支，**禁止 `val, level = cell`**（4 元组会炸）。**col_w 不要带 None**（v5 留过 `col_w=[180, 200, None]` 这种坑，被 `TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'` 砸中），必须函数内自动算或干脆不传让函数均分。**Image 缩放**：`PILImage.LANCZOS`/`Image.BICUBIC` 在 LSP 严格模式下会被 pyright 报"未知属性"，改用 `im.resize((w,h), 3)`（3 = BICUBIC 整数别名）。**`img.paste()`** 在 `_draw_tv_thumb` 子函数中报错时（v5 删函数前踩过），要用 `draw._image.paste(im, (x, y))`——因为 `img` 没传进子函数。详见 `references/pil-render-v7-bloomberg-style.md`（v7 风格参考） + `references/pil-render-v5-pitfalls.md`（v5 表格坑参考）。

45. **候选价只认 FinalVerdict.watch_*（2026-09-11 定版指标对齐·P0）** — 定版指标把「观察价」与「执行导出」彻底分开，渲染层必须跟着分。四条铁律：

    - **只读 `FinalVerdict.watch_*`**，永不回落到原始 `entry/stop/target`（推送卡旧代码有过「B/C 时把裸 entry 回填成 candidate_entry」的旁路，已删）。
    - **两份渲染器共用一份候选判定**：`render_tv_card.candidate_view` 对外暴露，`render_v96` import 它。候选规则只允许一个实现——两份实现必然漂移。
    - **watch 元组不完整 → 卡面写「候选数据不完整」，不补半个订单**；R:R 由元组**现算**（`|标-入|/|入-止|`），不信上游 `rr` 字段。
    - **未授权时主动剥价**：`风控`/`路径` 两行里的 `入/止/标/候选` 数字与 `x.xA`、`x.xR` 用正则剥除；**磁吸/结构/现位里的价位是行情事实，不剥**（否则误伤正常读数）。

    附两条易漏：**失效价 = 止损价**，同属订单三件套，完整报告卡的 `inv_line` 也必须挂 `final_executable` 闸（否则 NO-GO 卡面照样打印计划失效价）；**内部枚举不得上图** —— `FinalVerdict.reason` 是 `location/trigger/bar_closed/...` 机器码，卡面要用中文原因链（`no_trade_reasons`），否则用户看到 `SVP：C等待 等待：location/trigger/...`。

    唯一主推行现在有**三种形态**：`⭐主推 多/空`（GO-A 且几何有效）、`⭐主推 等待`（WAIT，带候选时写「【人工候选，未授权】」）、`⭐主推 禁做`（NO-GO/X）。全卡只能有一条 `⭐主推`。

    **授权标签判据**（别记错）：主指标「风控」行只有 **3 个标签**（`风控` / `风控·观察` / `风控·未授权`），`禁做·不出价` 是 `setupX` 时的**行值**而非标签；只有字面 `风控` 是授权出口。详见 `tradingview-indicator-analysis` -> `references/indicator-contract-drift-guard.md`（未落地·勿引）。
