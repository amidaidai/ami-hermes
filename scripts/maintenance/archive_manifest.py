"""Inventory archived Python files without importing or executing them."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def build_manifest(repo_root: Path) -> dict:
    """Return metadata only; dates/reasons are unknown without evidence.

    缺失归档根 -> FileNotFoundError（不能假装「0 个归档」）。
    归档区里的符号链接 -> ValueError（不允许把归档区以外的文件哈希进来）。
    """
    root = Path(repo_root).resolve()
    archive = root / "scripts/_disabled"
    if not archive.is_dir():
        raise FileNotFoundError(f"archive root missing: {archive.as_posix()}")
    entries = []
    for path in sorted(archive.rglob("*.py")):
        if path.is_symlink():
            raise ValueError(f"symlinked archive entry rejected: {path.as_posix()}")
        if not path.is_file():
            continue
        active = root / "scripts" / path.name
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        entries.append({
            "path": path.relative_to(root).as_posix(),
            "sha256": digest,
            "active_root_same_name": active.is_file(),
            "active_root_path": active.relative_to(root).as_posix() if active.is_file() else None,
            "reason": "unknown",
            "retired_date": "unknown",
        })
    return {
        "schema_version": 1,
        "archive_root": "scripts/_disabled",
        "active_root": "scripts",
        "archived_python_count": len(entries),
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    manifest = build_manifest(args.repo_root)
    output_dir = args.repo_root.resolve() / "docs/maintenance"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "archive_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    count = manifest["archived_python_count"]
    duplicates = sum(entry["active_root_same_name"] for entry in manifest["entries"])
    (output_dir / "README.md").write_text(
        "# Archived Python inventory\n\n"
        "Regenerate from the repository root:\n\n"
        "```sh\npython scripts/maintenance/archive_manifest.py\n```\n\n"
        "Optional: `--repo-root PATH`. Only `archive_manifest.json` and this README "
        "in `docs/maintenance/` are written. Archived and active scripts are read-only; "
        "nothing is imported, executed, deleted, moved, or restored.\n\n"
        f"Current inventory: **{count}** archived `.py` files; **{duplicates}** have "
        "a same-name file directly under `scripts/`. This name check is not proof of "
        "identical contents or actual runtime use.\n\n"
        "Each entry records a repository-relative path, SHA-256, same-name existence "
        "and its relative path (null if absent), reason, and retired_date. "
        "The scan is recursive under `scripts/_disabled/`, sorted by path. "
        "Reasons and retirement dates remain `unknown`: this tool has no validated "
        "retirement evidence input and does not infer from names, mtimes, or git history. "
        "No source text is included. No timestamp is emitted, so unchanged inputs "
        "produce identical output. Missing archive roots fail rather than claim zero.\n",
        encoding="utf-8",
    )
    print(f"Archived Python files: {count}; same-name active-root files: {duplicates}")
    print("Wrote docs/maintenance/archive_manifest.json and docs/maintenance/README.md")


if __name__ == "__main__":
    main()
