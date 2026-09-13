"""把「引用了但从未落地」的 references/*.md 就地标注为（未落地）。

背景：技能正文常写「详见 `references/xxx.md`」，但该文件从未随技能落地 ——
读者按图索骥必然扑空。审计口径：**不要为凑数而编造文档内容**，
就地标注比凭空生成诚实，也保住了「哪一份本来该写」的信息。

用法：
    python scripts/maintenance/annotate_missing_refs.py          # 预演（默认，不改盘）
    python scripts/maintenance/annotate_missing_refs.py --apply  # 落盘

安全边界：
  · 只改 live SKILL.md（跳过 .bak-* 与 references/ 目录内的文件）
  · 只处理 trading 分类下的技能（本次审计范围）
  · 已能解析到实体的引用不动；已标过的（后接「（未落地」）不重复标
  · 只改形如 `references/xxx.md` 的反引号引用
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# 只标注我们自己的 trading 技能；社区/内置技能的内容不归本系统维护，
# 改了也会被 `hermes skills update` 覆盖，且不属于「我方不可用资产」范畴。
SKILLS = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "skills" / "trading"
REF = re.compile(r"`(references/[A-Za-z0-9_\-.]+\.md)`(?!（未落地)")
MARK = "（未落地·勿引）"


def main() -> int:
    apply = "--apply" in sys.argv
    changed: list[tuple[str, str]] = []

    for path in sorted(SKILLS.rglob("SKILL.md")):
        if ".bak" in path.name or ".bak" in str(path.parent):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        skill_root = path.parent
        hits: list[str] = []

        def repl(m: re.Match[str], root: Path = skill_root, acc: list[str] = hits) -> str:
            ref = m.group(1)
            if (root / ref).is_file():
                return m.group(0)
            if ref not in acc:
                acc.append(ref)
            return f"`{ref}`{MARK}"

        new = REF.sub(repl, text)
        if new != text:
            if apply:
                path.write_text(new, encoding="utf-8")
            for ref in hits:
                changed.append((str(path.relative_to(SKILLS)), ref))

    verb = "已标注" if apply else "将标注（预演）"
    print(f"{verb} {len(changed)} 处未落地的参考文档引用：\n")
    for skill, ref in changed:
        print(f"  {skill:<56} {ref}")
    if not apply:
        print("\n（未改盘；确认后加 --apply 落盘）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
