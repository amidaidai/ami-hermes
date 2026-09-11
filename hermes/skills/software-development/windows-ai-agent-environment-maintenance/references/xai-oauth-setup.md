# xAI / Grok OAuth Setup in Hermes

## Overview

Hermes supports OAuth-based authentication for xAI (Grok) via a PKCE authorization code flow. This allows you to use Grok models without an API key — just log into your X account.

## Command

```bash
hermes auth add xai-oauth --type oauth --no-browser --manual-paste
```

## Flow

1. Run the command above — it prints an authorization URL
2. Open that URL on any device (phone, laptop) — it leads to `auth.x.ai/oauth2/authorize`
3. Log into your X account and authorize Hermes
4. The browser tries to redirect to `http://127.0.0.1:<port>/callback?code=xxx&state=yyy` — this will fail (expected, because your phone/laptop can't reach Hermes's local callback listener)
5. Copy the **full failed callback URL** from your browser's address bar
6. Paste it back into the Hermes prompt

The OAuth token is stored in `auth.json` under `providers.xai-oauth` and becomes available for use.

## Flags Explained

| Flag | Purpose |
|------|---------|
| `--type oauth` | Credential type: OAuth authorization code flow |
| `--no-browser` | Skip auto-opening a browser on the Hermes host machine |
| `--manual-paste` | Use the manual callback URL paste mode instead of loopback listener |

## Key Details

- **Client ID** is hardcoded in Hermes (`b1a00492-073a-47ea-816f-4c329264a828`)
- **Scopes requested**: `openid profile email offline_access grok-cli:access api:access`
- **PKCE**: Uses S256 code challenge method (secure, no client secret needed)
- **Token storage**: `~/.hermes/auth.json` → `providers.xai-oauth`
- **Model name**: `grok-4.20-non-reasoning` (or newer, varies by availability)

## Verification

After successful setup, test with:

```bash
hermes -p <profile> --provider xai-oauth chat -q "Hello from Grok"
```

Or in a session, switch model via `/model` or `hermes model`.

## Pitfalls

- The callback URL will **fail** on mobile — this is normal. Copy the failed URL from the address bar.
- xAI may show the authorization code **in-page** (not as a redirect). In that case, paste the bare code value.
- Token refresh: OAuth tokens may expire. Run the flow again if Grok stops working.
- This only works if you have an X account (Premium adds more quota, but free accounts may have rate limits).
