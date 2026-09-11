# Community Research: BTC Real-Time Trading System 2026-06-22

## Sources Consulted
1. SMC/ICT 2026 Medium (30 strategies, real backtest rates)
2. TradingView CVD community scripts (divergence, absorption)
3. Bookmap (CVD iceberg/absorption/orderflow)
4. GitHub (Freqtrade, awesome-systematic-trading)
5. KillZone/Silver Bullet community timing
6. Reddit (CVD divergences, R:R)

## Key Findings Adopted

### CVD Divergence Detection
- **Bearish divergence**: price makes higher high, CVD makes lower high → selling pressure building under rising price
- **Bullish divergence**: price makes lower low, CVD makes higher low → buying accumulation under falling price
- Community rank: #1 most reliable signal
- Implementation: 24-cycle (4min at 10s) price+CVD window, compare extremes between first 12 and last 12

### KillZone Timing (CST = UTC+8)
| Zone | CST Hours | Role |
|------|-----------|------|
| Asia | 08:00-16:00 | Liquidity building |
| London | 14:00-17:00 | Sweep + displacement |
| NY AM | 20:00-23:00 | Main directional move |
- Signal confidence boost when price action aligns with KillZone role

### Silver Bullet Windows
| Window | CST Time | Source |
|--------|----------|--------|
| London 3-4AM EST | 16:00-17:00 | ICT NY session entry |
| NY AM 10-11AM EST | 23:00-00:00 | Highest probability |
| NY PM 2-3PM EST | 03:00-04:00 | London close continuation |
- Real backtest win rate: 50-65% (NOT the 70-80% ICT claims)
- Used as a confidence tag on events, NOT a standalone signal

### Liquidity Sweep Classification
- Break + quick reclaim (<30s) = sweep (fakeout)
- Break + sustained continuation = genuine breakout
- VAL/VAH breaks that reclaim within 3 readings (30s) classified as sweep, not true level break

### CVD Absorption/Distribution
- CVD range > 150 + price range < $30 over 3min = absorption
- Positive CVD avg = accumulation (bullish)
- Negative CVD avg = distribution (bearish)
- Community: "high CVD with no price movement = smart money positioning"

### Premium/Discount Zone
- 50% midpoint of session high-low range
- Buy in discount (below midpoint), sell in premium (above midpoint)
- Always use TV's VAH/VAL for the range, not local kline calculation

## Verification Commands

```bash
# Daemon health
timeout 20 python btc_vwap_daemon.py  # exit 124 = OK, exit 1 = crash

# Signal accumulation check (need 36 cycles ~3.5min for divergence)
cat data/btc_state.json | python -c "import json,sys; d=json.load(sys.stdin); print(f'cnt approximated: {len(d.get(\"price_hist\",[]))}')"

# Signals output
cat data/btc_signals.json | python -c "import json,sys; d=json.load(sys.stdin); print(f'价={d[\"price\"]} KZ={d[\"killzone\"]} 折溢价={d[\"premium_discount\"]} 背离={d.get(\"divergence\")}')"

# Pending file
cat data/btc_pending.txt

# Chinese localization check
grep -E "Silver Bullet|Taker|LS |OI[^。]|F&G|KillZone" data/btc_pending.txt || echo "0 English leaks"
```
