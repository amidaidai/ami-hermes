# Cron Merge Pattern: 7→3 (2026-06-19)

## Problem

7 cron jobs running, some overlapping in function, causing unnecessary noise:
- 信号巡检 1m (480/day) + 持仓监测 5m (288/day) — both high-frequency, often silent
- 自动标注复盘 60m — script file missing (auto_label_bridge.py never existed)
- 凌晨 3 jobs at 3:20/3:50/4:10 — can be serial chain

## Merge Steps

1. Audit: read every script, understand what each does
2. Identify overlaps: 信号巡检 (meta-monitor) + 持仓监测 (position tracker) both run silently when idle
3. Create wrapper: `持仓与信号.py` — subprocess.run both sequentially
4. Delete stale: 自动标注复盘 (script missing), 黄金到价监控 (paused/merged), 每日治理 (paused/merged)
5. Merge 凌晨: 3 jobs → 1 (upgrade→backup→validation)
6. Register new crons, verify, delete old ones

## Final State

| Cron | Schedule | Script |
|------|----------|--------|
| 持仓与信号 | */5 8-23 * * * | 持仓与信号.py |
| 清理守护 | 0 12 * * * | 清理守护.py |
| 日间维护 | 30 8 * * * | 日间维护.py |

## Wrapper Pattern

```python
STEPS = [("name", "script.py", timeout_seconds), ...]
for name, script, timeout in STEPS:
    cp = subprocess.run([sys.executable, str(SCRIPTS / script)],
                        capture_output=True, text=True, timeout=timeout)
    if cp.stdout.strip():
        print(f"—— {name} ——")
        print(cp.stdout.strip())
```

## Sleep Gate

Use cron expression, NOT script time-check:
- ✅ `*/5 8-23 * * *` — cron handles 23-8 silence
- ❌ Script-level `if hhmm not in windows: sys.exit(0)` — fragile, hard to debug

## Cron CLI Recipes

```bash
hermes cron list                                    # view all
hermes cron create --name "..." --script "s.py" --no-agent --workdir "D:\..." --deliver "telegram:...:846" "schedule"
hermes cron edit <id> --schedule "*/5 8-23 * * *"  # change schedule
hermes cron edit <id> --name "新名称"               # rename
hermes cron delete <id>                             # remove
hermes cron tick                                    # force run due jobs
```
## Dual-Path Fix: Directory Junction (root) + Copy Redundancy (quick)

**Root solution**: Windows directory junction (one-time) so AppData and repo point to same files. See code in file.

**Quick interim for immediate effect** (used in 2026-06-20 "一起修复了" session when Junction not yet active):
- Explicitly `cp` the critical no-agent scripts (e.g. 持仓与信号.py, 日间维护.py) to `$LOCALAPPDATA/hermes/scripts/`
- Then `hermes cron delete <old>` + `hermes cron create ... --workdir "D:\\Hermes agent\\scripts" --no-agent`
- Verify: `hermes cron run <id>` and `ls "$LOCALAPPDATA/hermes/scripts/"`
- Also copy after any script edit if Junction pending.

This provides redundancy and makes the new cron pick up the file immediately. Combined with `taskkill //F //PID <stale-monitor>` to force watchdog respawn with fresh code (after pyclean).

**Iron law**: After cron recreate or script copy, always run the job manually once and check last_status + actual script presence.

---

## 棠溪 20→17 合并实战（2026-07-07）

背景：`hermes cron list` 膨胀到 20 个 active job。本轮合并到 17，落地 commit `ba8c707`。

### 关键发现：cron list 无 --json，直接读 jobs.json

`hermes cron list --json` 返回空（CLI 不支持）。拿到每个 cron 的真实 script 路径 + deliver + schedule 的唯一可靠方式：

```
find "$LOCALAPPDATA/hermes" -name "jobs.json"
# → C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json
python -c "import json; d=json.load(open(path)); [print(j['name'],'|',j['schedule']['expr'],'|',j.get('script'),'|',j.get('deliver')) for j in d['jobs']]"
```

字段：`name` / `schedule.expr` / `script` / `deliver` / `id`。删 cron 用 `hermes cron delete <id>`（list 里能拿到 id）。

### 合并模式 A：import-chain bundle（同进程调用各脚本 main）

适合「多个独立维护脚本，各自 main()+print(report)，无依赖顺序」的场景（如每日运维：技能更新+审计+备份+模型同步）。

不要 subprocess 套娃——直接 import 各模块 main 顺序跑，拼接输出一次推 TG：

```python
# scripts/repo-maintenance/daily_ops_bundle.py
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "repo-maintenance"))
from daily_skill_mcp_update import main as skill_update_main
from daily_system_audit import main as audit_main
from daily_private_repo_backup import main as backup_main
import freerouter

def run(label, fn):
    try:
        rc = fn() or 0
        return f"[{label}] exit={rc} OK"
    except Exception as e:
        return f"[{label}] ERROR: {e}"

def main():
    out = ["🛠 每日运维聚合"]
    out.append(run("skill_update", skill_update_main))
    out.append(run("audit", audit_main))
    out.append(run("backup", backup_main))
    out.append(run("freerouter", freerouter.main))
    report = "\n".join(out)
    print(report)
    return 1 if "ERROR" in report else 0
```

- 每个子任务 try/except 隔离，单点失败不连坐。
- 任一 ERROR → 返回非 0，cron 告警照常触发。
- 冒烟验证：`python -c "import sys; sys.path.insert(0,'scripts/repo-maintenance'); import daily_ops_bundle"` 确认 import 链无错（不必真跑备份/审计）。

合并 4→1：`hermes cron delete` 四个旧 id，`hermes cron create "40 6 * * *" --name "每日运维聚合" --script repo-maintenance/daily_ops_bundle.py --no-agent --workdir "D:/Hermes agent" --deliver telegram:...:846`。

### 合并模式 B：collector 末尾 import 分析卡（采集+渲染合一）

适合「采集脚本落盘 json，另有独立分析卡 cron 读该 json 渲染推 TG」的场景（如 Orion：采集 `orion_screener_radar.py` 写 `data/orion_radar.json`，分析卡 `orion_radar_card.py` 读 json 出 3 表）。

在 collector 的 `main()` 末尾、`return 0` 前，动态 import 分析卡并调用其 `main()`：

```python
# orion_screener_radar.py 末尾
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "orion_radar_card", os.path.join(os.path.dirname(os.path.abspath(__file__)), "orion_radar_card.py"))
    if _spec is None or _spec.loader is None:
        raise RuntimeError("orion_radar_card spec/loader 为 None")
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _mod.main()
except Exception as _e:
    log(f"⚠ Orion分析卡渲染失败(不影响采集): {_e}")
```

- collector 原 `deliver=local` 改成 `telegram:...:846`（分析卡输出要推 TG）。
- 删独立分析卡 cron：`hermes cron delete <分析卡id>`。
- 冒烟：先确认 `data/orion_radar.json` 存在，单独跑 `_mod.main()` 能出 3 表（验证了再接入 collector）。

合并 2→1：Orion全市场雷达(deliver改tg) + 删 Orion雷达分析。

### 评估后保留不动（合并风险高，勿强行合）

- **X情绪采集 + X情绪LLM分析**：数据源不同（collector=X实时；context=FNG+CG trending+global 独立抓）——功能不重叠，强合会丢信息。保留 2 个。
- **3 看门狗（BTC守护/行情守望/数据新鲜度）**：监控对象+重启逻辑不同（心跳120s/300s/文件mtime），合并风险高。保留 3 个。
- 其他独立采集 cron（Dune/COT/Deribit/清算/稳定币/QLib/宏观Poly/BTC关键位/执行桥接）：各独立数据源、频率不同、无重叠。保留。

### 合并判定树

| 条件 | 动作 |
|:---|:---|
| N 个脚本各自 main()+print，无依赖 | 模式A import-chain bundle，N→1 |
| 采集脚本落盘 json + 独立分析卡读 json 渲染 | 模式B collector 末尾 import 分析卡，2→1 |
| 两脚本数据源不同/功能不重叠 | 保留 |
| 看门狗监控对象/重启逻辑不同 | 保留（合并风险>收益） |

落地后 `hermes cron list` 数 active；`git add -A scripts/ && commit && push`。