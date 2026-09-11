---
name: tv-chart-layout-manager
description: "TradingView 图表布局管理 — 多品种(386 BTC/385 XAU/SPX)多周期(15m/1h/4h/D)标签管理、布局保存/恢复、Pine指标加载/切换、截图批量采集。基于 TV MCP 工具"
version: 1.0.0
author: 安禾
tags: [tradingview, layout, chart-management, tabs, BTC, XAU, SPX, TV-MCP]
---

# TV 图表布局管理 — Chart Layout Manager

管理 TradingView 的多品种多周期图表布局，快速切换品种和分析视图。

## 棠溪标准布局

### 品种→TV代码 映射
| 品种 | TV代码 | 路由 | 快捷键 |
|------|--------|------|--------|
| BTCUSDT | `BINANCE:BTCUSDT.P` | Telegram 386 | Tab 0 |
| XAUUSD | `FX:XAUUSD` 或 `OANDA:XAUUSD` | Telegram 385 | Tab 1 |
| 美元指数 | `TVC:DXY` | 参考 | Tab 2 |
| S&P 500 | `SP:SPX` 或 `TVC:SPX` | 参考 | Tab 3 |

### 标准周期链（2026-07-08 用户明确固化 · 2026-07-08 末次纠正补回1D）
```
BTC: 1D → 4h → 1h → 15m → 5m   （主周期截图=15m）
XAU: 1D → 4h → 1h → 15m → 5m   （主周期截图=5m）
```
**棠溪周期一致性验证统一五周期 = 1D/4h/1h/15m/5m（2026-07-08 末次纠正：原四周期规则漏 1D，已补回）。** 相邻反向即冲突→否决交易：判定 1D≠4h 或 4h≠1h 或 1h≠15m 或 15m≠5m（四组相邻任一反向即否决）。周期字符串：TV 用 "1D"（也接受 "D"），Binance REST 用 "1d"。

### 扁平 CLI 调用（实测可用 · 取代 MCP 函数式调用）
TV MCP 在 `tools/tradingview-mcp` 下提供扁平 CLI（`src/cli/index.js`），层级为平铺命令，不是 `tv chart state`，而是：
```bash
cd "D:/Hermes agent/tools/tradingview-mcp"
node src/cli/index.js state                  # 当前 symbol/resolution/studies（含 SVP+ICT+VWAP+CVD 是否加载）
node src/cli/index.js symbol OANDA:XAUUSD   # 切品种
node src/cli/index.js timeframe 5           # 切周期（"15"/"60"/"240"/"5"）
node src/cli/index.js screenshot -o btc_15m_main   # 截图存 tools/tradingview-mcp/screenshots/
```
注意：CLI 命令名是 `state` / `symbol` / `timeframe` / `screenshot`（无 `chart` 前缀），否则报 `Unknown command: chart`。多周期方向一致性真路径实现（独立会话 + 等加载 + 正确解析 OHLCV JSON）见 `references/tv-mcp-multitimeframe-direction.md`。

## TV MCP 布局操作

### 创建新标签页
```bash
# 1. 切换到 BTC 15m 执行图
TV: tab_new()
TV: chart_set_symbol("BINANCE:BTCUSDT.P")
TV: chart_set_timeframe("15")
# 加载棠溪 Pine 指标
TV: pine_open("tangxi-multi-factor-dashboard")  # 或指标名
TV: pine_compile()

# 2. 新标签页 → BTC 4h 方向图
TV: tab_new()
TV: chart_set_symbol("BINANCE:BTCUSDT.P")
TV: chart_set_timeframe("240")
# 加载 DMI 指标
TV: pine_open("dmi-trend-dashboard")
TV: pine_compile()

# 3. 新标签页 → XAU 5m 执行图
TV: tab_new()
TV: chart_set_symbol("OANDA:XAUUSD")
TV: chart_set_timeframe("5")
# 加载黄金专用指标
```

### 标签页管理
```python
# 列出所有标签页
tabs = tab_list()
# 输出: [Tab 0: BTC 15m, Tab 1: BTC 4h, Tab 2: XAU 5m]

# 切换到指定索引
tab_switch(index=1)  # 切到 BTC 4h

# 关闭标签
tab_close()
```

### 布局保存/恢复
```python
# 保存当前布局
layout_list()  # 列出已有布局
layout_switch(name="棠溪-BTC-XAU")  # 切换布局
```

### 批量截图
```bash
# 全品种全周期截图
TV: tab_switch(0)  # BTC 15m
TV: chart_set_timeframe("15")
TV: capture_screenshot(region="full", filename="btc-15m")
TV: chart_set_timeframe("240")
TV: capture_screenshot(region="full", filename="btc-4h")

TV: tab_switch(1)  # BTC 4h
TV: chart_set_timeframe("5")
TV: capture_screenshot(region="full", filename="xau-5m")
TV: chart_set_timeframe("240")
TV: capture_screenshot(region="full", filename="xau-4h")
```

## Pine 指标加载清单

| 指标 | 品种 | 周期 | 说明 |
|------|------|------|------|
| 棠溪多因子仪表盘 | BTC | 15m/1h | VWAP/EMA/CVD/关键位 |
| DMI 趋势仪表盘 | BTC/XAU | 4h/1h | ADX/趋势分/ABCD级 |
| 成交量分布 | BTC/XAU | 15m/5m | POC/VAH/VAL |
| 黄金专用 | XAU | 5m | M_VWAP/关联套利 |

> **切品种后必须重编译 Pine 指标** — `pine_compile()` 清理脏数据

## 常见问题
- 切品种后Pine指标数据可能残留旧品种 → **必须重编译**
- 多标签页模式下截图只截当前活跃页
- `batch_run` 可以跨品种一次截图，但无法设置不同周期
- **Windows TradingView 更新双路径陷阱（2026-07-03 实测）**：官方 `TradingView.msix` 通过 `Add-AppxPackage` 更新的是 `C:\Program Files\WindowsApps\TradingView.Desktop_<version>...`；但 TV MCP `tv_launch` 优先启动 `C:\Users\Administrator\AppData\Local\TradingView\TradingView.exe`。因此更新后必须同步本地 MCP 启动目录：先备份 `C:\Users\Administrator\AppData\Local\TradingView`，再把最新 WindowsApps 包目录内容复制过去，然后 `tv_launch(kill_existing=true)`，用 `curl http://127.0.0.1:9222/json/version` 确认 `TVDesktop/<new version>`，再 `tv_health_check` 确认 CDP。完整 runbook 见 `references/windows-tradingview-update-mcp-path.md`。
- **Hermes Desktop 环境变量陷阱（2026-07-05 实测）**：Hermes/Node 环境可能带 `ELECTRON_RUN_AS_NODE=1`；若 TV MCP `spawn(TradingView.exe, [--remote-debugging-port=9222])` 继承该变量，TradingView 会以 Node 模式启动并报 `bad option: --remote-debugging-port=9222` 后退出，表现为 `CDP connection failed`。修复：在 `tools/tradingview-mcp/src/core/health.js` 的 `launch()` 中构造 `childEnv={...process.env}` 并 `delete childEnv.ELECTRON_RUN_AS_NODE`、`delete childEnv.ELECTRON_NO_ATTACH_CONSOLE`，再把 `env: childEnv` 传给 `spawn`。验证：`node .../src/cli/index.js launch` 返回 `cdp_url`，`status` 返回 `cdp_connected:true`。
- Windows 下 TV 桌面版启动需要 CDP 端口 9222
- **`symbol set` 在 CDP 下切品种极不稳定（2026-07-08 实测）** — CLI `node .../index.js symbol set "BINANCE:BTCUSDT.P"` 反复调用会卡死在诡异品种 `CBOE_DLY:SET`（图表 async 加载未完成/指标未就绪），且 SVP **主指标**（POC/VAH/VAL/决策表）绑定图表当前品种，`values --symbol BTC` 直读只对 HALDRO 副指标生效、读不到 SVP 主驾驶。需要按品种独立采集 SVP 数据时，**不要切全局图表**，改用 MCP stdio 路径：`fetch_tv_mcp.set_symbol` + `get_study_values`/`get_pine_lines` 独立切目标品种读，读完 `set_symbol` 回切原图表（保住看盘）。详细 recipe 见 `tangxi-system-audit` 的 `references/btc-key-level-sync-mcp-stdio-recipe.md`。
- **`data_get_ohlcv(summary=True)` 返回 JSON 不是纯文本（2026-07-08 高价值坑）** — TV MCP 的 OHLCV summary 是 JSON 字符串（含 `change_pct`、`open/close/high/low`、`last_5_bars` 字段），并非形如 `change: -2.09%` 的纯文本。旧方向解析用正则匹配纯文本会**恒返回 0**，表现为「TV多周期方向全空」。正确做法：先 `json.loads(parse_result(raw))` 再读 `obj['change_pct']`（去百分号转 float，>0.05 多 / <-0.05 空 / 否则中性）。完整实现与五周期(1D/4h/1h/15m/5m)独立会话模板见 `references/tv-mcp-multitimeframe-direction.md`。

## TV 读取前置防御（2026-08-28 实测 · 每次读数据前必做）

以下坑在真实会话里都踩过，任一不防御都会导致**拿错品种的数据糊弄用户**。

1. **工具调用用 `tool_call(...)` 包装** — TV MCP 工具是 deferred 工具，直接写 `mcp__tradingview__xxx()` 时会报 `not exist`/`ClosedResourceError`。正确：`tool_call(name='mcp__tradingview__chart_get_state', arguments={})`。若 MCP 桥刚重连，先 `tv_health_check` 确认 `api_available:true` 再继续；报 `ClosedResourceError` 时用 `tv_launch(kill_existing=true)` 重启。

2. **每读一层前先 `chart_get_state` 校验 symbol** — 切品种/切周期后，TV 引擎可能**静默漂移**：`health_check` 读到 A 品种，`chart_get_state` 读到 B 品种（实测 XAUUSD↔BTCUSDT 漂移）。**必须**确认返回的 `symbol == 目标品种` 才读 study_values/table/lines；不一致立即重切 + 重验，绝不凑合。

3. **`study_values` 大数值被 TV 缩写** — S VWAP/POC/VAH/VAL 显示为 `4.6K`/`1.1M`，不是精确价。**精确关键位必须读 `data_get_pine_labels`/`data_get_pine_lines`**（那是 float 精确值），`study_values` 只用于判断行动格 coding 字段。

4. **现价一律用 `quote_get` 仲裁** — 多周期 `data_get_ohlcv(summary)` 的 close 会互相打架（实测 15m close=4616.96 vs 5m close=4587.22 差 30 点，同时间戳）。**以 `quote_get`（或 Binance ticker）为唯一真现价**，不信任 OHLCV close 直接下结论。

5. **1h/高周期 SVP 可能渲染不完整** — 实测 1h 主指标有时只回 Volume+Aggregated 无 SVP table，重读后 SVP 出现但数值异常（VWAP=4.41K 与 4h/15m 的 4.6K 不符，疑残留）。**1h 无可靠 SVP 时标注"继承 4h 背景"，不硬用异常值**，宁可注明也不编造。

6. **黄金/加密的副指标差异** — 黄金 `Volume Aggregated` 副指标 `HALDRO Valid Code=0` 罢工（非加密无 OI 聚合）；加密才是 5 所+4 所 OI 聚合（`Composite`/`State Pack=冲突` 是方向票异议来源）。黄金只读主指标，加密必读副指标做方向票。
