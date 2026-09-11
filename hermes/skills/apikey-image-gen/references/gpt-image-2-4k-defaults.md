# GPT Image 2 4K Default Preset

Use when the user asks to make `gpt-image-2` the default high-end / unlimited-budget image generation path in Hermes Web UI.

## Target defaults

```json
{
  "mode": "text",
  "model": "gpt-image-2",
  "size": "3840x2160",
  "quality": "high",
  "output_format": "png",
  "moderation": "low",
  "n": 4,
  "timeout_ms": 600000
}
```

## Runtime patch location

Hermes Web UI media endpoint code may live in the active Web UI bundle, for example:

`C:/Users/Administrator/.hermes-web-ui/webui/<version>/dist/server/index.js`

The handler function for `/api/hermes/media/apikey-image-generate` includes defaults similar to:

- text mode: `/v1/images/generations`
- image mode: `/v1/responses` with `image_generation` tool
- edit mode: `/v1/images/edits`

Patch defaults, not every call site blindly:

- `n`: default `4`
- `timeout_ms`: default `600000`
- text mode size: `3840x2160`
- text mode quality: `high`
- text mode output format: `png`
- text mode moderation: `low`
- image tool size/quality/output format: `3840x2160` / `high` / `png`
- edit mode size/quality: `3840x2160` / `high`

## Verification

After patching:

```bash
node --check 'C:/Users/Administrator/.hermes-web-ui/webui/<version>/dist/server/index.js'
```

Then inspect the handler text and confirm these tokens appear in the patched function:

- `msI(G.n,4,"n")`
- `msI(G.timeout_ms,600000,"timeout_ms")`
- `size:G.size||"3840x2160"`
- `quality:G.quality||"high"`
- `output_format:G.output_format||"png"`
- `moderation:G.moderation||"low"`

Warn the user that Web UI updates can overwrite the bundled `dist/server/index.js`; keep a timestamped or descriptive backup next to the patched file and reapply after update if needed.
