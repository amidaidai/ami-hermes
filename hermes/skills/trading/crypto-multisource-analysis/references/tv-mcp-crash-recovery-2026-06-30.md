# TV MCP Crash Recovery (2026-06-30 实战)

## 症状

所有 tool_call 到 `mcp_tradingview_*` 工具都返回 `ClosedResourceError` 或 `MCP server 'tradingview' is unreachable`。

## 根因

Hermes 的 MCP server 进程（Node.js `tools/tradingview-mcp/src/server.js`）崩溃或被 OOM kill。Agent session 内的 MCP 通道断开。这不是 TV Desktop 或 CDP 端口的问题——即使 `netstat` 显示 port 9222 在监听，MCP 通道也断了。

## 恢复流程

```
phase 1: 确认 MCP 状态
  tool_call → ClosedResourceError 或 unreachable → 确认 MCP server 进程不在
  tasklist 找 node.exe → 无 tradingview-mcp 进程

phase 2: 不要连续重试（~60s 冷却）
  MCP 有 auto-retry 机制，unreachable 后约 50-60s 自动恢复
  连续重试会重置冷却计时器，延长恢复时间
  ✓ 等 60s → 再调 health_check（此时应能连上但报 CDP 失败）
  ✗ 不要每秒重试

phase 3: 杀 TV + 重开（如果 TV 不在运行或 CDP 连不上）
  taskkill /F /IM TradingView.exe
  sleep 3
  tv_launch(kill_existing=true)

phase 4: 验证
  tv_health_check → cdp_connected: true, api_available: true
  chart_get_state → 确认 symbol 和 resolution
  开始正常分析
```

## 关键时间线（2026-06-30 实盘）

| 时间 | 事件 |
|:---|:---|
| T+0s | 首次 `tv_health_check` → ClosedResourceError |
| T+0s | 尝试 `tv_launch(kill_existing=true)` → 同样 ClosedResourceError |
| T+0s | tasklist 确认 TV.exe 在运行但 node MCP 进程已死 |
| T+10s | taskkill TV + 手动启动 TV → CDP 不响应（TV 未完全启动） |
| T+25s | 再次 `tv_health_check` → MCP server unreachable（auto-retry 中） |
| T+85s | 60s 冷却后 `tv_health_check` → 成功（CDP failed） |
| T+90s | `tv_launch` → 成功启动 TV + CDP |
| T+95s | `health_check` → ✅ 完全可用 |
| T+100s | 开始分析 |

## 教训

1. **MCP server 崩溃 ≠ TV Desktop 崩溃**。两个进程独立。MCP server 崩溃时 Tool call 全部返回 ClosedResourceError，但 TV 窗口可能还在。
2. **等 auto-retry**。不要连续重试——Hermes 的 MCPClient 有 ~50s 的自动重连间隔，连续调用会刷新冷却。
3. **TV MCP 是必须的**。用户明确「TVmcp 是必须的」。分析前先 check health，不通则按上述流程恢复，不能跳过 TV 步骤。
4. **health_check 先于 launch**。health_check 恢复连通后（即使返回 CDP fail）才能调 tv_launch。tv_launch 需要 MCP 通道已恢复。
5. **Binance MCP 随 TV MCP 一起恢复**。当 TV MCP server 崩溃时，Binance MCP 往往也一起不可用。恢复流程：先修 TV MCP（tv_launch），Binance MCP 会跟着 auto-recovery 自动恢复，不需要单独修复。
