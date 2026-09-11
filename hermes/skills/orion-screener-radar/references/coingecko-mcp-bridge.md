# CoinGecko MCP Bridge — stdio ↔ Streamable HTTP 代理

将 CoinGecko 的远程 Streamable HTTP MCP 转为 Hermes 可用的 stdio 协议。
不必须——FinanceKit MCP 已提供相同数据。

## 用法

```bash
python scripts/coingecko_mcp_bridge.py
```

## 工作原理

1. 侦听 stdin 上的 JSON-RPC 请求
2. 转发到 `https://mcp.api.coingecko.com/mcp`（keyless，Accept 头含 `text/event-stream`）
3. 返回响应到 stdout

## 限制

- Streamable HTTP 需要 Session 管理，bridge 简化了单次请求-响应
- `execute` 工具（JS代码调 CG API）在 sandbox 执行，Hermes 场景下不如 REST 直接
- 推荐路径：no_agent 脚本用 REST API，agent 分析用 FinanceKit MCP
