# WebUI model visibility cleanup and GPT Image 2 4K defaults

Use this note when maintaining Hermes Web UI image-generation model entries or when the user asks to prune stale image providers from the model selector.

## Files involved

- WebUI model visibility: `C:/Users/Administrator/.hermes-web-ui/config.json`
- Active Hermes profile config: `C:/Users/Administrator/AppData/Local/hermes/config.yaml`
- WebUI bundled server currently patched in this session: `C:/Users/Administrator/.hermes-web-ui/webui/0.6.24/dist/server/index.js`

## Model visibility cleanup pattern

`~/.hermes-web-ui/config.json` has a `modelVisibility` object keyed by provider IDs such as:

- `custom:right.codes`
- `custom:right.codes生图`
- `custom:www.micuapi.ai`
- `custom:www.micuapi.ai生图`

When the user says to delete a provider/model from the selector, remove the whole key from `modelVisibility`, then validate JSON.

Safe Python pattern:

```bash
python - << 'PY'
import json, shutil
from pathlib import Path
p = Path('C:/Users/Administrator/.hermes-web-ui/config.json')
bak = p.with_suffix('.json.bak-model-visibility-cleanup')
if not bak.exists():
    shutil.copy2(p, bak)
data = json.loads(p.read_text(encoding='utf-8'))
mv = data.get('modelVisibility', {})
for k in ['custom:right.codes', 'custom:right.codes生图', 'custom:www.micuapi.ai', 'custom:www.micuapi.ai生图']:
    mv.pop(k, None)
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('backup:', bak)
PY
python -m json.tool 'C:/Users/Administrator/.hermes-web-ui/config.json' >/dev/null && echo JSON_OK
```

Verification: search the file for the exact provider prefixes after editing. A clean result for the deleted prefixes means the UI selector entries are gone after WebUI restart.

## GPT Image 2 4K defaults patch pattern

If the user wants WebUI media endpoint defaults to maximize `gpt-image-2`, patch the bundled server request defaults for `/api/hermes/media/apikey-image-generate`:

- `n`: `4`
- `timeout_ms`: `600000`
- text generation size: `3840x2160`
- quality: `high`
- output format: `png`
- moderation: `low`
- image/reference and edit mode defaults should also prefer `3840x2160` and `high`

After patching a bundled/minified server file, run:

```bash
node --check 'C:/Users/Administrator/.hermes-web-ui/webui/<version>/dist/server/index.js'
```

Always create a backup beside the file before patching because WebUI updates may overwrite the bundled server file.

## Reporting style

For this user, report concise before/after tables with exact paths, JSON validation status, and whether restart is required. Avoid long explanations when the task is simply deleting entries.