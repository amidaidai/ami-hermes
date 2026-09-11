# 每日 Hermes Cron 维护脚本模式

## 背景

日常维护任务（系统审计、备份、技能/SkillMCP 更新）使用 Hermes no_agent cron。核心原则：

1. **静默原则** — 全正常时零输出，仅异常时输出报告
2. **单一职责** — 每个脚本聚焦一类任务
3. **版本控制** — 脚本同时在 `~/.hermes/scripts/`（cron 执行）和 `hermes/scripts/repo-maintenance/`（版本控制）保存
4. **no_agent 语义** — stdout 非空即推送；非零退出会被 Hermes cron 标记为脚本错误（即使脚本本身成功执行）

## 标准脚本模板

```python
#!/usr/bin/env python3
"""每日XXX — HH:MM cron，静默模式·仅异常时输出"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Windows Hermes no_agent cron 默认 stdout 可能走 cp936，
# 导致中文/emoji 推送乱码。在任何 print 之前强制 UTF-8。
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

TZ = timezone(timedelta(hours=8))
REPO_ROOT = Path("D:/Hermes agent")
LOG_DIR = REPO_ROOT / "outputs" / "maintenance-logs"


def run(cmd: list[str], timeout: int = 120, cwd: Path | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           cwd=str(cwd) if cwd else None)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, "FileNotFound"
    except subprocess.TimeoutExpired:
        return 124, f"Timeout after {timeout}s"
    except Exception as e:
        return 999, repr(e)


def compact(text: str, limit: int = 300) -> str:
    text = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    return text[-limit:] if len(text) > limit else text


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    start_ts = datetime.now(TZ)
    date_str = start_ts.strftime("%Y-%m-%d %H:%M:%S")

    lines = ["## 任务运行报告", ""]
    lines.append("| 项目 | 内容 |")
    lines.append("|---|---|")
    lines.append(f"| 任务 | 每日XXX |")
    lines.append(f"| 时间 | {date_str} |")
    lines.append("")
    lines.append("## 检查结果")
    lines.append("")
    changes = []

    # ── 执行各检查项，仅发现问题时 append changes ──

    end_ts = datetime.now(TZ)
    elapsed = (end_ts - start_ts).total_seconds()

    if changes:
        lines.append(f"⚠ 本次变更: {', '.join(changes)}")
        report = "\n".join(lines)
        print(report)
        # no_agent 语义：stdout 非空即推送。发现异常 ≠ 脚本失败，
        # 返回 0 避免 cron 标记为 error。
        return 0

    # 全干净时完全静默，零输出
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## 部署流程

```bash
# 1. 创建脚本到 cron 目录
# 2. 复制到仓库做版本控制
cp ~/.hermes/scripts/script_name.py /d/Hermes\ agent/hermes/scripts/repo-maintenance/

# 3. 创建 cron job
hermes cron create --name "任务名" --script "script_name.py" --no-agent "分钟 小时 * * *"

# 4. 验证
hermes cron list
```

## 日志保存

所有维护脚本将报告保存到 `D:/Hermes agent/outputs/maintenance-logs/`：
- `daily-audit-YYYYMMDD.log`
- `skill-mcp-update-YYYYMMDD.log`

## 现有三种任务

| 时间 | 任务 | 脚本 | 策略 |
|------|------|------|------|
| 06:00 | 每日系统备份 | `daily_private_repo_backup.py` | git push 失败 → print + return 0 |
| 06:30 | 每日系统审计 | `daily_system_audit.py` | 有异常 → print + return 0 |
| 07:00 | 每日技能SkillMCP更新 | `daily_skill_mcp_update.py` | 有变更 → print + return 0 |

所有任务返回 0。发现异常时输出报告（stdout 非空触发 cron delivery），返回 0 避免 cron 面板错误标记。

## Cron 时间编排

```
06:00 ─ 系统备份
06:30 ─ 系统审计
07:00 ─ 技能/MCP 更新
07:45 ─ OpenRouter 免费模型同步（已有）
```

各任务间隔 30 分钟以上，避免同时执行引发资源竞争。

## 报告格式规则

- 用 `## 标题` 代替 `══════════` 装饰性分隔线
- 用 Markdown 表格展示关键数据
- 尽量中文，只保留通用英文缩写（API、PID、cron）
- no_agent 脚本发现异常后仍返回 0，因为：
  - stdout 非空 → cron 自动推送
  - 非零退出 → cron 面板标红色 error（误报脚本崩溃）
