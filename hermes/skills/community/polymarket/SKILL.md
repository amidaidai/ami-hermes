---
name: polymarket
category: community
description: Query Polymarket prediction markets. (moved from research)
---

# Polymarket — Query Prediction Markets

Query Polymarket prediction markets to get real-time probabilities on real-world events — politics, finance, science, sports, and more.

## When to use

- You want to know the market-implied probability of an event (e.g., "Will X win the election?")
- You need to compare prediction market odds with your own estimates
- You're researching event probabilities for analysis or forecasting
- You want to track how market sentiment changes over time

## Requirements

- Internet access to Polymarket API or website
- Python with `requests` for API queries (optional: `web3` for on-chain queries)
- No API key required for read-only queries (API is public)

## Usage

### Query via Polymarket CLOB API

```python
import requests

# Search for markets by keyword
query = "election"
resp = requests.get(
    "https://clob.polymarket.com/markets",
    params={"tag": query, "limit": 5}
)
markets = resp.json()
for m in markets:
    print(f"{m['question']}")
    print(f"  Volume: ${float(m['volume']):,.0f}")
    print(f"  End: {m['endDate']}")
    print(f"  Outcomes: {[o['price'] for o in m['outcomes']]}")
    print()
```

### Get specific market details

```python
import requests

# Get market by condition ID
condition_id = "0x..."  # from search results
resp = requests.get(f"https://clob.polymarket.com/markets/{condition_id}")
market = resp.json()
print(f"Question: {market['question']}")
print(f"Description: {market['description']}")
for outcome in market['outcomes']:
    print(f"  {outcome['name']}: ${float(outcome['price']):.4f} ({(float(outcome['price'])*100):.1f}%)")
```

### Get price history

```python
import requests

# Get price ticks for a market
market_slug = "will-bitcoin-reach-100k-2024"
resp = requests.get(
    f"https://clob.polymarket.com/markets/{market_slug}/price-history"
)
ticks = resp.json()
print(f"Got {len(ticks)} price ticks")
if ticks:
    print(f"Latest: {ticks[-1]['price']} at {ticks[-1]['timestamp']}")
```

### Simple market analysis

```python
def analyze_market(question, outcomes):
    """Analyze a prediction market for arbitrage or mispricing."""
    total = sum(float(o['price']) for o in outcomes)
    spread = abs(total - 1.0)
    
    print(f"Market: {question}")
    print(f"Total probability: {total:.4f} (spread: {spread:.4f})")
    
    if spread > 0.05:
        print("⚠️  Large spread — potential inefficiency")
    
    for o in outcomes:
        price = float(o['price'])
        print(f"  {o['name']}: {price*100:.1f}%")
    
    return spread
```

## Pitfalls

- The CLOB API is rate-limited — don't poll more than once per few seconds
- Markets have an `endDate` — check it before making decisions; expired markets have stale data
- Price ≠ true probability; markets can be manipulated on low-volume events
- Not all markets have liquidity — check `volume` before trusting the price
- The API response format may change — wrap queries in try/except

## Verification

Search for a well-known market (e.g., "Will the Fed cut rates"), verify the returned question text matches the expected event, and check that outcome prices sum to approximately 1.0 (100%).
