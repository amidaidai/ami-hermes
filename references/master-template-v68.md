# 棠溪分析卡 · 主模板 v9.12（手机驾驶舱 · 结论前置 · 角色制关键位 · 唯一主推裁决 · 排版精简）

定位：这是棠溪 Telegram 交易驾驶舱的权威输出模板。v9.12 在 v9.11 基础上做「减法 + 角色化」：完整卡从 120 行压到 ≤40 行，位表/多源表不再搬运指标输出，改为回答「上面卡哪 / 中间看什么 / 下面废哪」。截图负责结构，文字负责决策。

## 权威铁律

1. 每次正式分析前必须读取本文件；对话内加密/XAU每轮更新必须首行附本轮TradingView全屏截图（含价格轴+CVD窗格）；推Telegram时截图与RichMarkdown文字卡分开发送，文字表格仍走RichMarkdown。
2. 时间一律北京时间中文格式：`2026年7月8日14：30`，不用 UTC，不用 BJT 后缀。
3. 首屏先给结论，但结论必须带结构上下文：价格前面要有 `🔴VAH/VWAP/POC/VAL/FVG/阻` 与 `⚖现价` 的夹层结构。
4. 裁决必须是唯一主推：第一行 `⭐主推` 只有一个；`🔁备选` 只作为主推失效后的路径；禁止 A/B/X 菜单式平铺。`⭐` 只在真正可执行（GO-A）时点亮，等待/禁做沿用 `🔵主推 等确认` / `⚠️主推 禁做` 前缀。
5. 完整卡必须显式使用双指标：`SVP主驾驶` + `HALDRO副驾驶` + `订单流/多源`。不能只写“多源验证一句话”。
6. 加密卡必须显式五周期，按棠溪看盘顺序 **D → 4h → 1h → 15m → 5m**（自上而下，背景→执行层）；贵金属主周期 5m、加密主周期 15m。**完整卡 = 一行体温条 + 一行副读**（v9.12 起由宽四列表降为行，五周期与主周期标记 `⭐` 仍必须全部出现）；快速卡同样保留一行五周期体温（同顺序）。
7. 关键位表为**角色制 ≤4 行**：`上沿阻力簇 / 近端转撑 / 主观察 / 失效·支撑带`。相邻 <0.15% 的位先并簇成区间（`77,847`+`77,865` → `77,847–77,865` 阻力簇）；其余结构位与 24h 极值下沉表下「远端」注脚，不逐行占卡面。
8. Telegram 真表格必须走 Bot API 10.1 `sendRichMessage` + `RichMarkdown`；普通 `hermes send` 不算。
9. 最终状态只允许：`GO-A` / `GO-B` / `WAIT` / `NO-GO`；旧A/B/C/X仅作指标等级，不得决定执行权。
10. R:R < 1:2 不得输出为可执行方案；只能观察、禁做或重算。
11. 单笔风险≤1%，硬上限 10U。
12. 中文优先。允许保留 BTC、USDT、VWAP、EMA、CVD、OI、Funding、Spot、FVG、OB、ATR、R:R、DXY。
13. 正文不给 `setup_id/model_id/entry_tag` 等机器字段。
14. emoji 视觉锚点：🟢多/有利 · 🔴空/不利 · 🔵等 · ⚖现价/中轴 · ⚠️警告 · ⭐唯一主推 · 🔁备选失效路径。
15. **上限与去重（v9.12）**：完整卡正文 ≤40 行；每张表 ≤3 列；同一事实只写一遍 —— 禁止同时出现「结构位表 + 关键位表」「做法表 + 裁决行」这类重复；装饰性 `｜`/分隔线一律不出现在卡面。
16. **数据源状态压一行**：③ 表下固定一行 `已入FinalVerdict：… ；仅展示/辅助：…`，不给每个源一行。

## 完整分析卡模板（v9.12 · 驾驶舱版）

```markdown
📊 {DISPLAY_SYMBOL} · {TIME_CN} · {SESSION}时段 · {STATUS_EMOJI}{STATUS} · {BIAS}
{⭐/🔵/⚠️}主推 {NAME}：{TRIGGER} · {EXEC} · R:R {RR}
结构：⚖现价 {PRICE} · 🔴上 {UP_PRICE}（{UP_KIND}） · 🟢下 {DOWN_PRICE}（{DOWN_KIND}）
VWAP/EMA：VWAP `{VWAP}`（价在上/下·{BAND}） · EMA9/55 `{EMA9}`/`{EMA55}` · {TREND}

① 周期体温 D{E} {D_STATE} · 4h{E} {4H_STATE} · 1h{E} {1H_STATE} · 15m⭐{E} {15M_STATE} · 5m{E} {5M_STATE}
副读 D{CVD} · 4h{CVD} · 1h{CVD} · 15m{CVD} · 5m{CVD}

② 关键位 / 结构关键位

| 角色 | 价位 | 距现价 |
|:---|:---:|:---:|
| 🔴 上沿阻力簇·{UP_KIND} | `{UP_LO}–{UP_HI}` | {UP_DIST_LO}~{UP_DIST_HI} |
| 🟢 近端转撑·{MID_KIND} | `{MID}` | {MID_DIST} |
| 🟢 主观察·{POC_KIND} | `{POC_LO}–{POC_HI}` | {POC_DIST_LO}~{POC_DIST_HI} |
| 🟢 失效/支撑带·{DN_KIND} | `{DN_LO}–{DN_HI}` | {DN_DIST_LO}~{DN_DIST_HI} |
远端：{FAR_KIND} {FAR_PRICE} ／ {FAR_KIND2} {FAR_PRICE2}

③ 多源验证 / 双指标

| 能力 | 读数 | 裁决 |
|:---|:---|:---|
| SVP主驾驶 | {SVP_ACTION_GRID} | 结构/入场/止损/目标优先 |
| HALDRO副驾驶 | {COMPOSITE/OI/CVD/CONFIRM} | {同向/冲突/不足} |
| 订单流 | CVD{CVD} · 主动买卖{TAKER} · Funding{FUNDING} | CVD/OI不配则降级 |
| 质量 | 覆盖{COVERAGE} · 量能{VOLUME} · 爆仓{LIQ} | 覆盖不足不追 |
已入FinalVerdict：{源A live · 源B live}；仅展示/辅助：{源C stale_cache · 源D cache}

④ 最推荐方案

| 优先级 | 条件 | 动作 |
|:---|:---|:---|
| {⭐主推/🔵主推 等确认/⚠️主推 禁做} | {TRIGGER} | {EXEC} · R:R {RR} |
| 🔁备选 {DIR_B} | 主推失效后反向确认 | 只作失效路径，不与主推平权 |
| ⚠️禁止 | 不做单：不追单·主副不共振 | 数据失效不执行 |

【裁决】{ONE_LINE_VERDICT} · 风控{RISK}U · {LEVERAGE}
失效 `{INV_LINE}` · 价格共识{DATA_GRADE}（非全源健康度） · 源状态见③
```

## 快速更新模板（v9.11 · 手机窄卡）

```markdown
📊 {SHORT_SYMBOL} · {TIME_CN}
{DIR_EMOJI}{DIRECTION} · {GRADE_EMOJI}{GRADE}
**{CONCLUSION}**
现价 `{PRICE}` · 日高 `{HIGH}` · 日低 `{LOW}` · `{CHANGE}%`
D{D_EMOJI} · 4h{4H_EMOJI} · 1h{1H_EMOJI} · 15m{15M_EMOJI} · 5m{5M_EMOJI}

| 结构 | 价格 | 距现价 |
|:---|:---:|:---|
| {UP_LEVEL} | `{UP_PRICE}` | {UP_DIST} |
| ⚖现价 | `{PRICE}` | — |
| {DOWN_LEVEL} | `{DOWN_PRICE}` | {DOWN_DIST} |

| 执行 | 触发/价格 | 风险与目标 |
|:---|:---|:---|
| ⭐主推 {DIR} | {ENTRY} | 损{STOP} · 标{TARGET} |
| 🔁失效看{REV_DIR} | {MAGNET} | 主推失效后再看 |
| ⚠️禁止 | 追单/冲突 | 主副不共振不做 |

| 验证 | 当前读数 | 作用 |
|:---|:---|:---|
| SVP主驾驶 | {SVP_ACTION} | 结构与执行 |
| HALDRO副驾驶 | {HALDRO_ACTION} | {DUAL_VERDICT} |
| 订单流 | 持仓{OI} · CVD{CVD} · 量{VOLUME} · 覆盖{COVERAGE} | 确认/降级 |

**下一步**：{DIR_EMOJI}{DIRECTION} · 主副指标已纳入 · 不追单
**失效**：{INVALIDATION}
```

## v9.12 变更清单（2026-09-14 用户批准「按建议推进」）

| 变更 | 旧（v9.11） | 新（v9.12） |
|:---|:---|:---|
| 首屏 | 【现在】结构位表 + 【做法】决策摘要表 | ⭐主推行 + 结构夹层行（单行） |
| ① 多周期 | 4 列 × 5 行表 | 一行体温条 + 一行副读 |
| ② 关键位 | 最近 7 个位平铺（4 列） | 并簇 → 角色制 ≤4 行（3 列）+ 远端注脚 |
| ③ 多源 | 每源一行（实测 14 行） | 4 行 + 源状态一行 |
| ④ 方案 | 3 行表（4 列）+ 独立【裁决】+ 失效行 | 3 行表（3 列）+ 【裁决】/失效两行 |
| 全卡 | ~120 行 | ≤40 行 |

实现落点：`scripts/render_v96.py::render_v96_card`（完整卡）、`scripts/render_tv_card.py::_render_push`（快速卡）。

## 社区对标结论

| 来源 | 吸收点 | 落地 |
|:---|:---|:---|
| Telegram信号社区 | 必须有交易对、方向、入场、止损、目标 | ④最推荐方案保留执行三件套 |
| TradingView多周期Dashboard | 一眼看多周期共振/冲突 | ①体温条固定五层 + 主周期标记 |
| Bookmap订单流方法 | 微观订单流必须放在高周期结构上下文里 | ③双指标与多源验证：CVD/OI不配降级 |
| ICT/SMC社区 | 结构位、FVG、扫流动性比单指标重要 | ②角色制关键位 + 远端注脚 |
| 机构Dashboard | 首屏先给当前位置和动作 | 首屏三行（品种/主推/结构） |

## 渲染器映射

| 场景 | 渲染器 | 要求 |
|:---|:---|:---|
| 完整卡 | `render_v96_card()` | 首屏三行 + 体温条 + ②③④ 三窄表 + 裁决块；每表≤3列；全文 ≤40 行 |
| 快速卡 | `render_tv_card(..., mode="push")` | 首屏结论 + 结构表 + 执行表 + 验证表；每表≤3列，表格块前留空行 |
| 推送通道 | `send_telegram_reliable(parse_mode='RichMarkdown')` / `telegram_reliable.send_telegram_reliable(parse_mode="RichMarkdown")` | 必须 RichMarkdown 真表格 |
