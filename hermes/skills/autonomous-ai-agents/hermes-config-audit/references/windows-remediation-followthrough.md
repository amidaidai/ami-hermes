# Windows Audit Remediation Follow-Through

Use this when a Hermes/Windows audit moves from findings into fixes. Keep it focused on repeatable remediation patterns, not one-off machine state.

## Lock down a Web UI port without breaking localhost

If Hermes Studio / Web UI listens on `0.0.0.0:<port>` and the user wants local-only access, add a Windows Firewall inbound block scoped to the local subnet while leaving loopback available:

```bash
netsh advfirewall firewall add rule \
  name="Anhe Block Hermes Web UI LAN <port>" \
  dir=in action=block protocol=TCP localport=<port> \
  remoteip=localsubnet profile=any

netsh advfirewall firewall show rule \
  name="Anhe Block Hermes Web UI LAN <port>" verbose
```

Verification:

```bash
curl -sS -I --max-time 5 http://127.0.0.1:<port>/
# From another LAN device, verify http://<host-lan-ip>:<port>/ is blocked.
```

Note: probing `http://<host-lan-ip>:<port>/` from the same host may still succeed because Windows can route it locally; do not treat that as proof the LAN block failed.

## Hermes update Web UI build recovery on Windows

After `hermes update`, the update can report success while the Web UI build fails if workspace dev dependencies are absent. Typical errors:

- `Cannot find module '@vitejs/plugin-react'`
- `Could not find a declaration file for module 'qrcode'`
- `Cannot find type definition file for 'vite/client'` or `node`

Recovery pattern from the Hermes source checkout:

```bash
cd /c/Users/Administrator/AppData/Local/hermes/hermes-agent
export PATH="/c/Users/Administrator/AppData/Local/hermes/node:$PATH"
npm install --prefix web --include=dev
npm run --prefix web build
hermes doctor
```

Expected verification:

- `npm run --prefix web build` ends with `built in ...`.
- `hermes doctor` reports `web workspace deps (no known vulnerabilities)` and `ui-tui workspace deps (no known vulnerabilities)`.

## Gateway restart after update

`hermes update` may stop the manually managed Windows gateway. Verify status after updating:

```bash
hermes status --all
```

If the gateway is stopped and no service is installed, run it as a manual process/background job from the correct Hermes venv entrypoint, then verify Telegram/Discord connection lines in `gateway.log` and `hermes status --all`.
