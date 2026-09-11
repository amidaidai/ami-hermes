# 推送管线架构与排障

## 完整链路（v6.3.4 更新）

```
行情守望.py (10s poll)
  → get_price() → 价格 (Binance/金十/OANDA/Yahoo)
  → source_snapshot() → 数据质量快照
  → condition_ready() → 检测触发 (near/breach)
  → push_allowed() → 推送闸门
  → push() → Telegram (主站, 3次重试) + Discord (副站, 单次)
```

## push() 双平台（v6.3.4）

```python
def push(msg):
    # Telegram: 3次重试，2s间隔
    for attempt in range(3):
        subprocess.run([sys.executable, "-m", "hermes_cli.main", "send",
                        "-t", "telegram:-1003733144325:416", "-q", msg], timeout=15)
    # Discord: 单次尝试，失败不阻塞
    try:
        subprocess.run([sys.executable, "-m", "hermes_cli.main", "send",
                        "-t", "discord:1474072925199143167", "-q", msg], timeout=15)
    except: pass
```

- Telegram target: `telegram:-1003733144325:416`（阿弥黛黛警报话题 416）
- Discord target: `discord:1474072925199143167`（安禾 bot · 频道）

## 触发条件分流 (condition_ready)

| condition 类型 | breach 阈值 | reason 文本 |
|---|---|---|
| near_or_breach | d < BREACH_PCT (0.1%) | "价格触发关键位" (含"触发") |
| near_or_breach | d < NEAR_PCT (0.3%) | "接近计划位" |
| breach | d < BREACH_PCT | "触发关键位" |
| retest/sweep_reclaim/order_block/breaker_block/FVG/bos | d < NEAR_PCT | 各自描述 |
| choch | d < BREACH_PCT | "性质转变确认触发" |
| close_confirm/combo | 组合条件 | 收盘确认/组合触发 |

## push_allowed 闸门逻辑（v6.3.4 更新）

### warning 层级
两套条件，满足其一即推送：
- **条件A**：`high_priority` AND (`breached_like` OR `score>=70`) AND `data_q∈{A,B}`
- **条件B**：`high_priority` AND `breached_like` AND `score>=60` AND (`data_q≠C` OR `xau_single_ok`)

### invalidated 层级
两套条件：
- `high_priority` AND `score>=60`
- `score>=MIN_WARNING_LEVEL_SCORE` — 非 high_priority 但位信够也推

> v7.4（2026-06-19）：`MIN_WARNING_LEVEL_SCORE` 现为 **65**（曾为 70）。warning medium / info 分支原硬编码 `>=68` 已全部改为引用此常量，消除 65/68 死区。门槛只认这一个常量，禁写裸数字。详见 `monitor-card-format-v74.md`。

### expired 层级（v6.3.4 新增推送）
- `high_priority` 的过期事件可推
- 非 high_priority 仍拒收

### info 层级
永远拒收（"严格模式不推送接近/过期提醒"）

## v6.3.2 前致命 bug

`condition_ready("near_or_breach")` 无论 breach 还是 near 都返回 "接近计划位"。
→ `breached_like` 检查 `"触发" in reason` → 永远 False
→ 全部 warning/invalidated 事件被拒收
→ 89 条事件 push_sent=0

修复：按 `d < BREACH_PCT` 返回 "价格触发关键位"（含"触发"），near 返回 "接近计划位"。

## notified 字段陷阱

修复前三个 event 构造点都写死 `notified: True`，掩盖推送失败。
修复后 `notified: pushed`，如实反映 push() 返回值。
排查时优先看 `push_sent` 而非 `notified`。

## 已知限制

- `high_priority` 只认 priority=high → medium 优先级位即使 breach 也不推送 warning
- `info` 永远不推送（严格模式设计如此）
- 监控日志只写触发/降噪事件，正常运行无日志是正常的（非 bug）
- 监控死亡不会自愈 → 依赖 `信号巡检.py` cron 告警
- Discord 推送失败不影响 Telegram（try/except 隔离）

## 排查命令

```bash
# 查看推送历史
python -c "import json; d=json.loads(open('data/monitor_events.json')); print(sum(1 for e in d if e.get('push_sent')), '/', len(d))"

# 查看降噪原因
python -c "import json; d=json.loads(open('data/monitor_state.json')); [print(n['tier'], n['symbol'], n['reason']) for n in d.get('noise_history', [])[-5:]]"

# 查看监控心跳
python -c "import json; d=json.loads(open('data/monitor_heartbeat.json')); print(d.get('status'), d.get('pid'), d.get('time'))"

# 测试 Telegram 通道
python -m hermes_cli.main send -t "telegram:-1003733144325:416" -q "测试消息"

# 测试 Discord 通道
python -m hermes_cli.main send -t "discord:1474072925199143167" -q "测试消息"
```
