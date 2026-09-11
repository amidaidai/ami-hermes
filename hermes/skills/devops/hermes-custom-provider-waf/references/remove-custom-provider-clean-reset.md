# Removing a Custom Provider for Clean Reconfiguration

Use this when the user says to clear/reset a named custom provider such as `lingsuan` and reconfigure from scratch.

## Scope

Clear active configuration and credentials, not historical audit records.

Remove provider traces from:
- `C:/Users/<user>/AppData/Local/hermes/config.yaml`
- `C:/Users/<user>/AppData/Local/hermes/config.yaml.bak` when it contains stale provider entries that can be copied back later
- `C:/Users/<user>/AppData/Local/hermes/auth.json` credential pool entries such as `custom:<provider>`
- request dump files under `sessions/request_dump*` that contain the provider hostname or name
- `.env` entries if the provider used named environment variables

Usually leave untouched:
- `logs/agent.log`, `logs/errors.log` — historical audit logs only
- `state.db`, `state.db-wal` — conversation history / search index; do not mutate just to remove historical text
- source/test files and skills that mention the provider as documentation examples

## Safe reset procedure

```python
from pathlib import Path
import json, yaml

home = Path('C:/Users/Administrator/AppData/Local/hermes')
needles = ['lingsuan', '灵算']

def hit_text(x):
    s = json.dumps(x, ensure_ascii=False).lower() if not isinstance(x, str) else x.lower()
    return any(n.lower() in s for n in needles)

# 1. config.yaml and config.yaml.bak
for path in [home / 'config.yaml', home / 'config.yaml.bak']:
    if not path.exists():
        continue
    data = yaml.safe_load(path.read_text(encoding='utf-8-sig')) or {}

    cps = data.get('custom_providers')
    if isinstance(cps, list):
        data['custom_providers'] = [p for p in cps if not hit_text(p)]

    def scrub(obj):
        if isinstance(obj, dict):
            for k in list(obj.keys()):
                v = obj[k]
                if isinstance(v, str) and hit_text(v):
                    if k == 'provider':
                        obj[k] = 'auto'
                    elif k in ('base_url', 'api_key', 'model'):
                        obj[k] = ''
                    else:
                        obj.pop(k, None)
                else:
                    scrub(v)
        elif isinstance(obj, list):
            for item in obj:
                scrub(item)
    scrub(data)

    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False), encoding='utf-8')

# 2. auth.json credential_pool
path = home / 'auth.json'
if path.exists():
    auth = json.loads(path.read_text(encoding='utf-8'))
    cp = auth.get('credential_pool')
    if isinstance(cp, dict):
        for k in list(cp.keys()):
            if hit_text(k):
                cp.pop(k, None)
            elif isinstance(cp[k], list):
                cp[k] = [entry for entry in cp[k] if not hit_text(entry)]
    if hit_text(auth.get('active_provider', '')):
        auth['active_provider'] = ''
    path.write_text(json.dumps(auth, ensure_ascii=False, indent=2), encoding='utf-8')

# 3. request dumps only
for p in (home / 'sessions').glob('request_dump*'):
    try:
        b = p.read_bytes()
    except Exception:
        continue
    if b'lingsuan' in b.lower() or '灵算'.encode() in b:
        p.unlink()
```

## Verification

Run these after reset:

```bash
hermes config check
hermes auth list
python - <<'PY'
from pathlib import Path
home = Path('C:/Users/Administrator/AppData/Local/hermes')
for p in [home/'config.yaml', home/'config.yaml.bak', home/'auth.json', home/'.env']:
    if not p.exists():
        print(p, 'MISSING')
        continue
    b = p.read_bytes()
    print(p, 'PROVIDER_HIT=' + str(b'lingsuan' in b.lower() or '灵算'.encode() in b))
PY
```

If `hermes auth list` no longer shows the provider and config check passes, the provider is cleanly removed for reconfiguration. Remind the user to restart Hermes Desktop / gateway / CLI so in-memory clients reload config and credentials.
