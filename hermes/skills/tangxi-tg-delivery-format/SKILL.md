---
name: tangxi-tg-delivery-format
description: 棠溪 Telegram 报告/卡片投递格式铁律 — 所有推 TG 的内容（审计/任务盘点/行情卡/运维聚合/信号）必须用纯 Markdown 管道表，经 RichMarkdown 通道渲染真表格。禁止图片表格、禁止裸竖线退化。适用于任何要发到 telegram 的棠溪报告。
---

# 棠溪 Telegram 投递格式铁律

## 核心规则（用户多次纠正后确立）

1. **必须用纯 Markdown 管道表**，绝不用图片表格。用户原话："不要照片的表格，我很讨厌照片的表格，必须要纯 Markdown 管道表格，渲染 RichMarkdown 文本表"。
2. **TG 投递通道必须走 RichMarkdown**（`sendRichMessage`），否则表格退化成裸 `|` 文本不渲染。
3. 对话内（CLI/网页）也用真管道表输出，文字极少。

## 为什么 `hermes send` 不行（关键陷阱）

- `hermes send` 与 cron 的 no_agent 投递都走 `tools/send_message_tool.py` → `parse_mode=MARKDOWN_V2`。
- **Telegram 官方 MarkdownV2 不渲染管道表格**（只支持粗体/斜体/链接等）。所以任何经 `hermes send` 或 cron Deliver=telegram 直发的内容，管道表都会退化成裸 `|` 文本。
- 用户实测确认：经 `hermes send` 发的表格"不是真表格"；经 `telegram_reliable.py` `parse_mode="RichMarkdown"` 发的才渲染。

## 正确通道（已验证）

仓库 `scripts/telegram_reliable.py` 的 `send_telegram_reliable(target, text, parse_mode="RichMarkdown")`：
- 内部走 Bot API 10.1 `sendRichMessage` 端点（`rich_message.markdown`），**真渲染管道表**。
- 自动检测：文本含管道表且 `parse_mode=None` 时也走 RichMarkdown（`_contains_markdown_table`）。
- 支持 `--target telegram:-1003733144325:846`（topic 846 = 阿弥黛黛/审计运维报告；386 = BTC 信号源）。
- 失败落盘 `data/pending_telegram.jsonl` 可 `flush_pending()` 补发。

### 调用示例（任何脚本/对话发 TG 表格都用这个）

```python
import sys; sys.path.insert(0, "scripts")
from telegram_reliable import send_telegram_reliable
md = """| # | 任务 | 频率 | 投递 | 实测 |
|:--:|:---|:---:|:---:|:---:|
| 1 | BTC关键位同步 | 每天4次 | TG | ✅ 根治后成功 |
| 18 | XAU TV现场同步 | 每15分 | 本地 | ✅ |"""
ok, reason = send_telegram_reliable("telegram:-1003733144325:846", md, parse_mode="RichMarkdown")
# reason == "rich_sent" 即真表格送达
```

对话里要发 TG 表格时，直接调用上述代码（execute_code / terminal python），**不要**用 `hermes send`。

### 回执 `automated_delivery_disabled`（2026-09-03 实测 · 关键分支）

`send_telegram_reliable` 可能返回 `ok=False, reason="automated_delivery_disabled"`。**这不是网络失败、不是表格格式问题，而是策略层主动禁止自动 TG 投递**（用户偏好：TG 仅在明确授权时发）。处理方式：

1. **不要重试、不要报错为通道坏了**。这是预期内的策略开关，不是 bug。
2. **本地留档**：把完整卡写到 `data/`（如 `data/btc_light_card_YYYYMMDD.md`），标注本地留档成功。
3. **在对话回复里直接呈现可扫读卡**：此时只能走 CLI/本地渲染路径，按用户偏好的手机卡片式布局输出（短标题分组、每行一个关键值、窄两列 `项目 | 当前状态` + `多源 | 读数 | 含义` + 表尾操作行），不要用宽表。
4. **回复里声明**：`（卡已本地留档 data/...；TG 自动推送当前禁用，如需推 <thread> 频道请明确授权）`。

**判断顺序**：先看 `reason` 是否等于 `automated_delivery_disabled`（策略关闭）→ 不等于才继续排查网络/权限/格式问题（`rich_sent` 是否真渲染）。

## 统一格式要求（所有棠溪 TG 报告）

- 表头用 `|:--:|:---|` 对齐（居中/左对齐按列语义）。
- 状态列用 ✅/❌/⚠️ 前缀，颜色由客户端自动渲染。
- 多张表用空行分隔，不要加"表1·"前缀标题行（RichMarkdown 在表前紧跟中文标题时部分客户端不渲染，保持顶格管道表最稳）。
- 文字叙述压到最少，报告基本都是表格形式（用户原话："报告基本都是要表格的形式"）。

## 用户确认的手机卡视觉模板（2026-09-03）

用户明确认可的表格卡形态不是宽泛的“字段—数据”大表，而是以下窄、分层布局：

1. 时间置顶；随后是品种标题与一句自然语言裁决。
2. 第一张窄表：`项目 | 当前状态`，承载主周期、结构、SVP、关键支撑/参考/失效。
3. 第二张窄表：`多源 | 读数 | 含义`，承载报价、OI/持仓、资金费率、多空比、主动买卖、聚合副指标。
4. 表后用“操作：”列出主推、破位失效和执行闸门；不要把每条操作塞进超宽表格。
5. 优先 2 列/3 列、短单元格、少重复字段；避免四列以上、超长解释、Unicode框线、代码块和图片表格。
6. 若有截图，截图说明/媒体应在整张卡最前；时间仍置于卡正文顶部。

用户给出的参考骨架：

```markdown
2026年9月3日 12：51

## BTCUSDT.P · BINANCE

结论：○ 等待，不追多，不执行。

| 项目 | 当前状态 |
|---|---|
| 15m主指标 | … |
| 结构 | … |
| 关键支撑 | … |

| 多源 | 读数 | 含义 |
|---|---:|---|
| 币安报价 | … | … |
| 持仓 | … | … |

操作：

- **主推：…**
- 跌破失效位：…
```

该模板只描述 RichMarkdown 投递后的正文布局；普通 assistant 回复仍不能保证显示为真表格。

## Studio 与 Telegram 对话渲染边界（2026-09-03 新增）

**Studio 能显示真表格，不代表普通 Telegram 回复也会显示真表格。** 两者可能走不同渲染链：Studio/原生富消息走 Rich Message；当前对话若走 legacy MarkdownV2，管道表会被降级为项目符号或代码块。Telegram MarkdownV2 本身不支持表格，不能用代码块或 Unicode 框线冒充 RichBlockTable。

排查顺序：
1. 先区分“回复正文”与“独立 RichMarkdown 投递”，不要把普通 assistant 输出当作已渲染表格。
2. 检查官方配置路径 `gateway.platforms.telegram.extra.rich_messages: true`，不要只看旧式/顶层 `telegram.extra` 是否存在。
3. 配置变更后必须重启 Gateway；运行中的 Gateway 不会自动重新读取富消息开关。
4. Rich 投递必须验证回执及目标 chat/thread；`rich_sent` 只证明 HTTP 发送成功，不证明发到了当前话题。
5. 若 Rich 投递被策略禁用或失败，必须如实说明“当前通道无法显示真表格”，不要回退成代码块后声称是表格。

权威说明与复现细节见 `references/telegram-studio-vs-chat-rendering.md`。

## 双通道铁律（用户 2026-08-28 反复纠正 · P0）

**普通 assistant 回复 ≠ 表格卡正文。** 若在对话回复里放管道表，Telegram 会把管道表降级成裸 `|` 文本/项目符号（用户测试确认"又不是表格了／这个是没用的这种文本"，多次发火）。正确做法：

1. **完整表格卡只走 RichMarkdown 推话题**：`send_telegram_reliable(target, md, parse_mode="RichMarkdown")` → 回执 `rich_sent` 即真渲染。
2. **普通 assistant 回复只放三样**：`MEDIA:<截图>` 首行 + 一句裁决（`↑/↓/○/× 品种 价 · 结论 · 中文时间`）+ 回执（`rich_sent`）。**不要**在对话回复里再复制表格正文 / 再推一张"关键位表"。
3. **一张完整表 + 一句结论**（用户原话"前面有表格了，表格加一个一句话结论"）：不要为"看哪几个位置"再单独拆出一张关键位表推，把关键位并进主卡表，表尾一句话总结论即可。
4. **首句裁决必须自然语言直白**（`↓ BTC 79,277 · 空头结构vs副指标转多 · C级观望`），不要用编号①②③开头，不要装饰分隔线（`══════`/`━━━` 禁用）。

## 重复推送陷阱（用户 2026-08-28 实测）

- 若同一轮里既推了 386 表格卡、又在对话回复里放了一样的表格/再来一张"关键位表"，用户会觉得冗余（"这个就不要了，前面有表格了"）。
- **结论**：表格永远只发一次（走 RichMarkdown 推送），对话回复只留截图+一句裁决。需要补"看哪几个位置"时，把位置并入主卡表格，不单独二次推送。

## 更新/追踪档位 = 简洁三表，不是完整 8 表（用户 2026-08-29 实测）

用户说「现在呢」「更新」「扫一下」这类追踪语时，**只出手机三表速读版**，不要重放完整驾驶舱 8 表卡。

- **三表速读版固定为**：① 方向速览表（周期 | 方向，1D/4h/1h/15m/5m 五行）② 关键位表（方向 | 价位 | 距现价，只列 3-6 个近端）③ 一句触发结论（放量→方向 / 破位→顺势 / 收回→反转，含止损目标）。
- **完整 8 表卡只在用户明确说「分析」「深度」「完整卡」「出完整卡」时才出**。用户原话 2026-08-29：「太繁琐了，要简洁一点」。
- 等级变化（如 C观望→偏空）是追踪档的重要增量，用一行「变化」点出来：`C观望→偏空·条件6/10`，但整体保持 3 表骨架，不膨胀。
- 追踪档仍必须给**明确动作**（等反抽/等破位/等收回，二选一触发），不允许只写「等确认」踢皮球。

## 适用场景

- 系统审计（P0/P1/P2 表、能力矩阵表）
- 任务盘点（cron 清单表、频率/投递/实测表）
- 行情卡 / Orion 雷达 / X 情绪 LLM 卡
- 运维聚合 / 每日复盘提醒
- 任何推 `telegram:-1003733144325:846` 或 `:386` 的结构化内容

## 避坑清单

- ❌ 用 `hermes send --to telegram:...` 发含表格的报告（退化裸 `|`）
- ❌ 用图片表（PNG/screenshot 渲染表格）发给用户（用户明确讨厌）
- ❌ cron Deliver=telegram 直发 no_agent stdout（走 MarkdownV2 不渲染）
- ✅ 脚本内调用 `telegram_reliable.send_telegram_reliable(..., parse_mode="RichMarkdown")`
- ✅ 需要 cron 触发的报告，让脚本自己发 RichMarkdown，cron Deliver 改 `local` 避免重复/退化

## Topic 目标陷阱（2026-08-31 实测 · P0）

本会话所在的 TG thread 必须从 session 元数据读出（系统消息 `Source: Telegram ("group: 阿弥黛黛, thread: 386")`），**不能凭记忆写默认的 846**。

| 错误写法 | 后果 | 修复 |
|:---|:---|:---|
| `target = "telegram:-1003733144325:846"`（在 386 会话里） | 返回 `rich_sent` 但消息到了 Home 频道，**用户在对话里看不到** | target 必须用当前 thread |
| `target = "telegram:-1003733144325:386"`（在 386 会话里） | 正确，用户能立刻看到 | ✅ |

**铁律**：发 TG 前先确认两件事：① 当前会话在哪个 thread（从 system prompt `Source:` 行读）② target 字符串是否匹配该 thread。**写了 846 就以为发出去了 = 沉默失败**。

回执 `rich_sent` 只代表 HTTP 200，不代表用户看到了——必须 target 与会话 thread 一致。

## Binance MCP 不可用 → curl 兜底（2026-08-31 实测）

`mcp__binance__*` 在部分配置/平台下会返回 `'is not a deferrable tool'`（与单下划线命名陷阱同源），导致衍生品三件套拉空。降级路径是 terminal+curl 直取 Binance 公开 REST：

```bash
# 价格
curl -s "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
# 24h 统计（价/量/高低/涨跌幅）
curl -s "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"
# OI
curl -s "https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT"
# 资金费率
curl -s "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT"
# 大户/全局多空比（注：fapi 部分 path 在某些 IP 被 ban，返回 HTML 404）
curl -s "https://fapi.binance.com/fapi/v1/topLongShortPositionRatio?symbol=BTCUSDT&limit=3"
```

**已知 ban**：`/fapi/v1/topLongShortPositionRatio` 经常返回 404 HTML 页面（被 Cloudflare 封禁）。**发现返回 HTML 直接在卡里标 `⚠ 404`**，不要重试多次浪费时间。已采集到的价格/24h/OI/费率正常，写入分析卡的"方向票"区块。

## 参考文件

- `references/realtime-keylevel-alert-daemon.md` — 实时关键位到价提醒（用户要"实时"时 cron 不够，用守护进程 + crossing 检测 + `deliver=local` + 看门狗）。含为什么用 crossing 不用窄带、cron deliver 自动投递的坑、repeat 默认 once 的坑。
- `references/svp-haldro-indicator-keylevel-recommendation.md` — 读懂主/副指标 + 从指标自动推荐关键位的工作流。用户不报价格，安禾从主指标磁吸位（dist+freshness+prio+HTF 评分公式）推荐候选位 → 用户确认 → 写配置。含指标源码位置。
- `references/svp-keylevel-six-layer-and-guard.md` — **纠偏 + 演进版**：磁吸位只是 SVP 七层关键位体系的 2 个（用户纠正"图表上那些关键位不显示在磁吸位"），必须五源齐读才算完整集。含 `keylevels_collect.py` 六层分级采集器、通用化多品种守护 `keylevel_guard.py`（配置驱动零重启）、磁吸正则、按层去重陷阱、指标源码当前版位置。
