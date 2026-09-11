# Model Traffic Proxy Diagnosis

Use this when the user asks whether Hermes model calls are direct, through a custom relay, or through a local proxy.

## What to Distinguish

There are three separate layers:

| Layer | Example | Meaning |
|---|---|---|
| Hermes provider | `custom:tian-shu.org` | Which configured provider Hermes selected |
| Provider base URL | `https://tian-shu.org/v1` | Relay / mid-station endpoint, not necessarily the final model vendor |
| Local network proxy | `HTTP_PROXY=http://127.0.0.1:7897` | Whether the HTTP client routes traffic through a local proxy process |

Do not collapse these into one claim. A request can be both a custom relay and locally proxied.

## Minimal Diagnosis

1. Check active runtime logs first when the current conversation may differ from disk config:

```bash
grep -n "OpenAI client created" C:/Users/Administrator/AppData/Local/hermes/logs/agent.log | tail -20
```

Look for:

```text
provider=custom base_url=https://tian-shu.org/v1 model=gpt-5.5
```

2. Check disk config for the current default provider:

```python
from pathlib import Path
import yaml
p = Path.home() / '.hermes' / 'config.yaml'
cfg = yaml.safe_load(p.read_text(encoding='utf-8'))
print(cfg.get('model'))
for cp in cfg.get('custom_providers', []):
    if cp.get('name') in str(cfg.get('model', {}).get('provider', '')):
        print(cp.get('name'), cp.get('base_url'), cp.get('model'), cp.get('api_mode'))
```

3. Check inherited proxy env and NO_PROXY:

```bash
env | grep -Ei '^(HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY|http_proxy|https_proxy|all_proxy|no_proxy)='
```

4. Verify whether the provider host bypasses proxy according to Python/urllib rules:

```python
import urllib.request
for host in ['tian-shu.org', 'openrouter.ai', 'api.yairouter.com', 'localhost']:
    print(host, 'proxy_bypass=', urllib.request.proxy_bypass(host))
```

Interpretation:
- `proxy_bypass=False` + `HTTPS_PROXY` set means normal library calls will use the proxy.
- `proxy_bypass=True` means the host is covered by `NO_PROXY` and should go direct.

## Pitfalls

- `hermes config` or `config.yaml` may show a new provider after a model switch, while the already-running session logs show the provider actually used for this turn. Prefer logs for the current conversation.
- `NO_PROXY` entries are host-specific. If `tian-shu.org` is absent while `HTTPS_PROXY` is set, requests to `https://tian-shu.org/v1` will not bypass the local proxy.
- A custom relay (`tian-shu.org`, `jbbtoken.cn`, `api.aijws.com`, etc.) is not the same thing as a local proxy. Report both layers separately.

## Example Conclusion

```text
当前链路：Hermes Agent -> 本机代理 127.0.0.1:7897 -> tian-shu.org/v1 -> 后端模型。
这不是官方直连，也不是 Hermes 到 tian-shu.org 的裸直连；它是 custom relay + local proxy。
```
