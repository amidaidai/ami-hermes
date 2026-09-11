# TV MCP CDP 恢复流程

## 触发条件

任一下列错误信号触发恢复：
- `data_get_study_values` 返回 `"CDP connection failed after 5 attempts: fetch failed"`
- `tv_health_check` 返回 `success: false`
- auto_card 打印 `⚠ TV DMI缓存未采用: 缓存过期 NNNN分钟`

## 标准恢复流程

### 1. 启动 TradingView Desktop

```python
mcp_tradingview_tv_launch()
# 输出: platform, binary, pid, cdp_port=9222, cdp_url=http://localhost:9222
```

TradingView Desktop 安装路径（Windows）：
```
C:\Users\Administrator\AppData\Local\TradingView\TradingView.exe
```

### 2. 等待 Desktop 完全加载

```bash
sleep 8   # Windows 冷启动至少 8 秒（Electron + WebView 双启动）
```

**不要缩短等待时间** — Desktop 启动包含 3 个串行阶段：
1. Electron shell 启动 (~3s)
2. WebView 渲染引擎初始化 (~3s)
3. 图表加载 + 指标初始化 (~2s)

### 3. 验证连接

```python
mcp_tradingview_tv_health_check()
# 成功输出: cdp_connected=true, chart_symbol="BINANCE:BTCUSDT.P", chart_resolution="15"
```

### 4. 切换品种（按需）

```python
# XAU 分析时切换
mcp_tradingview_chart_set_symbol(symbol="OANDA:XAUUSD")
sleep 5   # 等指标重新加载
```

### 5. 数据采集验证

```python
# 至少验一项确认管线正常
mcp_tradingview_data_get_pine_tables(study_filter="SVP")
# 成功输出: 行动格行含"结论|B空"或"结论|C多"等
```

## 恢复后检查清单

- [ ] `cdp_connected: true`
- [ ] `chart_symbol` 匹配预期品种
- [ ] `pine_tables` 含 SVP 行动格（非空 rows）
- [ ] `data_get_study_values` 返回 VWAP/EMA/POC/VAH/VAL
- [ ] `data_get_pine_lines` 返回 ≥5 条水平价位

## Pitfalls

- **只启动 Desktop 不够** — 必须等 WebView 渲染 + 指标初始化，否则读出来的表格是空的或过时的
- **指标未加载完成前 `pine_tables` 返回空 rows** — 再等 3-5 秒重试，不要认为指标没加载
- **Yahoo GC=F 不可用于 XAU K 线** — TV MCP 离线时 XAU 宁可占位 `_xau_klines_pending`，不用期货代理
- **CDP 断连后 MCP 进程仍显示 `enabled`** — Node 进程还在但 CDP tunnel 挂了，`hermes mcp list` 看不出，必须实测 `tv_health_check`

## 架构

```
Claude ←→ MCP Server (stdio, Node) ←→ CDP (localhost:9222) ←→ TradingView Desktop (Electron)
```

断连场景：
- **Desktop 挂掉** → 整个链断裂 → `tv_launch` 重拉
- **CDP port 9822 被占用** → `tv_launch` 会自动 kill 旧进程
- **MCP 进程挂掉** → `hermes mcp` 会自动重启 Node server

最常见的是 Desktop 关闭后用户忘了重开。
