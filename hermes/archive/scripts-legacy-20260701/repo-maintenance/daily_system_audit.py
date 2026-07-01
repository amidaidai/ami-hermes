#!/usr/bin/env python3
"""每日系统审计 — 06:30 cron

静默审计 Hermes 系统健康，仅异常时输出报告。
检查项：技能完整性、MCP连通性、Hermes状态、Curator状态、磁盘/日志健康。
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Windows Hermes no_agent cron 默认 stdout/stderr 可能走 cp936，中文/emoji 会乱码。
# 在任何 print 之前强制 UTF-8，保证 Telegram 推送可读。
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

TZ = timezone(timedelta(hours=8))
HERMES_HOME = Path(os.environ.get("HERMES_HOME") or Path.home() / "AppData" / "Local" / "hermes")
SKILLS_ROOT = HERMES_HOME / "skills"
REPO_ROOT = Path("D:/Hermes agent")
LOG_DIR = REPO_ROOT / "outputs" / "maintenance-logs"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
try:
    from telegram_reliable import flush_pending, send_telegram_reliable
except Exception:  # noqa: BLE001
    flush_pending = None
    send_telegram_reliable = None

# ── helpers ──────────────────────────────────────────────

def run(cmd: list[str], timeout: int = 120, cwd: Path | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(cwd) if cwd else None)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError as e:
        return 127, f"FileNotFound: {e}"
    except subprocess.TimeoutExpired:
        return 124, f"Timeout after {timeout}s"
    except Exception as e:
        return 999, repr(e)


def ok(s: str) -> str:
    return f"✓ {s}"


def warn(s: str) -> str:
    return f"⚠ {s}"


def fail(s: str) -> str:
    return f"✗ {s}"


def compact(text: str, limit: int = 300) -> str:
    text = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    return text[-limit:] if len(text) > limit else text


# ── audit checks ─────────────────────────────────────────

def check_skill_integrity() -> dict:
    """运行 skill_integrity_guard.py 并解析 JSON 输出"""
    guard = SKILLS_ROOT / ".." / ".." / "skills" / "community" / "skill-integrity-guard"
    guard_script = REPO_ROOT / "hermes" / "scripts" / "repo-maintenance" / "skill_integrity_guard.py"

    if guard_script.exists():
        script = guard_script
    else:
        # fallback: try in-app skills path
        script = HERMES_HOME / "skills" / "repo-maintenance" / "skill_integrity_guard.py"

    if not script.exists():
        return {"status": "skipped", "reason": "skill_integrity_guard.py not found"}

    code, out = run([sys.executable, str(script), "--json"], timeout=60)
    try:
        result = json.loads(out)
        return {
            "status": "clean" if result.get("clean") else "issues",
            "scanned_md": result.get("scanned_md", 0),
            "scanned_skill_md": result.get("scanned_skill_md", 0),
            "pollution_count": len(result.get("line_pollution", [])),
            "frontmatter_broken_count": len(result.get("frontmatter_broken", [])),
            "code": code,
        }
    except (json.JSONDecodeError, Exception):
        return {"status": "error", "reason": compact(out, 200), "code": code}


def check_mcp_health() -> list[dict]:
    """测试所有 MCP 服务器连通性"""
    results = []
    code, out = run(["hermes", "mcp", "list"], timeout=30)
    if code != 0:
        return [{"name": "hermes-mcp-list", "status": "error", "reason": compact(out, 200)}]

    # 从 mcp list 输出解析服务器名称
    servers = []
    for line in out.splitlines():
        line = line.strip()
        if line and not line.startswith("├") and not line.startswith("└") and not line.startswith("─") and not line.startswith("Name") and not line.startswith("MCP Servers"):
            parts = line.split()
            if parts and parts[0] not in ("──", "Name", "MCP"):
                servers.append(parts[0])

    for name in servers:
        code, out = run(["hermes", "mcp", "test", name], timeout=30)
        results.append({
            "name": name,
            "status": "ok" if code == 0 else "fail",
            "code": code,
            "detail": compact(out, 100) if code != 0 else "",
        })

    return results


def check_hermes_doctor() -> dict:
    """运行 hermes doctor 检查"""
    code, out = run(["hermes", "doctor"], timeout=60)
    # 统计警告和失败
    warnings = [line.strip() for line in out.splitlines() if "⚠" in line or "✗" in line or "error" in line.lower() or "fail" in line.lower()]
    return {
        "status": "ok" if code == 0 else f"code={code}",
        "warnings": len(warnings),
        "details": warnings[:5],  # 最多5条
    }


def check_disk_space() -> dict:
    """检查 C 盘和 D 盘可用空间"""
    results = {}
    for drive in ["C:\\", "D:\\"]:
        try:
            usage = shutil.disk_usage(drive)
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)
            pct = usage.free / usage.total * 100
            results[drive[0]] = {
                "free_gb": round(free_gb, 1),
                "total_gb": round(total_gb, 1),
                "free_pct": round(pct, 1),
                "healthy": pct > 10,
            }
        except Exception:
            results[drive[0]] = {"status": "unavailable"}
    return results


def check_git_state() -> dict:
    """检查仓库 git 状态"""
    if not (REPO_ROOT / ".git").exists():
        return {"status": "not_a_repo"}
    code, status_out = run(["git", "status", "--short"], cwd=REPO_ROOT, timeout=30)
    modified = len([l for l in status_out.splitlines() if l.strip()])
    # 获取落后提交数
    code2, ahead_behind = run(["git", "rev-list", "--count", "HEAD..@{upstream}"], cwd=REPO_ROOT, timeout=30)
    behind = int(ahead_behind.strip() or 0) if code2 == 0 else -1
    return {
        "status": "clean" if modified == 0 and behind <= 0 else "dirty",
        "modified": modified,
        "behind": behind,
    }


def collect_recent_logs() -> list[str]:
    """检查近期日志中有无异常"""
    log_dir = HERMES_HOME / "logs"
    if not log_dir.exists():
        return ["logs dir not found"]
    warnings = []
    for f in sorted(log_dir.glob("*.log"))[-5:]:  # 最近5个日志文件
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            # 找错误关键词
            for line in content.splitlines():
                if any(kw in line.lower() for kw in ["error", "traceback", "exception", "failed"]):
                    warnings.append(f"{f.name}: {line[:120].strip()}")
                    break  # 每文件只取一条
        except Exception:
            pass
    return warnings[:5]


# ── main ─────────────────────────────────────────────────

def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    start_ts = datetime.now(TZ)
    date_str = start_ts.strftime("%Y-%m-%d %H:%M:%S")

    # 执行所有审计
    skill_result = check_skill_integrity()
    mcp_results = check_mcp_health()
    doctor_result = check_hermes_doctor()
    disk_result = check_disk_space()
    git_result = check_git_state()
    log_warnings = collect_recent_logs()

    end_ts = datetime.now(TZ)
    elapsed = (end_ts - start_ts).total_seconds()

    # ── 构建报告 ──
    lines = ["## 任务运行报告", ""]
    lines.append("| 项目 | 内容 |")
    lines.append("|---|---|")
    lines.append("| 任务 | 每日系统审计 |")
    lines.append(f"| 时间 | {date_str} |")
    lines.append(f"| 耗时 | {elapsed:.0f}s |")
    lines.append("")
    lines.append("## 检查结果")
    lines.append("")

    # 技能完整性
    if skill_result["status"] == "clean":
        lines.append(ok(f"技能完整性 — {skill_result.get('scanned_md', 0)} .md / {skill_result.get('scanned_skill_md', 0)} SKILL.md 全部干净"))
    elif skill_result["status"] == "issues":
        lines.append(warn(f"技能完整性 — {skill_result.get('pollution_count', 0)} 行号污染 / {skill_result.get('frontmatter_broken_count', 0)} frontmatter损坏"))
    elif skill_result["status"] == "skipped":
        lines.append(warn(f"技能完整性 — 跳过（脚本未找到）"))
    else:
        lines.append(fail(f"技能完整性 — 检查失败: {skill_result.get('reason', '')}"))

    # MCP 健康
    mcp_ok = sum(1 for r in mcp_results if r["status"] == "ok")
    mcp_fail = sum(1 for r in mcp_results if r["status"] == "fail")
    if mcp_results:
        lines.append(ok(f"MCP 服务器 — {mcp_ok}/{len(mcp_results)} 正常" + (f", {mcp_fail} 异常" if mcp_fail else "")))
        for r in mcp_results:
            if r.get("status") != "ok":
                detail_text = r.get("detail") or r.get("reason") or f"code={r.get('code', '?')}"
                detail = f"{r.get('name', 'unknown')}: {detail_text}"
                lines.append(f"  {warn(detail)}")
    else:
        lines.append(warn("MCP 服务器 — 未检测"))

    # Hermes doctor
    if doctor_result["status"] == "ok":
        lines.append(ok(f"Hermes 状态 — 正常"))
    else:
        lines.append(fail(f"Hermes 状态 — {doctor_result['status']}"))
    if doctor_result.get("warnings", 0) > 0:
        for d in doctor_result["details"]:
            lines.append(f"  {warn(d)}")

    # 磁盘空间
    disk_warnings = []
    for drive, info in disk_result.items():
        if isinstance(info, dict) and "free_gb" in info:
            lines.append(ok(f"磁盘 {drive}: {info['free_gb']}G 可用 / {info['total_gb']}G ({info['free_pct']}%)"))
            if not info.get("healthy", True):
                disk_warnings.append(f"{drive}盘可用空间不足 ({info['free_pct']}%)")
        else:
            lines.append(warn(f"磁盘 {drive}: 无法检测"))

    # Git 状态
    if git_result.get("status") == "clean":
        lines.append(ok(f"Git 仓库 — 干净"))
    elif git_result.get("status") == "dirty":
        lines.append(warn(f"Git 仓库 — {git_result.get('modified', 0)} 项未提交, 落后 {git_result.get('behind', '?')} 提交"))
    elif git_result.get("status") == "not_a_repo":
        lines.append(warn(f"Git 仓库 — 非 git 目录"))

    # 日志异常
    if log_warnings:
        lines.append(warn(f"近期日志异常 ({len(log_warnings)} 条)"))
        for lw in log_warnings:
            lines.append(f"  {warn(lw)}")
    else:
        lines.append(ok("近期日志 — 无异常"))

    total_issues = (
        (1 if skill_result["status"] == "issues" else 0) +
        mcp_fail +
        (doctor_result.get("warnings", 0) > 0) +
        len(disk_warnings) +
        (1 if git_result.get("status") == "dirty" else 0) +
        (1 if log_warnings else 0)
    )

    if total_issues == 0:
        lines.append(f"\n✅ 全部 {len(mcp_results) + 6} 项检查通过")
    else:
        lines.append(f"\n⚠ {total_issues} 项异常，请及时处理")

    report = "\n".join(lines)

    # 保存报告到日志文件
    log_path = LOG_DIR / f"daily-audit-{start_ts.strftime('%Y%m%d')}.log"
    log_path.write_text(report, encoding="utf-8")

    # Hermes cron 自带 delivery 曾出现 Telegram timeout；这里直连可靠推送并失败落盘。
    if total_issues > 0 and send_telegram_reliable is not None:
        if flush_pending is not None:
            flush_pending(limit=10)
        send_telegram_reliable("telegram:-1003733144325:846", report, retries=5, timeout=15)

    # 静默模式：仅异常时输出
    if total_issues > 0:
        print(report)
    # 全干净时完全静默

    # no_agent 语义：stdout 非空即推送；非零退出会被 Hermes 标记为脚本错误。
    # 审计发现异常不是脚本失败，因此成功产出报告后仍返回 0。
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
