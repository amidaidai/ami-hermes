# 实时关键位到价提醒 — 守护进程 + crossing 检测（用户要"实时"，cron 不够）

> 2026-08-28 实测。用户质疑"为什么是一分钟？不应该是实时吗？" —— cron 最快就是分钟级，
> 关键位到价提醒要**真实时**必须上常驻守护进程 + 亚秒轮询（或 WebSocket）。本文档记录
> 已验证可用的 REST 亚秒轮询守护方案，以及踩过的跨会话数据坑。适用范围：所有推 TG 的
> 实时行情/关键位提醒类脚本（棠溪 BTC/XAU 关键位哨兵等）。

## 为什么 cron 轮询不够

- cron 调度器最小间隔 = 1 分钟（`* * * * *`）。"每 2 分钟查一次价"对快进快出的关键位提醒太慢，
  价格可能在两轮之间冲穿关键位又回落，哨兵**漏捕捉**（用户实测"不是到价了吗怎么没推"）。
- 用户要的是"价格碰到位置就告诉我"，cron 轮询只能做到"上次巡检时价格在位置附近"。

## 触发判定：用 crossing，不要用窄带

**旧做法（漏捕捉）**：`ZONE_LOW <= price <= ZONE_HIGH`（价格落在 ±0.07% 窄带内）才触发。
价格从 79,260 一路跳到 79,735 时越过 79,633 窄带但**不在任一轮巡检的窄带内** → 漏报。

**正确做法（crossing 检测）**：保存 `last_price`（上次轮询价），当
`(prev < LEVEL <= price)` = 向上穿 或 `(prev >= LEVEL > price)` = 向下穿 → 触发。
价格跳涨越过关键位、任何方向穿越都能捕捉。边界摆荡（如 79,500↔79,550 未触及 79,633）
不误报——实测 6 组用例全对。

```python
crossed = None
if prev is not None:
    if prev < LEVEL <= price:   crossed = "up"
    elif prev >= LEVEL > price: crossed = "down"
```

## 三套可选项（按首选用）

### 方案 A（本机实测跑通）：REST 亚秒轮询守护进程（首选）
常驻 `while True` 循环，`POLL_SECONDS = 0.5` 轮询 `fapi/v1/ticker/price`（实测每次 ~0.35s，稳）。
- 触发 → 写 `data/btc_keylevel_trigger.json`（含 zone/price/direction/ts/cooldown_until）。
- 每触发点独立 30min 冷却防刷屏；写心跳 `data/btc_keylevel_rest_heartbeat.json`。
- `terminal(background=true)` 启动，`psutil` 校验 PID 存活。

### 方案 B：WebSocket 毫秒级（本机代理/DNS 卡死，未采用）
`websockets` / `websocket-client` 走 `fstream.binance.com` 时：域名解析到不可达 IPv6
（`2001::...`），Python 库的代理隧道与 curl 不一致连不上；curl 能返回 101 但流式读帧不可靠。
→ **本机别再硬试 WS**，用方案 A。其它机器若 WS 通畅则优先 WS。

### 方案 C：纯 no_agent cron（最低频，仅作兜底）
只适合低频、非实时场景；用户明确要"实时"时被否决。

## 把"实时捕捉"与"分析推送"解耦（关键设计）

守护进程是纯 Python，没有 LLM 能力，不能自己出分析卡。正确闭环：
1. **守护进程**（实时）= 捕捉到价，只写 `btc_keylevel_trigger.json`，零 token，常驻。
2. **cron 搬运**（2min）= 前置脚本 `btc_keylevel_read_trigger.py` 读触发文件：
   - 有未过期的 `triggered:true` → 输出 `TRIGGER ...` 注入 context → agent 跑完整分析推 386。
   - 无 → 输出 `WAIT no-trigger`（agent 必须零输出，不调任何推送函数）。
3. **看门狗**（2min, no_agent）= 检查守护心跳，>90s 自动杀旧+重启。

这样"捕捉到价"是实时的（守护 0.5s），"分析推送"最迟 2min 内跟上——够用且省 token
（不在触发区间时 agent 不烧 token）。

## Cron `deliver` 的坑（用户 2026-08-28 纠正 · 铁律）

**cron `deliver='telegram:...386'` 会把 agent 每次的最终回复（包括"未触发"那句）都自动投递到 TG。**
用户明确："没有到位置就不要推送给我。"

修复：
- cron `deliver='local'`（不自动投递任何内容）。
- agent 只在 `TRIGGER` 时才显式用 `send_telegram_reliable(parse_mode='RichMarkdown')` 推送。
- `WAIT`/`COOLDOWN` 分支强制零输出（连"未触发，现价X"都不要发）。

## 其他坑

- **创建 cron 时 `repeat` 默认 once**：`cronjob(action='create', ...)` 若不带 `repeat=-1`
  会建成一次性任务（schedule 显示 "once in 2m"）。必须显式 `repeat=-1` 且用 cron 表达式
  （如 `*/2 * * * *`）确认循环。
- **Pyright 对 `sys.stdout.reconfigure`、`_GLOBAL["k"]=float` 报静态误报**：用 `hasattr`
  守卫 + 注释忽略；`python -m py_compile` 通过即运行安全。
- **同向冷却语义**：`if now >= cool_until or info.get("dir") != crossed` — 冷却内但方向
  变了也触发（价格反向穿越同样值得提醒），冷却内同方向则跳过（防刷屏）。

## 参考实现（本机已有）
- `scripts/btc_keylevel_rest_guard.py` — 实时守护（REST 0.5s + crossing + 心跳）
- `scripts/btc_keylevel_read_trigger.py` — cron 前置（读触发文件 → TRIGGER/WAIT）
- `scripts/btc_keylevel_guard_watchdog.py` — 看门狗（心跳超时自动重启）
