# Cron 管理

## Cron 创建

```bash
hermes cron create \
  --name "中文名" \
  --script "脚本名.py" \
  --no-agent \
  --workdir "D:\\Hermes agent\\scripts" \
  --deliver "telegram:-1003733144325:846" \
  "every 5m"
```

- `schedule`: `every 5m` / `every 360m` / `20 3 * * *`（**位置参数，不是 `--schedule`**）
- `--no-agent`: 脚本 stdout 直接推送，不经过 LLM
- `--workdir`: 必须是绝对路径，用反斜杠双写 `\\`

## Cron 删除

```bash
hermes cron delete <job_id>
# job_id 从 hermes cron list 获取
```

**⚠ 暂停 ≠ 删除**：`hermes cron list` 只显示活跃 job，但 Web UI 会统计所有 job（含 paused）。暂停的废弃 job 会虚增"任务数"。必须 `hermes cron delete` 彻底删除。

## Cron 验证（创建后必做）

1. `hermes cron list` — 确认 last_run 不是 `error: Script not found`
2. 若报脚本找不到 → 检查 `%LOCALAPPDATA%/hermes/scripts/` 是否有该脚本
3. `python "$LOCALAPPDATA/hermes/scripts/新脚本.py"` — 手动跑一次确认无语法错

## 精简架构（已验证）

3 个 cron + 1 个后台进程 = 完整监控体系：

```
Cron 层（no_agent·topic 846）
├─ 持仓与信号 5m — wrapper：持仓监测 + 信号巡检
├─ 清理守护 6h — 过期数据清理
└─ 凌晨维护 3:20 — wrapper：Hermes升级 + 仓库备份 + 每日验证

后台进程（独立·非 cron）
└─ 行情守望 v7.5 — 10s 扫价 · 警报推送 topic 385/386
```

## 合并 Cron 的铁律模式（wrapper 脚本）

当多个 cron 职责不同但频率相同（或相近），用 wrapper 脚本串行调用子脚本：

```python
#!/usr/bin/env python3
"""合并脚本 v1.0 — 串行执行多个子脚本。每个子脚本各自控制是否输出。"""
import subprocess, sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent

STEPS = [
    ("子任务1", "脚本1.py", 30),
    ("子任务2", "脚本2.py", 90),
]

for name, script, timeout in STEPS:
    try:
        cp = subprocess.run(
            [sys.executable, str(SCRIPTS / script)],
            capture_output=True, text=True, timeout=timeout,
        )
        out = cp.stdout.strip()
        if out:
            print(f"—— {name} ——")
            print(out)
    except subprocess.TimeoutExpired:
        print(f"⚠ {name} 超时 ({timeout}s)")
    except Exception as e:
        print(f"⚠ {name} 失败: {e}")
```

**关键设计决策**：
- 子脚本各自负责"有无输出"的判断（空仓静默等），wrapper 只做串行调度
- 任一步失败不阻断后续（独立子脚本）
- 超时时间按子脚本特性设定：轻量 30s，重量 90-180s

## 话题路由

- 846: 任务报告（cron 输出、系统状态、审计报告）
- 386: BTC 警报
- 385: XAU 警报
- 416: 通用/兜底（已废弃，不要用）
