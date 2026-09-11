---
name: tangxi-tg-rich-reporting
description: 棠溪系统电报(TG)报告推送规范 — 所有推TG任务统一走RichMarkdown真表格(纯Markdown管道表)，禁止图片表、禁止MarkdownV2退化。含四topic架构、静默collector改造模板、报告做厚方法、常见陷阱。当用户说"报告太简单/要做厚"、"统一TG格式"、"很多都发电报的"、"推TG退化成裸|"、"386卡片不像表格"时加载。
---

# 棠溪电报报告推送规范 (Tang Xi Telegram RichMarkdown Reporting)

## 铁律 (Iron Law) — 用户原话级别（2026-08-31 重大反转：分析卡默认=图片，报告默认=管道表）
- **TG 报告（盘点/审计/运维/Orion/复盘/静态内容）= 纯 Markdown 管道表，经 RichMarkdown 渲染成真表格。**
- **TG 分析卡（手动分析输出、行情卡、用户要"看一下 BTC"产生的快照）= PNG 图片（`render_analysis_card.py` 渲染 + `send_telegram_photo` 发送），用户原话：「不是照片来吗？就是那个分析卡」「类似这样，再优化的」（提供深色终端式参考图）。**
- ❌ **图片表禁用于报告**（用户对"报告"明确讨厌照片表格"），但**分析卡就是要照片**——区分报告 vs 分析卡是核心。
- ❌ **禁止 MarkdownV2 退化**（用于报告场景）。`hermes send` / cron 的 Deliver 通道底层 `send_message_tool.py` 用 `parse_mode=MARKDOWN_V2`，**Telegram 官方 MarkdownV2 不渲染管道表**，会退化成裸 `| a | b |` 文本。
- ✅ 用户已确认 `sendRichMessage`(RichMarkdown) 在客户端渲染为**真表格**（"是的，真表格"）。

## 核心机制
- 统一入口：`scripts/telegram_reliable.py` 的 `push_tg_rich(target, text)` → 调 `send_telegram_reliable(parse_mode="RichMarkdown")` → Bot API `sendRichMessage`，payload 含 `rich_message={"markdown": text}`。
- 失败落盘 `data/pending_telegram.jsonl`，不抛异常。
- 386 通道 `scripts/telegram_direct.py` 的 `send_telegram_direct()` 已改为**默认 `parse_mode="RichMarkdown"`**（原默认 None 走纯文本退化）。

## 四 Topic 架构（全系统盘点）
| Topic | 用途 | 推送方 | 状态 |
|:---|:---|:---|:---|
| `telegram:-1003733144325:846` | 情报/提醒（Orion/X情绪/BTC关键位/复盘/运维/看门狗/11个collector） | 各脚本内 `push_tg_rich` | ✅ 真表格 |
| `telegram:-1003733144325:416` | auto_card 交易卡 | `auto_card.py` → `send_telegram_reliable(RichMarkdown)` | ✅ 本来真表格 |
| `telegram:-1003733144325:386` | BTC分析卡 | `btc_card_gen/btc_daemon/btc_push_386` → `telegram_direct` | ✅ 改默认RichMarkdown |
| **`telegram:-1003733144325:<thread_id>`** | **手动分析输出（当前会话所在 thread，动态）** | `push_tg_rich(target, text)` | ⚠ 必须动态追踪，禁止硬编码 |
| collector 静默层 | dune/deribit/cot/liquidation/stablecoin/qlib/x_sentiment/macro_poly/xau_tv/data_freshness/trade_exec | 原只 `print` 给 cron(Deliver=local) | ✅ 已接846 |

**thread_id 动态判定规则**：每次推送前从会话上下文读取当前 thread（source 里 `thread: 386` / `thread: 846` 等），拼成 target `"telegram:-1003733144325:<thread_id>"`。后台 cron 脚本写死 846 是设计如此（Home 广播），但手动分析必须跟随用户所在 thread。

## 审计流程（接到"统一TG格式/很多没推"类需求时）
1. `hermes cron list` 看所有任务 Schedule/Script/Deliver。
2. `grep -rlnE "telegram|push_tg|send_telegram|telegram_reliable" scripts/` 找所有发电报脚本。
3. `grep -rhoE "telegram:-1003733144325:[0-9]+" scripts/` 找所有目标 topic。
4. 逐个脚本看 `main()`：是否 `print` 仅给 cron（Deliver=local=静默）、是否走 `push_tg_rich`、表格是否够厚。

## 改造模板（把静默 collector 接 TG + 做厚）
```python
# 在 main() 构造完 report 后（不要直接 print 散行，先拼成变量）：
report = "\n".join(lines)
print(report)
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from telegram_reliable import push_tg_rich
    push_tg_rich("telegram:-1003733144325:846", report)
except Exception as _te:
    print(f"⚠ XXX RichMarkdown推送失败: {_te}", file=sys.stderr)
```
- 静默型看门狗：用 `alert_dedup.dedup_wrapper` 限频后仍要 `push_tg_rich`（原漏发）。
- 缓存命中分支也要走详表（见陷阱 COT）。

## 报告做厚方法（决策维度，不凭空编）
在已有数据源字段上加：偏离现价%、振幅%、信号分层解读、动作建议、仓位系数、关键位磁吸位。
例：BTC关键位加 `偏离现价=(ref-cur)/cur*100`；Orion 加 `24h%` 列 + `仓位系数` 列；X情绪加恐惧贪婪分层（极度恐惧·潜在抄底区）；Deribit 加 C/P γ区判定 + MaxPain磁吸。

## RichMarkdown 真表格落地经验（2026-09 复盘）

### 手机窄表与边界规范
- Telegram 报告表格默认控制在 **≤3 列**；前两列保留核心字段，其余字段合并为“详情”列，避免移动端横向拥挤。
- 每个表格块必须从顶格 `| 表头 |` 开始，表头前与相邻非表格标题之间保留空行。标题行不能紧贴表格，否则部分 RichMarkdown 客户端会把整块降级为裸管道文本。
- 规范化应在构造 `rich_message.markdown` 前完成；`telegram_reliable._normalize_rich_markdown_tables` 与 `telegram_direct._canonical_rich_text` 必须保持同一规则，防止不同入口产生格式漂移。

### RichMarkdown 失败时的语义降级
- RichMarkdown 或 `sendRichMessage` 失败时，禁止把原始管道表直接交给普通 `sendMessage`。普通 Markdown/HTML 没有表格原语，裸 `| A | B |` 在手机端不可读。
- 应改用标签式文本兜底，例如：`指标：OI · 读数：107,616 · 状态：持平`。兜底目标是保留语义，不是用空格重新伪造表格。
- 失败路径应在返回原因中明确标记降级状态，便于监控和回归测试；RichMarkdown 成功路径仍优先走 Bot API 的 `sendRichMessage`。

### 自动化投递隔离
- 自动任务必须同时满足显式启用开关与显式配置的 `TANGXI_AUTOMATED_TG_TARGET`，调用点传入的历史 target 不能覆盖当前配置。
- 缺失配置或 target 不匹配时应安全拒绝或进入受控 pending/dead-letter 流程，不得静默发送到旧 topic。

详见 `references/richmarkdown-fallback-and-narrowing.md`。

## 陷阱 (Pitfalls) — 含 2026-08-29/08-31 用户纠正固化
0. **target 必须追踪当前会话 thread_id（P0·08-31 新）**：用户明确要求「我在哪里和你对话，你就发哪里」。`rich_sent`/`photo_sent` 返回 `True` 不代表送达正确位置——曾出现返回 `True` 但实际发到 846（Home）而用户（thread=386）完全看不到的故障。**每次推送前必须**：①目标 chat_id 固定为 `-1003733144325`；②thread 必须取当前会话所在 thread（从会话上下文 `thread: 386` 等读取）；③禁止硬编码任何固定 thread（846 例外是后台 cron 脚本设计如此，手动分析必须跟随用户所在 thread）。验证：推送后用户确认收到，或观察 pending 文件确认无该条（而非依赖返回值）。
0b. **手机端排版偏好**：列窄(2-3列)、表头短、默认手机三表速读(方向速览+关键位+一句触发)，完整8表仅「完整/深度」才出；首行给结论、末行给现价+触发；推386真表格后对话回复只留一句不重贴表。
1. **表格块被 standalone 标题行打断（P0·真凶）**：`sendRichMessage` 解析管道表时，若表格**前紧贴独立章节标题行**（`**当前基本情况**`/`**多周期定位**` 或 `表1 · xxx`、`【现在】`、`【做法】`、`①周期体温`），客户端把整块当段落渲染成 `| a | b |` 裸文本。**已根治（2026-08-31）**：①`render_v96.py` 每个章节标题（【现在】/【做法】/①周期体温/②关键位/③多源/④方案）与其下一张表间补 `lines.append("")` 空行（块边界）；②`telegram_reliable._normalize_rich_markdown_tables` 加兜底：任何表头行前非空行非表行时强插空行。双保险。**教训：改多行缩进时勿用 `patch`/`write_file` 覆盖整文件（会毁文件/破坏缩进），用 `execute_code` 按行号或唯一子串精准替换 + `git checkout` 可回滚。****必须每张表直接从 `| 表头 |` 顶格开始**，表间空行分隔。`_normalize_rich_markdown_tables()` 只清 `表X ·` 前缀，**不会清 `**XX**` 粗体标题**——粗体标题才是真凶。验证：客户端看渲染，或 monkeypatch 检查 `rich_message.markdown` 表头前是否还有非表行。
2. **MarkdownV2 退化**：任何经 `hermes send` / cron Deliver 的表格都退化。必须脚本内 `push_tg_rich` 且 cron `Deliver=local`（避免双重/退化发送）。
3. **Deliver=local 静默**：cron `Deliver: local` 只把 stdout 留本地，不推 TG。脚本必须自己 `push_tg_rich`。
4. **386 默认 None**：`telegram_direct.send_telegram_direct` 原 `parse_mode=None` 走纯文本 → 改默认 `"RichMarkdown"`。
5. **COT 缓存命中绕过详表**：`_load_cache()` 命中时原调 `line_summary()`（单行退化）。抽 `_build_detail()` 函数，缓存命中与强制拉取都走详表。
6. **qlib RSI 被 `or 50` 掩盖**：`(f.get("RSI") or 50)` 当真实 RSI=26 时走 50，扭曲三维评分；且 `f"{mom:+d}"` 对 float 报 `Unknown format code 'd'` → 用 `int()` 转换 + 独立 `rsi_score` 判定。
7. **Pyright 误报 `sys` 未定义**：在文件顶部确无 `import sys` 时（如 `x_sentiment_context.py`），加 `import sys`，别信 Pyright。

## 中文表格不渲染的根因(2026-09-03 实锤·GPT-5.6 Luna 主模型场景)

**现象**: 用户换 GPT-5.6 Luna 为主模型后,分析卡在 Telegram "从来不会推表格"。

**根因链(必须理解,不是 token/topic 问题)**:
1. `prefill_trading_rules.json` 曾指示「分析卡用管道表格呈现」→ 模型在对话回复里内联管道表。
2. 网关 Telegram 插件 `plugins/platforms/telegram/adapter.py` 的 `_rich_eligible()` 里 `and not self._has_telegram_desktop_cjk_rich_garble_shape(content)` —— **只要内容含任何中文(CJK)就跳过富文本渲染**,回退 MarkdownV2。
3. MarkdownV2 无表格原语(`helpers.convert_table_to_bullets`)→ 管道表被转成 `• header: value` 子弹列表。

**已修复(2026-09-03) — 重要更正: 原 Fix 1 方案 BACKFIRE, 勿照抄**:
- ❌ 原 Fix 1(已废弃): prefill 改成「禁止内联, 必须经 `telegram_reliable.push_tg_rich` 推卡」——**这个方案反噬了**。GPT-5.6 Luna 不执行 Python 推送工具调用: 它照抄「回复只留一句」, 却从不调 `push_tg_rich`(实测该会话工具清单里无任何推送脚本执行), 结果**表格根本没生成**, 只在 TG 发了截图+148字短句。
- ✅ 正确 Fix 1: `prefill_trading_rules.json` 改为「**允许内联真管道表格**」(模型天然可靠地写内联表), 由 Fix 2 负责渲染。
- ✅ Fix 2 `adapter.py` `_rich_eligible()`: 移除 CJK 守卫(仅放宽**最终发送**), 草稿路径 `_should_attempt_rich_draft` 仍独立保留 CJK 防乱码守卫。理由: `telegram_reliable` 直发中文富消息一直正常, 证明客户端能渲染中文富文本; CJK 乱码只是 Mac/Desktop 草稿 overlay 问题。**注意**: 网关需重启才生效; Hermes 更新可能覆盖此补丁, 更新后需复查。
- ✅ 禁用 `hooks/tg_table_guard/HOOK.yaml`(改名 `.off`): 该钩子靠「含管道表=误发」启发式, Fix 2 生效后会**误报**(内联表现能渲染)。

**核心教训(2026-09-03)**:
- **要让模型在 TG 出真表格, 就让它内联写表 + 修好渲染管线(适配器/网关); 不要逼它经工具调用 push。** 模型**可靠地内联写表**, 但**不可靠地执行 Python 推送脚本**(会跳过/只回短句)。凡「让模型触发外部推送」的方案, 必须先验证模型真的会调用, 别只改提示词。

**验证渲染链路是否打通(2026-09-03 实测, 全闸门 pass 才走 sendRichMessage)**:
在 `hermes-agent/plugins/platforms/telegram/adapter.py` 的 `_rich_eligible()` 上命中以下全部才渲染真表格: ① `_rich_messages_enabled`←config.yaml `telegram.extra.rich_messages: true`(经 `PlatformConfig.from_dict` 读 `data["extra"]`, config.py L724 映射打通) ② `not _rich_send_disabled`(能力失败会 latch off, 重启清空) ③ `_needs_rich_rendering(content)`=True(含管道表分隔行, 语言无关, 中文表也 True) ④ `_bot_supports_rich()`=True(`inspect.iscoroutinefunction(bot.do_api_request)`, PTB 22.6 为 async) ⑤ `len≤32768` ⑥ 不再被 CJK 守卫拦截(Fix 2 已移除)。群 topic(386)流式最终编辑走 `_try_edit_rich`(L2336)用 `editMessageText` 的 `rich_message` 升级富文本, 同样受 `_rich_eligible` 门控。诊断必查项: `_rich_eligible` 是否仍含 `_has_telegram_desktop_cjk_rich_garble_shape`(应在=已修)、`_needs_rich_rendering` 是否识别中文管道表。

**判定铁律**: 用户报「表格不渲染/变成子弹」时,先查此链: ① 是否内联管道表(是→改走 telegram_reliable) ② adapter `_rich_eligible` CJK 守卫是否还在(在→已回退) ③ `data/hooks_tg_table_guard.log` 是否记到同 session 表格误发(实锤)。不要归因于 token/topic/模型能力。

## 验证方法
- 真渲染：实跑脚本看 stdout 是否 RichMarkdown 表格；或 monkeypatch `telegram_reliable._post_json` 验证 `method=='sendRichMessage'` 且 payload 含 `rich_message`。
- 构造 payload 时也必须检查 `rich_message.markdown` 已经过规范化；不能只断言 parse mode。
- 回归至少覆盖：标题行与表格边界、宽表压缩、普通正文中的 `|` 不误判、RichMarkdown 失败时不发送裸管道表。
- 386 通道：`send_telegram_reliable('...:386', tbl)` 应走 `sendRichMessage`；对比 `parse_mode='MarkdownV2'` 走 `sendMessage`。
- 真实外部发送不是默认验证步骤：除非用户明确授权，否则使用 monkeypatch/fixture 验证 payload、路由和降级结果，避免测试消息污染生产 topic。
- **表格块被粗体标题打断的根因 + monkeypatch 验证法**：见 `references/richmarkdown-table-block-constraint.md`（2026-08-29 实战）。`_normalize_rich_markdown_tables` 只剥 `表X ·` 前缀，**不剥 `**XX**` 粗体标题**——粗体标题才是让表格退化成段落的真凶。
- **target 正确性**：推送后检查用户是否在目标 thread 收到；观察 `data/pending_telegram.jsonl` 确认该条不在 pending（即真正送达，非返回值依赖）。

详见 `references/tangxi-tg-inventory.md`（实际文件清单 + 验证命令）、`references/analysis-card-v4-design.md`（分析卡 PNG 设计规范）。

---

## 分析卡（PNG 图片）—— 手动分析输出专用通道（2026-08-31 用户反转）

**何时用图片**（不是管道表）：
- 用户说「看一下 BTC」「现在呢」「分析」→ 输出"分析卡"
- 用户明示要图片（「这个要照片」「来个图」「发图」）
- 卡片需要被手机长按转发/保存到相册（图片是唯一可分享形式）

**何时用管道表**（不图片）：
- 系统盘点（cron 清单 / 能力矩阵 / 审计报告）
- 静态结构化数据（Orion 雷达 / X 情绪 / 复盘）
- 用户明示"出报告" / "盘点" / "审计"

**渲染器**：`scripts/render_analysis_card.py` v4（2026-08-31）。详细设计规范见 `references/analysis-card-v4-design.md`。

**核心接口**：
```python
import sys; sys.path.insert(0, "scripts")
from render_analysis_card import render_card
from telegram_reliable import send_telegram_photo

render_card(
    out_path="outputs/btc_20260831_1905.png",
    title="BTC 78,541 · 15m · 2026年8月31日 19:05",
    kpis=[("现价 USDT", "78,541", "white"), ...],   # 4 个
    verdict_line="裁决：⚠ C级等待 · VWAP 78,014.5 多空分水",
    sections=[("信号矩阵", "副标题", ["维度","数值","评级"], rows), ...],
    risk_text="🔴 警惕：...",
    callout=("📋 推荐操作 · 空仓等待", [(text, level), ...]),
    footer="TV✅ / Binance✅ · L2标准档",
    sparkline=[(i, price), ...],       # KPI 右侧折线（可选）
    price_scale=[(79400, "止损↑", "bad"), ...],  # 第一section 右侧竖向价格标尺（可选）
)
send_telegram_photo("telegram:-1003733144325:<thread_id>", "outputs/btc_20260831_1905.png", caption="...")
```

**目标对话 thread_id 取法**（P0 · 沉默失败陷阱）：
- 永远从当前 session 的 `Source: Telegram ("group: 阿弥黛黛, thread: 386")` 读取
- 拼成 `"telegram:-1003733144325:386"`
- **禁止硬编码 846 / 任何固定 thread**（除非 cron 后台广播）
- `photo_sent` 返回 True 也不代表用户看到了——必须 target 与会话 thread 一致

---

## TradingView MCP 拉取陷阱（2026-08-31 实测·P0）

`mcp__tradingview__*` 频繁踩坑的三个：

1. **timeframe 必须传字符串**：`chart_set_timeframe(timeframe='"15"')` 或 `timeframe='"15m"'`，**不能传数字 `15`**——会报 `Input validation error: expected string, received number`。这是 TradingView API 的强制要求，不是 MCP 包装问题。
2. **切 symbol / 切 timeframe 后 Pine 指标需 15-30s 重渲染**：调 `data_get_pine_tables` 前**必须 `sleep 20+`**，否则拿到空表或上一品种的残留数据。OHLCV / chart state 1-2s 即可用。
3. **图表可能停留在错误品种**：上次会话的 `chart_set_symbol` 可能没生效或被其他工具覆盖，调 Pine 前**先 `chart_get_state` 确认 symbol + timeframe**，错就重设再 sleep。

## PIL 渲染深色主题的填充色陷阱（v4 实测）

深色背景 `#0E0E12` 下，**填充色必须明显**否则视觉上"消失"：

| 用途 | 错误色 | 正确色 | 原因 |
|:---|:---|:---|:---|
| 红色裁决条/风险条背景 | `#1F0707` ❌（视觉上等同黑） | `#3A0808` ✅ | 差 1-2 个色阶就完全看不出填充 |
| 绿色 callout 背景 | `#07140A` ❌ | `#062812` ✅ | 同上 |
| 红色主色 | — | `#EF4444` | 高饱和信号色 |
| 绿色主色 | — | `#4ADE80` | 高饱和信号色 |
| 蓝色表头 | — | `#2563EB` | 与主色形成对比 |
| 黄色警示 | — | `#F59E0B` | 中间态 |

**调试方法**：渲染后 `Image.open(path).crop((x,y,x2,y2))` 单独裁出元素块，调 `vision_analyze` 让模型描述"看到什么颜色"——视觉模型比人眼更严格，能识破"看起来像黑"的伪填充。
