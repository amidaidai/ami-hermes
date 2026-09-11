# 改动未生效 — Git Untracked 陷阱诊断

当用户说"我改了 XX 但没生效"时的系统化排查。最常见根因不是代码逻辑错误，
而是文件只在本地磁盘存在、未被 git 跟踪 → 重启/回滚/切换分支都会丢。

## 诊断流程

### 第一步：确认文件是否被 git 跟踪

```bash
git status --short | grep <filename>
```

- `M` (staged/modified) = 已跟踪，改动已暂存
- ` M` (unstaged modified) = 已跟踪，改动未暂存但不会丢
- `??` (untracked) = **文件在磁盘上存在，但 git 完全不知道它** — 这是 P0 级风险
- 文件完全不出现 = 已被 `.gitignore` 排除或在 disk 上不存在

⚠ 如果 `??` 出现在 `hermes/scripts/auto_card.py`、`scripts/行情守望.py` 等关键脚本上，
所有审计时做的改动一旦 `git reset --hard` 就会丢失。

### 第二步：确认是否有重复文件（不同路径的双版本）

```bash
find . -name "auto_card.py" -type f 2>/dev/null
```

本例中：
- `scripts/auto_card.py` (406 bytes) — 薄 wrapper，调用 hermes/scripts/
- `hermes/scripts/auto_card.py` (21,853 bytes) — 主实现，含 render_card_locked()

如果用户改了其中一个但监控 import 的是另一个 → 改动不生效。

### 第三步：确认运行中进程用的是哪个版本

```bash
# 对比文件修改时间 vs 进程启动时间
stat --format="%y" scripts/行情守望.py
cat data/monitor_heartbeat.json  # 看 PID
# PowerShell: Get-Process -Id <pid> | Select StartTime
```

如果进程启动时间早于文件修改时间 → 进程用的是旧代码，需重启。

### 第四步：确认渲染路径（是否存在多个渲染系统）

本例发现：监控 `行情守望.py` 有独立内联 `render_message()`，不调 `auto_card.py` 的 `render_card_locked()`。
两者格式已对齐但渲染路径独立。用户在 auto_card.py 改排版不会影响监控推送的卡片。

## Fix：git add + commit + push

```bash
cd "D:/Hermes agent"
git add <all-the-files>
git commit -m "lock: ..."
git push origin main
```

- `git add` 前先 `git status --short` 确认要加的所有文件
- Commit message 要清楚列出锁定了哪些内容
- Push 后确认远端有备份

## 预防（审计后必做）

每次大规模审计修复完成后：
1. `git status --short` — 确认没有 `??` 关键文件
2. `git add` + `git commit` + `git push`
3. 确认监控心跳推进，说明新代码在运行
