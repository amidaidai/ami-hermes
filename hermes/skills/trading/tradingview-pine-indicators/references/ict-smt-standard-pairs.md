# ICT SMT Standard Pairs & Correlation Logic

Reference for implementing Smart Money Technique (SMT) divergence detection in Pine Script indicators. Source: ICT inner circle trader documentation + community consensus (innercircletrader.net, Reddit r/InnerCircleTraders, TTrades YouTube).

## Standard SMT Pairs

### Positive Correlation (assets move together)

| Current Symbol | SMT Reference | Pine Ticker Examples | Notes |
|---|---|---|---|
| BTC | ETH (same exchange) | `BINANCE:ETHUSDT`, `OKX:ETHUSDT`, `BYBIT:ETHUSDT` | Cleanest crypto pair; always match exchange |
| ES (S&P 500) | NQ (Nasdaq 100) | `CME_MINI:ES1!` → `CME_MINI:NQ1!` | **NOT ES/RTY** — Russell 2000 is not the ICT standard |
| EUR/USD | GBP/USD | `OANDA:EURUSD` → `OANDA:GBPUSD` | Standard forex SMT pair; bidirectional |
| GBP/USD | EUR/USD | `OANDA:GBPUSD` → `OANDA:EURUSD` | Reverse of above |
| XAU/USD | XAG/USD | `OANDA:XAUUSD` → `OANDA:XAGUSD` | Gold vs silver; strong results |

### Negative Correlation (assets move opposite)

| Current Symbol | SMT Reference | Pine Ticker | Notes |
|---|---|---|---|
| BTC | DXY (Dollar Index) | `TVC:DXY` | BTC rises when DXY falls |
| XAU/USD | DXY | `TVC:DXY` | Gold rises when DXY falls |
| EUR/USD | DXY | `TVC:DXY` | EUR rises when DXY falls |

## Divergence Logic — Differs by Correlation Type

The key insight: **positive and negative correlation pairs have OPPOSITE divergence conditions.**

### Positive Correlation (e.g. BTC/ETH)

| Divergence | Condition | Signal |
|---|---|---|
| Bear | I make new high + ETH does NOT make new high | Bearish reversal (ETH weakness = BTC likely fake) |
| Bull | I make new low + ETH does NOT make new low | Bullish reversal (ETH strength = BTC likely fake) |

### Negative Correlation (e.g. BTC/DXY)

| Divergence | Condition | Signal |
|---|---|---|
| Bear | I make new high + DXY ALSO makes new high | Bearish reversal (DXY should FALL when BTC rises; if DXY rises too, something is wrong) |
| Bull | I make new low + DXY ALSO makes new low | Bullish reversal (DXY should RISE when BTC falls; if DXY falls too, something is wrong) |

**Common bug**: applying positive-correlation logic to a negative-correlation pair inverts all signals. Use a `smtIsNegative` boolean flag to gate the logic branch.

## Pine Implementation Pattern

### Pair Detection Helpers

```pine
f_is_btc_pair(string t) => str.contains(t, "BTCUSDT") or str.contains(t, "BTC/USDT") or str.contains(t, "BTCUSD") or str.contains(t, "XBTUSDT") or str.contains(t, "XBTUSD")
f_is_xau_pair(string t) => str.contains(t, "XAUUSD") or str.contains(t, "XAU/USD") or str.contains(t, "GOLD")
f_is_xag_pair(string t) => str.contains(t, "XAGUSD") or str.contains(t, "XAG/USD") or str.contains(t, "SILVER")
f_is_eur_pair(string t) => str.contains(t, "EURUSD") or str.contains(t, "EUR/USD")
f_is_gbp_pair(string t) => str.contains(t, "GBPUSD") or str.contains(t, "GBP/USD")
f_is_es_pair(string t) => str.contains(t, "ES1!") or str.contains(t, "SP500") or str.contains(t, "SPX")
```

### Ticker Selection with Negative-Correlation Flag

```pine
string smtTicker = ""
bool smtIsNegative = false
if SHOW_SMT
    string exchPrefix = str.contains(syminfo.tickerid, "BINANCE") ? "BINANCE" :
        str.contains(syminfo.tickerid, "OKX") ? "OKX" :
        str.contains(syminfo.tickerid, "BYBIT") ? "BYBIT" :
        str.contains(syminfo.tickerid, "COINBASE") ? "COINBASE" :
        str.contains(syminfo.tickerid, "KRAKEN") ? "KRAKEN" : ""
    string autoEthTicker = exchPrefix != "" ? exchPrefix + ":ETHUSDT" : "BINANCE:ETHUSDT"

    if SMT_PAIR_MODE == "BTC/ETH"
        smtTicker := f_is_btc_pair(stdTickerUpper) ? autoEthTicker : stdTicker
    else if SMT_PAIR_MODE == "BTC/DXY"
        smtTicker := f_is_btc_pair(stdTickerUpper) ? "TVC:DXY" : stdTicker
        smtIsNegative := true
    else if SMT_PAIR_MODE == "XAU/XAG"
        smtTicker := f_is_xau_pair(stdTickerUpper) ? "OANDA:XAGUSD" : stdTicker
    else if SMT_PAIR_MODE == "XAU/DXY"
        smtTicker := f_is_xau_pair(stdTickerUpper) ? "TVC:DXY" : stdTicker
        smtIsNegative := true
    else if SMT_PAIR_MODE == "ES/NQ"
        smtTicker := f_is_es_pair(stdTickerUpper) ? "CME_MINI:NQ1!" : stdTicker
    else if SMT_PAIR_MODE == "EURGBP"
        smtTicker := f_is_eur_pair(stdTickerUpper) ? "OANDA:GBPUSD" : f_is_gbp_pair(stdTickerUpper) ? "OANDA:EURUSD" : stdTicker
    else if SMT_PAIR_MODE == "手动"
        smtTicker := SMT_MANUAL_TICKER
    else
        // Auto mode: match by instrument type
        if marketCrypto and f_is_btc_pair(stdTickerUpper)
            smtTicker := autoEthTicker
        else if marketMetal and f_is_xau_pair(stdTickerUpper)
            smtTicker := "OANDA:XAGUSD"
        else if marketForex and f_is_eur_pair(stdTickerUpper)
            smtTicker := "OANDA:GBPUSD"
        else if marketForex and f_is_gbp_pair(stdTickerUpper)
            smtTicker := "OANDA:EURUSD"
        else if f_is_es_pair(stdTickerUpper)
            smtTicker := "CME_MINI:NQ1!"
```

### Divergence Detection (single-line intermediate booleans)

**⚠ CRITICAL: Pine v5 does NOT allow multi-line parenthesized expressions.** The following uses named intermediate booleans to avoid `Syntax error at input 'end of line without line continuation'`:

```pine
float smtRefClose = SHOW_SMT and smtTicker != "" and smtTicker != stdTicker ? request.security(smtTicker, timeframe.period, close) : na
int SMT_SWING_LEN = 10
float smtMySwingHigh = ta.highest(high, SMT_SWING_LEN)
float smtMySwingLow = ta.lowest(low, SMT_SWING_LEN)
float smtRefSwingHigh = SHOW_SMT and not na(smtRefClose) ? ta.highest(smtRefClose, SMT_SWING_LEN) : na
float smtRefSwingLow = SHOW_SMT and not na(smtRefClose) ? ta.lowest(smtRefClose, SMT_SWING_LEN) : na
bool smtMyNewHigh = high >= smtMySwingHigh[1]
bool smtMyNewLow = low <= smtMySwingLow[1]

// Positive correlation: ref fails to confirm my extreme
bool smtBearPos = not smtIsNegative and smtMyNewHigh and smtRefClose < nz(smtRefSwingHigh[1], smtRefClose)
bool smtBullPos = not smtIsNegative and smtMyNewLow and smtRefClose > nz(smtRefSwingLow[1], smtRefClose)

// Negative correlation: ref confirms when it should diverge (DXY rises with BTC = divergence)
bool smtBearNeg = smtIsNegative and smtMyNewHigh and smtRefClose > nz(smtRefSwingHigh[1], smtRefClose)
bool smtBullNeg = smtIsNegative and smtMyNewLow and smtRefClose < nz(smtRefSwingLow[1], smtRefClose)

// Combine with momentum confirmation (each on ONE line)
bool smtBearDiv = SHOW_SMT and not na(smtRefClose) and (smtBearPos or smtBearNeg) and close > close[3]
bool smtBullDiv = SHOW_SMT and not na(smtRefClose) and (smtBullPos or smtBullNeg) and close < close[3]
```

## Input Options Pattern

```pine
string SMT_PAIR_MODE = input.string("自动", "SMT对照品种", options=["自动", "BTC/ETH", "BTC/DXY", "XAU/XAG", "XAU/DXY", "ES/NQ", "EURGBP", "手动"], group=SMT_GROUP)
```

## Common Mistakes

1. **ES/RTY instead of ES/NQ** — Russell 2000 is not the ICT standard pair for S&P 500. Always use Nasdaq 100.
2. **Same logic for all pairs** — negative-correlation pairs (vs DXY) need reversed divergence conditions.
3. **Cross-exchange ETH** — comparing BINANCE:BTC vs OKX:ETH introduces exchange-specific price differences. Auto-detect the exchange prefix from `syminfo.tickerid`.
4. **Multi-line boolean expressions** — Pine v5 rejects `(\n a or\n b)`. Use intermediate variables (see pattern above).
5. **Fixed-window change rate** — use swing pivot detection (`ta.highest/ta.lowest`) not `(close - close[N]) / close[N]` for divergence detection.

## Source

- innercircletrader.net — ICT SMT Divergence tutorial (authoritative)
- TTrades YouTube "SMT Divergence - ICT Concepts" — correlated vs inversely correlated SMT
- Reddit r/InnerCircleTraders — community consensus on standard pairs
