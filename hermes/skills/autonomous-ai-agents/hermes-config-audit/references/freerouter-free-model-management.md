# Freerouter: OpenRouter Free Model Auto-Management

Auto-discovers, scores, health-checks, and patches Hermes config with the best free
OpenRouter models. Runs as a daily cron job.

## Installation

### 1. Deploy the script

The canonical source is `KrabbiAI/freerouter-for-hermes` on GitHub. Copy
`scripts/freerouter.py` to `~/.hermes/scripts/freerouter.py`.

### 2. Ensure OPENROUTER_API_KEY

Confirm the key is set in the Hermes `.env` (check path via `hermes config env-path`):

```bash
grep OPENROUTER_API_KEY "$(hermes config env-path 2>/dev/null || echo ~/.hermes/.env)"
```

### 3. Dry-run test

```bash
cd "$(dirname "$(hermes config path)")"   # or cd ~/.hermes
DRY_RUN=true python scripts/freerouter.py
```

Expect output showing:
- Fetched N free models from OpenRouter
- Top-3 per category with scores
- Health checks passing

### 4. Live run

```bash
DRY_RUN=false python scripts/freerouter.py
```

This patches:
- `model.default` → top-scoring free model
- `model.provider` → `openrouter`
- `auxiliary.vision.model` → top-scoring free vision-capable model
- `delegation.model` → same as default

### 5. Cron job (daily auto-update)

```bash
hermes cron create '0 6 * * *' \
  --prompt 'Run Freerouter (live mode). Script: ~/.hermes/scripts/freerouter.py. Set DRY_RUN=false.' \
  --name 'Freerouter' \
  --toolsets terminal
```

## What the script does

| Phase | Action |
|-------|--------|
| Fetch | `GET https://openrouter.ai/api/v1/models?free=true` → 26+ free models |
| Quality gate | Context ≥128K, prompt/completion price = 0, not banned |
| Score | Weighted: context 20%, trending 25%, feature 30%, speed 10%, quality 15% |
| Health check | Real API call (max_tokens=5) to top-3 per category; 3 failures = 24h ban |
| Patch config | Backs up `config.yaml` → `config.yaml.bak`, writes new provider/model |
| Notify | Telegram (if `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` configured) |

## Scoring output (example)

```
  === TOP MAIN ===
    1. [85.9] openrouter/owl-alpha         1M ctx, tools ✓
    2. [83.3] qwen/qwen3-coder:free        1M ctx, coding
    3. [80.9] nvidia/nemotron-3-ultra-550b-a55b:free  1M ctx
    4. [80.0] nvidia/nemotron-3-super-120b-a12b:free  1M ctx
    5. [59.5] google/gemma-4-26b-a4b-it:free          262K ctx, vision ✓
```

## Windows-Specific Path Notes

The script resolves `HERMES_HOME` as:

```python
HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")))
```

On standard Windows Hermes installations, `HERMES_HOME` is set to
`C:\Users\<user>\AppData\Local\hermes`, so `~/.hermes` is **not** the live
config. Always run the script from the directory of the canonical config
(`hermes config path`) to avoid confusion.

## Script location

The script saves its state files under `HERMES_HOME`:

| File | Purpose |
|------|---------|
| `config.yaml.bak` | Pre-patch backup |
| `.model_selection.json` | Last run's full ranked output |
| `.model_history.json` | Change tracking (current vs previous) |
| `.model_failures.json` | Ban tracking (3 failures = 24h ban) |
| `.model_fallback.json` | Top-5 fallback chains per category |
| `logs/freerouter.log` | Run log |

## Post-Freerouter Verification

After a live Freerouter run, always audit these three things:

### 1. model.provider may become `custom:openrouter.ai`

The Freerouter script's regex-based `provider:` line edit can collide with
a `custom_providers` entry whose `name:` matches `openrouter.ai`. Result:
`model.provider` becomes `custom:openrouter.ai` instead of `openrouter`.

**Fix:**
```bash
hermes config set model.provider openrouter
```

### 2. `hermes config set model.default <id>` auto-detects provider

If the model ID contains a `/` (e.g. `deepseek/deepseek-v4-flash`),
`hermes config set` splits on `/` and sets `model.provider` to the prefix.
After a manual `hermes config set model.default <model>`, verify provider hasn't changed.

### 3. Auxiliary models all set to `openrouter`

Freerouter sets ALL auxiliary tasks to `provider: openrouter`. This is fine for
vision and delegation but can waste tokens on tasks that should use the main
model. Consider resetting non-critical aux tasks back to `auto` after the run.

## Model Distribution Recommendations (Free/Cheap Setup)

When the user has DeepSeek V4 Flash as main + OpenRouter free models available:

| Slot | Recommended | Rationale |
|------|------------|-----------|
| **Main** | `deepseek/deepseek-v4-flash` | Cheap ($0.14/M input), fast (50-100 tok/s), strong tool calling |
| **Vision** | `openrouter/owl-alpha` | Best free (1M ctx, multimodal, tools ✓) |
| **Compression** | auto (same as main) | DeepSeek V4 Flash is cheap enough; no reason to offload |
| **web_extract** | **auto** (main model) | ⚠ Do NOT use `nvidia/nemotron-3-ultra-550b-a55b:free` — too slow (6-9 tok/s), 93% uptime, overkill for summarization. Official docs + community consensus recommend auto (use main model) for web_extract. |
| **Delegation** | same as main | Match main model to avoid cold-start on subagent spawn |
| **Fallback** | `xiaomi/mimo-v2.5-pro` or `qwen/qwen3-coder:free` | Free 1M ctx coding model |

## Community Research Protocol

Before concluding "this feature doesn't exist / no solution available" for
any Hermes config question, check ALL of these:

1. **GitHub Issues** — `NousResearch/hermes-agent/issues?q=is:issue <keyword>`
   - Check both open AND closed issues
   - Note linked PRs
2. **GitHub PRs** — `NousResearch/hermes-agent/pulls?q=is:pr <keyword>`
   - Open PRs may contain working solutions that just haven't been reviewed
   - Merged PRs tell you what's in latest release
3. **Official Docs** — `hermes-agent.nousresearch.com/docs/`
   - Configuring Models, Configuration, Model Catalog reference
4. **OpenRouter Blog** — `openrouter.ai/blog/tutorials/hermes-agent/`
5. **Reddit** — `r/hermesagent` search
6. **Community projects** — GitHub search for `hermes + <feature>` (e.g. KrabbiAI/freerouter-for-hermes)
7. **X/Twitter search** — limited but can surface fresh discussions

## Pitfalls

### 🚨 Windows Python: `f'\\1{var}'` 在 `re.sub` 中被当作八进制转义

Freerouter 使用 `f'\\1{var}'` 作为 `re.sub` 的反向引用替换字符串（`patch_config()` 和 `restore_config()` 中）。但在 **Windows MSVC Python 3.11+** 上，`\\1` 在 f-string 中被解释为**八进制转义 `\x01`**（SOH 控制字符），而非 `re.sub` 的反向引用 `\1`。

**后果**：`model.default`、`delegation.model` 等字段无法被正确替换。regex 匹配到了，但替换写入的是 `\x01openrouter/owl-alpha` 而非 `  default: openrouter/owl-alpha`。只有 `model.provider` 被改了（因为 provider 的替换 `r'\1openrouter'` 用的是 raw string，不受此 bug 影响）。

**检测方法**：live run 后检查：
```bash
grep -A2 "^model:" "$(hermes config path)"
```
如果显示 `default` 没变、`provider` 变了，几乎肯定是触发了此 bug。

**跨平台修复**：用 `lambda` 代替 f-string 反向引用：
```python
# 错误（Windows 上不工作）：
re.sub(r'^(\s*default:\s*).+$', f'\\1{main_model}', content, re.MULTILINE)

# 正确（跨平台）：
re.sub(r'^(\s*default:\s*).+$', lambda m: m.group(1) + main_model, content, re.MULTILINE)
```

Python 3.13+ 可能修复了此行为（f-string 中 `\\1` 的行为），但 3.11/3.12 仍受影响。

---

- **`hermes config set` may delete env vars from `.env`.** Setting an auxiliary key
  like `hermes config set auxiliary.web_extract.provider auto` can inadvertently
  remove unrelated lines from `.env` (e.g. `OPENROUTER_API_KEY` disappears).
  **Always verify `.env` integrity after any `hermes config set` call**:
  ```bash
  grep -c "OPENROUTER_API_KEY" "$(hermes config env-path)"  # should be 1
  ```
  If missing, restore from a backup or copy from a secondary `.env` file
  (e.g. `~/.hermes/.env` on Windows).

- **Script patches `model.provider` to `openrouter`.** If the user's main provider
  is something else (DeepSeek, Anthropic, custom), the live run will switch away
  from it. Verify before running live.
- **`hermes config set model.default <id>` may auto-detect the provider.**
  If the model ID contains a `/` (e.g. `deepseek/deepseek-v4-flash`), `hermes config set`
  may split on `/` and set `model.provider` to the prefix. After Freerouter patches
  config, the provider may need manual correction via `hermes config set model.provider openrouter`.
- **Gateway restart via systemctl/pkill fails on Windows.** This is non-blocking
  — `hermes config set` changes take effect on the next `hermes` invocation.
- **Telegram notifications fail if keys are missing.** Not a critical error;
  the config patch still succeeds.
- **The script sees 340 "free" models from OpenRouter API** but quality-gates
  them to ~26 that are truly free and ≥128K context.
- **Do NOT use `nvidia/nemotron-3-ultra-550b-a55b:free` for `web_extract`.**
  It's too slow (6-9 tok/s), has only 93% uptime, is massive overkill for
  page summarization, and its free-tier ToS logs your data. Use `auto` (main
  model) instead — DeepSeek V4 Flash is fast enough that a single model covers
  both roles, saving cold-start latency per fetch.
