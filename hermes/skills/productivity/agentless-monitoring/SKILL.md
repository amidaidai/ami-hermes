---
name: agentless-monitoring
version: 1.3.0
description: 零 token 看门狗模式 — 用 no_agent cron + Python 脚本实现静默条件监控，只有触发时才发通知。
triggers:
  - 用户要求"盯一下 X，XXX 时通知我"
  - 用户说"到那个点提醒我"、"到那个点叫我"、"提醒我"
  - 用户表现出对某个价格/条件被触发的关注，即使没有明确要求"创建监控"
  - 你在分析中说"到那个点提醒你"、"有信号再推你"、"到关键位提醒"之类的话
  - 需要持续监控某个条件但不想消耗 token
  - 需要零成本的定时检查任务
  - 任何 "watch / monitor / alert when" 类需求
  - 分析中说"到时候提醒你"后用户说"你设置一下" — 立即创建监控
  - 用户确认关键位后说"你设置一下/设一下" — 立即创建自动监控
  - 用户说"每次都提醒你设置好麻烦啊" — 挫败信号，必须立即行动
  - 用户说"不是三分钟，是实时" — 用户需要常驻守护进程级提醒，不是每 1 分钟 Cron
  - 用户说"你总不实时" — 改用 daemon 直接检测/通知，Cron 只做看门狗
---

# agentless-monitoring

> ⚠ 2026-09-11 校正（**已实测核实**）：本文件部分段落把下列脚本当现行工具，实际状态是——
> ① `btc_alert_watch_v3` / `btc_push_cron` / `btc_collector` / `btc_fast_daemon` **已移入**
>    `scripts/_archive/`（`scripts/` 根下已无此文件）；
> ② `btc_keylevel_ws_guard` / `btc_keylevel_sentinel` / `btc_keylevel_rest_guard` /
>    `btc_price_arrival_sentinel` **文件仍在 `scripts/`，但既不在 cron 也不在任何进程中运行**
>    —— 属历史代际，不要拿它们当现行链路。
> **现行监控链只有一条**：`keylevel_guard.py`（常驻·亚秒 REST·多品种多顶点·每位 30min 冷却）
> + `btc_keylevel_guard_watchdog.py`（cron `*/2` 拉起）+ `keylevel_read_trigger.py`（事件本地分析）
> + `btc_tv_refresh.py`（五周期快照续航）。对照表：
> `trading/realtime-trading-pipeline/references/dead-script-index.md`；
> 系统全貌：`D:/Hermes agent/docs/系统总览.md`；指标字段/行名：`D:/Hermes agent/docs/tv-indicator-field-map.md`。

## 概念

Hermes cronjob 的 `no_agent=True` 模式：
- **不启动 LLM agent** — 零 token 消耗
- 只跑脚本 -> 脚本 stdout=通知内容 / 空 stdout=不通知
- 适合纯条件判断的监控任务（价格警戒、技术指标触发、磁盘/内存阈值等）

## 工作流程

### 1. 写脚本

用 Python 直接调目标服务的 **公开 HTTP API**（不要走 MCP 工具，MCP 只在 agent 会话可用）。

脚本结构：

```python
#!/usr/bin/env python3
import json, urllib.request, sys

def get_json(url):
    """安全 GET 请求"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None

# 1. 获取数据（直接用 API）
data = get_json('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT')
if not data:
    sys.exit(0)  # 出错静默退出

# 2. 条件判断
if condition_met:
    print(f"【条件达成】{message}")
else:
    # 静默退出 — no_agent 模式下空输出=不通知
    sys.exit(0)
```

### 2. 部署到 Hermes 脚本目录

```bash
# 写入 ~/AppData/Local/hermes/scripts/<name>.py
# 也可以用 write_file 直接写
```

### 3. 创建 no_agent cron

**频率选择铁律**：
- 用户说“实时”或“不是一分钟” → 使用常驻 daemon 直接检测和通知；不要把每分钟 Cron 称为实时
- 价格监控、关键位盯盘的分钟级降级方案才使用 `* * * * *`
- Cron 在实时架构中只承担看门狗/维护职责
- 非时间敏感的数据采集 → 可用 `*/5 * * * *` 或更长

```python
cronjob(
    action='create',
    name='描述性名称',
    schedule='* * * * *',  # 每分钟！用户要实时
    repeat=12,           # 跑 12 次后自动停止
    script='script_name.py',
    no_agent=True,       # 关键！零 token
)
```

### 4. 更新已存在的 cron 为 no_agent

```python
cronjob(
    action='update',
    job_id='xxx',
    no_agent=True,
    script='script_name.py',
)
```

## 重要规则

| 规则 | 说明 |
|:--|:--|
| 空 stdout = 静默 | 条件未满足时不要 print 任何内容，直接 `sys.exit(0)` |
| 非零退出码 = 错误通知 | 脚本异常退出会发送错误提醒，所以要吞掉预期的网络错误 |
| stdout 内容 = 通知正文 | 条件满足时 print 的内容就是用户收到的消息；只适合纯文本、单脚本、无乱码风险的简单监控 |
| 不要用 MCP 工具 | MCP 只在 agent 会话上下文可用；脚本里直接用 requests/urllib |
| 超时 10s | 脚本默认 timeout 由 Hermes 控制；脚本内部也设自己的 timeout |
| cron `repeat` 默认为 `forever` | 除非显式传 `repeat=N`，否则去心化循环不停。**特别注意 `repeat='once'` 会让 job 跑完一次就永久停止**，不会循环。bug 排查时先 `cronjob(action='list')` 看 `repeat` 值。 |

### Windows/Telegram 中文提醒模式

当监控内容要发中文、Markdown、Telegram 话题，或运行在 Windows 上时，不要让业务中文走 no_agent cron stdout：

- 检测脚本：无事件 `stdout` 为空；有事件把中文写入 UTF-8 `pending.txt`，不要 `print()` 中文。
- 推送脚本：读取 pending 后用 Telegram API / `telegram_direct.py` 发送；成功保持 `stdout` 空，失败只输出 ASCII 错误并非零退出。
- Cron 配置：检测 cron 建议 `deliver='local'`；独立推送 cron 才负责发目标话题。
- 格式规则：pending 可用中文和少量 emoji；stdout 只允许 ASCII 诊断，避免 Windows GBK/控制台转码乱码。

详细排查和模板见 `references/windows-telegram-cron-output.md`。

## 进阶：多源数据采集（no_agent collector）

当监控需要多个数据源（价格 + OI + 资金费率 + 多空比 + Taker量），不要每个源一个 cron。**用一个 collector 脚本聚合全部**：

> ⚠ **示例里的脚本名已退役**（`btc_collector` / `btc_push_cron` / `btc_vwap_daemon` / `btc_alert_watch_v3`）——
> 它们已移入 `scripts/_archive/` 或不再运行。本节的**模式**依然成立，但脚本名只是历史示意：
> **不要照抄 `script=` / `command=` 的值**，否则会创建指向不存在文件的 cron。
> 现行监控链见 `trading/realtime-trading-pipeline/references/dead-script-index.md`。

```python
# collector.py（示意名）— 单脚本聚合一分钟内的所有数据
record = {"ts": ts}
# 逐字段 try/except，一个字段失败不影响其他
try:
    record["price"] = float(http_get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")["price"])
except: pass
try:
    k = http_get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=30")
    record["vwap"] = sum((float(x[2])+float(x[3]))/2*float(x[5]) for x in k) / sum(float(x[5]) for x in k)
except: pass
try:
    oi = http_get("https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT")
    record["oi"] = float(oi["openInterest"])
except: pass
try:
    funding = http_get("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT")
    record["funding"] = float(funding["lastFundingRate"])
except: pass
try:
    lsr = http_get("https://fapi.binance.com/futures/data/topLongShortAccountRatio?symbol=BTCUSDT&period=5m&limit=1")
    record["ls_ratio"] = float(lsr[0]["longShortRatio"])
except: pass
try:
    tak = http_get("https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=5m&limit=1")
    record["taker_ratio"] = float(tak[0]["buySellRatio"])
except: pass
# 落盘
json.dump(record, open(OUT, "w"))
```

**关键原则**：
- 每个字段独立 try/except — 一个 API 超时不拖垮全部
- 输出 JSON 文件供其他 cron/daemon/LLM 读取
- 不 print 任何内容（no_agent 模式空输出=正常运行中）
- 同一路径用 `os.path.expanduser("~/AppData/Local/hermes/data/")` 统一管理
- 保留历史：追加 JSONL 文件，保留最近 2000 行

## 进阶：多层级区间看门狗（zone-based watchdog + auto-analysis）

当监控目标不是单一价位，而是**价格进入某个区间时自动分析并推送**（例如"BTC到63,270附近时分析一下"），用这套模式：

### 场景
- 用户说"到那个点分析一下，看行不行再提醒我"
- 需要区分"触及前低" vs "跌破前低" vs "触及大底"等多个级别
- 触发时不但报价格，还要有简单技术背景（K线趋势、量能、阴阳比）

### 设计原则

```
1. 定义 2-3 个关键价位 + 触发区间宽度（±100）
2. 脚本每 1 分钟跑一次（* * * * * cron），实时性足够
3. 不在区间内 → sys.exit(0) 静默
4. 在区间内 → 触发后做三件事：
   a. 拉最近 15m K线（3-8根）
   b. 计算趋势方向 + 量能分析 + 阴阳比
   c. 输出格式化分析（包含两种走法）
5. 同级别 5 分钟内不重复推送（状态文件去重）
6. 零 token：纯 urllib + 无 agent
```

### 触发级别类型

看门狗可以监控多种级别，按优先级从高到低排列：

| 级别 | 场景 | 触发条件 | 典型输出 |
|:--|:--|:--|:--|
| `VWAP_ZONE` | 反弹做空区 | 价格进入 `[VWAP_ZONE_LO, VWAP_ZONE_HI]` | 入场价·止损·目标 |
| `L1` | 前低决策区 | `LEVEL_L1 ± ZONE_WIDTH` | 破/守两种走法 |
| `L2` | 大底 | `LEVEL_L2 ± ZONE_WIDTH` | 双底机会 vs 趋势转空 |
| `L1_BROKEN` | 已破前低 | 低于 L1 但高于 L2 | 下一目标 |
| `L2_BROKEN` | 已破大底 | 低于 L2 | 趋势转空 |

每个级别都有独立的 COOLDOWN 计数器，5分钟内不重复推送同一级别。

### VWAP_ZONE 特殊处理

当价格反弹至 VWAP 附近（通常是下跌后的第一次反弹），适合做空而非追空：

```python
# 触发优先级高于 L1/L2
if VWAP_ZONE_LO <= price <= VWAP_ZONE_HI:
    triggered = "VWAP_ZONE"
```

输出应包含：入场区间、止损位、目标位，帮助用户**立即行动**而非分析。

### 防重复机制

```python
# 状态文件 .watchdog_state.json
state = json.load(open(STATE_FILE))  # or {}
last = state.get(f"last_{triggered}", 0)
if now - last < COOLDOWN:            # 300秒
    sys.exit(0)
state[f"last_{triggered}"] = now
json.dump(state, open(STATE_FILE, "w"))
```

### 分析内容格式（棠溪用户偏好）

每条触发推文应包含：
- 触发级别说明（前低/大底/已破位）
- 当前价位和距离目标位的差值
- 15m 短线趋势（方向·量能·阴阳）
- 最近 3 根 K线收盘价
- 两种走法（破/守的不同目标）

### 完整模板

见 `templates/btc_price_watchdog.py` — 修改 LEVEL_L1/LEVEL_L2/VWAP_ZONE_* 即可复用。

## 进阶：全区间覆盖看门狗 (v4 模式)

当价格走势快速时，仅监控 2-3 个离散区间可能因为 timing 问题错过触发。用 ZONES 字典 + MID 兜底确保**每个价格位置都有输出**。详见 `references/full-range-watchdog-pattern.md`。

## 进阶：穿越检测（漏检修复）+ 真实时守护（2026-08 实证）

**窄带触发会漏检**：`价格落在关键位±0.07%窄带内才触发` 时，价格能在两轮巡检间直接跳过窄带（实案：BTC 79,260→79,735 跳过 79,633，到价却没触发）。改用**穿越检测**（自上次巡检以来穿过关键位，任一方向即触发），同侧窄幅摆荡不误报。详见 `references/crossing-detection-vs-zone-trigger.md`。

**"实时"≠分钟级 cron**：cron 最小粒度 1 分钟。用户说"不该是一分钟、应该是实时"时，必须用**常驻守护进程 + 亚秒(0.5s)轮询**（`terminal(background=True)`），探价源用 REST（`fapi/v1/ticker/price` 每次 ~0.35s 实测稳定）。WS 在部分环境被代理/DNS 卡死，别当默认假设。

**分层免噪**：守护(零token)写触发文件 → agent cron 读触发文件，`TRIGGER` 才分析推送 / `WAIT` 零输出 → 看门狗 cron 守护重启。**agent cron 必须 `deliver=local`**，否则会把 agent 每次"未触发"回复自动推送成噪音；prompt 硬性命令只有 `TRIGGER` 才允许推话题。用户明确："没有到位置就不要推送给我。"

---

## 进阶：区间自动更新架构（Hot-Read Pattern）

**问题**：daemon 的 7 区间（大底/前低已破/VAL折价区/VWAP测试区/…）基于 VWAP/VAL/VAH/周VWAP 等动态指标计算，但 daemon 本身不能调 TV MCP（no_agent 环境），硬编码值会随市场移动迅速过时。

**方案**：双轨自动更新 — daemon 热读 JSON + agent cron 维护 JSON。

```
daemon (15s循环) ──热读──→ btc_ref_levels.json ←──写入── agent cron (每4h读TV MCP)
```

### 1. daemon 热读逻辑

daemon 每轮循环检查 `btc_ref_levels.json` 的 mtime，有变化则动态重算全部区间：

```python
REF_FILE = DATA_DIR / "btc_ref_levels.json"
_last_ref_mtime = 0

def load_dynamic_levels():
    """读 btc_ref_levels.json → 动态重算7区间。文件没变则跳过。"""
    global _last_ref_mtime
    mtime = REF_FILE.stat().st_mtime
    if mtime <= _last_ref_mtime:
        return  # 没变化
    _last_ref_mtime = mtime
    ref = json.load(open(REF_FILE))
    vwap = ref.get("vwap")
    val = ref.get("val")
    vah = ref.get("vah")
    w_vwap = ref.get("w_vwap")
    r_low = ref.get("recent_low")
    # 重算区间（公式见 references/zone-calculation-formula.md）
    global LEVELS
    LEVELS = OrderedDict([
        ("大底",       {"lo": int(r_low - 250), "hi": int(r_low + 50), "prio": 1}),
        ("前低已破",   {"lo": int(r_low + 51),  "hi": int(val),        "prio": 2}),
        ("VAL折价区", {"lo": int(val + 1),      "hi": int(vwap),       "prio": 3}),
        ("VWAP测试区",{"lo": int(vwap + 1),     "hi": int(vwap + 120), "prio": 2}),
        ("VWAP上运行", {"lo": int(vwap + 121),   "hi": int(vah),        "prio": 3}),
        ("周VWAP测试", {"lo": int(w_vwap - 75),  "hi": int(w_vwap + 75), "prio": 2}),
        ("周VWAP上方", {"lo": int(w_vwap + 76),  "hi": 99999,           "prio": 4}),
    ])
```

**关键**：mtime 比较避免每次循环都做 JSON 解析（开销小但频繁）。`global LEVELS` 直接替换模块级变量，后续 `detect_zone()` / `score_opportunity()` 自动使用新区间。

### 2. agent cron 维护 JSON

**不能用 no_agent cron** — 更新需要读 TV MCP 的 `study_values`（MCP 工具只在 agent 上下文可用）。这是 agent cron 的少数正当用途之一：**不是做市场分析推送（噪音），而是做基础设施维护（静默更新数据文件）**。

```bash
hermes cron create "0 */4 * * *" \
  --name "BTC关键位同步" \
  --deliver "local" \        # 静默，不推送
  --workdir "D:\Hermes agent" \
  --skill "tradingview-indicator-analysis" \
  "Connect TV MCP. Set BINANCE:BTCUSDT.P 15m. Read study_values for 
   S_VWAP VAH VAL POC W_VWAP DO. Read 100 OHLCV bars find recent_high/low.
   Write JSON to C:/Users/Administrator/AppData/Local/hermes/data/btc_ref_levels.json
   with keys vwap/val/vah/poc/do/w_vwap/recent_low/recent_high + updated_at ISO.
   Output NOTHING if successful. Skip silently if TV MCP unavailable."
```

**频率建议**：每 4 小时（`0 */4 * * *`）。太频繁浪费 token（TV MCP 会话 ~5K token/次），太稀可能导致 VWAP 在新 session 开始后滞后 4 小时。VAL/VAH 每 session（约 8h）滚动一次，4h 刷新足够。

### 3. 首次对齐流程

创建/更新 daemon 时，先手动对齐区间：

1. TV MCP → `chart_set_symbol BINANCE:BTCUSDT.P` → `chart_set_timeframe 15` → 等 8s
2. `data_get_study_values` → 提取 S VWAP/VAH/VAL/POC/DO/W_VWAP
3. `data_get_ohlcv(count=100)` → 找近期最低点/最高点
4. 按公式计算 7 区间，更新 daemon 硬编码值（作为 `btc_ref_levels.json` 不可用时的 fallback）
5. 写初始 `btc_ref_levels.json`
6. 创建 agent cron 维持后续自动更新
7. 启动 daemon（`terminal(background=True)`，不加 `notify_on_complete`）

详见 `references/zone-calculation-formula.md`。

---

## 进阶：三轨架构（daemon + cron 推送 + LLM 分析）

对于交易系统，**数据采集和事件预警只是第一层**，还需要定期深度分析。完整架构：

```
┌─ 零 Token 层 ──────────────────────────────────┐
│                                                  │
│ daemon (10s)  → pending.txt  → push cron (1m)   │
│ collector (1m) → btc_latest.json                 │
│ TV 截图 (5m)  → screenshots/*.png                │
│                                                  │
├─ LLM 分析层（默认 15m） ─────────────────────────┤
│                                                  │
│ MTF 分析 cron (15m, KillZone 8-23)               │
│  · 读 collector JSON                             │
│  · TV 截图 + 指标数据 (via MCP)                   │
│  · 生成压缩分析卡 + 截图 → 推话题                  │
│                                                  │
├─ LLM 分析层（Token-Rich 5m 变体） ────────────────┤
│                                                  │
│ 高频分析 cron (5m, KillZone 8-23)                 │
│  · TV MCP 全周期 + SVP 行动格 + 截图 full         │
│  · Binance MCP (OI/多空/费率/Taker)               │
│  · 多因子评分 ≥7/10 才推完整卡 → Telegram 386     │
│  · 模型: deepseek-v4-flash (~10K token/run)       │
│  · 前提: 用户有大量 token 额度且主动要求           │
│                                                  │
└──────────────────────────────────────────────────┘
```

### 创建 LLM 分析 cron

**默认版本（15m，适合有限 token）：**

```bash
hermes cron create "*/15 8-23 * * *" \
  --name "BTC MTF 分析" \
  --deliver "telegram:-1003733144325:386" \
  --workdir "D:\Hermes agent" \
  --skill "tradingview-indicator-analysis" \
  "BTC multi-timeframe analysis via TV MCP..."
```

**Token-Rich 变体（5m，适合无限 token）：**

```bash
hermes cron create "*/5 8-23 * * *" \
  --name "BTC高频分析" \
  --deliver "telegram:-1003733144325:386" \
  --workdir "D:\Hermes agent" \
  --skill "tradingview-indicator-analysis" \
  --skill "crypto-multisource-analysis" \
  "short_prompt_placeholder"
# Then edit with full prompt:
hermes cron edit <job_id> --prompt "Full prompt with scoring threshold..."
```

**Token-Rich 变体 prompt 要点**：
- 明确写「score≥7 AND direction clear → push card」「score<7 or X/conflict → output EMPTY」
- 走全套：TV MCP 全周期 + Binance MCP 交叉验证 + 截图 full
- deliver 用显式 `telegram:CHAT_ID:THREAD_ID`，不用 origin
- 模型用低成本高容量（deepseek-v4-flash / opencode-go ~10K token/run）
```

**关键**：
- `enabled_toolsets` 必须包含 `terminal` 和 `file` 以读取 JSON 文件
- `vision` 用于查看 TV 截图
- 分析 cron 用 `deliver='origin'` 自动回到创建时的对话话题
- 带 `skills=[...]` 加载分析模板 skill

### KillZone 时间表

KillZone = 流动性集中时段，适用于所有交易品种：

| 时段 | 时间 (CST) | 分析频率 |
|:--|:--|:--|
| 亚洲 | 08:00-16:00 | `*/15 8-16 * * *` (每15分) |
| 伦敦 | 14:00-23:00 | `*/15 14-23 * * *` (每15分) |
| 纽约 | 20:00-05:00+1 | `*/15 20-23,0-5 * * *` |

合并时间表: `*/15 8-23 * * *` = 亚盘到纽盘收盘前

### daemon VS cron VS LLM cron 对比

| 方式 | 延迟 | Token | 能力 | 场景 |
|:--|:--|:--|:--|:--|
| daemon (background) | ~10s | 0 | 纯价格/条件判断 | 实时事件预警 |
| no_agent cron | ~1m | 0 | HTTP API 调用 | 数据采集、推送 |
| LLM cron | ~15m | ~10K/run | MCP 工具、推理 | 深度分析、出卡 |

## 进阶：双轨架构（daemon + cron 推送）

对于亚秒级的实时监控（< 1s 响应），cron 的最小粒度 `* * * * *`（每分钟）不够快。方案：**daemon 做实时检测 + cron 做消息推送**，通过 pending 文件桥接。

```
daemon (10s 轮询) ──写──→ pending.txt ←──读── cron (1m) ──推──→ Telegram
```

### 架构说明

| 层 | 工具 | 频率 | token 消耗 | 职责 |
|:--|:--|:--|:--|:--|
| 检测 | `terminal(background=True)` 启动的 daemon | 10s | 0 | 轮询数据源，检测触发条件 |
| 桥接 | 本地文件 `pending.txt` | — | 0 | daemon 写事件，cron 读+清空 |
| 推送 | `cronjob(no_agent=True)` | 1m | 0 | 读 pending → 有内容就 print（即推送） |

### Daemon 关键模式

```python
# 防重复：按时间块去重，同一 5 分钟内不重复触发同一事件
block = now.minute // 5
state["last_blocks"]["vwap_test"] = block  # 记录已触发的块
# 下次只在新块才触发
```

```python
# pending 文件写入
def write_pending(msg):
    with open(PENDING, "a") as f:
        f.write(msg + "\n---\n")

# 只有 true 条件才写
if condition_met:
    write_pending(f"【信号】{message}")
```

```python
# 状态持久化（JSON），daemon 重启后恢复去重状态
import json
state = json.load(open(STATE_FILE))
# ... update state ...
json.dump(state, open(STATE_FILE, "w"))
```

### Cron 推送脚本（含渲染清理）

⚠️ 写入 pending 时使用的 `---` 分隔线（用于区分多条消息），如果直接 print 到 Telegram，会渲染为纯文本 `---`，视觉上像排版断裂。

**推送脚本必须做 render-safe 清理**：

```python
#!/usr/bin/env python3
# pusher.py（示意名）— no_agent cron 读取 pending 文件 + 渲染清理
import os, re

PENDING = os.path.expanduser("~/AppData/Local/hermes/data/btc_pending.txt")

if not os.path.exists(PENDING) or os.path.getsize(PENDING) == 0:
    exit(0)

with open(PENDING, "r") as f:
    content = f.read()

if not content.strip():
    with open(PENDING, "w") as f:
        f.truncate(0)
    exit(0)

# === 渲染清理 ===

def clean_pending(text: str) -> str:
    """清理 pending 内容，修复 Telegram 渲染问题。"""
    lines = text.strip().split("\n")
    cleaned = []
    for line in lines:
        s = line.strip()
        # 跳过纯分隔线 (--- / ___ / ***)
        if re.match(r'^[-_*]{3,}$', s):
            continue
        if s == "---":
            continue
        cleaned.append(line)
    # 去除首尾空行
    while cleaned and cleaned[0].strip() == "":
        cleaned.pop(0)
    while cleaned and cleaned[-1].strip() == "":
        cleaned.pop()
    result = "\n".join(cleaned)
    if result:
        result += "\n"
    return result

def fix_markdown_balance(text: str) -> str:
    """修复不成对的 ** 和 ` 标记。"""
    if text.count("**") % 2 != 0:
        text += "**"
    lines = text.split("\n")
    fixed, in_block = [], False
    for line in lines:
        if line.strip().startswith("```"):
            in_block = not in_block
            fixed.append(line); continue
        if not in_block and line.count("`") % 2 != 0 and "```" not in line:
            line += "`"
        fixed.append(line)
    return "\n".join(fixed)

# === 输出 & 清空 ===
cleaned = clean_pending(content)
cleaned = fix_markdown_balance(cleaned)
if cleaned:
    print(cleaned)

with open(PENDING, "w") as f:
    f.truncate(0)
```

### 创建步骤

```python
# 1. 启动 daemon（后台）
terminal(
    command=f'python ~/AppData/Local/hermes/scripts/keylevel_guard.py',   # 现行常驻守护
    background=True,
)

# 2. 创建推送 cron（每分循环）
cronjob(
    action='create',
    name='BTC 告警推送',
    schedule='* * * * *',   # 每分钟
    script='<你 scripts/ 下真实存在的推送脚本>.py',   # 必须是真实文件名，否则 cron 空转
    no_agent=True,
    deliver='telegram:-1001234567890:386',  # 目标群话题
    # repeat 不传 = forever
)
```

### 启动冷却 (startup cooldown)

Daemon 重启后，前几轮循环可能拿到"陈旧的"触发条件（重启前价格已经变化，重启后才读到）。用计数器避免误报：

```python
cnt = 0
while True:
    time.sleep(10)
    cnt += 1

    # 前 30 秒抑制 VAL/VAH 事件（让市场状态稳定）
    if bl and cnt > 3 and lb.get("b") != block:
        # 新破 vs 持续破 — 用 cnt 区分
        d = "持续" if cnt > 10 else "新破"
        alerts.append(f"🔴 BTC{d}破VAL...")

    # 前 30 秒抑制站回事件
    if al and cnt > 3 and lb.get("k") != block:
        alerts.append(f"🟡 BTC站回VAL...")
```

- `cnt > 3`: 跳过前 ~30s（3次 × 10s），防止重启时的假触发
- `cnt > 10`: 区分"新破"与"持续"，让报警信息更精确

### 硬编码价位同步

VAL/VAH/DO 等关键位如果在 daemon 里硬编码，需要与 TV 指标值保持一致。建议每次系统升级时同步：

```python
# 从 TV SVP 指标读数更新（对照 data_get_study_values 的输出）
VAL_REF = 63886.0   # TV 15m VAL
VAH_REF = 64490.0   # TV 15m VAH
DO_REF = 63312.0    # 当日开盘
```

当 TV 指标的 VAL/VAH 变化时（随 session 滚动），手动更新这些值。或让 collector 脚本读取 TV 指标后自动写入一个共享 ref 文件供 daemon 读取。

## Pitfalls

- ⚠️ **cron `repeat='once'` = run once and stop forever** — 创建时如果不传 repeat，默认为 forever（正确）。如果之前是 `repeat=12`，跑完 12 次就永久停止，不会自动续。排查时先 `cronjob(action='list')` 看 `repeat` 值。
- ⚠️ **daemon 重启**：Hermes 重启后 daemon 不会自动恢复，需手动 `process(action='list')` 检查，或通过 `cronjob(script='...', no_agent=True, schedule='1h')` 做心跳检测。
- ⚠️ **pending 文件路径**：daemon 和 cron 必须用相同 `os.path.expanduser("~/AppData/Local/hermes/data/...")`，不要硬编码。
- ⚠️ **Windows daemon 管理**：`kill` 用 `taskkill //PID <pid>`（双斜杠），不要用 `kill -9`（Linux only）。
- ⚠️ **pending 膨胀**：高频事件（每 10s 触发）会撑大文件。用 block 去重限制同一 5min 内只写一次。
- ⚠️ **cron deliver 话题丢失**：含 `:thread_id` 的 deliver 目标在 cron 更新时可能丢失话题后缀。更新后手动检查 `cronjob(action='list')`。
- ⚠️ **Telegram 的 $ 符号渲染**：pending 消息中的美元符号跟在反引号内部（如 `` `$1,234` ``）可能导致 Telegram 格式化异常。建议将美元符号放在反引号外部：`` $`1,234` `` 或完全避免美元符号标记。
- ⚠️ **pending 中的 `---` 分隔线渲染为纯文本**：daemon 写入 `{msg}\n---\n` 分隔多条消息，但 `---` 直接 print 到 Telegram 会渲染为纯文本横线。推送脚本必须过滤 `---` 行（用 `re.match(r'^[-_*]{3,}$', line)` 检测）。
- ⚠️ **Markdown 不平衡导致整条消息不渲染**：多条消息拼接后可能产生奇数个 `**` 或 `` ` ``，导致 Telegram markdown 解析失败、整条消息变纯文本。推送脚本应做平衡修复（`**` 成对，`` ` `` 成对）。
- ⚠️ **TV 截图在 no_agent 模式下不可用 MCP 工具**：agent 层可以 `mcp_tradingview_capture_screenshot` 截图，但 no_agent cron/daemon 脚本里 MCP 工具不可用。方案：写一个独立的 `tv_screenshot.py` 脚本，通过 subprocess 调用 TV CLI（`node path/to/cli/index.js screenshot`）截图，再在 daemon 高概率信号触发时 subprocess 调用它。截图路径通过 `state.json` 写入供后续分析 cron 使用。
- ⚠️ **proactive alert setup required** — when the user shows interest in a price level and says "提醒我" / "到那个点叫我" / "到关键位提醒", or when you yourself say "到那个点提醒你" / "有信号推你", **immediately create the monitoring mechanism (cron job or daemon) right then**. Do NOT just say "我会提醒你的" and wait for the user to ask again. The user has explicitly expressed frustration about having to ask twice. This is a FIRST-CLASS action item, not a future plan.
- ⚠️ **no_agent 脚本不要导入 `mcp` Python SDK** — `from mcp.client.stdio import stdio_client` 依赖于 `pydantic_core` C 扩展模块，该模块在大量场景下可能缺失或版本不匹配。no_agent 脚本应仅使用纯 Python HTTP 请求（`urllib.request`）。所有 MCP 工具调用只能在有 agent 的 cron 或交互会话中进行。
- ⚠️ **Cron 脚本路径解析：相对路径从 `~/.hermes/scripts/` 解析，不是 workdir** — 创建 cron 时 `script='btc_price_watchdog.py'` 表示 Hermes 从 `~/.hermes/scripts/` 找文件，**不是工作目录**。即使设置了 `workdir='D:/Hermes agent/scripts'`，脚本也是从 `~/.hermes/scripts/` 加载（不是 `~/AppData/Local/hermes/scripts/`）。所以脚本以及它 import 的所有依赖（`dmi_decision.py` 等）都必须复制到 `~/.hermes/scripts/` 才能正常工作。排查 cron 错误时，先确认脚本在 `~/.hermes/scripts/` 下存在。**注意 `last_run: ok` 在 cron 列表中的含义是"cron 调度引擎已执行"，不等于脚本实际执行成功**——脚本不存在或 import 失败的 cron 也可能显示 `ok`。必须通过 `ls ~/.hermes/scripts/` 验证脚本真实存在。

- ⚠️ **状态文件路径必须用 cron 可写目录** — no_agent 脚本的 `__file__` 在 cron 环境下的解析可能与终端不一致，导致状态文件（用于防重复、持久化）无法写入，进而使脚本每次运行都认为"已触发过"，防重复逻辑吞掉所有输出。**必须使用 `os.path.expanduser("~/AppData/Local/hermes/data/")`** 作为状态文件基路径，避免 `os.path.dirname(__file__)` 的 cron 环境不稳定性。实案：`btc_price_watchdog.py` v2 使用 `os.path.join(os.path.dirname(__file__), ".state.json")` 在 cron 下始终静默；改为 `~/AppData/Local/hermes/data/.state.json` 后正常触发。
- ⚠️ **`hermes cron delete` 不会杀死正在执行的 no_agent 脚本进程** — 脚本被 cron 调度器触发后在独立进程中运行。即使用 `hermes cron delete` 删除了该 cron 作业，已经启动的脚本仍然会继续执行直到结束，可能数分钟后才输出结果。这是**脚本执行生命周期** vs **cron 调度生命周期**不同步导致的正常行为。排查"删了cron还收到消息"问题时，检查 `~/.hermes/scripts/` 下对应脚本的执行耗时（尤其是含多轮 HTTP API 调用 + 健康检查的脚本，如 freerouter.py 单次执行耗时 4-5 分钟）。如需紧急阻止，用 `taskkill //F //PID <pid>` 在 Windows 上强制终止进程。
- ⚠️ **`last_run: ok` 不等于脚本成功** — cron 列表的 `last_status: ok` 只表示"调度器已启动脚本"，不代表脚本实际执行成功。以下情况均可能显示 `ok` 但实际失败：
  - 脚本在 `workdir` 路径下不存在（但 Hermes 后备从 `~/.hermes/scripts/` 找到旧版）
  - 脚本 import 的模块缺失
  - 脚本内的 API 调用全部超时导致无输出（no_agent 模式下空输出=正常静默，更难排查）
  - 脚本写了不完整的 JSON 到硬盘（部分 try/except 块失败但脚本无报错）
  **排查铁律**：先用 `ls ~/.hermes/scripts/` 确认脚本存在，再用 `python ~/.hermes/scripts/<name>.py` 手动运行查看实际输出。
- ⚠️ **cron 作业有两层存储：活跃调度 vs jobs.json 存档** — 活跃的 cron 作业通过 `hermes cron list` 可见，存储于调度器中。但 `~/AppData/Local/hermes/cron/jobs.json` 中可能还存有**已暂停或已删除的旧 cron 记录**，不会被 `hermes cron list` 显示，但仍占用文件空间。这些旧记录不会触发执行，但会误导 `jobs.json` 的 `updated_at` 时间戳。彻底清理 cron 时务必检查两个位置：
  1. `hermes cron list` — 确认活跃作业已清空
  2. `cat ~/AppData/Local/hermes/cron/jobs.json` — 确认无残留

- ⚠️ **Agent-mode cron jobs 会持续推送低置信信号 = 噪音（默认原则）** — 当用户说"没有确定的机会不要推我"时，必须立即暂停所有推送X级/冲突级信号的 agent-mode cron。这些 cron 即使 prompt 写"无事件静默"也无法完全抑制 agent 的自发分析输出。**默认原则**：市场监控只用 no_agent 脚本（确定性条件触发），不做 agent-driven 定时分析推送。**例外（Token-Rich Override）**：当用户明确表示有大量 token（如 8B 额度）且主动要求"随便造，按照最优解来实时更新"时，可以部署高频 agent cron（每5分钟）。前提：① cron prompt 明确写清推送阈值（评分≥7/10 才推）② 使用 deepseek-v4-flash 等低成本模型 ③ daemon（零token）仍作为第一道快速哨兵 ④ 用户知情并主动要求。
- ⚠️ **部署新版本后必须清空旧状态文件** — 更新看门狗脚本后，旧的 `.btc_watchdog_state.json` 里的 cooldown 时间戳还在，会阻止新版本的首次触发（因为 `now - last < COOLDOWN` 仍然成立）。部署新版本后执行 `rm -f ~/AppData/Local/hermes/data/.watchdog_state.json` 清空状态。或者在脚本中检测版本变更时自动重置。
- ⚠️ **cooldown 过长会错过快速行情** — 300s (5min) cooldown 在亚洲流动性低时合适，但伦敦/纽约开市后价格可能在 2 分钟内过完一个区间。建议用 180s (3min) 作为默认值，快市时可临时降至 60s。
- ⚠️ **no_agent cron** 不要用 MCP 工具 — 脚本里只能裸 HTTP 请求
- ⚠️ **`deliver="origin"` 会静默丢消息 — 已多次验证，不要使用** — 无论 no_agent 还是 agent mode，`deliver="origin"` 在话题（thread）中创建的 cron job **从来不保证消息送达用户可见的界面**。表现如下：
  - `cronjob(action='list')` 显示 `last_status: ok`, `last_delivery_error: null` — 系统认为推送成功
  - **但用户完全没收到任何消息**
  - 这是最致命的模式：**静默丢消息**，没有任何 error 可以排查
  - 已多次验证（同一系统，同一脚本：origin = 静默丢，explicit = 立即收到）
  - 尤其发生在话题中创建、Hermes 重启后、cron pause/resume 后
  
  **铁律**：所有需要用户收到的 cron 推送，**永远**使用显式 delivery 目标 `telegram:CHAT_ID:THREAD_ID`。绝不用 `deliver="origin"`。通过列出已有的、已知正常工作的 cron job 获取正确的 CHAT_ID 和 THREAD_ID（参考 `cronjob(action='list')` 中 deliver 字段格式正确的那些 job）。

- ⚠️ **Agent-mode cron 推送即使成功也产噪音，已被用户投诉** — 用户明确说"没有确定的机会不要推我"后，Agent cron 仍然推送了 X 级冲突信号。agent 模式无法真正静默，即使 prompt 写"无事件输出空字符串"，模型也会生成分析文本。**市场监控只用 no_agent 脚本做确定性条件触发推送。** 用户如需要深度分析，在收到 no_agent 触发消息后手动请求即可。
- ⚠️ **不要用 agent-mode 做条件监控推送** — agent 模式的 LLM 无法真正"静默退出"。即使 prompt 写"不触发就输出空字符串"，模型仍然倾向于生成分析文本（投喂 token 后必然有产出），结果就是：
  - 要么持续推送低置信（X/B/C 级）信号 → 噪音，用户抱怨
  - 要么消耗 token 生成被丢弃的内容 → 浪费
  **原则**：条件监控只用 no_agent 脚本（确定性触发，零 token）。深度分析由用户在收到 no_agent 触发消息后**手动请求**，不做定时推送。如果用户说"不要推不确定的信号"，立即暂停所有 agent-mode 定时分析 cron。
- ⚠️ **部署新脚本版本后必须清空旧状态文件** — 更新看门狗脚本版本后（v1→v2→v3→v4），旧的 `.btc_watchdog_state.json` 里可能保存了旧版本的 cooldown 时间戳。如果旧版本已经触发了某个区间（比如 `VAL_ZONE`），新版本启动后检查 `state.get("VAL_ZONE", 0)` 拿到旧时间戳，`now - old_timestamp < COOLDOWN` 仍然成立，导致新版本的首次触发**被静默吞掉**。修复命令：`rm -f ~/AppData/Local/hermes/data/.watchdog_state.json`。或者在脚本启动时检测版本号变化自动重置。
- ⚠️ **看门狗版本部署时机可能完美错过行情窗口** — 价格在 30 秒内穿越 $400（典型场景：亚盘流动性低 + 消息驱动），no_agent cron 每 1 分钟跑一次，有可能永远抓不到价格"在区间内"的那个瞬间。缓解方案：v4 全区间覆盖 + MID 兜底，确保即使错过了 VWAP_ZONE 也会在 MID_LOW/VAL_ZONE 输出当前状态。但**最佳时机一旦错过无法补救**——如果 VWAP 反弹做空区被跳过，就不要在 MID_LOW 区域补做空通知，因为逻辑已经变了。接受现实，等待下一轮机会。
- ⚠️ **状态文件路径必须用 `os.path.expanduser()`，不要用 `os.path.dirname(__file__)`**（见上详） — 在 cron 环境下 `__file__` 的解析可能与终端不一致（特别是 MSYS/bash on Windows 混合路径时），导致状态文件写入失败或写入到错误路径。始终用 `os.path.expanduser("~/AppData/Local/hermes/data/.watchdog_state.json")`。
- ⚠️ **no_agent cron** 不要用 MCP 工具 — 脚本里只能裸 HTTP 请求（见上）
- ⚠️ **脚本用 urllib.request** 而非 requests，因为 Hermes 环境不一定装 requests
- ⚠️ **超时处理**：公共 API 可能限流或延迟，每个请求单独加 timeout
- ⚠️ **no_agent 模式忽略 prompt/skills/model override**，只有 script 生效
- ⚠️ **daemon 硬编码区间过时导致监控失能** — VWAP/VAL/VAH/周VWAP 是动态值，随 session 滚动变化。硬编码的 7区间若超过 2 天未更新，实际价格可能已完全脱离所有区间，导致 `detect_zone()` 返回 None → daemon 永久静默（连心跳都不更新 zone 字段）。**修复**：用热读 `btc_ref_levels.json` + agent cron 维护。详见 `references/zone-calculation-formula.md`。
- ⚠️ **首次启动 daemon 前必须写初始 btc_ref_levels.json** — daemon 依赖该文件做热读，没有就永远用硬编码 fallback（即此次对齐前的过期值）。
- ⚠️ **棠溪数据新鲜度看门狗不要只看一个数据目录** — 项目数据常写 `D:/Hermes agent/data/`，部分采集写 `~/AppData/Local/hermes/data/`。新鲜度脚本应对每个文件配置候选路径并取最新 mtime；`fast_daemon_state.json` 已废弃，BTC daemon 心跳看 `.btc_daemon_heartbeat.json`。该看门狗默认 `deliver=local`，不要把后台体检报告推 Telegram。详细排查见 system-ops 的 `references/tangxi-data-freshness-watchdog.md`。
