# AI CLI Provider Routing on Windows: codex + cc-switch + opencode gateway

Session: 2026-08-11. User's codex could not connect through cc-switch to an
"opencode cg" (opencode.ai zen/go) provider. Two stacked root causes, plus two
self-inflicted npm hazards discovered during the repair.

## Architecture (cc-switch "local proxy takeover" model)

cc-switch (AppData `~/.cc-switch/cc-switch.db` SQLite, GUI app) manages CLI
provider configs. For codex it works by **taking over** `~/.codex/config.toml`:

- While the proxy is active, config.toml has:
  ```toml
  [model_providers.custom]
  base_url = "http://127.0.0.1:15721/v1"   # local proxy, NOT the upstream
  wire_api = "responses"
  experimental_bearer_token = "PROXY_MANAGED"
  ```
- cc-switch's local proxy (PID = cc-switch.exe itself, port 15721) does the
  **protocol conversion**: codex speaks `responses`, but many upstreams
  (opencode zen/go, apiFormat=openai_chat) only speak `chat/completions`.
  Proxy log shows the conversion target:
  `[Codex] >>> 请求目标: https://opencode.ai/zen/go/v1/chat/completions`
- Token is injected by the proxy (`PROXY_MANAGED`), so the user's real key
  lives only in cc-switch's db, not in config.toml/auth.json.

## Symptom & root cause chain

1. `codex --version` → `Error: Missing optional dependency @openai/codex-win32-x64`
   — codex binary itself broken (see below), never even reached cc-switch.
2. After fixing the binary: `codex exec` → `ERROR: unexpected status 422
   Unprocessable Entity ... url: https://opencode.ai/zen/go/v1/responses`
   — config.toml had been **reverted to direct-connect**:
   ```toml
   base_url = "https://opencode.ai/zen/go/v1"   # direct, no proxy
   wire_api = "responses"
   ```
   opencode zen/go only accepts chat/completions → responses direct = 422.
   This happens when cc-switch auto-revokes the takeover: log lines
   `检测到接管残留，开始恢复 Live 配置` / `codex Live 配置已从备份恢复` /
   `代理已停止`. The app then exits (also crash-prone: tao event loop
   `cannot move state from Destroyed` in `~/.cc-switch/crash.log`).

**Diagnosis order** (all quick):
- `grep base_url ~/.codex/config.toml` → proxy (127.0.0.1:15721) vs direct (upstream)?
- `netstat -ano | grep 15721` → proxy listening? PID should be cc-switch.exe
- `tail ~/.cc-switch/logs/cc-switch.log` → 接管/恢复 lines
- Probe both endpoints through the proxy:
  `curl -s -X POST http://127.0.0.1:15721/v1/chat/completions -d '{"model":"<m>","messages":[{"role":"user","content":"hi"}]}'`
  (proxy converts responses↔chat, so EITHER /v1/responses or /v1/chat/completions answers)

**Fix**: restart cc-switch (GUI app — `cmd /c start` may fail silently in
git-bash; use `powershell Start-Process`). It re-takes-over the takeover and
rewrites config.toml back to the proxy address. Verify with a real `codex exec`.

## codex platform binary: alias package, not a real package

- `@openai/codex-win32-x64` does **not** exist on the npm registry (404).
  It's an **alias**: in codex's package.json optionalDependencies →
  `"@openai/codex-win32-x64": "npm:@openai/codex@0.144.4-win32-x64"`.
  So `npm view @openai/codex-win32-x64 versions` → 404 is EXPECTED.
- When the optional dep is silently skipped at install, `bin/codex.js` throws
  `Missing optional dependency @openai/codex-win32-x64. Reinstall Codex`.
- Fix (temp-dir pattern, see hazard below):
  ```bash
  mkdir /tmp/codex-fix && cd /tmp/codex-fix
  echo '{"name":"t","version":"1.0.0"}' > package.json   # REQUIRED, see hazard
  npm install @openai/codex@<ver>        # pulls main + win32-x64 alias
  cp -r node_modules/@openai/codex* <hermes-node>/node_modules/@openai/
  ```
- Latest known: 0.147.0 at the time. Same alias trick applies to darwin/linux variants.

## HAZARD: `npm install` in a directory WITHOUT package.json wipes node_modules

Running `npm install <pkg>` in a dir with no package.json (e.g. a portable
Node root like `AppData/Local/hermes/node`) makes npm treat the whole
node_modules as an orphaned tree → `removed 199 packages` — including npm
itself, corepack, and any other global CLIs. This is how the repair session
broke npm/claude/codex further.

**Rule**: never `npm install` into a bare toolchain dir. Always create a temp
project dir with a `package.json` first, install there, then copy artifacts.

**Recovery from a wiped portable Node**:
- npm + corepack: download the matching official zip
  `https://nodejs.org/dist/v<ver>/node-v<ver>-win-x64.zip`, extract, copy
  `node_modules/npm/` and `node_modules/corepack/` back. `npm --version` proves it.
- Other globals (claude-code, codex): reinstall in temp dir + copy, or copy
  from a sibling global install (`node/global/node_modules/...`).
- Delete the recovery zip after.

## `ignore-scripts=true` in ~/.npmrc → broken postinstall packages

User `~/.npmrc` has `ignore-scripts=true` (plus proxy 127.0.0.1:7897). Packages
that download/place binaries in postinstall silently ship a stub instead:
- opencode-ai: `bin/opencode.exe` is a 479-byte `echo "Error: opencode-ai's
  postinstall script was not run"` stub. Fix: `cd node_modules/opencode-ai && node postinstall.mjs`
- @anthropic-ai/claude-code: `bin/claude.exe` missing (only
  `claude.exe.old.<ts>`); real binary lives in the platform dep
  `node_modules/@anthropic-ai/claude-code-win32-x64/claude.exe`. Fix:
  `cp <pkg>/node_modules/@anthropic-ai/claude-code-win32-x64/claude.exe <pkg>/bin/claude.exe`

## corepack shim on git-bash (MSYS)

`corepack --version` from git-bash failed with a `C:\c\Users\...` double-drive
path: the generated shim only had a `*CYGWIN*)` branch, missing MINGW/MSYS.
Fix: rewrite the shim to handle all three (same pattern as npm's codex/claude shims):
```sh
case `uname` in
    *CYGWIN*|*MINGW*|*MSYS*)
        if command -v cygpath > /dev/null 2>&1; then basedir=`cygpath -w "$basedir"`; fi ;;
esac
```
