---
name: tangxi-tg-report-standard
description: 棠溪交易系统 · 所有推 Telegram 的情报/报告类脚本的格式与质量铁律。覆盖 RichMarkdown 真表格、末尾总体结论、置信度降序排序、表情侧重点、富文本加粗重点、决策厚度。当用户要求"报告太简单/加结论/按自信度排/加符号表情/重点突出/加粗/统一TG格式"，或重构/新建任何推 TG 的 collector 或 cron 报告脚本时加载。与 xau-analysis-format（XAU分析卡叙事结构）互补但不重叠——本技能管"数据表型情报报告"，后者管"分析卡叙事卡"。
triggers:
  - 用户说"报告太简单/信息不够/做得更厚"
  - 用户说"要有结论/加总体结论/简洁一点"
  - 用户说"自信度排前面/按分数排/有机会排前"
  - 用户说"为什么没有符号/多加表情/侧重点用符号"
  - 用户说"统一TG格式/推TG的表格"
  - 用户说"盈亏比太小/要达到2/不达到先别发方案"
  - 用户说"执行计划要带分析/不能只列数字"
  - 用户说"把某某分析能力融进来/用上已有能力验证/多方面验证是不是支持"
  - 用户说"推送太频繁/信息太多/TG轰炸/减少推送"
  - 改造/新建任何 scripts/*_collector.py 或 cron 报告脚本
---

> **同族导航** — TG投递组 5 个技能各司其职，别加载错 （同族入口：`tangxi-tg-delivery-format`）
> · **本技能 `tangxi-tg-report-standard`** = 报告质量铁律（总体结论、置信降序、决策厚度）
> · 同族其余：`tangxi-tg-delivery-format`（入口 · 投递格式铁律（纯 Markdown 管道表 / RichMarkdown 真表格 / 禁图片表））、`tangxi-tg-reports`（4 个 topic 架构 + 脚本改造通用规范（最短版））、`tangxi-tg-rich-reporting`（RichMarkdown 通道与「静默 collector」改造模板、做厚方法）、`telegram-delivery-reliability`（投递可靠性加固（重试/格式化守卫））
> · 组内改动请同步其余成员的触发词，避免同名族抢触发。


# 棠溪推 TG 报告格式与质量铁律

棠溪系统有 19 个 cron 任务、4 个 TG topic（846 情报/提醒、416 auto_card 交易卡、386 BTC分析卡、其余看门狗）。本技能管"数据表型情报报告"的统一标准——所有推 TG 的 collector / 报告脚本都必须遵守。

## 六条铁律

1. **纯 Markdown 管道表 + RichMarkdown 渲染，绝不图片、绝不退化**
   - 推送统一走 `telegram_reliable.push_tg_rich(target, text)` → 底层 `sendRichMessage`（真表格渲染）。
   - 禁止 `hermes send` / cron 默认 Deliver 通道：它们走 `MARKDOWN_V2`，**不渲染管道表**，退化成裸 `|`。
   - 禁止图片表（`tg_table_card.py` 这类 PIL 生成器）——用户明确"不要照片的表格，我很讨厌照片的表格"。
   - `telegram_direct.send_telegram_direct` 已修为默认 `RichMarkdown`（仓库内已改），调用它也可。

2. **每个报告末尾必须有简洁总体结论**
   - 格式：`**总体结论**: <一句话决策>。`
   - 要决策导向（偏多/偏空/规避/观望 + 原因），不是复述数据。
   - 无信号/平静也要给一句（如"市场平静，无中高置信异动，不追单"）。

3. **按置信度/评分降序排，高置信与有机会的排最前**
   - Orion 等候选类：候选表**置信列前置**，带等级符号 ⭐高(≥6)/🔸中(4–5.9)/⚪低(<4)，`sort(key=confidence, reverse=True)`。
   - 高评分+量价齐升的天然排前；禁抄底/去杠杆排后。

4. **侧重点用表情符号，密度要够**
   - 方向/多空：🟢强多 / 🔴强空 / ⚪中性
   - 偏离%：▲涨 / ▼跌 / →平
   - 信号强弱：🔥(OI扩张>5%) / 💰(负费率) / ⚠️
   - 置信等级：⭐🔸⚪
   - 恐惧贪婪：😱≤25 / 😟≤45 / 😐≤55 / 😀≤75 / 🤪>75
   - 关键位磁吸：🧲 ；价格运动：📈📉 ；资金流：🔴流出/🟢流入
   - 结论词也带色：🟢偏多 / 🔴偏空 / ⚪待选

5. **报告要决策厚度，不只列数字**
   - 用真实可用数据源：TV MCP 五层 SVP/HALDRO、Binance OI/资金费率、Orion、CoinGecko、X情绪。
   - 每个数字配：偏离%(相对现价/关键位)、信号分层解读、动作建议、阈值触发说明。
   - 例：清算压力不只给 OI，要给 OI变化%+价格变化%+爆仓决策动作；稳定币给各币占比+资金流信号。

6. **中文时间格式**：`2026年7月8日18：35`（全角冒号，无 BJT/UTC）。

7. **RichMarkdown 富文本加粗重点，让结论一眼锁定**
   - 电报 `sendRichMessage` 支持 `**粗体**`（Bot API 10.1 RichMarkdown 语法），普通 `*` 不行，必须成对 `**`。
   - 加粗对象：**核心判断词 + 动作词**，不是整句。例：
     - Orion：`最优 **BTCUSDT**（信7.2）**量价齐升**，有机会**短多**` / `**去杠杆下跌**，**规避**` / `**不接刀**`
     - BTC关键位：`**总体结论**: **🔵多头区**（现价62,380），**回踩VWAP/VAL支撑做多**。**`
     - 清算：`**检测到爆仓**，顺势跟随方向、**不接刀**` / `**OI拥挤**，警惕**插针清算**`
     - 稳定币：`**稳定币增量=潜在买盘**` / `**稳定币减量=撤资信号**`
     - QLib：`多因子共振**偏空**，**规避为主**`
     - COT：`机构**净多主导**` / `**净空主导**`
     - 数据新鲜度：`**N个数据源过期**，**需检查对应采集脚本/接口**`
   - 规则：结论行原有的 `**总体结论**` 标签保留；把句内决策动词/方向词之外再用 `**` 包裹一次，形成「标签 + 内文重点」双层加粗。
   - f-string 与 `.format()` 都支持 `**`（它只是普通字符），本系统结论行多为 f-string，直接加 `**` 即可；`.format()` 时别把 `{}` 拆开即可。

8. **全出口矩阵验收，不只修眼前脚本**
   - 用户反馈“很多都没按计划来”时，先枚举全部 active cron 的 `Script:`，再扫描所有真实 TG 发送出口。
   - 每个活跃推送脚本都检查：RichMarkdown、管道表、首行自然语言 `↑↓○×`、`**总体结论**`、topic、去重/信号闸门、遗留 `send-message` 或普通 `parse_mode: Markdown`。
   - 最终输出缺项矩阵并修到 `BAD=[]`，不能只抽查几个 collector。
   - 模型同步、系统审计、备份聚合等自动维护脚本也属于 TG 报告，不得豁免。

## 改造一个推 TG 报告的标准步骤

1. 读脚本全文，确认它**是否真推了 TG**：很多 collector 只 `print` 给 cron（Deliver=local）→ 静默无推送。这种必须加 `push_tg_rich`。
2. 确认推送通道：情报类推 `telegram:-1003733144325:846`；交易卡走 416/386 已有通道勿动。
3. 重排表格：置信列前置+等级符号；候选按置信降序。
4. 加表情侧重点（见铁律4）。
5. 表末加 `**总体结论**` 一行。
6. 做厚：补偏离%/动作/阈值（铁律5）。
7. 语法 `ast.parse` 自检 → 实跑 `python scripts/xxx.py` 确认 EXIT=0 且 emoji/表格出现在输出 → `git commit`。
8. **结论行加粗重点**（铁律7）：把 `**总体结论**` 之后的决策动词/方向词再用 `**` 包裹一次（如 `**可做多**`/`**规避**`/`**不接刀**`/`**净多主导**`）。实跑确认 `**` 成对出现、未破坏 `.format()` 字段大括号。

## 常见坑（已在本系统踩过）

- **COT collector 缓存命中退化**：`_load_cache` 命中时原走 `line_summary`（单行文本），详细表只在强制拉取分支。修复：缓存命中也走 `_build_detail` 表格。
- **qlib_factors RSI 被掩盖**：`f.get("RSI") or 50` 在三维归类时把真实 RSI=26 吃掉，导致 `mom` 算出 +23 错值。修复：用真实 RSI 值参与，RSI 方向独立判定。
- **stablecoin 结论逻辑冲突**：`verdict` 用 `abs(delta)<0.1` 判"平静"，结论又用 `total_delta<0` 判"撤资"→ 同一行既"平静"又"撤资"。修复：统一用 `abs(delta_b)` 阈值分段。
- **推送双发**：脚本内 `push_tg_rich` 推真表格 + cron Deliver 也推 → 退化版双发。修复：cron `Deliver` 改 `local`，脚本内自推。
- **386 通道退化**：`telegram_direct` 默认 `parse_mode=None` 走纯文本。已修为默认 `RichMarkdown`。
- **结论加粗误加分号**：用 patch 工具改 f-string 结论时，曾误在行尾多写一个 `;` 又删掉。改 RichMarkdown 结论行后务必 `ast.parse` 自检，确认没有遗留 `;` 或破坏 f-string 引号。
- **融合脚本复用 collectors 的 `main()` 会双重推送**：`signal_confluence.py` 模式——只 `import` 各 collector 的**纯数据函数**（`fetch_*`/`detect_*`/`compute_*`），绝不可调 `main()`，否则其内嵌 `push_tg_rich` 会重复推 + 污染 stdout。稳定币不要 import `stablecoin_collector.main`（强耦合），自写轻量读 `data/stablecoin_snapshot.json` 差值即可。
- **`orion_screener_radar.compute_confidence(c)` 接受单候选 dict，不是 list**——误传 list 报 `list indices must be integers or slices, not str`。正确：`cands = [o.compute_confidence(c) for c in cands]` 逐个算。
- **融合报告主品种必须锚定 BTCUSDT**：Orion 选出的是「异动最强」品种（如 KAITOUSDC），但 QLib/Deribit/X情绪/稳定币都是 BTC 维度，不能把 headline symbol 设为 KAITO 造成错位。固定 `symbol="BTCUSDT"`，Orion 只作动量贡献。
- **`hermes cron add` 命令不存在**——正确是 `hermes cron create "17 * * * *" --name ... --script xxx.py --workdir "D:/Hermes agent" --deliver local --no-agent`。`--no-agent` 即 watchdog 模式（stdout 直接投递，空则静默）。
- **TV 缓存 DATA_DIR 路径坑**：棠溪脚本读取 TV 缓存/数据 JSON 时 `DATA_DIR` 必须用 `REPO / "data"`（`REPO = Path("D:/Hermes agent")`），**不是** `os.path.expanduser("~/AppData/Local/hermes/data")`。两目录都有同名旧文件，`signal_confluence.py` 初版误用后者 → 读到 9 天前的结构位（BTC 在 59k）+ 新鲜度 12845min，价位全错。新建/改造脚本时核对两目录差异。
- **执行计划盈亏比硬门槛（用户 2026-7-8 明确）**：止损绝不能设在 VAL/VAH 等结构位外——那只把 R 撑大、盈亏比压到 1.xR。必须**紧贴入场 0.5% 夹层**（VWAP×0.995 做多 / VAH×1.005 做空），R 缩小后目标 VAH/DO 自然 ≥2R。**未达标（R<2 或评分中间区 4–5.5）一律不发执行计划表**，只发一行 `**分析**: …` 说明原因。用户原话：「盈亏比大于等于2，不允许小于」「不达到的暂时不发后面那一段方案执行计划」。
- **推送频率必须双层控制（2026-07-09 用户明确「TG信息太频繁」）**：仅靠 cron schedule 降频不够——还要在每个推 TG 脚本的 `push_tg_rich` 调用前包 `alert_dedup.should_send()`。**审计推送频率时必查**：每小时/每30分跑的脚本若 `push_tg_rich` 前无 `should_send`/`dedup_wrapper` 包裹且无信号 gate，标 P1 补限频。2026-07-09 修复：`signal_confluence.py` 和 `x_sentiment_context.py` 缺 dedup → 每小时无条件推 → 加 `should_send(key, content, force_every_seconds=7200)`。完整 dedup 覆盖矩阵 + cron 批量降频模式见 `tangxi-system-audit/references/cron-night-silent-and-downschedule.md`。

## 多源融合报告（作战室）

当 11 个分散 collector 需要聚合成「单资产总评分」时，新建一个融合脚本（参考 `scripts/signal_confluence.py` + `references/multi-source-fusion.md`）：
- 融合源：Orion(主基底0–10) / QLib因子(映射0–5) / Deribit C/P(±2) / X情绪FOMO(过热反向±2) / 稳定币流向(±1)。
- 公式：`score = clamp(0,10, orion_conf + clamp(-3,3, 其余源权重和))`。
- 输出：每源一行真表（信号/权重/状态emoji）+ `**融合总评分**: ⭐/🔸/⚪` + `**总体结论**: 共振源[...]`。
- **独立验证闸门（2026-7-8 新增）**：用户要求「有计划了就要多方面验证是不是支持」→ 把重型引擎（如 `auto_card.py` 4200 行）的**核心验证逻辑抽成轻量验证器** `scripts/signal_validators.py`，而非 import 整个引擎（会拖垮 hourly cron）。双闸：源表加 🔍维度展示 + `compute_plan` 硬门否决。详见 `references/multi-source-fusion.md` 的「从重型引擎抽取轻量验证器」。
- 必须带铁律7 的**双层加粗**（标签 + 内文决策词）。
- **用户说「全面的来/给具体价位」时必加执行计划段**：方向结论不够，要可直接下单参数。评分→具体价位映射、风险%(高1.5/中1/偏空0.5)、盈亏比R、结构位新鲜度、现价。详见 `references/multi-source-fusion.md` 的「执行计划段」。
- **两条不可妥协的硬规则（用户 2026-7-8 明确下达）**：
  1. **盈亏比必须 ≥2R，否则不发执行计划段。** 达标（R:R≥2）才输出「执行计划」真表；未达标（中间区 4–5.5 方向不清 / 结构位窄导致 R<2）**只发一行 `**分析**: …` 说明原因，绝不发入场/止损/目标表**。R 不够就憋着，不硬发凑数方案。
  2. **执行计划必须带分析，不能只列数字。** 达标时也要有 `**分析**: 方向逻辑（融合分+共振源）· 入场逻辑（为何此位进）· 风控逻辑（止损依据+风险%+盈亏比）` 三段式，让接收方知道「为什么」。

  **让盈亏比达 ≥2R 的关键技术**：止损必须**紧贴入场（入场×0.995 做多 / ×1.005 做空，即 0.5% 夹层）**，绝不设在 VAL/VAH 外（那样 R 被撑大、盈亏比压到 1.xR）。贴紧后 R 缩小，目标 VAH/DO 自然给 2–4R+。
  - 做多：入场=VWAP、加仓=VAL、止损=VWAP×0.995、目标=VAH→DO→W-VWAP。
  - 做空：入场=VAH、加仓=VWAP、止损=VAH×1.005、目标=VAL→POC。

## 验证

实跑脚本看 stdout 是否含 emoji 与管道表；若脚本内 `push_tg_rich`，确认 EXIT=0 即推送成功（富文本回执 `rich_sent`）。用户端 TG 应看到真表格+表情+末尾结论。

## 参考与模板

- `references/collector-inventory.md` — 19 个 cron 任务、4 个 topic、各 collector 改造要点清单。
- `references/emoji-and-format.md` — emoji 图例 + 改造前后对照样例。
- `references/multi-source-fusion.md` — 多源融合报告（作战室）模式：`signal_confluence.py` 的源权重/评分公式/纯函数清单/两个坑/cron create 命令。
- `templates/report_skeleton.py` — 一个最小可运行的推 TG 报告脚本骨架（表格+结论+push_tg_rich+emoji）。
