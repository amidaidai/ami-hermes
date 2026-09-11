# 待接入数据源集成方案

2026-06-28 审计产出。记录每个可加但未接入的第三方数据源的集成方式。

## 优先待接入

### 1. CoinGecko API（免费 · 零配置）

**为什么加**：过滤垃圾币。当前只靠 OI≥$500k 过滤，但有些币 OI 不小却几乎没有现货深度，容易假突破。加上市值排名和现货量可以大幅提高信号质量。

**API**：`https://api.coingecko.com/api/v3/coins/markets`（无需 key）

**接入方式**：在 `orion_screener_radar.py` 的 `deep_verify` 函数中，对 Top 候选币种查 CoinGecko：

```python
import urllib.request, json
url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin,ethereum&order=market_cap_desc"
req = urllib.request.Request(url, headers={"User-Agent": "Hermes/1.0"})
with urllib.request.urlopen(req, timeout=10) as r:
    data = json.loads(r.read())
# data = [{"id":"bitcoin","symbol":"btc","market_cap_rank":1,"total_volume":...}, ...]
```

**关键字段**：`market_cap_rank`（选 rank≤200 的币）、`total_volume`（现货量验证）、`price_change_percentage_24h`（现货涨幅核对）

**过滤规则建议**：
- market_cap_rank ≤ 200 → 大盘/中盘币，直接放行
- market_cap_rank 200-500 → 小盘，需额外确认
- market_cap_rank > 500 或不存在 → 标记为低置信度
- 24h 现货量 < OI 的 10% → 合约主导品种，波动更剧烈

### 2. Fear & Greed API（免费 · 零配置）

**为什么加**：宏观情绪定调。极端恐惧（<20）时异动信号更准（假突破少），极端贪婪（>80）时需警惕回调。

**API**：`https://api.alternative.me/fng/`

**接入方式**：写入 `orion_screener_radar.py` 的 `build_report` 头部添加一行：

```python
# 在 main() 中
import urllib.request, json
try:
    req = urllib.request.Request("https://api.alternative.me/fng/?limit=1")
    with urllib.request.urlopen(req, timeout=5) as r:
        fng = json.loads(r.read())
    fear_greed = f"{fng['data'][0]['value']}/100 - {fng['data'][0]['value_classification']}"
except:
    fear_greed = None
```

### 3. Bybit API

**为什么加**：用户在 Bybit（利安）交易，可验证 OI/费率是否与 Binance 一致，且查自己持仓是否受影响。

**门槛**：需要用户在 Bybit 生成 API Key + Secret，写入 `.env` 为 `BYBIT_API_KEY` / `BYBIT_SECRET_KEY`。

**API**：`https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT`

**接入方式**：类似 Binance REST 模式，Bybit 使用 API Key + 时间戳签名。

---

## 后续待接入

### 4. Coinglass API（付费）

**为什么加**：全交易所爆仓热力图是判断轧空/清算瀑布的黄金标准。当前只能靠 OI+资金费率间接判断。

**价格**：Free tier 有 1 天历史数据，Pro $19.99/月有实时。

**API 示例**：`https://open-api.coinglass.com/api/pro/v1/futures/liquidation_chart?symbol=BTC&exchange=all`

### 5. X/Twitter 实时情绪

**为什么加**：爆拉币往往有叙事驱动（新闻/大V喊单）。当前只能靠 web_search 搜索（延迟 15-60min）。

**方案**：需要 x_search MCP 工具（已装但未启用），或使用独立 Twitter API v2。
