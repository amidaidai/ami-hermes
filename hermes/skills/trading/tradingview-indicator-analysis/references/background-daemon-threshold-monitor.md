# 后台守护进程到价监控模式

当用户要求"实时到价通知"（比 cron 5m 更频繁），用 **terminal(background) 启动常驻 Python 守护进程**，而非 cron job。

## 对比：三种监控模式

| 模式 | 最小间隔 | Token | 适用场景 |
|------|---------|-------|---------|
| cron no_agent | 5m | 零 | 宽松价位监控、心跳巡检 |
| cron LLM agent | 5m+ | 消耗 | 需要推理判断的周期性任务 |
| **后台守护进程** | **10s** | **零** | **用户要求"实时"的价位监控、条件触发即通知** |

## 实现模式（基础版 — 单条件）

```python
#!/usr/bin/env python3
import urllib.request, json, time, sys

CHECK_INTERVAL = 10
TARGET_PRICE = 64600

def get_json(url):
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(1)
    return None

while True:
    p = get_json('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT')
    if p: cp = float(p['price'])
    else: time.sleep(CHECK_INTERVAL); continue
    if cp >= TARGET_PRICE:
        print(f"【条件达成】`{cp:,.0f}`")
        sys.exit(0)
    time.sleep(CHECK_INTERVAL)
```

## 实现模式（进阶版 — 多因子评分）

当用户要求"多角度/机灵一点/75%胜率才报"时，必须用多因子评分替代单条件：

```python
import urllib.request, json, time, sys

VWAP = 64235.0; VAL = 63946.0; STOP = 64580.0

def calc_vwap(klines):
    vol_sum = 0; vwap_sum = 0
    for k in klines[-50:]:
        hl2 = (float(k[2]) + float(k[3])) / 2
        vol, vol_sum = float(k[5]), vol_sum + float(k[5])
        vwap_sum += hl2 * vol
    return vwap_sum / vol_sum if vol_sum else VWAP

def calc_ema(klines, period):
    closes = [float(k[4]) for k in klines[-60:]]
    if len(closes) < period: return None
    k = 2 / (period + 1); r = closes[0]
    for v in closes[1:]: r = v * k + r * (1 - k)
    return r

def score(scores):
    """空头评分。每因子固定分，累加≥75即报"""
    total = 0; signals = []
    p, v = scores.get('price',0), scores.get('vwap',VWAP)
    if p < v: total += 30; signals.append(f"破VWAP下`${v-p:,.0f}` [+30]")
    e9=e21=None
    k=scores.get('klines',[]); e9=calc_ema(k,9); e21=calc_ema(k,21)
    if e9 and e21 and e9<e21: total+=20; signals.append(f"EMA死叉 [+20]")
    t=scores.get('taker')
    if t and t<0.8: total+=20; signals.append(f"Taker卖{t:.2f} [+20]")
    h=scores.get('daily_high',0)
    if h and p<h-(h-v)*0.5: total+=15; signals.append(f"日高回撤深 [+15]")
    ls=scores.get('ls_ratio')
    if ls and ls<0.95: total+=15; signals.append(f"大户比{ls:.2f}偏空 [+15]")
    return total, signals

last_side='init'
while True:
    time.sleep(10)
    try:
        p=float(json.loads(urllib.request.urlopen(
            'https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT',timeout=8
        ).read())['price'])
    except: continue
    if time.time()-last_refresh>60:
        cache = refresh_all()  # 聚合 Taker/K线/LS/24h
        last_refresh=time.time()
    short_pts, reasons = score(cache)
    if short_pts >= 75 and short_pts > last_pts:
        print(f"🔴 做空 · {short_pts}/100")
        for r in reasons: print(f"  • {r}")
        print(f"止损{STOP:,.0f} · 止盈{VAL:,.0f}")
        sys.exit(0)
    last_pts = short_pts
```

### 因子评分表（棠溪专属）

| 因子 | 满分 | 数据源 | 说明 |
|------|------|--------|------|
| 价格 vs VWAP | 30 | Binance price + 自算VWAP | 破VWAP=30, 紧贴上方=10 |
| EMA死叉/金叉 | 20 | 自算EMA9/21 | 死叉做空+20, 金叉做多+20 |
| Taker买卖比 | 20 | Binance futures/public | <0.8卖压+20, >1.2买压+20 |
| 日高/低回撤 | 15 | 24h ticker | 从日高回撤>50%=+15 |
| 大户多空比 | 15 | Binance futures/public | <0.95偏空+15, >1.05偏多+15 |
| 近5K趋势 | 10 | 15m K线 | >=3根看跌+10 |

**铁律**：任一方向总分>=75且大于对向时，才推送通知。低于75或双方都低时完全静默。

## 对齐TV指标的评分（2026-06-22 新增）

棠溪的 TV 定制指标 `SVP+ICT+VWAP+EMA+CVD`（2025行 Pine Script）内置了比上述通用评分更精确的评级系统（A空/B空/A多/B多/C等待/X）。守护进程 Python 评分应尽量对齐该指标逻辑：

### 关键对齐点

| 指标系统 | Python实现 |
|---------|-----------|
| trendShortScore 0-10 | 自算EMA9/21 + VWAP位置 + CVD(CVD来自K线delta累积) + 量能。截断0-10 |
| trendLongScore 0-10 | 同上，方向取反 |
| A空判级 | shortScore>=8 且 gap>=2 且 cvdBearConfirm 且 priceBelowS → A空 |
| B空判级 | shortScore>=6 且 gap>=2 → B空 |
| 等级稳定化 | A/B级需持续多根K线确认后才输出，避免毛刺 |
| cvdBearConfirm | cvdSlope<0 且 close <= close[5] (5根前收盘) |
| priceBelowS | 价格 < S VWAP (15m周VWAP) |

### 关键差异（可接受范围）

Python评分以固定因子累加为主（分满100），指标以0-10加权评分+条件链为主。两者评分体系不同但触发条件等价：
- A空 ≈ Python评分>=75 且 价格在VWAP下
- B空 ≈ Python评分>=65 且 价格在VWAP下 或 紧贴VWAP

## 启动命令

```bash
python /path/to/watch_script.py
```

**关键参数：**
- `background=true` — 在 Hermes terminal 后台运行
- **绝对不要加 `notify_on_complete=true`** — 见"避坑"第8条
- 脚本只在**条件满足时 print → sys.exit(0)**，条件未满足时保持**完全静默**

## 节奏控制

- 主循环 10s 间隔（调 Binance 公共价格 API，1200次/分上限，绰绰有余）
- 因子数据每 60s 刷新一次（Taker/K线/LS/24h ticker）
- 单因子级固定分不浮动，避免阈值漂移

## 避坑

1. **无限循环进程不会自然退出** — 条件满足才 print+exit。如永不触发，需手动停止
2. **杀守护用 `terminal("taskkill /PID <pid> /F")`，绝对不用 `process(action='kill')`** — process kill 会产生回溯通知到会话
3. **吃满 stdout 缓冲区** — 不要在循环内 print 心跳行（累积几十 KB 后被截断）。要么零输出，要么每 N 次才 print 一行心跳
4. **API 速率限制** — Binance 免费 API 约 1200 次/分钟，10s 间隔绰绰有余
5. **进程生命周期** — terminal(background) 进程随 Hermes 进程生命周期运行。Hermes 重启后需重新启动
6. **静默初始化** — 如果条件在启动时已满足（如价格已在VWAP附近），首轮先静默赋值 `last_state` 不触发，只有状态变化才报
7. **勿用 cron 替代 daemon** — 用户已明确纠正：实时(10s)用守护，不用5m/1m cron。cron只适合分钟级宽松监控
8. **🔴 守护进程回溯陷阱（2026-06-22 实战教训）**：用 `terminal(background=true)` 启动守护时，如果加了 `notify_on_complete=true`，当进程被 kill/exit 时系统自动发送回溯通知到会话 — 每杀一次旧版本就刷一次噪音。铁律：守护类长期进程**永远** `background=true` **不加** `notify_on_complete=true`。这样即使进程被 kill 或自行退出，也不会污染会话。需检查守护状态时，主动调 `process(action='poll')` 查看。
9. **🔴 指标判 X 不等同于不分析（2026-06-22 实战教训）**：当 SVP 指标判 X（结构冲突）时，不要直接结束为"X禁做不进场"。正确流程：拆解冲突原因 → 看多空优先级 → 给倾向判断 + 双路触发。详见 SKILL.md 系统哲学章节
10. **🔴 用户要方向，不是两个选项（2026-06-22 实战教训）**：当用户主动问"你觉得/什么方向/分析"时，给一个明确判断（偏多/偏空/观望）附理由，不要同时丢两个方向让人选
