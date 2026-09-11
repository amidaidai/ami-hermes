# Hermes Vision Routing Audit

Use this reference when diagnosing why image/vision requests choose an unexpected provider or when the user wants a split setup such as DeepSeek for text and OpenRouter for image understanding.

## What to inspect

1. Locate the active Hermes home and config. On Windows this is often `C:/Users/<user>/AppData/Local/hermes/config.yaml`, not `C:/Users/<user>/.hermes/config.yaml`.
2. Read these fields in `config.yaml`:
   - `model.provider`
   - `model.default`
   - `agent.image_input_mode`
   - `auxiliary.vision.provider`
   - `auxiliary.vision.model`
   - `auxiliary.vision.base_url`
   - any custom provider `supports_vision` override
3. Check `.env` and current process environment for provider keys, but never print credential values.
4. Verify runtime resolution from code rather than relying only on config text.

## Runtime probe

Run this from the Hermes workspace, adjusting paths if needed:

```bash
python - <<'PY'
import os, sys
sys.path.insert(0, r'C:/Users/Administrator/AppData/Local/hermes/hermes-agent')
os.environ['HERMES_HOME'] = r'C:/Users/Administrator/AppData/Local/hermes'
from agent.auxiliary_client import get_available_vision_backends, resolve_vision_provider_client
print('available:', get_available_vision_backends())
print('resolved:', resolve_vision_provider_client())
PY
```

To inspect image input routing mode and capability detection:

```bash
python - <<'PY'
import os, sys
sys.path.insert(0, r'C:/Users/Administrator/AppData/Local/hermes/hermes-agent')
os.environ['HERMES_HOME'] = r'C:/Users/Administrator/AppData/Local/hermes'
from hermes_cli.config import load_config
from agent.image_routing import decide_image_input_mode, _lookup_supports_vision
cfg = load_config()
provider = cfg['model']['provider']
model = cfg['model']['default']
print('provider', provider)
print('model', model)
print('supports_vision', _lookup_supports_vision(provider, model, cfg))
print('image_input_mode', decide_image_input_mode(provider, model, cfg))
print('aux vision cfg', cfg.get('auxiliary', {}).get('vision'))
PY
```

## Interpretation pattern

- `auxiliary.vision.provider: auto` does not mean OpenRouter is forced. Runtime may try the main provider first when the main provider is considered vision-capable or its capability is unknown.
- If the main provider/model is a custom OpenAI-compatible endpoint and `supports_vision` is unset, capability can be unknown; auto-routing may try that custom endpoint before OpenRouter/Nous.
- Hermes' built-in vision auto fallback order includes OpenRouter and Nous, but an explicitly configured auxiliary vision provider is clearer and more reliable.
- Known text-only main models should be skipped for direct image input; image handling should then use auxiliary vision when configured.
- DeepSeek is usually a text/reasoning provider rather than the vision backend. For a "DeepSeek + OpenRouter vision" design, set DeepSeek as the main provider and explicitly set `auxiliary.vision.provider: openrouter` with a vision-capable model.
- OpenRouter may be available through config/auth sources even if `OPENROUTER_API_KEY` is missing in the shell. Do not infer absence from environment alone.
- Nous warnings such as missing auth or temporary unhealthy/payment errors mean Nous should not be treated as an available vision path for that run.

## Recommended split config shape

```yaml
model:
  provider: deepseek
  default: deepseek-chat

agent:
  image_input_mode: auto

auxiliary:
  vision:
    provider: openrouter
    model: google/gemini-3-flash-preview
    timeout: 120
    download_timeout: 30
```

If the user wants the main model to go through OpenRouter too, use `model.provider: openrouter` and an OpenRouter DeepSeek model ID, but still keep `auxiliary.vision.provider: openrouter` explicit.
