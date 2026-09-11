# Hermes Local Update And Self-Check Notes

Use these notes when a Windows Hermes install has been updated or repaired and the user asks for a local self-check.

## Useful Verification Sequence

1. Resolve the active Hermes command first: compare `command -v hermes`, the venv script under `%LOCALAPPDATA%/hermes/hermes-agent/venv/Scripts/hermes`, and any desktop/runtime shim that appears earlier on PATH.
2. If a shim/trampoline is broken but the source venv entrypoint works, prefer temporarily prioritizing the source venv path or shell startup path rather than reinstalling immediately.
3. Run a compact but real self-check:
   - `hermes --version`
   - `hermes doctor`
   - `hermes status --all`
   - app-specific build/test command when the repair touched Web UI or dependencies.
4. Before running update/repair commands, back up local config/auth in a timestamped folder and redact secrets in any copied diagnostic notes.
5. If `hermes update` leaves a conflict or `.update-incomplete` marker, inspect git status and update logs first. Do not delete user custom changes; stop or resolve only files clearly within the requested repair scope.
6. After dependency changes in the Web UI, validate with `npm run build` rather than only checking `npm install` exit status.

## Pitfalls

- A successful direct venv `hermes --version` does not prove the shell PATH uses that entrypoint. Verify both direct path and PATH lookup.
- `npm config omit=dev` can leave Web UI build tools missing; installing dev dependencies locally may be required before `npm run build` can validate the UI.
- Do not normalize or clean unrelated git changes while doing a local self-check. Report residual dirty files separately.
- Treat update conflicts and transient missing binaries as setup state. Capture the repair pattern, not a permanent claim that a tool is broken.
