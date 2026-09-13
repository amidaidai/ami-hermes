# Archived Python inventory

Regenerate from the repository root:

```sh
python scripts/maintenance/archive_manifest.py
```

Optional: `--repo-root PATH`. Only `archive_manifest.json` and this README in `docs/maintenance/` are written. Archived and active scripts are read-only; nothing is imported, executed, deleted, moved, or restored.

Current inventory: **81** archived `.py` files; **30** have a same-name file directly under `scripts/`. This name check is not proof of identical contents or actual runtime use.

Each entry records a repository-relative path, SHA-256, same-name existence and its relative path (null if absent), reason, and retired_date. The scan is recursive under `scripts/_disabled/`, sorted by path. Reasons and retirement dates remain `unknown`: this tool has no validated retirement evidence input and does not infer from names, mtimes, or git history. No source text is included. No timestamp is emitted, so unchanged inputs produce identical output. Missing archive roots fail rather than claim zero.
