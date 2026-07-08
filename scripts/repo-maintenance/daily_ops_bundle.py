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
    results = []
    results.append(("Skill/MCP 更新", run("skill_update", skill_update_main)))
    results.append(("系统审计", run("audit", audit_main)))
    results.append(("私有仓库备份", run("backup", backup_main)))
    results.append(("OpenRouter 模型同步", run("freerouter", freerouter.main)))

    # 管道表报告（RichMarkdown 真表格）
    now = __import__("datetime").datetime.now(__import__("datetime").timezone(__import__("datetime").timedelta(hours=8)))
    ts = now.strftime("%Y年%m月%d日%H：%M")
    rows = "\n".join(
        f"| {label} | {'✅ OK' if 'OK' in r and 'ERROR' not in r else '❌ 异常'} | {r.split('] ',1)[-1]} |"
        for label, r in results
    )
    report = f"""🛠 每日运维聚合报告 · {ts}

| 模块 | 状态 | 详情 |
|:----|:----:|:----|
{rows}"""
    print(report)
    # v9.7: 统一走 RichMarkdown 真表格通道推 TG
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from telegram_reliable import push_tg_rich
        push_tg_rich("telegram:-1003733144325:846", report)
    except Exception as _te:
        print(f"⚠ 运维聚合RichMarkdown推送失败: {_te}", file=sys.stderr)
    return 0 if all("ERROR" not in r for _, r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
