---
name: provider-subscription-comparison
description: Research and compare AI provider subscriptions, coding plans, and API gateways for Hermes/agent workflows; produce Telegram-legible visual table cards and a direct purchase recommendation.
version: 1.0.0
created_by: agent
---

# Provider Subscription Comparison

Use this skill when the user asks for packages like Ollama Cloud, OpenCode Go, NeuralWatt, Z.ai/GLM Coding Plan, Nous Portal, Codex, Claude, Copilot, OpenRouter, or other AI subscription/API plans that can be used with Hermes, OpenCode, Claude Code, Cline, Kilo, OpenClaw, Cursor, etc.

## Core rule for Tang Xi

The user is very sensitive to table legibility on Telegram. Do **not** rely on long Markdown pipe tables for large comparisons. If the answer has more than a tiny table, produce **real visual table cards** as images first, then a short text verdict.

- Output `MEDIA:/absolute/path/to/card.png` at the top for each card.
- Use mobile-first vertical cards around `1080px` wide.
- Split long comparisons into 2-4 cards instead of one huge sheet.
- Keep each visual table to 3-4 columns max.
- Text response should be brief: final recommendation, reason, and what changed from prior assumptions.
- If Telegram Markdown fails to render as a real table, it does not count as a table for this user.
- 这条规则与平台无关：CLI 会话里同样先出卡片图再给结论，不要因为「这次不是 Telegram」就退回文本表。
- 卡片直接用 `scripts/render_table_card.py` 渲染（列宽自动归一到表宽、CJK 字体已内建），不要每次手搓。

## Research workflow

1. **Define the target model/workflow first.** If the user states a preferred model (e.g. GLM-5.2), re-rank plans around that model instead of giving generic multi-model advice.
2. Search official docs/pricing pages first, then corroborate with marketplace/router pages for effective price and provider availability.
3. Separate:
   - native Hermes providers,
   - OpenAI/Anthropic-compatible custom endpoints,
   - external CLI/ACP-only usage,
   - IDE-only subscriptions that are poor fits for Hermes.
4. Compare on the user's actual metric:
   - monthly price,
   - included quota/credits,
   - request/prompt semantics,
   - effective cost per request when enough data exists,
   - limits by 5-hour/weekly/monthly windows,
   - whether usage is allowed for interactive coding only.
5. Give one direct recommendation first; do not bury the answer behind options.

## Visual card pattern

Recommended card set for large comparisons:

1. **Purchase order** — rank, plan, price, why buy.
2. **Hermes access** — service, connection mode, key/provider/base URL.
3. **Limits and pitfalls** — service, quota/cost, caveat.
4. Optional model-specific card — e.g. GLM-5.2 value ranking.

Use clean typography, alternating row backgrounds, and highlight the recommended rows. Verify the generated files exist and have plausible dimensions before final delivery.

## GLM-5.2 specific guidance

When the user says they plan to use **GLM-5.2**, re-rank around GLM rather than generic Nous/Claude/GPT access:

- For lowest-cost trial: OpenCode Go can be the best first step.
- For sustained GLM-5.2 coding: Z.ai GLM Coding Plan Pro is usually the main plan to evaluate.
- NeuralWatt can be attractive for transparent energy billing and fast/short variants, but full 1M GLM-5.2 may not beat OpenCode Go on per-request cost.
- OpenRouter is good fallback/routing, not usually the cheapest fixed GLM-5.2 main plan.
- Ollama Cloud must be included in GLM-5.2 comparisons when the user asks about Ollama or cloud subscriptions: it has `glm-5.2` as a cloud model and offers Pro $20/月 (3 concurrent cloud models, 50× Free) and Max $100/月 (10 concurrent, 5× Pro). However, Ollama publishes GPU-usage/session/weekly style limits rather than exact GLM-5.2 request or prompt counts, so rank it as an **ecosystem/concurrency option**, not as the most transparent quota plan.
- Always explain request vs prompt semantics: Z.ai Coding Plan counts prompts/workflows; OpenCode Go documents request estimates; NeuralWatt documents energy per request; Ollama Cloud documents cloud usage/GPU utilization; direct APIs bill tokens.

See `references/glm-5-2-subscription-notes.md` for the condensed research notes from the 2026年7月7日 comparison.
See `references/codex-relay-station-notes.md` for Codex 中转站（兔小店 vs aijws）倍率兑换公式、套餐表和按量vs包月决策树（2026年7月15日）.
See `references/2026-09-us-plan-landscape.md` for the 2026年9月13日 snapshot of the 「~$20 档」五个候选（Command Code / OpenCode Go / Ollama Cloud / b.ai / DeepSeek 官方）：档位表、额度倍数换算、DeepSeek 峰谷价，以及其中三个方案在该价位根本不存在的核实结论。
See `scripts/render_table_card.py` for the reusable 竖版对比表卡片 renderer used by this skill.

## 先验证前提，再排序（2026年9月教训）

用户报来的方案清单本身可能是错的。这一轮五个方案里只有两个真有 $20 档：OpenCode Go 是 $10，b.ai 订阅最低 $200 且要邀请码，DeepSeek 官方**根本没有订阅**（只有按量 API）。

流程：

1. 逐家打开官方定价页/文档，确认「该价格档位是否存在」。不存在的，先直白纠正，再给排序——不要顺着错误前提硬比。
2. 报「$X/月」时把一次性手续费算进去（Command Code 官网只写 `+ processing fee`，Provider 页公示 $1.01 刷卡费），并注明是估算还是公示价。
3. 看额度是**池化**还是**每模型独立**：Command Code Pro 的 $80 可跨 45+ 模型；OpenCode Go 的 $15–$60 是每模型各自上限，余量不能挪用。两者名义倍数差很远但可用性不同。
4. 订阅限制要看窗口：Command Code Pro 有 5h $16 / 周 $40 上限，$80 月度额度烧不完；Ollama Pro 明确「no 5-hour or weekly limits」。

### 接入 Hermes 前必须验证本机能力，而不是只读厂商文档

厂商文档说「支持 Hermes」≠ 当前安装能跑好。OpenCode Go 要求客户端发 `x-opencode-session` 头，文档点名 Hermes 需要含 **PR #101864**（合并于 v0.21.0 之后）的构建。验证动作：

```bash
hermes --version                       # 版本号
cd <hermes install dir> && git log --oneline -3
grep -rn "x-opencode-session" --include=*.py .   # 无输出 = 该修复不在构建里
```

把「需要先升级到含 X 的构建」作为前置条件写进结论，而不是默默推荐一个当下跑不满血的东西。

## Pitfalls

- Do not present a generic “best Hermes subscription” if the user names a target model. Model-specific economics can invert the ranking.
- Do not rank IDE subscriptions (Cursor/Windsurf/Augment) as Hermes provider choices unless they expose a usable generic API or custom endpoint path.
- Do not harden transient setup failures into rules. If a search/helper CLI is missing, use the available web tools and note the coverage.
- Do not overproduce text after creating visual cards; for Tang Xi, the card is the artifact and the text is only the verdict.
- **中转站倍率对比必须算到「每 $1 官方用量实付¥」** 再比较，不能只看倍率数字或月费。公式：`每$1官方实付 = 倍率 × 充值汇率`。同一套餐不同渠道倍率差异可达 10 倍，必须注明渠道倍率。
- **按量 vs 包月决策**：先算盈亏平衡点（月费 ÷ 单价差 = 最低月消耗量），轻度用户推荐按量白嫖试用再决定，重度稳定用户切包月低倍率渠道。
- **动态渲染电商页**（如 tu-zi.com/store）web_extract 只能拿到静态公告，套餐列表需 browser_vision 截图；**Cloudflare 防护站**（如 aijws.com）browser 被拦时，从第三方探测站（hvoy.ai）和社区帖（linux.do）交叉获取定价。
- **别把「$1 拉新档」当可用档位**：Command Code 的 Go $1/月**不含 API 权限**，要接 Hermes 必须 Pro 起或走 Provider 按量档。看到超低价档先查它有没有 API/端点。
- **卡片渲染后必须抽查**：PIL 手搓表格时列宽总和必须等于 `表宽 = 1080 - 2×44`；不相等时最后一列会静默溢出圆角边框（肉眼看还像是对的）。用 `scripts/render_table_card.py` 并至少对一张卡跑 vision_analyze 确认无溢出/重叠/截断。