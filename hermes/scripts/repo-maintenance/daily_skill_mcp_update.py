#!/usr/bin/env python3
"""每日技能/SkillMCP更新 — 07:00 cron

检查技能更新、运行 Curator 维护、测试并重启 MCP 服务器。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
HERMES_HOME = Path(os.environ.get("HERMES_HOME") or Path.home() / "AppData" / "Local" / "hermes")
REPO_ROOT = Path("D:/Hermes agent")
LOG_DIR = REPO_ROOT / "outputs" / "maintenance-logs"
SCRIPTS_DIR = HERMES_HOME / "scripts"

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


def compact(text: str, limit: int = 400) -> str:
    text = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    return text[-limit:] if len(text) > limit else text


def run_for_output(cmd: list[str], timeout: int = 120) -> str:
    """Run and return stdout+stderr, or error message."""
    code, out = run(cmd, timeout=timeout)
    if code == 0:
        return out.strip()
    return f"exit={code}: {compact(out, 200)}"


# ── checks ────────────────────────────────────────────────

def check_skills_update() -> dict:
    """检查并更新 hub skills"""
    code, out = run(["hermes", "skills", "check"], timeout=60)
    has_updates = "updates found" in out.lower() or "can update" in out.lower()
    return {
        "status": "updates_found" if has_updates else "no_updates",
        "raw": compact(out, 200),
        "code": code,
    }


def run_skills_update() -> dict:
    """执行技能更新"""
    code, out = run(["hermes", "skills", "update"], timeout=180)
    return {
        "status": "ok" if code == 0 else "failed",
        "raw": compact(out, 300),
        "code": code,
    }


def run_curator() -> dict:
    """运行 Curator 维护"""
    code, out = run(["hermes", "curator", "run"], timeout=120)
    # 检查是否做了事
    has_changes = "archived" in out.lower() or "consolidated" in out.lower() or "updated" in out.lower()
    return {
        "status": "changes" if has_changes else "no_changes",
        "summary": compact(out, 400),
        "code": code,
    }


def test_mcp_servers() -> dict:
    """测试所有 MCP 服务器"""
    code, out = run(["hermes", "mcp", "list"], timeout=30)
    if code != 0:
        return {"status": "error", "detail": compact(out, 200), "servers": []}

    servers = []
    for line in out.splitlines():
        line = line.strip()
        if line and not line.startswith("├") and not line.startswith("└") and not line.startswith("─") and not line.startswith("Name") and not line.startswith("MCP"):
            parts = line.split()
            if parts and parts[0] not in ("──", "Name", "MCP"):
                servers.append(parts[0])

    results = []
    for name in servers:
        code, out = run(["hermes", "mcp", "test", name], timeout=30)
        results.append({
            "name": name,
            "ok": code == 0,
            "detail": "" if code == 0 else compact(out, 100),
        })

    ok_count = sum(1 for r in results if r["ok"])
    fail_count = sum(1 for r in results if not r["ok"])

    return {
        "status": "all_ok" if fail_count == 0 and len(results) > 0 else "partial",
        "total": len(results),
        "ok": ok_count,
        "fail": fail_count,
        "servers": results,
    }


def check_official_update() -> dict:
    """运行每日 Hermes 官方升级检查"""
    script = SCRIPTS_DIR / "daily_hermes_official_update.py"
    if not script.exists():
        # fallback to repo path
        script = REPO_ROOT / "hermes" / "scripts" / "repo-maintenance" / "daily_hermes_official_update.py"

    if not script.exists():
        return {"status": "skipped", "reason": "script not found"}

    code, out = run([sys.executable, str(script)], timeout=300)
    return {
        "status": "ok" if code == 0 else "failed",
        "output": compact(out, 200),
        "code": code,
    }


# ── main ──────────────────────────────────────────────────

def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    start_ts = datetime.now(TZ)
    date_str = start_ts.strftime("%Y-%m-%d %H:%M:%S")

    # 执行
    skill_status = check_skills_update()
    mcp_status = test_mcp_servers()
    curator_status = run_curator()
    update_status = check_official_update()

    # 如果有 hub 技能更新，执行更新
    if skill_status["status"] == "updates_found":
        update_result = run_skills_update()
    else:
        update_result = {"status": "skipped", "raw": "无可用更新"}

    end_ts = datetime.now(TZ)
    elapsed = (end_ts - start_ts).total_seconds()

    # ── 构建报告 ──
    changes = []
    lines = [f"══════════ 任务运行报告 ══════════"]
    lines.append(f"任务：每日技能/SkillMCP更新")
    lines.append(f"时间：{date_str}")
    lines.append(f"耗时：{elapsed:.0f}s")
    lines.append("")

    # 技能更新
    if skill_status["status"] == "updates_found":
        changes.append("hub技能更新")
        lines.append(f"✓ Hub技能 — 发现更新")
        if update_result["status"] == "ok":
            lines.append(f"  更新结果: 成功")
            lines.append(f"  详情: {update_result['raw']}")
        else:
            lines.append(f"  ⚠ 更新结果: {update_result['status']}")
    else:
        lines.append(f"✓ Hub技能 — 无可用更新")

    # Curator
    if curator_status["status"] == "changes":
        changes.append("curator归档")
        lines.append(f"✓ Curator维护 — 有变更")
        lines.append(f"  详情: {curator_status['summary']}")
    else:
        lines.append(f"✓ Curator维护 — 无变更")

    # MCP 服务器
    if mcp_status["status"] == "all_ok":
        lines.append(f"✓ MCP服务器 — {mcp_status['ok']}/{mcp_status['total']} 全部正常")
    elif mcp_status["status"] == "partial":
        changes.append("MCP异常")
        lines.append(f"⚠ MCP服务器 — {mcp_status['ok']}/{mcp_status['total']} 正常, {mcp_status['fail']} 异常")
        for s in mcp_status["servers"]:
            if not s["ok"]:
                lines.append(f"  ⚠ {s['name']}: {s['detail']}")
    else:
        lines.append(f"⚠ MCP服务器 — 检查失败: {mcp_status.get('detail', '')}")

    # Hermes 官方升级
    if update_status.get("status") == "ok":
        lines.append(f"✓ Hermes升级检查 — 通过")
    elif update_status.get("status") == "skipped":
        lines.append(f"✓ Hermes升级检查 — 跳过（脚本未找到）")
    else:
        changes.append("Hermes升级异常")
        lines.append(f"⚠ Hermes升级检查 — 异常: {update_status.get('output', '')}")

    if changes:
        lines.append(f"\n⚠ 本次变更: {', '.join(changes)}")
    else:
        lines.append(f"\n✅ 全部检查通过，无需变更")

    lines.append("══════════")
    report = "\n".join(lines)

    # 保存日志
    log_path = LOG_DIR / f"skill-mcp-update-{start_ts.strftime('%Y%m%d')}.log"
    log_path.write_text(report, encoding="utf-8")

    # 有变更时输出报告（触发 Telegram 推送）
    if changes:
        print(report)
    # 无变更时静默

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
