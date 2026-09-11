# JBBToken OpenAI-Compatible Image Provider

Use this reference when Hermes Web UI's `apikey-image-generate` endpoint cannot use its default `fun-codex` provider and the active/custom provider is JBBToken.

## Durable endpoint facts

- Base URL: `https://jbbtoken.cn/v1`
- Text-to-image: `POST /v1/images/generations`
- Image edit / image-to-image / reference edit: `POST /v1/images/edits`
- Protocol shape follows OpenAI-compatible image APIs.

## Probe workflow

1. Read the selected Hermes profile `config.yaml` and locate a `custom_providers` entry whose name or `base_url` contains `jbbtoken`.
2. Confirm the provider has an API key, but do not print or store the key in conversation output.
3. Call `GET {base_url}/models` to see which models the account currently exposes.
4. For text-to-image, call `POST {base_url}/images/generations` with an image model, prompt, `n`, and `size`.
5. Accept either OpenAI-style `data[0].b64_json` or `data[0].url`; if a URL is returned, download it and verify the file exists.
6. Verify generated image dimensions/format with PIL or another local image inspector before telling the user it worked.

## Common results and interpretation

- `400 images endpoint requires an image model, got "<chat-model>"`: the endpoint is working, but a chat model was used. Retry with the real image model name.
- `503 No available channel for model <image-model>`: the endpoint is reachable and protocol-compatible, but the account/group currently has no usable channel for that image model. Ask the user to enable an image model channel or provide the exact model name.
- `GET /models` may list only chat models such as `gpt-5.5`; that does not prove the image endpoint is absent, only that no image model is currently advertised for this key.

## Minimal Python direct probe pattern

Use Python rather than hand-written shell JSON when prompts are long or paths are Windows-native.

```python
import base64, json, pathlib
from urllib.request import Request, urlopen

base = "https://jbbtoken.cn/v1"
api_key = "..."  # read from config, never print
out = pathlib.Path("C:/Users/Administrator/AppData/Local/hermes/workspace/jbbtoken_direct_test.png")
body = {
    "model": "gpt-image-2",
    "prompt": "A small clean test image",
    "n": 1,
    "size": "1024x1024",
}
req = Request(
    base + "/images/generations",
    data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
    headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
    method="POST",
)
with urlopen(req, timeout=600) as resp:
    payload = json.loads(resp.read().decode("utf-8"))
item = payload["data"][0]
if "b64_json" in item:
    out.write_bytes(base64.b64decode(item["b64_json"]))
elif "url" in item:
    out.write_bytes(urlopen(item["url"], timeout=600).read())
```
