# Binance MCP Server 构建与注册

创建于 2026-06-15，扩展于 2026-06-17 (v1.1)。

## 架构

```
Python FastMCP server → python-binance + 裸REST(带签名) → Binance API
         ↓
Hermes MCP (stdio transport)
         ↓
Agent 直接调用 14 个工具
```

## 快速注册命令

```bash
hermes mcp add <name> --command python --args "path/to/server.py"
```

**关键：** `--args` 必须是最后一个选项。不支持一次性注册。

## 服务器文件结构

```
tools/binance-mcp/
├── server.py          # FastMCP 服务器，14 个工具 (v1.0 9个 + v1.1 5个)
└── requirements.txt   # fastmcp, python-binance (仅 v1.0 工具需要)
```

## 依赖安装

v1.0 工具需要：
```bash
pip install fastmcp python-binance
```

v1.1 工具仅用 stdlib (`hmac`, `hashlib`, `urllib.request`)，零额外依赖。

## 工具列表（14 个）

### v1.0 公开基础（9 个）

```python
@mcp.tool()
def get_price(symbol: str) -> str: ...

@mcp.tool()
def get_prices(symbols: str = "") -> str: ...

@mcp.tool()
def get_klines(symbol: str, interval: str = "15m", limit: int = 100) -> str: ...

@mcp.tool()
def get_balance(asset: str = "") -> str: ...

@mcp.tool()
def get_futures_positions(symbol: str = "") -> str: ...

@mcp.tool()
def get_open_orders(symbol: str = "") -> str: ...

@mcp.tool()
def cancel_order(symbol: str, order_id: int, market: str = "spot") -> str: ...

@mcp.tool()
def get_symbol_info(symbol: str) -> str: ...

@mcp.tool()
def get_account_summary() -> str: ...
```

### v1.1 签名认证（5 个 · 需 BINANCE_API_KEY + BINANCE_SECRET_KEY）

```python
@mcp.tool()
def get_long_short_ratio(symbol: str = "BTCUSDT", period: str = "5m", limit: int = 5) -> str:
    """获取大户多空账户比（top trader long/short）。period: 5m/15m/1h/4h/1d
       端点: /futures/data/topLongShortAccountRatio
       返回: [{long, short, ratio, side, timestamp}]"""

@mcp.tool()
def get_global_long_short(symbol: str = "BTCUSDT", period: str = "5m", limit: int = 5) -> str:
    """获取全局多空账户比（all accounts）
       端点: /futures/data/globalLongShortAccountRatio
       返回: [{long, short, ratio, side, timestamp}]"""

@mcp.tool()
def get_taker_volume(symbol: str = "BTCUSDT", period: str = "5m", limit: int = 5) -> str:
    """获取Taker买卖量比（主动吃单方向·接近真实CVD）
       端点: /futures/data/takerlongshortRatio
       返回: [{buy_vol, sell_vol, ratio, direction, timestamp}]
       质量: B级（期货主动成交，优于K线估算C级）"""

@mcp.tool()
def get_funding_rate_history(symbol: str = "BTCUSDT", limit: int = 5) -> str:
    """获取最近N期资金费率历史
       端点: /fapi/v1/fundingRate (签名版)
       返回: [{rate, rate_pct, time}]"""

@mcp.tool()
def get_open_interest_history(symbol: str = "BTCUSDT", period: str = "5m", limit: int = 5) -> str:
    """获取OI历史变化
       端点: /futures/data/openInterestHist
       返回: [{oi, oi_value, timestamp}]"""
```

## 关键发现（2026-06-17）

**端点路径差异**：公开文档中的 `/fapi/v1/globalLongShortAccountRatio` 和 `/fapi/v1/takerlongshortRatio` 返回 404。正确路径是 `/futures/data/*` 系列：

| 需求 | 错误路径 | 正确路径 |
|------|---------|---------|
| 大户多空 | `/fapi/v1/topLongShortAccountRatio` | `/futures/data/topLongShortAccountRatio` |
| 全局多空 | `/fapi/v1/globalLongShortAccountRatio` | `/futures/data/globalLongShortAccountRatio` |
| Taker买卖 | `/fapi/v1/takerlongshortRatio` | `/futures/data/takerlongshortRatio` |
| OI历史 | `/fapi/v1/openInterestHist` | `/futures/data/openInterestHist` |

这些 `/futures/data/*` 端点需要签名认证（X-MBX-APIKEY + timestamp + HMAC-SHA256）。v1.1 工具通过裸 `urllib.request` + 手动签名实现，不依赖 `python-binance` 库。

## 启动后生效

修改 server.py 后，需重启 Hermes session（`/reset`）才能加载新工具。MCP 工具列表在每个 session 启动时注册。

## 注意事项

- v1.0 工具返回用 `json.dumps()` 序列化（FastMCP 要求）
- v1.1 工具同样返回 JSON 字符串
- API Key/Secret 从环境变量 `BINANCE_API_KEY`/`BINANCE_SECRET_KEY` 读取（.env 中配置）
- v1.1 的 `_signed_futures_get()` 每次请求重新生成 HMAC-SHA256 签名
- MCP 的 K 线 limit 上限 500（Binance API 限制）
- 所有返回值用 `json.dumps()` 序列化为字符串
