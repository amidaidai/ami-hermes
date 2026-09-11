# xAI / Grok OAuth Authorization for Hermes

Use this when the user says they are already logged into X and want to authorize Hermes to use the account. This is not the generic Twitter/X Developer OAuth flow; Hermes uses xAI/Grok OAuth via `auth.x.ai` / `accounts.x.ai` and stores tokens in Hermes auth state.

## Correct Flow

1. Start the Hermes OAuth helper so a local callback listener is active:

```bash
hermes auth add xai-oauth
```

2. If the normal `hermes` shim fails because PATH resolves to the Web UI desktop runtime, use the desktop runtime Python module entrypoint:

```bash
HERMES_HOME='C:/Users/Administrator/AppData/Local/hermes' \
'C:/Users/Administrator/.hermes-web-ui/desktop-runtime/hermes/0.16.0/win-x64/python/python.exe' \
-u -m hermes_cli.main auth add xai-oauth --no-browser --timeout 120
```

3. Give the user the URL printed by the running helper, not a hand-built static link from memory. The helper prints a URL like:

```text
https://auth.x.ai/oauth2/authorize?...&redirect_uri=http%3A%2F%2F127.0.0.1%3A56121%2Fcallback&scope=openid+profile+email+offline_access+grok-cli%3Aaccess+api%3Aaccess&code_challenge=...&state=...&nonce=...&plan=generic&referrer=hermes-agent
```

4. Keep the helper process alive until the browser redirects to `http://127.0.0.1:56121/callback`. If the helper is not running, the authorization cannot be written to `auth.json`.

5. Verify with:

```bash
hermes auth list
```

or, if the shim is unreliable, run the same Python module entrypoint with `auth list`.

## Manual Paste Fallback

If the browser cannot reach the local callback, use:

```bash
hermes auth add xai-oauth --manual-paste --no-browser
```

The user can paste either the full failed callback URL, `?code=...&state=...`, or the bare authorization code if xAI displays it in-page. This requires an interactive stdin; do not run it in a background process with closed stdin.

## Pitfalls

- Do not generate a generic `https://twitter.com/i/oauth2/authorize` link for this task. That is for X Developer apps, not Hermes Grok OAuth.
- Do not kill or timeout the OAuth helper after extracting the URL. The link is tied to the helper's PKCE verifier/state and needs the live callback listener.
- `--no-browser` still starts the loopback listener; it only prevents automatic browser launch.
- `--manual-paste` skips the loopback listener and prompts for the callback/code. It will fail with "missing authorization code" if stdin is not interactive.
- The Hermes auth store is profile/home dependent. Set `HERMES_HOME` to the active Hermes home before using alternate Python entrypoints so tokens land in the intended `auth.json`.
