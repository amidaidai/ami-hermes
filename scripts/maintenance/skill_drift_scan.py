#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能/文档 指标漂移扫描（只读体检，可反复跑）。

为什么要有这个
--------------
指标改了，仓内代码有契约+守卫把关；但**技能文档**里散落的旧版本号、
旧行数、已废止 DW 名、被取代的脚本名没人管，下一次会话就会照着错的干活。
本工具把「哪些技能还写着旧事实」变成一次可复现的扫描。

用法:
    python tools/skill_drift_scan.py               # 只列清单
    python tools/skill_drift_scan.py --live-only    # 只列 SKILL.md 与无日期参考（可自动修）
    python tools/skill_drift_scan.py --json out.json

分级:
    LIVE       = SKILL.md 本体，或文件名不含日期的参考文档 —— 这是当下真会被人读的
    HISTORICAL = 文件名/文头日期早于定版（2026-09-01）的历史记录 —— 只报告，不改写（它们是当时的实况）

抑制规则（避免噪声淹没真问题）:
    · 行内含「已废止/已移入/已归档/退役/示意名/历史记录」等标记 → 已显式声明，不算漂移
    · 文件顶部 60 行内含 `dead-script-index.md`（文件级退役横幅）→ 该文件的「脚本名」类不再逐行报
      （字段/行名类仍报，因为横幅没覆盖它们）
    · 指针文件 `dead-script-index.md` / `tv-dual-indicator-field-map.md` 整体跳过
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SKILLS = Path.home() / "AppData/Local/hermes/skills"
REPO = Path("D:/Hermes agent")
DATE_RE = re.compile(r"20\d{2}[-_]?\d{2}[-_]?\d{2}")
# 定版指标的日期：比它更早的「当前」声明都已过期。
CURRENT_EPOCH = 20260901
_ANY_DATE = re.compile(r"20\d{2}[-_年]?\s?\d{1,2}[-_月]?\s?\d{1,2}日?")


def _newest_date(lines: list[str]) -> int:
    """取文件头 14 行里最大的日期（YYYYMMDD）；找不到返回 0。"""
    best = 0
    for line in lines[:14]:
        for match in _ANY_DATE.finditer(line):
            digits = re.sub(r"\D", "", match.group(0))
            if len(digits) == 8:
                best = max(best, int(digits))
    return best

# (分类, 正则, 说明)。只用「确定过期」的模式，避免误报。
PATTERNS: list[tuple[str, str, str]] = [
    # 行数必须紧跟「行/lines」，否则会把年份 2024/2025 之类的数字当行数。
    ("旧行数", r"\b(3446|3463|3419|3163|3134|2859|2518|921|876|469)\s*(行|lines?)\b",
     "定版主指标 3557 行 / 副指标 966 行"),
    ("旧版本号", r"\bv(5|6|10|13|14|15)\s*(指标|版指标|production|生产)",
     "定版 = 主「空格修正」/ 副「最终版」(2026-09-11)"),
    ("旧sha", r"(98d6338b|9f713669|84094d32|fdbcdf73|0cf4feb0|703eb981|b049bac0)",
     "定版 sha 主 68a34fc3 / 副 c4c563ef"),
    ("废止DW名", r"(MCP CVD Value|OI Total|Estimated CVD Value|MCP EMA Length|MCP Risk Pack|"
                 r"Bull FVG CE|Bear FVG CE|MCP FVG Quality Code)",
     "这些 DW 字段当前指标已不导出；只在契约 LEGACY_* 里为历史缓存保留"),
    ("废止DW名(长)", r"MCP StructPack \(FvgQ", "当前 DW 名就是 `MCP StructPack`"),
    ("四态标签误写", r"四态(标签)?[^\n]{0,40}(风控|禁做)",
     "「风控」行只有 3 个标签（风控/风控·观察/风控·未授权）；`禁做·不出价` 是 setupX 的行值"),
    ("旧10行行名", r"(进场|止损|目标|确认|核对)\s*[·、/|]\s*[^\n]{0,24}(磁吸|前位|现位|协同|核对)",
     "主指标当前 13 行：位置/结论/方向/路径/风控/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位"),
]

# 被取代/不存在的脚本名被当成「当前工具」时
DEAD_SCRIPTS = ["btc_keylevel_ws_guard", "btc_keylevel_sentinel", "btc_keylevel_rest_guard",
                "btc_price_arrival_sentinel", "btc_alert_watch_v3", "btc_push_cron",
                "btc_collector", "btc_fast_daemon", "btc_vwap_daemon"]
LIVE_SCRIPTS = {"keylevel_guard", "keylevel_read_trigger", "btc_keylevel_guard_watchdog",
                "btc_tv_refresh", "xau_tv_sync", "data_freshness_watchdog", "tv_keepalive",
                "cron_signal_tick", "cron_signal_report", "keylevels_structure_review"}


def classify(path: Path, lines: list[str] | None = None) -> str:
    if path.name == "SKILL.md":
        return "LIVE"
    if DATE_RE.search(path.name) or DATE_RE.search(str(path.parent)):
        return "HISTORICAL"
    # references/ 下的文档默认是「记录」：若文头自报的日期早于定版，按历史处理，
    # 不去改写它 —— 它是当时的实况，改了反而失真。
    if "references" in path.parts and lines:
        newest = _newest_date(lines)
        if newest and newest < CURRENT_EPOCH:
            return "HISTORICAL"
    return "LIVE"


# 已经**显式标注**为废止的段落不算漂移：那正是我们希望文档做的事。
ANNOTATED = ("已废止", "已作废", "作废", "已不存在", "已删除", "不可读", "勿再当现行",
             "历史记录", "已被删除", "已移入", "已归档", "退役", "示意名", "不要照抄")


def main() -> int:
    live_only = "--live-only" in sys.argv
    findings: list[dict] = []
    if not SKILLS.exists():
        print(f"✗ 找不到技能目录 {SKILLS}")
        return 1
    for path in sorted(SKILLS.rglob("*.md")):
        if any(part in {"node_modules", "__pycache__"} for part in path.parts):
            continue
        if path.name in {"dead-script-index.md", "tv-dual-indicator-field-map.md"}:
            continue  # 指针/索引文件本身就要列废止名，不算漂移
        if path.stat().st_size > 900_000:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        level = classify(path, lines)
        if live_only and level != "LIVE":
            continue
        # 已带文件级退役横幅的文件：横幅已声明「本篇提到的这些脚本已退役」，
        # 再逐行报「脚本名」是噪声（但字段/行名类仍要报 —— 横幅没覆盖它们）。
        banner_declared = any("dead-script-index.md" in ln for ln in lines[:60])
        for lineno, line in enumerate(lines, 1):
            if any(mark in line for mark in ANNOTATED):
                continue  # 已显式标注废止的段落：不是漂移，是正确做法
            for category, pattern, fix in PATTERNS:
                if re.search(pattern, line):
                    findings.append({"level": level, "category": category, "file": str(path),
                                     "line": lineno, "text": line.strip()[:220], "fix": fix})
            for name in DEAD_SCRIPTS:
                if banner_declared and level == "LIVE":
                    break  # 横幅已声明的脚本类提及，跳过
                if name in line and (REPO / "scripts" / f"{name}.py").exists() is False:
                    findings.append({"level": level, "category": "不存在/被取代的脚本",
                                     "file": str(path), "line": lineno,
                                     "text": line.strip()[:220],
                                     "fix": "当前关键位链路 = keylevel_guard.py(常驻) + "
                                            "keylevel_read_trigger.py + btc_keylevel_guard_watchdog.py；"
                                            "到价提醒不走 btc_price_arrival_sentinel"})

    by_level: dict[str, list[dict]] = {"LIVE": [], "HISTORICAL": []}
    for item in findings:
        by_level[item["level"]].append(item)

    for level in ("LIVE", "HISTORICAL"):
        items = by_level[level]
        print(f"\n===== {level} 漂移 {len(items)} 处 =====")
        if not items:
            print("  ✓ 无")
            continue
        grouped: dict[str, list[dict]] = {}
        for item in items:
            grouped.setdefault(item["file"], []).append(item)
        for file, rows in grouped.items():
            print(f"\n  {file}  ({len(rows)})")
            for row in rows[:14]:
                print(f"    L{row['line']:<5} [{row['category']}] {row['text']}")
            if len(rows) > 14:
                print(f"    … 另 {len(rows) - 14} 处")

    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        out.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n→ {out}")
    print(f"\n合计 {len(findings)} 处（LIVE {len(by_level['LIVE'])} / 历史 {len(by_level['HISTORICAL'])}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
