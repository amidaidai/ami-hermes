# MCP 连接故障排查

> 2026-06-18 · Binance MCP websockets 冲突 + Finance MCP 命令格式修复实战记录

## 故障现象

`config.yaml` 中 `mcp_servers.<name>.enabled: true`，但 Hermes agent 工具列表中**不出现**对应 `mcp_<name>_*` 工具。

Hermes 不会为崩溃的 MCP 进程报错——它只是不注册工具。

## 排查步骤（按顺序）

### ① 验证 config 配置

```bash
# 确认 enabled: true，command/args 正确
cat ~/.hermes/config.yaml | grep -A 8 "mcp_servers"
```

### ② 手动启动 server 测崩溃

```bash
# 对于 Python MCP:
timeout 8 python <server.py>        # 脚本路径
timeout 8 python -m <module.server>  # 模块方式

# 对于 Node MCP:
timeout 8 node <server.js>
```

### ③ 读启动输出

- 如果看到 `FastMCP 3.x.x · Starting MCP server ... with transport 'stdio'` → **进程正常**
- 如果看到 `ImportError / ModuleNotFoundError / PermissionError` → **依赖或权限问题**
- 如果超时或静默退出 → **端口冲突或进程已挂**

### ④ 修复后重启 Hermes

修复依赖后 Hermes 不会自动重新加载 MCP。需要重启 Hermes 让新进程生效。

## 已知冲突模式

### Pattern A: websockets 版本冲突

**症状**：
```
ImportError: cannot import name 'WebSocketClientProtocol' from 'websockets'
```

**根因**：Hermes 锁定 `websockets==15.0.1`，但某个 MCP 依赖的库（如 `python-binance`）需要旧版。

**修复**：去掉引发冲突的外部库依赖，改用 Python 标准库（`urllib.request` + HMAC 签名）实现纯 REST 客户端。

### Pattern B: Windows cmd 分号解析

**症状**：MCP 配置用 `args: ["-c", "import x; import y; run()"]` 启动，进程瞬间退出。

**根因**：Windows cmd 对 `python -c` 的多分号字符串解析不可靠。

**修复**：改为 `args: ["-m", "module.server"]` 标准模块启动方式。

### Pattern C: 依赖缺失

**症状**：`ModuleNotFoundError: No module named 'xxx'`

**修复**：`pip install <module>`。如果包名不确定，去 PyPI 搜索确认。

## 验证命令

```bash
# 快速验证所有 MCP server 是否能启动
for srv in binance finance financekit jin10 tradingview; do
  echo "=== $srv ==="
  # 根据实际启动方式调整
done

# 重启后验证
hermes mcp list  # 列出已连接的 MCP
```
