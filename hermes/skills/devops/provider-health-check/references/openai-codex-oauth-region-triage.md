# OpenAI Codex OAuth / Region Triage

## Durable workflow

- Establish the local state before changing anything: `hermes --version`, `hermes auth list`, `hermes doctor`.
- Distinguish **credential state** from **route eligibility**. `openai-codex` may be listed as logged in while the active proxy egress is rejected by OpenAI.
- Inspect proxy presence and endpoint metadata only; never print proxy URLs containing credentials.
- For a manual device flow, run:

```bash
hermes auth add openai-codex --no-browser --timeout 90
```

The command prints `https://auth.openai.com/codex/device`, a one-time device code, and waits for completion. The user must enter the code and complete login/consent in their own browser. Keep the waiting process alive until success or timeout.

## Acceptance checks

1. Device flow exits successfully.
2. `hermes auth list` still shows an `openai-codex` OAuth credential.
3. `hermes doctor` reports OpenAI Codex auth as logged in.
4. A minimal real request succeeds through the same route.

A successful device authorization alone does not prove that subsequent API inference is permitted from the current egress region.

## Safety and interpretation

- Do not delete or overwrite a working credential before testing another route.
- Do not collect passwords, MFA codes, access tokens, refresh tokens, cookies, or full proxy URLs.
- A 403 from `auth.openai.com` or Cloudflare proves the endpoint was reached, not that the Hermes installation is broken.
- If the user's actual location is unsupported, report the restriction and use an available provider instead of recommending circumvention.
