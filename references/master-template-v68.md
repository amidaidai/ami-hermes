# 棠溪分析卡 · 主模板 v9.10（手机驾驶舱 · 结构位前置 · 双指标全用 · 唯一主推裁决 · 排版精简）

定位：这是棠溪 Telegram 交易驾驶舱的权威输出模板。v9.10 在 v9.9 基础上精简排版：结构位用法去内部ID、订单流压缩、HALDRO精简、快速卡加裁决收尾。

## 权威铁律

1. 每次正式分析前必须读取本文件；对话内加密/XAU每轮更新必须首行附本轮TradingView全屏截图（含价格轴+CVD窗格）；推Telegram时截图与RichMarkdown文字卡分开发送，文字表格仍走RichMarkdown。
2. 时间一律北京时间中文格式：`2026年7月8日14：30`，不用 UTC，不用 BJT 后缀。
3. 首屏先给结论，但结论必须带结构上下文：价格前面要有 `🔴VAH/VWAP/POC/VAL/FVG/阻` 与 `⚖现价` 的夹层结构。
4. 裁决必须是唯一主推：第一行 `⭐主推` 只有一个；`🔁备选` 只作为主推失效后的路径；禁止 A/B/X 菜单式平铺。
5. 完整卡必须显式使用双指标：`SVP主驾驶` + `HALDRO副驾驶` + `订单流/多源`。不能只写“多源验证一句话”。
6. 加密卡必须显式五周期，按棠溪看盘顺序 **D → 4h → 1h → 15m → 5m**（自上而下，背景→执行层）；贵金属主周期 5m、加密主周期 15m。快速卡也要一行五周期体温（同顺序），完整卡用表格，主周期行标 `⭐主`。
7. 结构位表必须包含：VAH/VWAP/POC/VAL/FVG/nPOC/阻支中能读到的最近6个；列为 `结构位 | 价格 | 用法 | 距现价`。
8. Telegram 真表格必须走 Bot API 10.1 `sendRichMessage` + `RichMarkdown`；普通 `hermes send` 不算。
9. 最终状态只允许：`GO-A` / `GO-B` / `WAIT` / `NO-GO`；旧A/B/C/X仅作指标等级，不得决定执行权。
10. R:R < 1:2 不得输出为可执行方案；只能观察、禁做或重算。
11. 单笔风险≤1%，硬上限 10U。
12. 中文优先。允许保留 BTC、USDT、VWAP、EMA、CVD、OI、Funding、Spot、FVG、OB、ATR、R:R、DXY。
13. 正文不给 `setup_id/model_id/entry_tag` 等机器字段。
14. emoji 视觉锚点：🟢多/有利 · 🔴空/不利 · 🔵等 · ⚖现价/中轴 · ⚠️警告 · ⭐唯一主推 · 🔁备选失效路径。

## 完整分析卡模板（v9.9 · 驾驶舱版）

```markdown
📊 {DISPLAY_SYMBOL} · {TIME_CN} · {STATUS_EMOJI}{STATUS} · {BIAS}
【结构】{UP_LEVEL}｜⚖现{PRICE}｜{DOWN_LEVEL}
【主推】{DIR_OR_WAIT} · {TRIGGER} · {RR_OR_WAIT}
【依据】SVP {SVP_STATE}｜HALDRO {HALDRO_STATE}｜{DUAL_VERDICT}

① 周期体温 / 多周期定位（D→4h→1h→15m→5m）
| 周期 | SVP主指标 | HALDRO副指标 | 位置 |
|:---:|:---|:---|:---|
| D | {D_SVP} | {D_HALDRO} | {D_VWAP_POS} |
| 4h | {4H_SVP} | {4H_HALDRO} | {4H_VWAP_POS} |
| 1h | {1H_SVP} | {1H_HALDRO} | {1H_VWAP_POS} |
| 15m ⭐主 | {15M_SVP} | {15M_HALDRO} | {15M_VWAP_POS} |
| 5m | {5M_SVP} | {5M_HALDRO} | {5M_VWAP_POS} |
→ 主执行{MAIN_TF} · 自上而下确认（D背景→{MAIN_TF}执行）

② 关键位 / 结构关键位

|:---|:---:|:---|---:|
| 🔴VAH/VWAP/阻/FVG | `{R1}` | {R1_USE} | {R1_DIST} |
| ⚖POC/VWAP | `{MID}` | {MID_USE} | {MID_DIST} |
| 🟢VAL/支/FVG | `{S1}` | {S1_USE} | {S1_DIST} |

③ 多源验证 / 双指标与多源验证
| 能力 | 读数 | 裁决 |
|:---|:---|:---|
| SVP主驾驶 | {SVP_ACTION_GRID} | 结构/入场/止损/目标优先 |
| HALDRO副驾驶 | {COMPOSITE/OI/CVD/CONFIRM} | {同向/冲突/不足} |
| 订单流 | CVD{CVD} · 主动买卖{TAKER} · Funding{FUNDING} | CVD/OI不配则降级 |
| 质量 | 覆盖{COVERAGE} · 量能{VOLUME} · 爆仓{LIQ} | 覆盖不足不追 |

④ 最推荐方案
| 优先级 | 条件 | 动作 | R:R |
|:---|:---|---|---:|
| ⭐主推 {DIR_A} | `{ENTRY_A}`确认 | {DIR_A} `{ENTRY_A}` 损`{STOP_A}` 标`{TARGET_A}` | 1:{RR_A} |
| 🔁备选 {DIR_B} | 主推失效后反向确认 | 只作失效路径，不与主推平权 | 观察 |
| ⚠️禁止 | 追单/数据过期/主副冲突 | 夹击+去杠杆+R:R不足 | — |

【裁决】{ONE_LINE_VERDICT} · 风控{RISK}U · {LEVERAGE}
失效 `{INV_LINE}` · 数据{DATA_GRADE} · 主副指标已纳入
```

## 快速更新模板（v9.10 · 11行左右）

```markdown
📊 {SHORT_SYMBOL} · {TIME_CN}
{UP_LEVEL}｜⚖现{PRICE}｜{DOWN_LEVEL}
{DIR_EMOJI}{DIRECTION} · {GRADE_EMOJI}{GRADE} · {CONCLUSION}
D{D_EMOJI} · 4h{4H_EMOJI} · 1h{1H_EMOJI} · 15m{15M_EMOJI} · 5m{5M_EMOJI}

| 优先级 | 触发价 | 操作 |
|:---|:---:|:---|
| ⭐主推 {DIR} | {ENTRY} | {DIR} 损{STOP} 标{TARGET} |
| 🔁备选 {REV_DIR} | {MAGNET} | 主推失效后再看 |
| ⚠️禁止 | 追单/冲突 | 主副不共振不做 |

SVP {SVP_ACTION} · HALDRO {HALDRO_ACTION} · {DUAL_VERDICT}
持仓{OI} · CVD{CVD} · 量{VOLUME} · 覆盖{COVERAGE}
【裁决】{DIR_EMOJI}{DIRECTION} · 主副指标已纳入 · 不追单
```

## 社区对标结论

| 来源 | 吸收点 | 落地 |
|:---|:---|:---|
| Telegram信号社区 | 必须有交易对、方向、入场、止损、目标 | ④最推荐方案保留执行三件套 |
| TradingView多周期Dashboard | 一眼看多周期共振/冲突 | ①多周期定位固定五层 |
| Bookmap订单流方法 | 微观订单流必须放在高周期结构上下文里 | ③双指标与多源验证：CVD/OI不配降级 |
| ICT/SMC社区 | 结构位、FVG、扫流动性比单指标重要 | ②结构关键位 + 结构位前置 |
| 机构Dashboard | 首屏先给当前位置和动作 | 【结构】【主推】【依据】三行 |

## 渲染器映射

| 场景 | 渲染器 | 要求 |
|:---|:---|:---|
| 完整卡 | `render_v96_card()` | 4表：多周期/结构位/双指标/最推荐 · 结构位用法去内部ID · 订单流精简 |
| 快速卡 | `render_tv_card(..., mode="push")` | 结构位前置 + 五周期行 + 1张执行表 + 双指标合并一行 + 裁决收尾 |
| 推送通道 | `send_telegram_reliable(parse_mode='RichMarkdown')` / `telegram_reliable.send_telegram_reliable(parse_mode="RichMarkdown")` | 必须 RichMarkdown 真表格 |
