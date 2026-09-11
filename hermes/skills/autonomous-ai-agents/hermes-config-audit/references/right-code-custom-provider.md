# Right Code / Custom Provider Audit Notes

Use this reference when a user asks whether Hermes is correctly configured for Right Code or another OpenAI-compatible custom provider.

## What to Check

1. **Do not assume WSL paths on Windows.** Hermes Studio and current Windows-native installs commonly use `C:/Users/<user>/AppData/Local/hermes/config.yaml`, not `~/.hermes/config.yaml`.
2. **Read `model` and `custom_providers` together.** A working setup may use:
   - `model.provider: custom:<name>`
   - `custom_providers[].name: <name>`
   - `custom_providers[].base_url: https://right.codes/codex/v1`
3. **Check the credential pool without exposing secrets.** `auth.json` may contain `credential_pool.custom:<name>` entries with `secret_fingerprint`, `base_url`, and request counters. Report existence/status, not raw keys.
4. **Use logs as proof of real operation.** `logs/agent.log` lines with `provider=custom`, the expected `base_url`, model name, token counts, and `cache=...` are strong evidence that Hermes has successfully called the provider.
5. **Treat direct curl/urllib probes carefully.** A minimal `/chat/completions` request can fail with provider-side gateway errors even when Hermes succeeds, because Hermes may send a different request shape, headers, or patched Codex-compatible payload.
6. **Look for provider naming mismatches.** Warnings like `Credential pool provider mismatch: pool=custom:right.codes, agent=custom` mean the setup may work but credential-pool bookkeeping can be inconsistent.

## Reporting Guidance

- Say “configured and has successfully run” only when config/auth exists and logs show successful API calls.
- Say “not exactly matching the external doc” when docs expect `provider: custom` plus `model.base_url`, but the install uses named `custom_providers` and `custom:<name>`.
- Avoid declaring the API key invalid from one direct probe if Hermes logs show recent successful calls.
- For Right Code caching questions, check recent `cache=` values in `agent.log`; high cache percentages are evidence that prompt caching compatibility is working.
