---
name: apikey-image-gen
description: "Generate or edit images through Hermes Web UI or direct OpenAI-compatible API providers (JBBToken, Right Codes Draw) when Hermes Web UI is unavailable."
version: 1.1.0
author: Ekko + aggregator
license: MIT
platforms: [linux, macos, windows, termux]
metadata:
  hermes:
    tags: [api.apikey.fun, custom-provider, image-generation, jbbtoken, image-editing, media]
prerequisites:
  commands: [curl]
---

# APIKEY Image Generation

Use this skill when the user wants to generate an image from a text prompt.

Primary path: Hermes Web UI media endpoint (`/api/hermes/media/apikey-image-generate`).
Fallback paths: Direct OpenAI-compatible API calls to configured custom providers.

## Fallback: JBBToken Direct API

When Hermes Web UI is unavailable and the user provides (or config has) a JBBToken API key at `https://jbbtoken.cn/v1`:

- Model: `gpt-image-2` (only option)
- Cost: $0.04/generation for all sizes
- Auth: `Authorization: Bearer <key>`
- Endpoint: `POST /v1/images/generations` with `{"model":"gpt-image-2","prompt":"...","n":1,"size":"2048x3072"}`

See `references/jbbtoken.md` for full details on:
- Secret redactor workaround (character codes for writing API keys)
- Prompt engineering (keep under 200 words, always request perfect hands)
- Billing checks and error handling
- 4K background process pattern

## References

| File | Content |
|------|---------|
| `references/jbbtoken-api.md` | JBBToken API details, auth, billing, prompt engineering, secret redactor workaround |
