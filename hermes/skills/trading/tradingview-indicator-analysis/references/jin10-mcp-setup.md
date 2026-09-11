# 金十 MCP 配置记录

## 配置方式

使用 cmd wrapper 脚本（因 API token 含特殊字符，直接通过 shell 传递会截断）。

### 文件

| 文件 | 用途 |
|------|------|
| `hermes/secrets/jin10_token.txt` | API token（纯文本，单行） |
| `hermes/secrets/jin10_mcp.cmd` | Wrapper 脚本，读取 token 并启动 npx |

### Wrapper 脚本

```bat
@echo off
set /p TOKEN=<"%~dp0jin10_token.txt"
npx -y mcp-remote https://mcp.jin10.com/mcp --header "Authorization: Bearer %TOKEN%"
```

### Hermes 配置

```yaml
mcp_servers:
  jin10:
    command: cmd
    args: ['/c', 'D:/Hermes agent/hermes/secrets/jin10_mcp.cmd']
    enabled: true
```

## 可用工具

- `get_quote` — 实时报价
- `get_kline` — K 线数据
- `list_flash` — 快讯分页
- `search_flash` — 快讯搜索（最多 150 条）
- `list_news` — 资讯分页
- `search_news` — 资讯搜索
- `get_news` — 文章详情
- `list_calendar` — 本周财经日历

## 踩坑

- **token 不能直接放命令行**：含特殊字符会被 bash 截断，必须走文件读取
- **npx mcp-remote** 需要 Node.js 环境
- **首次连接可能需要 2-3 秒初始化**
