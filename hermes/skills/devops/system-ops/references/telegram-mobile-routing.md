# 全渠道手机端推送路由与格式

适用场景：用户查看 Telegram/飞书/Discord 主要在手机端，要求“表格优先、少横向滚动、不要刷屏”。用于 Hermes cron、no_agent 脚本、交易系统雷达/情绪/维护摘要推送。

## 路由原则

| 类别 | 默认 deliver | 说明 |
|---|---|---|
| 决策类/异常类/维护摘要 | Telegram/对应渠道 | 需要用户看见：Orion/X 情绪 LLM、系统审计、备份、关键位、异常看门狗 |
| 原始采集类 | local | Dune/COT/Deribit/清算/稳定币/QLib/宏观等只落盘，供分析卡读取 |
| 高频 watchdog | 条件推送 | 健康静默，只在异常、重启、关键位触发时推 |
| 模型/工具同步 | local 为主 | 只在失败或重大变化时推，避免每日小变动刷屏 |

## 手机优先格式

非完整交易卡（Orion 简报、X 情绪、市场概况、复盘提醒、维护摘要）默认：

1. 首行直给结论 + 中文时间，例如 `⚡ Orion雷达 · 候选3个 · 2026年7月1日09：02`
2. 恰好 3 张真 Markdown 管道表
3. 每表 ≤3 列，避免 Telegram/飞书/Discord 手机横向滚动
4. Telegram 必须走 Bot API 10.1 `sendRichMessage` + `rich_message.markdown`，不能用普通 `sendMessage`/`parse_mode=MarkdownV2` 冒充
5. 禁止表格前紧贴 standalone `表1 · xxx` 标题行；会导致手机端降级为文字
6. 禁止表格外长段落、尾注、标题解释、“分析完成”
7. 禁止文字对齐伪表格；不同客户端字体会导致错乱

模板：

```markdown
⚡ 结论 · 关键数据 · 2026年7月1日09：02

| 品种 | 数据 | 状态 |
|:----|:----|:----|
| BTC | 价`$58,472`·24h`-2.2%` | 🐻守`$58K` |

| 来源 | 方向 | 证据 |
|:----|:---:|:----|
| X·短线 | 🐻偏空 | `$58K`支撑测试·ETF流出 |

| 方向 | 触发 | 动作 |
|:---:|:----|:----|
| ↑多 | 站回`$59,500` | 轻仓多·目标`$62K` |
```

## Cron prompt 必写约束

LLM cron prompt 里必须显式写：

```text
格式铁律：
- 只输出：首行结论 + 恰好3张Markdown管道表
- Telegram 真表格必须走 Bot API 10.1 RichMarkdown/sendRichMessage
- 表格前不要紧贴 standalone `表1 · xxx` 标题行；直接从 `| 表头 |` 开始
- 每张表≤3列；禁止4列表/宽表/长段落
- 禁止文字对齐伪表格、表格外解释、尾注、总结、标题前言
- 时间必须中文格式：2026年7月1日09：02，全角冒号
- 每行必须有具体数据，不能写空话
```

## 运行态审计 checklist

审计“为什么不推电报/哪些推电报/哪些渠道推送”时必须同时检查：

1. `cronjob(action='list')` 或 `~/AppData/Local/hermes/cron/jobs.json` 的 `deliver`
2. 脚本路径解析：`workdir/script`、`workdir/scripts/script`、AppData fallback
3. 脚本内直连：搜索 `send_telegram`、`api.telegram.org`、`telegram:-...`、Bot API
4. 常驻 daemon 和手动推送脚本；它们不在 cron list，但仍可能推
5. `deliver=local` 只代表 cron delivery 不推；脚本内直连仍可能推
6. 飞书 sidecar 卡片：先发 MEDIA 图片，再用 sidecar 发文字卡；文字仍用3张窄表

## 降噪模式

### OpenRouter/模型同步

- cron `deliver=local`
- 脚本内如果保留 Telegram，必须加重大变化闸门：如变化数 ≥3 或主/视觉/委派链变化才推
- 小变化、无变化只落盘/写日志

### 每日复盘提醒

- no_agent 条件推送脚本
- 只有当天存在未复盘计划/事件时输出 3 表；无缺口时 stdout 为空，避免刷屏

### BTC关键位同步

- 成功时输出空
- 失败或 TV 不可用时输出 3 张Markdown窄表错误卡

## 入库策略

- `~/AppData/Local/hermes/cron/jobs.json` 是运行态动态文件，含 last_run/next_run 等噪音；不要整份提交到仓库。
- 如果需要持久化规则，写 `references/` 或项目文档中的“路由矩阵”，不要提交动态状态。
