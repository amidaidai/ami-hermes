# 后台守护+看门狗架构 v2 — 2026-06-23

## 问题

旧监控系统的问题：
1. **10+个竞争脚本**：btc_alert_watch.py / v3 / vwap_daemon / fast_daemon → 用户不知道用哪个
2. **cron不够实时**：用户两次纠正"太慢了" — cron 最短 1m 粒度，跌 0.5% 可能已错过
3. **不报警**：守护停了但没人知道，用户以为系统在工作
4. **模板矛盾**：多个格式声明互相覆盖
5. **TV MCP指标加载过快**：`chart_set_timeframe` 后只等 2-3s，高周期指标未计算完成

## 解决方案：后台守护 + 看门狗

只有一个后台 daemon 常驻（15s 轮询）+ 一个看门狗 cron（1m 保活）= 零 LLM token。

```
┌─ 后台守护进程(15s) ──────────────────────────┐
│  btc_daemon.py  (terminal background 常驻)     │
│                                                │
│  每15秒: Binance API → 7区间检测               │
│         ↓ 命中关键区                            │
│         推TG告警(自然语言) + 写 signal.json     │
│         更新心跳文件 + 状态持久化               │
│                                                │
│  每60秒: 检查 signal → pending 时              │
│         直连TV MCP(subprocess stdio)            │
│         → 3周期(15m/1h/4h) VWAP/EMA/CVD/DMI    │
│         → 完整分析卡 + 截图 → 推TG:386          │
│         标记 signal completed                   │
│  零token                                        │
└────────────────────────────────────────────────┘

┌─ 看门狗(1m cron no_agent) ───────────────────┐
│  btc_watchdog.py                              │
│  → 读心跳文件                                  │
│  → 心跳 < 120s → 静默退出（零token）           │
│  → 心跳过期/damaged → taskkill + restart       │
│  零token                                       │
└────────────────────────────────────────────────┘
```

## 关键实现模式

### MCP子进程直连
no_agent 脚本通过 `mcp.client.stdio` 自行启动 MCP 服务器子进程来调用工具：

```python
import sys
from pathlib import Path
hermes_venv = Path("~/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages").expanduser()
sys.path.insert(0, str(hermes_venv))
from mcp.client.stdio import stdio_client, StdioServerParameters

async def get_tv_data():
    server_params = StdioServerParameters(command="node", args=["D:/.../server.js"])
    async with stdio_client(server_params) as (read, write):
        from mcp import ClientSession
        async with ClientSession(read, write) as session:
            await session.initialize()
            # ... 后续 tool 调用
```

### TV MCP 加载延迟处理
`chart_set_timeframe` 后指标需要时间计算。务必用以下模式：

```python
await call_tool(session, "chart_set_timeframe", {"timeframe": tf})
wait = 5 if tf == "15" else (8 if tf == "60" else 12)  # 4h = 12s
await asyncio.sleep(wait)

studies_text = ""
for retry in range(3):
    studies_text = parse_text(await call_tool(session, "data_get_study_values", {}))
    if studies_text and ("S VWAP" in studies_text or "VWAP" in studies_text):
        break
    log(f"TF {tf} not ready, retry {retry+1}...")
    await asyncio.sleep(3)
```

### 推送（自然语言 vs 分析卡格式）
- **快速价格告警**：自然语言，不要编号。用户说"看不懂"旧格式。
  ```
  ↓ BTC 62460，跌到大底区(62172-62472)
  62,272是周级别大底，守住做多64K+，跌破看61K
  15分走跌、量正常
  ```
- **完整分析卡**：保留 ↑↓○× 方向 + 关键位 + 操作建议（含 MEDIA 截图）

### 信号文件协同
```json
{
  "status": "pending",
  "zone": "大底",
  "price": 62460.0,
  "triggered_at": "2026-06-23T18:15:20+08:00"
}
```
守护写 `status: pending` → 深度分析读取 → 分析成功后改 `status: completed`。

## 文件清单

| 文件 | 用途 |
|------|------|
| `scripts/monitor/btc_daemon.py` | 后台守护进程（15s 轮询 + TV MCP 分析） |
| `scripts/monitor/btc_card_gen.py` | TV MCP 深度分析（可被 daemon subprocess 调用） |
| `scripts/monitor/btc_watchdog.py` | 看门狗 cron（1m 保活） |
| `scripts/_archive/` | 旧脚本归档（10 个 BTC 脚本） |
| `data/btc_signal.json` | 信号协同文件 |
| `data/btc_latest_card.md` | 最新分析卡缓存 |
| `data/.btc_daemon_heartbeat.json` | 守护心跳（15s 更新，看门狗据此判断存活） |
| `data/.btc_daemon_state.json` | 状态持久化（已触发区间、告警计数） |
| `data/.btc_daemon.pid` | PID 文件 |
