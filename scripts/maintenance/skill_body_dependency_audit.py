"""技能正文依赖交叉核验：扫 SKILL.md 正文里引用的凭证/环境变量，实测是否齐备。

frontmatter 的 required_* 覆盖率极低（351 个里只有 1 个声明），
真正的依赖声明散落在正文（如「Key: secrets/massive_api_key.txt」「需要 XXX_API_KEY」）。
本脚本把它们提取出来并逐条验证 → 才知道哪些技能「装了但跑不动」。
"""
from __future__ import annotations

import json
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path

SKILLS_DIR = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "skills"
SECRETS_DIR = Path("D:/Hermes agent/hermes/secrets")

# 只审 enabled 的技能（disabled 的是有意关闭，不算「不可用」）
DISABLED = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "skills_state.json"

PAT_SECRET_FILE = re.compile(r"secrets[/\\]([A-Za-z0-9_\-]+\.(?:txt|json|cmd))")
PAT_ENV = re.compile(r"\b([A-Z][A-Z0-9]{2,}_(?:API_KEY|TOKEN|KEY|SECRET|ID))\b")
PAT_CMD = re.compile(r"^\s*(?:\$ |`)?(uvx|npx|node|python3?|pip3?|deno|bun|gh|docker|ffmpeg|yt-dlp|rg|jq|curl)\b", re.M)


def load_disabled() -> set[str]:
    """从 hermes skills list 的输出反推已被禁用的技能名（若状态文件不可用则退化为空集）。"""
    import subprocess
    try:
        r = subprocess.run(["hermes", "skills", "list"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
    except Exception:
        return set()
    out = set()
    for line in r.stdout.splitlines():
        if line.startswith("│") and "Name" not in line and "─" not in line:
            parts = [x.strip() for x in line.strip("│\n").split("│")]
            if len(parts) >= 5 and parts[4] != "enabled":
                out.add(parts[0])
    return out


def env_or_secret(name: str) -> tuple[bool, str]:
    if os.environ.get(name):
        return True, "env"
    for cand in (name, f"{name}.txt", f"{name.lower()}.txt"):
        p = SECRETS_DIR / cand
        if p.is_file():
            v = p.read_text(encoding="utf-8", errors="replace").strip()
            if v.startswith("#") or len(v) < 8:
                return False, "占位符"
            return True, "secrets"
    return False, "无"


def main() -> int:
    disabled = load_disabled()
    findings: dict[str, dict] = defaultdict(lambda: {"secret_files": set(), "envs": set(), "cmds": set(), "missing": set()})

    for path in sorted(SKILLS_DIR.rglob("SKILL.md")):
        if ".bak" in path.name or path.parent.name.endswith(".bak") or "references" in path.parts:
            continue
        name = path.parent.name
        text = path.read_text(encoding="utf-8", errors="replace")
        f = findings[name]
        f["disabled"] = name in disabled or any(name.startswith(d[:18]) for d in disabled)

        for m in PAT_SECRET_FILE.finditer(text):
            f["secret_files"].add(m.group(1))
        for m in PAT_ENV.finditer(text):
            f["envs"].add(m.group(1))
        for m in PAT_CMD.finditer(text):
            f["cmds"].add(m.group(1))

        # 逐条验证
        for sf in f["secret_files"]:
            p = SECRETS_DIR / sf
            if not p.is_file():
                f["missing"].add(f"凭证文件 secrets/{sf} 不存在")
            else:
                v = p.read_text(encoding="utf-8", errors="replace").strip()
                if v.startswith("#") or len(v) < 8:
                    f["missing"].add(f"secrets/{sf} 是占位符/空")
        for e in f["envs"]:
            ok, why = env_or_secret(e)
            if not ok:
                f["missing"].add(f"环境变量 {e}（{why}）")
        for c in f["cmds"]:
            if not shutil.which(c):
                f["missing"].add(f"命令 {c} 不在 PATH")

    enabled_bad = {k: v for k, v in findings.items()
                   if v["missing"] and not v.get("disabled")}
    disabled_bad = {k: v for k, v in findings.items()
                    if v["missing"] and v.get("disabled")}

    out = Path("D:/Hermes agent/data/maintenance/skill_body_dependency_audit.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {k: {kk: sorted(vv) if isinstance(vv, set) else vv for kk, vv in v.items()}
         for k, v in findings.items() if v["missing"]},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"扫描技能: {len(findings)}  禁用名单命中: {len(disabled)}")
    print(f"有缺失依赖的启用技能: {len(enabled_bad)}")
    print(f"有缺失依赖的禁用技能: {len(disabled_bad)}")
    print(f"报告: {out}\n")

    print("=" * 96)
    print("【启用中但依赖缺失】—— 这些是「装了跑不动」的")
    print("=" * 96)
    for k in sorted(enabled_bad):
        print(f"\n{k}")
        for m in sorted(enabled_bad[k]["missing"]):
            print(f"   ✗ {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
