---
name: tangxi-tg-reports
description: 棠溪交易系统所有推Telegram电报报告的通用规范——报告质量(做厚决策维度/总体结论/置信前置)、4个topic架构、统一RichMarkdown真表格通道、常见坑。改/建任何推TG的cron脚本前加载。
---

> **同族导航** — TG投递组 5 个技能各司其职，别加载错 （同族入口：`tangxi-tg-delivery-format`）
> · **本技能 `tangxi-tg-reports`** = 4 个 topic 架构 + 脚本改造通用规范（最短版）
> · 同族其余：`tangxi-tg-delivery-format`（入口 · 投递格式铁律（纯 Markdown 管道表 / RichMarkdown 真表格 / 禁图片表））、`tangxi-tg-report-standard`（报告质量铁律（总体结论、置信降序、决策厚度））、`tangxi-tg-rich-reporting`（RichMarkdown 通道与「静默 collector」改造模板、做厚方法）、`telegram-delivery-reliability`（投递可靠性加固（重试/格式化守卫））
> · 组内改动请同步其余成员的触发词，避免同名族抢触发。


# 棠溪电报情报报告规范 (tangxi-tg-reports)

## 何时用
改造/新建任何推 Telegram 的 cron 脚本，或调整 棠溪 交易系统电报报告格式时。
覆盖所有 topic：846(情报/提醒)、416(auto_card交易卡)、386(BTC分析卡)、及其他。

## 核心原则（棠溪明确要求，已多次纠正）
1. **详实准确高质量** —— 用户原话"太简单了""要详实准确高质量"。禁止信息单薄、只罗列裸数字。决策维度要厚：关键位+偏离%+波动区间+振幅、OI/费率/主动买卖、信号分层、仓位系数(建议非指令)。
2. 每份报告末尾必须有**一句简洁总体结论**：`**总体结论**: <一句话>。`
3. **置信度/自信度必须前置**（排第一列或最显眼处）。
4. **"有机会"的候选排在最前**（按置信度倒序，高置信+量价齐升天然靠前）。
5. 纯 Markdown 管道表 → 走 **RichMarkdown 真表格**渲染。**禁止图片表**（用户明确讨厌照片表格）。

## TG 推送架构（必读）
- 统一通道：`telegram_reliable.push_tg_rich(target, text)` → 走 `sendRichMessage` 渲染真表格（失败落盘 pending）。
- `telegram_direct.send_telegram_direct` 已修默认 `parse_mode="RichMarkdown"`（v9.8），386 卡片通道同理。
- **关键坑**：cron `Deliver=local` 时，脚本**必须自己调用 push_tg_rich** 发 TG，否则只落盘/静默，根本不推。
- 4 个 topic：
  - 846 `telegram:-1003733144325:846` 情报/提醒（Orion/X情绪/BTC关键位/复盘/运维/看门狗/各collector）
  - 416 auto_card 交易卡（`send_telegram_reliable` RichMarkdown）
  - 386 BTC分析卡（`btc_card_gen`/`btc_daemon`/`btc_push_386` → `telegram_direct`）
- 全量 collector（曾静默未推，已接TG）：dune/deribit/cot/liquidation/stablecoin/qlib/x_sentiment/macro_poly/xau_tv/data_freshness/trade_exec。详见 references/architecture.md。

## 报告结构模板
首行结论 → 来源状态表 → 数据/信号表（**置信前置**） → 判断/动作表 → **总体结论**。
无候选时直接给一句结论，不要堆空表。

## 常见坑（已踩过，写此skill以防复发）
- `telegram_direct` 旧默认 parse_mode=None → 纯文本退化，已修 RichMarkdown。
- qlib_factors：`f.get("RSI") or 50` 当 RSI 真实值≤50 时被 `or 50` 掩盖，三维归类算出离谱值 → 改用阈值比较 `1 if rsi>55 else -1 if rsi<45 else 0`。
- stablecoin 结论：verdict 用 `abs(delta)>=0.1` 判，结论又用 `total_delta<0` 判 → 两套阈值冲突，统一用 abs 分段。
- collector 缓存命中分支（如 cot `_load_cache`）可能走旧单行输出，绕过厚表+推送 → 缓存命中也要走详细表+push。
- 报告表格须是真 Markdown 管道表（`| a | b |` + 分隔行 `|:--:|`），TG RichMarkdown 才渲染；裸 `|` 文本不渲染。

## 验证
实跑脚本确认 EXIT=0 且打印出含总体结论的 RichMarkdown 表；必要时 spy `telegram_reliable._post_json` 确认走 `sendRichMessage` 而非 `sendMessage`。

## 与现有 skill 关系
与 `xau-analysis-format`(XAU卡格式)、`orion-screener-radar`(Orion单报告) 互补：本 skill 是跨所有渠道的电报报告通用规范，后两者是具体报告实例。重叠处由 curator consolidation。
