# uv venv stub 双节点陷阱 — 看门狗实例计数误判（2026-08-31 实测）

## 症状

keylevel_guard 看门狗 cron 每 2 分钟输出：

```
RESTART needed: guard process count=2 (alive=True hb_age=0.4)
killed PID=3856
killed PID=15892
multi-symbol keylevel guard started PID=8796
```

下一轮又是 count=2、又杀 2 起 1——无限循环。心跳文件 `.keylevel_guard_heartbeat.json` 显示 `status=running` 且新鲜（<1min），但 **PID 每 2 分钟漂移**。

## 根因

Hermes venv 由 `uv venv` 创建：`C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe` 是 **redirector stub**（pyvenv.cfg 的 `home`/`executable` 指向 `AppData\Roaming\uv\python\cpython-3.11-windows-x86_64-none\python.exe` 真实解释器）。

用 stub 启动脚本时：`python.exe keylevel_guard.py` → stub 检测到自己不是真实解释器 → spawn 一个真实 uv python 子进程执行同一命令 → **同一逻辑实例出现 2 个进程节点**：

```
PID=16336 [venv python] keylevel_guard.py   ← stub 父
└─ PID=7276 [uv python] keylevel_guard.py    ← real 子（实际执行者，写心跳）
```

看门狗用 psutil 按 cmdline 匹配 `keylevel_guard.py` → 数到 2 个 → 判定 count≠1 → 杀 2 个 → Popen 1 个（又产生 stub+real）→ 下轮又是 2 个。**永远杀不干净，因为每次重启都从新产生双节点。**

## 诊断命令（区分 stub 双节点 vs 真多实例）

```python
import psutil
procs = {p.info['pid']: p for p in psutil.process_iter(['pid','ppid','cmdline'])}
for p in psutil.process_iter(['pid','ppid','cmdline']):
    cmd = ' '.join(p.info['cmdline'] or [])
    if 'keylevel_guard.py' in cmd and 'watchdog' not in cmd:
        pp = procs.get(p.info['ppid'])
        tag = 'STUB' if 'hermes-agent\\venv' in cmd else 'real'
        print(f'{p.info["pid"]} [{tag}] parent={(pp.info["cmdline"][0] if pp else None)}')
```

判读：
- **stub 双节点**：venv python 节点是 uv python 节点的父进程（stub→real 父子链）→ 只有 1 个逻辑实例。
- **真多实例**：多个进程各自独立父进程（不同 cron/手动启动）→ 才是真 P0 多实例。

## 修复（已落地 btc_keylevel_guard_watchdog.py）

1. **Popen 用真实解释器**——解析 pyvenv.cfg 的 `executable` 字段：

```python
PYVENV_CFG = Path(sys.prefix) / "pyvenv.cfg"
def _resolve_real_python() -> str:
    try:
        if PYVENV_CFG.exists():
            for line in PYVENV_CFG.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("executable") and "=" in line:
                    exe = line.split("=",1)[1].strip()
                    if exe and Path(exe).exists():
                        return exe
    except Exception: pass
    return sys.executable
REAL_PYTHON = _resolve_real_python()
# Popen([REAL_PYTHON, GUARD])  ← 不再 Popen([sys.executable, GUARD])
```

2. **计数跳过 stub**——cmdline 首元素含 `hermes-agent\venv\Scripts\python.exe` 且其子进程也是同脚本 → 不算实例。

```python
STUB_MARK = "hermes-agent\\venv\\Scripts\\python.exe"
pypath = (p.info.get("cmdline") or [""])[0]
if STUB_MARK in pypath:
    children = p.children()
    if any("keylevel_guard.py" in " ".join(c.info.get("cmdline") or []) for c in children):
        continue  # stub 带 real 子 → 不算实例
```

3. **验证**：等 2 个 cron 周期（watchdog 每 2 分钟），日志从 `RESTART needed` 变 `OK guard alive(alive=True) hb_age=0s pid=<稳定>`，心跳 PID 不再漂移。

## 适用范围

任何用 uv venv 启动守护脚本 + psutil 按 cmdline 数实例的看门狗都有此坑：`btc_watchdog.py`、`market_watchdog.py`、`keylevel_guard_watchdog` 同理。

---

# 心跳新鲜 ≠ 监控有效：keylevels_config valid_until 空转（P0）

## 症状

`.keylevel_guard_heartbeat.json` 新鲜（<1min、running），但自 config 的 `valid_until` 过期后**没有任何新 trigger 文件产生**（trigger_BTCUSDT.json 停在旧 ts）。守卫活着但没在监控。

## 根因

keylevel_guard 每 0.5s 轮询时对每条 level 调 `level_is_active()`：

```python
expires = level.get("valid_until") or level.get("expires_at")
if not expires: return True
return now_epoch <= datetime.fromisoformat(str(expires)...).timestamp()
```

`valid_until` 过期 → 返回 False → 该位不参与穿越检测。实案：config 2026-08-29 10:39 批准、4 个 level 全部 `valid_until=2026-08-30T00:00`，8-30 全天空转，直到 8-31 审计发现。

## 审计必查

```bash
python -c "import json; d=json.load(open('D:/Hermes agent/data/keylevels_config.json')); [print(l['name'], l['price'], l.get('valid_until')) for l in d['symbols']['BTCUSDT']['levels']]"
```

全部 `valid_until` 早于当前时间 = P0 空转。

## 修复链路（2026-08-31 已验证）

1. `python scripts/keylevels_collect.py` 重新采集五层候选（写 keylevels_candidates.json）。
2. **若报 `D 采集失败: timeframe mismatch: expected D, got 1D`**：`set_timeframe("D")` 后 chart state 返回 `1D`，校验集需含 `{"D": "1D"}` 别名（2026-08-31 已修）。
3. 按候选重写 `keylevels_config.json`（schema_version=2、valid_until=当日 23:59:59、approved_source 注明 auto_refresh 时间）。
4. 守卫 0.5s 热读 config，无需重启；等心跳确认加载。

---

# 伴随发现（P1）

## 守护进程被误配成 cron

`ws_liquidation_daemon.py` 是 while True websocket 常驻，cron 配 `0 0 * * *` 每日跑 → `Script timed out after 3600s`、completed=1。**常驻 daemon 不该进 cron 每日调度**；守住守护+看门狗体系。

## 脚本归档后 cron 引用悬空

8/29 迁移把 `tv_keepalive.py` 移入 `scripts/_disabled_20260829/`，cron `TV Desktop保活` 仍引用 `scripts/tv_keepalive.py` → `Script not found`（paused 掩盖）。审计 `Script not found` 先查 `_disabled_*/` 归档目录：有意禁用 → cron 应同步 pause；误删 → 恢复。

## 分析档位实码（2026-08-31 复核）

`pipeline_router.resolve_analysis_mode`：
- 含「分析/全面/全周期/深度/完整卡」→ full
- 含「现在呢/继续/接着/更新/继承」→ inherit（仅当 has_context=True，否则 quick）
- 其余→ quick

auto_card 对 inherit：`load_analysis_context(symbol)` 失败/过期 → 自动升级 full（3200-3213 行），避免空背景冒充继承。
