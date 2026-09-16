# Layered memory review

Use when a user asks for a comprehensive memory or Studio-memory review.

## Evidence layers

1. Active preference files: `MEMORY.md`, `USER.md`, and the latest explicit user message.
2. 历史事实库：`memory_store.db`（SQLite）。**它属于 `holographic` 记忆插件，不是 built-in store**——插件未启用时一个字符都不进系统提示。里面有可用历史事实，但常常夹着过期的格式、模型、路由、积分制版本号断言。
3. 仓库证据：当前代码、测试、产物与运行时探针。

## 先枚举，再判定注入

```bash
ls -la "$HERMES_HOME/memories/"                      # 两个 .md + 0 字节 .lock
find "$HERMES_HOME" -maxdepth 3 -iname "*memor*"     # 会命中 memory_store.db
python scripts/memory_inventory.py                   # 一次导出三存储全状态
```

判定 `memory_store.db` 是否真在链路里，三个条件都要查：

```bash
grep -rl memory_store "$HERMES_HOME/hermes-agent" --include=*.py   # 谁读它
grep -n -A 20 "^plugins:" "$HERMES_HOME/config.yaml"              # holographic 是否 enabled
grep -n "provider" "$HERMES_HOME/config.yaml"                     # memory.provider 是什么
```

三者都指向插件未启用 → 报告写「休眠库·未注入」，**不要把它和两个 `.md` 并列成同等活跃的存储**，也不要把它计入 token 开销。

## 报告形状

- 两个 `.md`：**逐条原样列出**（条目数用代码数），附字符预算百分比、mtime、sha256。
- 历史库：条目总数、时间线分布、分类计数、最新写入时间，再按「仍有效 / 已过期 / 已冲突」分档。
- 单独给出「哪个进上下文、哪个没进」的判定表。
- 把「内容没丢」与「上次读全了」当成两个独立结论分别回答。
- 处置建议要有，但破坏性写入（删/合并）等用户确认；先导出归档。
4. Studio evidence: only what the Studio API/browser returns in this run.

## Review method

- Read the active preference files in full.
- Query fact-store schema and facts without exposing secrets.
- Compare claims by topic: output format, timeframes, assets, execution authority, data freshness, and routing.
- Mark each claim as active, historical, conflicting, or unverified.
- If Studio calls fail or return no operations, report Studio content as unverified; never infer that it is empty.
- Keep dated prices, expired key levels, and one-run health results out of durable memory.

## Durable lessons

- Current user corrections outrank old facts.
- Current code and tests outrank prose that says a pipeline has been integrated.
- A successful candidate collection does not equal human approval or a healthy monitor.
- A process being alive does not prove the source data or approved configuration is healthy.
