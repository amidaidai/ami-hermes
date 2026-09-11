# Hermes Personal Workspace Layout

This reference captures a reusable pattern from organizing a Windows Hermes personalization workspace at `D:/Hermes agent`.

## Context

The workspace root is both the default working directory and a Git-backed Hermes personalization repository. It should remain safe and easy to inspect while still giving the agent places to put active work.

## Layout

- `hermes/` — durable Hermes personalization material: persona files, memories, cron jobs, and scripts.
- `hermes/scripts/` — reusable scripts that support the workspace.
- `hermes/scripts/repo-maintenance/` — GitHub remote reset, backup, and repository maintenance helpers.
- `hermes/secrets/` — local-only credentials and token files. Must be ignored by Git.
- `projects/` — long-term user projects. Prefer separate repositories for substantial projects.
- `sandbox/` — disposable experiments and temporary tests.
- `outputs/` — reports, generated deliverables, and exported artifacts.
- `README.md` — concise explanation of the workspace structure and root rules.

## Ignore Rules

For this pattern, `.gitignore` should include at least:

```gitignore
projects/
sandbox/
outputs/
hermes/secrets/
```

Keep existing broad sensitive patterns such as `.env`, `*.env`, `auth.json`, `*.cred`, `*secret*`, `*password*`, `*token*`, and `*_key.txt` when already present.

## Verification

After moving files:

```bash
git check-ignore -v hermes/secrets/.token_gh.txt projects sandbox outputs || true
git status --short
```

Expected outcome: sensitive/local-only files are ignored, and Git status only shows intentional documentation, ignore-rule, or script-location changes.

## Memory Pattern

Save the durable convention, not the move log. Example:

`Workspace D:/Hermes agent is the Hermes personalization repo; projects go in projects/, experiments in sandbox/, outputs in outputs/, repo maintenance scripts in hermes/scripts/repo-maintenance/, and local secrets in hermes/secrets/.`
