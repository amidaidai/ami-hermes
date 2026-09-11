# 后台守护 v9 模式 (2026-06-22)

## 架构

```
terminal(background=true, notify_on_complete=false)
  └─ python btc_vwap_daemon.py
       ├─ 10s轮询 Binance 免费API (零token)
       ├─ 每60秒刷新动态VWAP (从15m K线自算)
       ├─ 状态持久化 (btc_state.json) — 重启不丢
       ├─ 写入 btc_alerts.jsonl — 可随时 cat 读取
       └─ 5min冷却窗口 — 同一事件不重复推送
```

## 三个关键设计

### 1. 启动方式
```python
terminal(background=true, notify_on_complete=false)
```
- 不加 `notify_on_complete` — 守护是永续进程，退出不需要通知
- 杀进程用 `terminal("taskkill /PID <pid> /F")` 不用 `process(kill)`
- 否则旧进程被杀时发回溯通知到会话

### 2. 状态持久化
```python
STATE_FILE = "~/AppData/Local/hermes/scripts/btc_state.json"
state = load_state()  # 读取上次运行状态
```
存储当前VAL/VWAP上下状态 + 时间戳。重启后续接，不丢失"价在某个位多久了"的计时。

### 3. 日志文件
```python
LOG_FILE = "~/AppData/Local/hermes/data/btc_alerts.jsonl"
log(msg) → writer jsonl
```
每行 `{"t": "2026-06-22T16:12:30+08:00", "msg": "📊 VWAP反抽测试 ..."}`。
`cat btc_alerts.jsonl` 可查看所有历史触发。只追加不清理。

## 冷却机制

```python
block = now.minute // 5  # 每5分钟一个块
state["last_blocks"]["vwap_test"] = block  # 记录
if state["last_blocks"].get("vwap_test") != block:
    # 触发推送
```
同事件同5分钟块内只报一次。防止10s循环刷屏。

## 参考实现

`scripts/btc_vwap_daemon.py` — 完整守护实现。
