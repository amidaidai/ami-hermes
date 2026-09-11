# Multi-Channel Hermes Model Audit

Full audit covering ALL model-related slots across config, env, MCP, and settings.
Run this when a user asks "全方位审计" / "全面检查配置" / "what models do I have across all slots".

## Audit Scope

| Channel | What to check | Source |
|---------|--------------|--------|
| ① Model allocation | main, vision, compression, web_extract, title_generation, delegation, fallback | `config.yaml` → `model`, `auxiliary.*`, `delegation`, `fallback_providers` |
| ② API key status | Each key present vs missing, with labels | `.env` file |
| ③ MCP servers | All configured servers, enabled/disabled | `config.yaml` → `mcp_servers` |
| ④ Key settings | approvals, memory, redact, search/extract backends, cron provider, delegation concurrency | `config.yaml` |
| ⑤ Warnings/pitfalls | YOLO mode, missing fallbacks, routing inefficiency | Cross-reference from above |

## Python Audit Script

```python
import yaml, os
from pathlib import Path

cfg_path = Path(os.path.expanduser('~')).parent / '<user>/AppData/Local/hermes/config.yaml'
with open(cfg_path) as f:
    cfg = yaml.safe_load(f)

env_path = Path(os.path.expanduser('~')).parent / '<user>/AppData/Local/hermes/.env'
env_keys = {}
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                env_keys[k.strip()] = v.strip()

# ① Models
m = cfg.get('model', {})
print(f'主模型:   {m.get("default","?")}')
print(f'provider: {m.get("provider","?")}')

aux = cfg.get('auxiliary', {})
for slot, label in [('vision','视觉'),('compression','压缩'),('web_extract','提取')]:
    t = aux.get(slot, {})
    model = t.get('model','') or '(主模型)'
    print(f'{label}: {model} [{t.get("provider","auto")}]')

d = cfg.get('delegation', {})
print(f'子任务: {d.get("model","?")} [{d.get("provider","?")}]')
for f in cfg.get('fallback_providers', []):
    print(f'降级: {f.get("model","?")} (via {f.get("provider","?")})')

# ② API Keys
key_map = {'OPENROUTER_API_KEY':'OpenRouter','DEEPSEEK_API_KEY':'DeepSeek','XIAOMI_API_KEY':'Xiaomi',
           'FIRECRAWL_API_KEY':'Firecrawl','BRAVE_API_KEY':'Brave','TAVILY_API_KEY':'Tavily',
           'BINANCE_API_KEY':'Binance','TELEGRAM_BOT_TOKEN':'Telegram'}
for key, label in key_map.items():
    val = env_keys.get(key,'')
    print(f'{"✔" if val and "..." not in val and val != "***" else "✘"} {label}')

# ③ MCP
for name in cfg.get('mcp_servers', {}):
    print(f'  ✔ {name}')

# ④ Warnings
if cfg.get('approvals',{}).get('mode') in (False,'off','false'):
    print('⚠ approvals.mode=off YOLO模式')
if not cfg.get('fallback_providers'):
    print('⚠ 无降级链')
```

## Output Format

```
主模型:   deepseek/deepseek-v4-flash    [deepseek]
视觉:     openrouter/owl-alpha          [openrouter]
压缩:     deepseek-v4-flash             [openrouter]
提取:     (主模型)                       [auto]
子任务:   openrouter/owl-alpha          [openrouter]
降级:     mimo-v2.5-pro                 [xiaomi]

API Key:  ✔ OpenRouter  ✔ DeepSeek  ✔ Xiaomi  ✔ Firecrawl ...

MCP:      ✔ binance  ✔ financekit  ✔ jin10  ✔ tradingview ...

⚠ approvals.mode=off
```

## Common Post-Audit Fixes

| Finding | Fix |
|---------|-----|
| `model.provider` became `custom:xxx` after Freerouter | `hermes config set model.provider openrouter` |
| `.env` lost a key after `hermes config set` | Restore from backup or secondary `.env` |
| `model.default` uses OpenRouter format but provider is `deepseek` | `hermes config set model.default openrouter/owl-alpha` then `hermes config set model.provider openrouter` |
| web_extract set to slow free model | `hermes config set auxiliary.web_extract.provider auto` |
