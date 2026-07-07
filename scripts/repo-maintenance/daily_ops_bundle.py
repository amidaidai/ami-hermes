"""每日运维聚合 v1.0 — 合并原 4 个独立 cron：
- daily_skill_mcp_update  (技能/SkillMCP 更新)
- daily_system_audit       (系统审计)
- daily_private_repo_backup(私有仓库备份)
- freerouter               (OpenRouter 免费模型同步)

设计原则：任一子任务失败不影响其余；统一输出拼接后一次打印（推 TG）。
用法: python scripts/repo-maintenance/daily_ops_bundle.py
"""
import sys
import traceback
from pathlib import Path

# 允许以 repo 根目录运行
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "repo-maintenance"))

from daily_skill_mcp_update import main as skill_update_main
from daily_system_audit import main as audit_main
from daily_private_repo_backup import main as backup_main
import freerouter


def section(title: str) -> str:
    return f"\n{'='*10} {title} {'='*10}\n"


def run(label: str, fn) -> str:
    try:
        rc = fn()
        rc = 0 if rc is None else rc
        return f"[{label}] exit={rc} OK"
    except Exception as e:
        return f"[{label}] ERROR: {e}\n{traceback.format_exc()[-800:]}"


def main() -> int:
    out = []
    out.append("🛠 每日运维聚合报告 (合并:技能更新/系统审计/仓库备份/模型同步)")
    out.append(section("1. Skill/MCP 更新"))
    out.append(run("skill_update", skill_update_main))
    out.append(section("2. 系统审计"))
    out.append(run("audit", audit_main))
    out.append(section("3. 私有仓库备份"))
    out.append(run("backup", backup_main))
    out.append(section("4. OpenRouter 免费模型同步"))
    out.append(run("freerouter", freerouter.main))
    report = "\n".join(out)
    print(report)
    # 任一子任务异常返回非 0，便于 cron 告警
    return 0 if "ERROR" not in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
