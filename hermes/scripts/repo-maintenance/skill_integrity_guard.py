#!/usr/bin/env python3
"""技能文件完整性护栏 (skill_integrity_guard)

防止「无声损坏」——文件被污染或 frontmatter 损坏后没人发现，
直到换渠道生成不出卡才暴露。每天扫一遍，当天报警。

检测两类问题：
  1. 行号污染：行首出现 `数字|` 前缀（read_file 带行号输出被当内容 write_file 回写的事故）
  2. frontmatter 损坏：SKILL.md 缺少 `---` 边界 / 缺 name / 缺 description / 首行不是 ---

用法：
  python skill_integrity_guard.py                # 扫默认技能根，发现问题退出码 1
  python skill_integrity_guard.py --root <dir>   # 指定扫描根
  python skill_integrity_guard.py --json         # 机器可读输出（接推送/cron）

退出码：0=全干净  1=发现问题  2=扫描出错
背景：2026-06-19 tradingview-indicator-analysis 母版被行号污染，
frontmatter 解析失败导致跨渠道认不出该技能、分析卡生成不了。本脚本即为防此类复发。
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(
    os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))
) / "hermes" / "skills"

LINE_NUM_PREFIX = re.compile(r"^\d+\|")


def scan_line_pollution(path: Path) -> list[str]:
    """返回前几行出现行号污染的样本（行首 `数字|`）。只看前 20 行即可判定。"""
    hits = []
    try:
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 20:
                    break
                if LINE_NUM_PREFIX.match(line):
                    hits.append(f"L{i+1}: {line[:50].rstrip()}")
    except (OSError, UnicodeDecodeError) as e:
        hits.append(f"<读取失败 {type(e).__name__}>")
    return hits


def check_frontmatter(path: Path) -> list[str]:
    """SKILL.md 专属：校验 YAML frontmatter 完整。返回问题列表，空=正常。"""
    problems = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [f"<读取失败 {type(e).__name__}>"]
    lines = text.splitlines()
    if not lines:
        return ["文件为空"]
    if lines[0].strip() != "---":
        problems.append(f"首行不是 `---`（实际: {lines[0][:40]!r}）")
        return problems  # 首行就坏，后面不用查了
    # 找第二个 --- 边界（放宽到 150 行：部分社区技能 frontmatter 含大量嵌套元数据，
    # 如 last30days 的 metadata.openclaw 块，结束边界可达 60+ 行）
    end = None
    for i in range(1, min(len(lines), 150)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        problems.append("缺少 frontmatter 结束边界 `---`")
        return problems
    fm = "\n".join(lines[1:end])
    if not re.search(r"^name:\s*\S", fm, re.M):
        problems.append("frontmatter 缺 name 字段")
    if not re.search(r"^description:\s*\S", fm, re.M):
        problems.append("frontmatter 缺 description 字段")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="技能文件完整性护栏")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="技能根目录")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        msg = f"技能根目录不存在: {root}"
        print(json.dumps({"error": msg}) if args.json else f"❌ {msg}")
        return 2

    md_files = sorted(root.rglob("*.md"))
    # 排除归档/备份
    md_files = [p for p in md_files if ".bak" not in p.name and "corrupted" not in str(p)]

    polluted = []      # 行号污染（所有 .md）
    fm_broken = []     # frontmatter 损坏（仅 SKILL.md）

    for p in md_files:
        hits = scan_line_pollution(p)
        if hits:
            polluted.append({"file": str(p), "samples": hits})
        if p.name == "SKILL.md":
            fm = check_frontmatter(p)
            if fm:
                fm_broken.append({"file": str(p), "problems": fm})

    total_skill = sum(1 for p in md_files if p.name == "SKILL.md")
    clean = not polluted and not fm_broken

    if args.json:
        print(json.dumps({
            "clean": clean,
            "scanned_md": len(md_files),
            "scanned_skill_md": total_skill,
            "line_pollution": polluted,
            "frontmatter_broken": fm_broken,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"扫描 {len(md_files)} 个 .md（含 {total_skill} 个 SKILL.md），根: {root}")
        if clean:
            print("✓ 全部干净：无行号污染、frontmatter 完整")
        else:
            if polluted:
                print(f"\n❌ 行号污染 {len(polluted)} 个文件：")
                for item in polluted:
                    print(f"  {item['file']}")
                    for s in item["samples"][:3]:
                        print(f"      {s}")
            if fm_broken:
                print(f"\n❌ frontmatter 损坏 {len(fm_broken)} 个 SKILL.md：")
                for item in fm_broken:
                    print(f"  {item['file']}")
                    for s in item["problems"]:
                        print(f"      - {s}")
            print("\n修复参考：Python 逐行剥离行首 `^\\d+\\|`（只剥第一个，不动正文表格 `|`），")
            print("先备份到 outputs/corrupted-backups/ 再写回，然后重跑本脚本验证。")

    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
