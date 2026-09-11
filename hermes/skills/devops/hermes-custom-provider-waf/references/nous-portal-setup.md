# Nous Portal Setup in Hermes Agent

## Official Endpoint (OpenAI-compatible)
- Base URL: `https://inference-api.nousresearch.com/v1`
- Source: portal.nousresearch.com/api-docs ("You can use this URL with OpenAI-compatible clients and libraries.")
- This is the endpoint to use if configuring Nous Portal as a `custom` provider via `hermes config set`.

## Two接入 paths

### Path 1 — `hermes setup --portal` (OAuth, official one-shot)
What it actually does:
- Runs an OAuth login against Nous Portal. Reuses existing OAuth creds if found at
  `C:\Users\<user>\AppData\Local\hermes\shared\nous_auth.json` (or `auth.json`) — no browser
  interaction needed when creds already exist.
- On success it writes OAuth tokens to `auth.json` / `nous_auth.json` under the
  `providers:` block (e.g. `xai-oauth`, `nous-oauth`).
- It does NOT write any model or provider into `config.yaml`. After login, the default
  model is STILL whatever was there before (commonly `tencent/hy3:free` via openrouter).
- It then shows an interactive model picker (30 curated models + "Enter custom model name").
  Free models show `free free free` in the price columns:
  - `28. tencent/hy3:free`
  - `29. stepfun/step-3.7-flash:free`
  - NOTE: `*-preview` models (e.g. `google/gemini-3-pro-preview`) are NOT free — they are
    preview builds with real pricing.
- Selecting a model here sets `model.default` + `model.provider` in config.yaml.

CRITICAL PITFALL — non-interactive TTY:
- Piping a choice into the wizard (`printf '28\n' | hermes setup --portal`) FAILS silently:
  "Running in a non-interactive environment (no TTY detected). The interactive wizard cannot
  be used here." It then just prints `hermes config set` hints and exits — the choice is NOT applied.
- The wizard MUST be run in a real interactive terminal. Do NOT try to script the selection via stdin.
- If you need to automate, use Path 2 (custom provider) instead.

### Path 2 — custom provider (API-key, for true scripting/automation)
Steps:
1. Get an API key from portal.nousresearch.com -> Keys page.
2. Configure via CLI (see redaction note below for the key):
   ```
   hermes config set model.provider custom:nous
   hermes config set model.base_url https://inference-api.nousresearch.com/v1
   hermes config set model.default tencent/hy3:free
   ```
3. Then MANUALLY edit config.yaml to add the `custom_providers:` block (because
   `hermes config set` stores values as strings — see parent skill section 2 YAML bug). The block:
   ```yaml
   custom_providers:
     - name: nous
       base_url: https://inference-api.nousresearch.com/v1
       api_key: sk-...        # write via base64+open(), NOT via patch/MCP (redaction trap)
       model: tencent/hy3:free
       api_mode: chat_completions
   ```
4. Verify: `hermes doctor` and a direct `curl` to `/v1/chat/completions`.

## Key distinction users miss
- `hermes setup --portal` = OAuth subscription login + optional default-model pick. It does
  NOT expose "use Nous Portal models" as a provider you can switch to later the way a
  custom provider does.
- The free models `tencent/hy3:free` and `stepfun/step-3.7-flash:free` are ALSO available on
  openrouter (the current default provider). If the user only wants those free models usable,
  staying on openrouter and registering both IDs is simpler than configuring Portal at all.
- To have BOTH 28 and 29 selectable: setup wizard picks only ONE default. For two, either
  (a) pick one as default via wizard + register the other as an extra model, or (b) use the
  custom-provider path and list both models.

## `hermes config` subcommands (verified)
Valid: `show | edit | set | path | env-path | check | migrate`.
- There is NO `hermes config get`. To read current model config use `hermes config show`
  (prints a formatted view) or parse `config.yaml` directly with Python.
- `hermes config show` output example for model section:
  ```
  Model:        {'default': 'tencent/hy3:free', 'provider': 'openrouter'}
  ```

## Decision guide for "configure Nous Portal"
1. Want subscription + Tool Gateway (web search / image / TTS / browser) via OAuth, and can
   run an interactive terminal? -> `hermes setup --portal`, pick a model, done.
2. Want scripting / automation / API-key based, or need the wizard's TTY but environment has
   none? -> custom provider path (Path 2) with the endpoint above.
3. Only want the two free models and already on openrouter? -> no Portal config needed; just
   confirm both model IDs are selectable.
