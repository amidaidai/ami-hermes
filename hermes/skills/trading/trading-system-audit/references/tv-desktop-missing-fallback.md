# TV Desktop 缺失时的 Cron Agent 回退模式

## 症状

Cron agent (TV 信号监控) 数据采集脚本执行失败，exit code 1。错误信息含乱码 `TV淇″彿鐩戞帶寮傚父(rc=1)`，解码后 = `TV信号监控异常(rc=1)`。

## 根因

TradingView Desktop **未安装**。MCP tradingview server 不可用（连续连接失败），CDP 调试端口（9222）无进程监听。

## 与 Monitor 进程的分离

```
cron agent (需要 TV Desktop MCP/CDP)         monitor (行情守望.py, 独立运行)
       │                                              │
       │ 依赖 TV Desktop 运行                         │ HTTP/API 数据源
       │ 读 decision_table 等 TV 特有数据              │ 读 exchange API、金十等
       │ MCP 协议通信                                │ 零 token，常驻进程
       ▼                                              ▼
   TV Desktop 未安装 → 卡死                        正常运行 ✅
```

**关键洞察**：monitor 进程（行情守望.py）不依赖 TV Desktop，它通过 HTTP/API 拉取价格/kline/关键位数据。因此即使 TV Desktop 缺失，监控系统仍可运行。

## 诊断步骤（按顺序执行）

1. **Check MCP server health** — `mcp_tradingview_tv_health_check()` → 预期失败 `"CDP connection failed"`
2. **Try to launch TV Desktop** — `mcp_tradingview_tv_launch(kill_existing=true)` → 预期失败 `"TradingView not found on win32"`
3. **Search filesystem for TV binary** — Windows MSIX path `C:\Users\<user>\AppData\Local\TradingView\TradingView.exe`; also check Program Files via `find /c/Program\ Files\*/ -name "TradingView.exe"` → 未找到 = TV Desktop 未安装

## 回退数据源

当 TV Desktop 缺失时，从以下文件获取最近等级：

### 1. monitor_state.json — `last_tv_grade`

```python
state = json.load(open("data/monitor_state.json"))
tv_grade = state.get("last_tv_grade", "未知")
tv_time = state.get("last_tv_time", "")
```

字段说明：`last_tv_grade` = monitor 最近一次从 TV 读取到的等级（字符串）；`last_tv_time` = 对应时间戳（ISO 格式 +08:00）。
注意：monitor_state.json 可能很大（300+ 行），直接 json.load 即可。

### 2. tv_dmi_cache.json — 最后的完整快照

```python
cache = json.load(open("data/tv_dmi_cache.json"))
# 老格式: cache["tv_data"]["grade"]
# 新格式: cache["grade"]
# 带错误: cache["last_good_data"]["decision_table"]["grade"]
grade = cache.get("grade") or cache.get("tv_data", {}).get("grade")
if not grade and "last_good_data" in cache:
    grade = cache["last_good_data"]["decision_table"]["grade"]
```

### 3. tv_signal_state.json — 最近推送记录

```python
sig = json.load(open("data/tv_signal_state.json"))
last_grade = sig.get("last_push_grade", "")
```

## 推送等级判定（走回退路径时）

| 回退等级 | 操作 |
|----------|------|
| A多/A空 | **不推** — TV 数据已过期，信号不可信。标记 `cron_error: TV Desktop 未安装`，记录到 tv_dmi_cache.json |
| B多/B空 | **不推** — 同上 |
| C等待/C反/X | **静默** — 符合常规规则 |
| 未知（无缓存） | **静默** — 等下一次 cron 或人工修复 |

**铁律**：回退路径永远不触发 A/B 级推送。缺少 TV 实时数据 = 信号不可信。宁可漏报不可误报。

## 更新 tv_dmi_cache.json（每次 cron 执行后必须写入）

格式：
```json
{
  "timestamp": "<ISO UTC>",
  "cron_run": "<ISO UTC>",
  "status": "error",
  "error": "TradingView Desktop not installed — MCP/CDP unreachable",
  "monitor_status": "running (PID N, heartbeat HH:MM)",
  "last_monitor_grade": "C等待",
  "last_monitor_grade_time": "2026-06-21T21:02:03+08:00",
  "last_good_data": { }
}
```

## 向用户报告结构

- 问题：TV Desktop 未安装
- 影响：无法使用 TV MCP 工具 → 无法读取 DMI 决策表
- monitor 状态：独立运行中（PID + 最近心跳）
- 当前等级（从 fallback 获取）
- 推送决定及理由
- 建议修复：安装 TradingView Desktop 并开启 `--remote-debugging-port=9222`
