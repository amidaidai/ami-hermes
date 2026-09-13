"""技能「空壳」扫描：SKILL.md 正文引用的本地文件是否存在。

比 python3/docker 这类环境依赖更致命的一类不可用：技能正文明确告诉你
「跑 scripts/xxx.py」，但那个脚本根本没随技能落地 —— 照着做必然失败。

扫描模式：
  scripts/xxx.py|sh|js   references/xxx.md   templates/xxx   assets/xxx
判据：相对技能目录找不到，且在仓库其它常见位置也找不到 → BROKEN_REF
"""
from __future__ import annotations

import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

SKILLS_DIR = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "skills"
REPO = Path("D:/Hermes agent")

PAT = re.compile(r"(?<![\w/.])((?:scripts|references|templates|assets)/[A-Za-z0-9_.\-/]+\.[A-Za-z0-9]{1,6})")
SKIP_PARTS = {"node_modules", ".git", "__pycache__", "hermes-agent"}
# 已就地声明「未落地」的引用不再视为缺陷（annotate_missing_refs.py 打的标记）
ANNOTATED_MARKERS = ("（未落地", "(future)", "（future)", "（未实现")
# 文档里的占位示例名，不是真引用
PLACEHOLDER_RE = re.compile(r"/(xxx|xx|foo|bar|X|Y|your_[a-z_]+)\.", re.IGNORECASE)


def disabled_names() -> set[str]:
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


def repo_index() -> set[str]:
    names: set[str] = set()
    for root in (REPO, Path(os.environ["LOCALAPPDATA"]) / "hermes" / "skills"):
        for p in root.rglob("*"):
            if p.is_file() and not any(s in p.parts for s in SKIP_PARTS):
                names.add(p.name)
    return names


def main() -> int:
    disabled = disabled_names()
    idx = repo_index()

    broken: dict[str, list[str]] = defaultdict(list)
    annotated: dict[str, list[str]] = defaultdict(list)
    placeholders: dict[str, list[str]] = defaultdict(list)
    total_refs = 0
    for path in sorted(SKILLS_DIR.rglob("SKILL.md")):
        if ".bak" in str(path):
            continue
        name = path.parent.name
        # 跳过子技能聚合目录里的重复
        skill_root = path.parent
        text = path.read_text(encoding="utf-8", errors="replace")
        refs = {r for r in PAT.findall(text)
                if "__pycache__" not in r and not r.endswith(".pyc")}
        total_refs += len(refs)
        for ref in refs:
            if (skill_root / ref).is_file():
                continue
            basename = Path(ref).name
            if basename in idx:
                continue  # 文件在仓库别处存在（引用路径写法不同，不算坏）
            # 该引用是否已被就地标注为「未落地」/「future」
            if any(
                (m.group(0).split("`")[0].endswith(ANNOTATED_MARKERS)
                 or any(mk in text[max(0, m.start() - 24):m.start() + len(ref) + 24]
                        for mk in ANNOTATED_MARKERS))
                for m in re.finditer(re.escape(ref), text)
            ):
                annotated[name].append(ref)
                continue
            if PLACEHOLDER_RE.search(ref):
                placeholders[name].append(ref)
                continue
            broken[name].append(ref)

    enabled_broken = {k: v for k, v in broken.items() if k not in disabled}
    dis_broken = {k: v for k, v in broken.items() if k in disabled}
    enabled_annotated = {k: v for k, v in annotated.items() if k not in disabled}
    enabled_ph = {k: v for k, v in placeholders.items() if k not in disabled}

    print(f"扫描技能目录: {len(list(SKILLS_DIR.rglob('SKILL.md')))} 个 SKILL.md")
    print(f"引用到的本地文件路径总数: {total_refs}")
    print(f"引用不存在文件的【启用】技能: {len(enabled_broken)}")
    print(f"引用不存在文件的【禁用】技能: {len(dis_broken)}")
    print(f"已就地标注为「未落地」的引用: {sum(len(v) for v in annotated.values())} 处 / "
          f"{len(annotated)} 个技能（不算缺陷）")
    print(f"文档占位示例（xxx/foo 类，不算缺陷）: {sum(len(v) for v in placeholders.values())} 处 / "
          f"{len(placeholders)} 个技能")
    print()
    print("=" * 92)
    print("【启用中】引用了不存在的文件 —— 照着技能做必然失败")
    print("=" * 92)
    for k in sorted(enabled_broken):
        print(f"\n{k}")
        for r in sorted(set(enabled_broken[k])):
            print(f"   ✗ {r}  (文件不存在)")

    if enabled_ph:
        print("\n" + "-" * 92)
        print("占位示例（供确认，通常无需处理）")
        print("-" * 92)
        for k in sorted(enabled_ph):
            print(f"  {k}: {', '.join(sorted(set(enabled_ph[k])))}")

    out = Path("D:/Hermes agent/data/maintenance/skill_broken_refs.json")
    out.write_text(__import__("json").dumps(
        {"enabled": {k: sorted(set(v)) for k, v in enabled_broken.items()},
         "disabled": {k: sorted(set(v)) for k, v in dis_broken.items()},
         "annotated_missing": {k: sorted(set(v)) for k, v in enabled_annotated.items()},
         "placeholders": {k: sorted(set(v)) for k, v in enabled_ph.items()}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
