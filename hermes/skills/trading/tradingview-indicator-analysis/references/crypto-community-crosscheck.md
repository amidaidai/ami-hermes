# Crypto Community + Market Cross-Check Notes

Use this reference when the user asks for BTC/ETH/crypto advice with community context, sentiment, or multi-channel联网验证.

## Source Roles

- Binance spot/futures: primary executable price, 15m/1h/4h klines, funding, open interest, long/short ratios, taker buy/sell.
- FinanceKit / CoinGecko: secondary spot price and market-wide context such as 1h/24h/7d change, volume, trending coins.
- TradingView: chart structure, indicators, screenshots, and community/news snippets when accessible.
- Jin10: Chinese flash/news catalyst source. For crypto, use it for 快讯 and macro/regulatory/news context, not price verification.
- Web search / CoinDesk / Cointelegraph / TradingView News / Reddit/X snippets: community sentiment and narrative discovery. Treat snippets as secondary unless original article/post is fetched.

## BTC Price Cross-Check

Jin10 quote codes do not include BTC/BTCUSD. Do not attempt Jin10 quote as a BTC price leg.

For BTC price, use:
1. Binance MCP or Binance public API as executable venue price.
2. FinanceKit crypto_price / CoinGecko as independent reference.
3. TradingView chart/quote if the TradingView MCP is available.

If only two price sources are available, mark the gap or say it is two-source validated; do not invent a third.

## Derivatives Probe

For Binance USDT futures, useful public endpoints:

```bash
curl -sS 'https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT'
curl -sS 'https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT'
curl -sS 'https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=5m&limit=5'
curl -sS 'https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=5m&limit=5'
```

Interpretation pattern:
- Funding slightly negative + long/short account ratio still above 1: crowd is long but perp pricing is soft; downside pressure can continue.
- Taker buy/sell below 1 on recent 5m windows: active sell pressure dominates.
- Taker buy/sell flipping back above 1 while price reclaims VWAP: short squeeze / failed breakdown risk.

## Community Sentiment Pattern

- Bearish social chatter at multi-week highs can be contrarian bullish, but only after price reclaims a structure level. It is not a standalone long signal.
- CoinDesk/Cointelegraph narratives such as ETF flows, profit-taking, geopolitical waits, regulatory catalysts, or accumulation bands should be mapped to immediate structure: support/resistance and invalidation.
- Trending coin lists help identify attention rotation. If BTC is trending below alt narratives like HYPE, treat it as attention dilution for BTC unless BTC structure confirms strength.

## Monitor Level Refresh After Analysis

After a new analysis, overwrite `data/monitor_levels.json` with actionable semantic levels, not stale labels only. Prefer structured v2 records so alerts can say what to do and when the level is invalid:

```json
{
  "symbol": "BTCUSDT",
  "analysis_cycle": "4h 偏多回撤 · 1h 转弱 · 15m 扫低反抽 · 5m 等确认",
  "price_at_analysis": 66110.0,
  "levels": [
    {
      "name": "R1_retest",
      "level": 66166.0,
      "side": "resistance",
      "type": "retest_short",
      "action": "反抽失败提醒，观察5m上影和Taker转卖",
      "priority": "high",
      "expires": "60m",
      "invalid_if": "5m close above 66275"
    },
    {
      "name": "S1_sweep_low",
      "level": 65928.0,
      "side": "support",
      "type": "liquidity_sweep_low",
      "action": "跌破未收回则二段下探，快速收回则扫低回收模型",
      "priority": "high",
      "expires": "90m",
      "invalid_if": "5m reclaim above 66166"
    }
  ]
}
```

Verification step: after writing the file, import `scripts/smart_monitor.py` and run its normalizer against `data/monitor_levels.json`; report the count and first/last names, e.g. `monitor_schema_ok 8 R1_retest S3_swing_vwap`. Do not claim the monitor is updated until the schema actually parses.

Do not leave only distant levels after the monitor auto-deletes breached VWAP/DO levels; otherwise alerts become too sparse for intraday execution.

## Output Guidance

For the user's trading card style:
- Keep the recommendation direct: e.g. `先不追空，等反抽空`.
- Use community/news as context inside 环境 and 博弈, not as a separate essay.
- Always tie sentiment to an executable condition: reclaim, rejection, sweep, or invalidation.
