"""技能可用性审计：解析每个 SKILL.md 的依赖声明并逐条实测。

判据（对齐 Hermes 的 readiness 语义）：
  required_environment_variables -> 检查环境变量 / secrets 里是否有对应值
  required_commands             -> 检查该命令是否在 PATH
  required_credential_files     -> 检查文件是否存在
分类：
  READY      依赖齐备
  MISSING    有明确缺失（这就是「当前不可用」的技能）
  NO_DEPS    未声明依赖
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

SKILLS_DIR = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "skills"
SECRETS_DIR = Path("D:/Hermes agent/hermes/secrets")


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(block)
        return data if isinstance(data, dict) else {}
    except Exception:
        out: dict[str, object] = {}
        for line in block.splitlines():
            m = re.match(r"^([a-zA-Z_]+):\s*(.*)$", line)
            if m and m.group(2):
                out[m.group(1)] = m.group(2).strip().strip("'\"")
        return out


def as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v else []
    if isinstance(v, list):
        return [str(x).strip().strip("'\"") for x in v if str(x).strip()]
    return []


def secret_value(name: str) -> str:
    """允许 name 是 secrets 文件名（可省 .txt）。"""
    cands = [name, f"{name}.txt", f"{name}.json"]
    for c in cands:
        p = SECRETS_DIR / c
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                return "?"
    return ""


def check_env(name: str) -> tuple[bool, str]:
    if os.environ.get(name):
        return True, "env"
    val = secret_value(name)
    if val and not val.startswith("#"):
        return True, "secrets文件"
    if val.startswith("#"):
        return False, "secrets里是占位符/注释"
    return False, "无"


def main() -> int:
    rows: list[dict] = []
    for path in sorted(SKILLS_DIR.rglob("SKILL.md")):
        rel = path.relative_to(SKILLS_DIR)
        fm = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        envs = as_list(fm.get("required_environment_variables"))
        cmds = as_list(fm.get("required_commands"))
        files = as_list(fm.get("required_credential_files"))

        missing_env, missing_cmd, missing_file = [], [], []
        for e in envs:
            ok, why = check_env(e)
            if not ok:
                missing_env.append(f"{e}({why})")
        for c in cmds:
            if not shutil.which(c):
                missing_cmd.append(c)
        for f in files:
            if not (Path(f).expanduser().is_file() if Path(f).is_absolute()
                    else (SECRETS_DIR / f).is_file() or (Path.cwd() / f).is_file()):
                missing_file.append(f)

        declared = bool(envs or cmds or files)
        missing = missing_env + missing_cmd + missing_file
        rows.append({
            "skill": str(rel.parent),
            "declared": declared,
            "envs": envs, "cmds": cmds, "files": files,
            "missing": missing,
            "status": "MISSING" if missing else ("READY" if declared else "NO_DEPS"),
        })

    out = Path("D:/Hermes agent/data/maintenance/skill_dependency_audit.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    missing = [r for r in rows if r["status"] == "MISSING"]
    ready = [r for r in rows if r["status"] == "READY"]
    nodeps = [r for r in rows if r["status"] == "NO_DEPS"]

    print(f"技能总数: {len(rows)}")
    print(f"  声明了依赖且齐备 (READY)   : {len(ready)}")
    print(f"  声明了依赖但有缺失 (MISSING): {len(missing)}")
    print(f"  未声明依赖 (NO_DEPS)       : {len(nodeps)}")
    print(f"\n报告: {out}\n")

    if missing:
        print("=" * 96)
        print("依赖缺失的技能（当前不可用/功能受限）")
        print("=" * 96)
        for r in missing:
            print(f"\n[{r['skill']}]")
            print(f"  缺失: {'; '.join(r['missing'])}")
    else:
        print("没有技能声明了未满足的依赖。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
