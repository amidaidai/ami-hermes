---
name: binance-trading
description: Binance 加密货币交易技能 — 查余额、下单（市价/限价/止损）、设止盈止损、查持仓、查 K 线数据、账户信息、交易对信息。基于 Binance API（已在 Hermes .env 配置 BINANCE_API_KEY 和 BINANCE_SECRET_KEY）。适用现货和 U 本位合约。
category: trading
---

# Binance Trading

> 前提：Hermes .env 已配置 `BINANCE_API_KEY`、`BINANCE_SECRET_KEY`。
> **Binance MCP Server v2.0 是纯 REST 实现，零外部交易库依赖**（无 python-binance/websockets 冲突）。
> MCP 源码在 `D:/Hermes agent/tools/binance-mcp/server.py`。

## 可用操作

### 1. 查询账户信息
**推荐走 MCP**：`get_account_summary`（现货+合约总览）或 `get_balance`（单币种/全量）。
如需写 Python 脚本，使用 `urllib` + HMAC 签名直接调 REST（参考 MCP 源码中的 `_get(url, signed=True)`）。

### 2. 查余额
- MCP: `get_balance(asset='BTC')` 或 `get_account_summary()`
- 脚本: GET `https://api.binance.com/api/v3/account` + 签名

### 3. 查价格
- MCP: `get_price(symbol='BTCUSDT')` / `get_prices(symbols='BTCUSDT,ETHUSDT')`
- MCP: `get_klines(symbol='BTCUSDT', interval='15m', limit=100)`
  - 常用 interval: 1m, 5m, 15m, 1h, 4h, 1d, 1w

### 4. 下单（现货）· 合约持仓
- MCP: `get_futures_positions(symbol='BTCUSDT')` — 查合约持仓
- 下单/止损止盈：目前需写 Python 脚本调 REST API（参考 MCP 源码签名模式）
  - `https://api.binance.com/api/v3/order` (现货)
  - `https://fapi.binance.com/fapi/v1/order` (合约)

### 5. 查未成交订单 / 撤单
- MCP: `get_open_orders(symbol='BTCUSDT')` — 现货+合约
- MCP: `cancel_order(symbol='BTCUSDT', order_id='xxx', market='futures')`

### 6. 多空比 / Taker / 费率 / OI（分析增强）
- `get_long_short_ratio(symbol='BTCUSDT', period='5m')` — 大户多空比 (A级)
- `get_global_long_short(symbol='BTCUSDT')` — 全局多空比 (A级)
- `get_taker_volume(symbol='BTCUSDT')` — Taker买卖量比 (B级·接近CVD)
- `get_funding_rate_history(symbol='BTCUSDT', limit=5)` — 资金费率历史 (A级)
- `get_open_interest_history(symbol='BTCUSDT')` — OI历史 (A级)

## Binance MCP Server（推荐路径）

**优先使用 Binance MCP v2.0**（14 个工具，纯 REST，零外部依赖，无 websockets 冲突）。

### 全量工具（v2.0 · 纯 REST）

| 工具 | 功能 | 数据质量 |
|------|------|---------|
| `get_price` / `get_prices` | 查单个/批量价格 | A级 |
| `get_klines` | K 线数据（1m~1w） | A级 |
| `get_balance` | 现货余额 | A级 |
| `get_account_summary` | 账户总览（现货+合约） | A级 |
| `get_futures_positions` | 合约持仓（含未实现盈亏） | A级 |
| `get_open_orders` | 未成交订单（现货+合约） | A级 |
| `cancel_order` | 撤单（market=spot/futures） | A级 |
| `get_symbol_info` | 交易对精度/过滤规则 | A级 |
| `get_long_short_ratio` | 大户多空账户比 | A级 |
| `get_global_long_short` | 全局多空账户比 | A级 |
| `get_taker_volume` | Taker主动买卖量比 | B级·接近CVD |
| `get_funding_rate_history` | 资金费率历史 | A级 |
| `get_open_interest_history` | OI历史 | A级 |

**MCP 技术细节**：v2.0 纯 `urllib` + HMAC 签名 REST，不再依赖 `python-binance` 包。避免 Hermes 内置 `websockets==15.0.1` 和 `binance` 包旧版 websockets 的版本冲突。MCP 源码在 `D:/Hermes agent/tools/binance-mcp/server.py`。

**排查连接问题**：如果 MCP 工具不出现，检查：
1. `config.yaml` → `mcp_servers.binance.enabled: true`
2. `command` 路径正确（`python` 需在 PATH 中）
3. Hermes 重启后 MCP 才重新加载配置
4. 手动测试：`timeout 5 python tools/binance-mcp/server.py` 应显示 FastMCP banner

## Binance REST API Direct Fallback（当 MCP 不可用时）

如果 Binance MCP server 不可达（unreachable 或 ClosedResourceError），用 `terminal('curl ...')` 直取 REST API 作为降级。以下端点均公开（无需签名），适用于分析和交叉验证：

### 价格与行情
```bash
# 当前价格
curl -s "https://api.binance.com/api/v3/ticker/price?symbol=GASUSDT"
# 24h 统计（含涨跌幅/高开低收/成交量）
curl -s "https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=GASUSDT"
# K 线数据
curl -s "https://fapi.binance.com/fapi/v1/klines?symbol=GASUSDT&interval=15m&limit=10"
```

### 衍生品数据
```bash
# 当前 OI（未平仓量）
curl -s "https://fapi.binance.com/fapi/v1/openInterest?symbol=GASUSDT"
# OI 历史（含 USD 价值）
curl -s "https://fapi.binance.com/futures/data/openInterestHist?symbol=GASUSDT&period=15m&limit=10"
# 资金费率
curl -s "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=GASUSDT"
# 大户多空比（账户数）
curl -s "https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol=GASUSDT&period=15m&limit=5"
# 全局多空比（账户数）
curl -s "https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=GASUSDT&period=15m&limit=5"
# Taker 买卖量比
curl -s "https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=GASUSDT&period=15m&limit=5"
```

### 深度数据
```bash
# Order Book (前20档)
curl -s "https://api.binance.com/api/v3/depth?symbol=GASUSDT&limit=20"
```

### 降级标注
使用 curl 直取时，在分析卡中标注「Binance MCP不可用·curl直取」并注明数据等级（公开REST = A级）。

## Binance网络与节点验收（账户测试前必做）

当 Binance 返回连接超时、TLS失败或连接重置时，**不要先判断API Key失效，也不要只测“直连 vs 当前代理”一次**。先按以下顺序验收：

1. 强制直连测试现货 `/api/v3/ping` 与合约 `/fapi/v1/ping`。
2. 显式使用本地代理测试同一组端点。
3. 用 Google 204 等控制站点确认代理端口本身正常。
4. 若控制站点正常而 Binance 失败，轮换代理策略组中的多个地区节点。
5. 记录每个节点的 HTTP码和延迟；`451`按地域限制处理，TLS失败按节点/上游限制处理。
6. 测试后恢复用户原代理选择；获得授权后再把Binance域名单独固定到已验证节点。
7. 公开Ping均为200后，才调用**签名只读**账户接口验证Key、IP白名单、权限与时间戳；禁止用下单/撤单测试连通性。

关键判读：TLS失败、超时、连接重置均发生在鉴权之前，不能据此判定Key错误；只有收到 Binance JSON业务错误码（如`-2015`、`-1021`）后才进入凭据排查。代理节点级复现方法见 `network-diagnostics` 的 `references/proxy-node-vs-proxy-path.md`（未落地·勿引）。

## 注意事项
- BINANCE_API_KEY/BINANCE_SECRET_KEY 已配置在 Hermes .env 中
- MCP v2.0 自动从 .env 或 config.yaml env 中加载密钥（`_load_env()`）
- 数量精度和价格精度需从 `get_symbol_info` 获取，否则下单会报错
- MCP 重启需 Hermes 重启（配置在启动时加载）
- 如果你在监控脚本中直接调 Binance API，用 `data_gatherer.py` 的 `signed_futures()` 模式（urllib + HMAC，无外部依赖）
- **不再依赖 python-binance 包**：v2.0 消除了与 Hermes websockets==15.0.1 的版本冲突
