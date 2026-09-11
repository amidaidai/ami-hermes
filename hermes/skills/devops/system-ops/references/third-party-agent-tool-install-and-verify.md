# Third-Party Agent CLI Tool: Install & Verify

## Common Pattern

When an agent needs to install a third-party CLI tool from GitHub (e.g. Agent Reach, rdt-cli, twitter-cli):

1. **Clone** — `git clone https://github.com/org/repo.git`
2. **Install** — `cd repo && pip install -e .` (editable dev install)
3. **Run diagnostic** — `python -m module.cli doctor` or the project's built-in health check
4. **Verify directly** — Don't trust the doctor alone; test each backend CLI directly

## Agent Reach Specifics

```
Agent-Reach/
├── agent_reach/
│   ├── channels/          # One file per platform (twitter.py, reddit.py, youtube.py, ...)
│   ├── cli.py             # CLI entry point (argparse)
│   ├── config.py          # Config management (YAML + env)
│   ├── doctor.py          # Diagnostics engine
│   └── core.py            # Agent integration
├── constraints.txt
└── pyproject.toml
```

- Doctor: `python -m agent_reach.cli doctor`
- Install optional channels: `agent-reach install --channels=twitter,opencli,reddit,all`
- Extract cookies: `agent-reach configure --from-browser chrome`
- Config stored in: `~/.agent-reach/config.yaml`

## Channel Availability Summary

| Tier | Platforms | Auth Required |
|------|-----------|---------------|
| ✅ Zero-config | GitHub, YouTube, V2EX, RSS, Exa Search, Web (Jina) | None |
| ⚠️ Medium | Twitter/X, Reddit, Bilibili, 小红书, 雪球 | Cookie / OAuth |
| 🔧 Complex | 小宇宙 (Whisper), LinkedIn (MCP server) | API key / server setup |

## ⚠️ Pitfall: Doctor False Negatives

Built-in diagnostics may report a channel as "uninstalled" when the tool is actually installed and working. Common root causes:

**Symptoms**: Doctor says "not installed" but `which <tool>` finds the binary and `<tool> status --json` returns `ok: true`.

**Common cause**: The doctor subprocess timeout is too short for the tool's startup time.

**Example (rdt-cli ≥ 0.4.2)**: `rdt status --json` takes ~12s on first invocation (tries to refresh Reddit cookies). Agent Reach doctor's timeout is 10s. Result: false-negative for Reddit even with rdt-cli installed and authenticated.

**Fix**: Always verify doctor results by running the backend tool directly:

```bash
# Reddit
rdt status --json | python -m json.tool   # look for authenticated: true
rdt sub python --limit 3                   # real data fetch

# Twitter
twitter status      # authenticated: true

# GitHub
gh auth status      # Logged in to github.com account X

# 小红书
xhs status          # ok: true

# 雪球 (needs browser cookie)
python -c "
import urllib.request
r = urllib.request.Request('https://stock.xueqiu.com/v5/stock/batch/quote.json?symbol=SH000001',
    headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://xueqiu.com/'})
import json; print(json.loads(urllib.request.urlopen(r).read())['data']['items'][0]['quote']['name'])
"
```

## Doctor Report Interpretation

Doctor categorizes channels into three tiers:
- **Tier 0 (zero config)** — works immediately after `pip install -e .`
- **Tier 1 (needs free key / login)** — needs API key or cookie setup
- **Tier 2 (complex)** — needs dedicated MCP server or additional infrastructure

When a Tier 1/2 channel shows "warn" instead of "ok", check whether it's:
- Missing an API key (`agent-reach configure <key> <value>`)
- Missing browser cookies (`agent-reach configure --from-browser chrome`)
- Missing a required binary (`which ffmpeg rdt gh twitter`)
- A timeout issue (run the tool directly to confirm)

## Required Infrastructure Checklist

| Component | Needed For | Windows Install |
|-----------|-----------|-----------------|
| ffmpeg | 小宇宙 transcription | `winget install ffmpeg` or portable zip |
| gh CLI | GitHub channel | `winget install GitHub.cli` |
| pipx | Isolated installs (bili-cli, etc.) | `pip install pipx` |
| node/npm | mcporter | Already present with Hermes Desktop |
| browser-cookie3 | Cookie extraction | `pip install browser-cookie3` |
| playwright | Browser automation | `pip install playwright && playwright install chromium` |
