# Hermes Studio (Web UI) Desktop App — Version Diagnosis & Update Path

The desktop "Hermes Web UI" ships as an **Electron app called Hermes Studio**, updated
through electron-updater — a channel completely separate from the `hermes update` CLI path.
This note captures the full diagnostic walk so a future session doesn't re-derive it.

## Two channels, never conflate them

| Component | Update mechanism | Version namespace | Location |
|-----------|------------------|-------------------|----------|
| Hermes Agent CLI | `hermes update` (git upstream) | `v0.17.0 (upstream <sha>)` | `%LOCALAPPDATA%/hermes/hermes-agent` |
| Hermes Studio desktop app (= Web UI) | electron-updater via `app-update.yml` | `0.6.x` (Electron app semver) | `%LOCALAPPDATA%/Programs/Hermes Studio/` |
| App's embedded backend runtime | bundled inside the app | `0.16.0` etc. | `~/.hermes-web-ui/desktop-runtime/hermes/<ver>/` |

The CLI and the app's embedded runtime are independent. Upgrading the CLI (e.g. to 0.17.0)
does NOT touch the app's bundled runtime (e.g. 0.16.0). The webui uses its own bundled copy.

## Diagnostic sequence (verified 2026-06-20)

```bash
# 1. CLI current state + whether behind
hermes --version            # shows "Update available: N commits behind" or "Up to date"
hermes update               # upgrade CLI; re-check hermes --version → "Up to date"

# 2. Locate the desktop app
ls -d "$LOCALAPPDATA"/Programs/*ermes*       # → "Hermes Studio"

# 3. Desktop app version (from the exe, no package.json present in Electron build)
APP="$LOCALAPPDATA/Programs/Hermes Studio"
powershell.exe -NoProfile -Command "(Get-Item '$APP\\Hermes Studio.exe').VersionInfo | Select-Object ProductVersion,FileVersion | Format-List"
#   → ProductVersion : 0.6.15.0   FileVersion : 0.6.15

# 4. Update source (electron-updater generic provider)
cat "$APP/resources/app-update.yml"
#   provider: generic
#   url: https://download.ekkolearnai.com        ← THIRD-PARTY mirror, not official Nous
#   updaterCacheDirName: hermes-studio-updater

# 5. What version the update source is actually serving
curl -fsSL "https://download.ekkolearnai.com/latest.yml" | grep -E 'version|releaseDate'
#   version: 0.6.15   releaseDate: '2026-06-15...'   ← equals installed → "already latest" from app's POV

# 6. Embedded backend runtime vs CLI
ls -1 ~/.hermes-web-ui/desktop-runtime/hermes/    # → 0.16.0
hermes --version | head -1                        # → v0.17.0 ... (independent)

# 7. Is the app running? (must be closed before any reinstall/overwrite)
tasklist //FI "IMAGENAME eq Hermes Studio.exe" //FO CSV
```

## The third-party distribution trap

- `npm view hermes-web-ui version` may show a newer number (e.g. `0.6.17`) — that is the
  **official NousResearch package**. A desktop app whose `app-update.yml` points at a
  third-party mirror (ekkolearnai.com, a Chinese-community custom distribution) is on a
  **different release line**. Its `latest.yml` lags the official npm package.
- If `<source>/latest.yml` version == installed version, the app's auto-update will report
  "already up to date" and genuinely cannot pull the npm number. This is not a bug.
- **Do NOT force-overwrite a third-party distribution with the official npm/installer build.**
  Risks: loses the distributor's customizations (`~/.hermes-web-ui/config.json` modelVisibility
  blocks, bundled runtime), and creates app/runtime version mismatch.
- Correct posture: present the tradeoff and let the user choose —
  ① wait for the distributor to push the new version to its own source (lowest risk),
  ② force-upgrade to the official build (back up `config.json` + entire `.hermes-web-ui` first),
  ③ click "check for updates" inside the app to confirm which source it consults.

## Key takeaway

When a user says "升级 hermes，升级 hermes webui" treat it as TWO tasks:
`hermes update` for the CLI (almost always works), and a separate electron-updater
diagnosis for the desktop app where the binding constraint is usually the distribution
source's `latest.yml`, not anything on the local machine.
