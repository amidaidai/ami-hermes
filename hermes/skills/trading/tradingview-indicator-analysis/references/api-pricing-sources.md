# 价格源与期货/现货区分 v1.0

◷ 2026-06-21 · 棠溪："期货和现货的价格不一样，我是tradingview的价格"

## 价格层级

### BTC/ETH（加密永续）
- **主源**: Binance Perp 期货价 (`fapi/v1/ticker/price`)
- **备用**: CMC 现货价
- **期现差**: 自动计算并显示 `期现差+0.096%`
- **卡面**: `③ 现价：期货 64,210（Binance期货）`

### XAUUSD（黄金）
- **主源**: gold-api.com 现货 (`api.gold-api.com/price/XAU`)
- **K线**: Yahoo GC=F 期货 (-$20 ≈ 现货)
- **DXY**: Yahoo DX-Y.NYB
- **卡面**: `③ 现价：现货 4,157（gold-api现货）`

### 股票
- **主源**: Alpha Vantage → Twelve Data → FMP（三级回退）
- **卡面**: `③ 现价：150.25（Alpha Vantage）`

### 外汇
- **主源**: FMP fmp_forex() → Alpha Vantage
- **卡面**: `③ 现价：现货 1.0850（FMP）`

## `_price_label()` 函数

```python
def _price_label(symbol: str, engine_data: dict) -> tuple[str, str]:
    """返回(价格标签, 来源)"""
    prices = engine_data.get("prices", {})
    source = prices.get("source", "")
    ac = _asset_class(symbol)
    if ac == "crypto":
        label = "期货 " if prices.get("futures") else "现货 "
        return label, source or "Binance Perp"
    if ac == "gold":
        return "现货 ", source or "gold-api"
    ...
```

## 铁律
- 加密优先期货价（非CMC现货），CMC现货作备用
- XAU 只用现货源（gold-api + 金十 + OANDA），GC=F 期货作 K线/趋势参考，不作主价
- TradingView 是图表工具，不是价格源 — 品种行显示实际交易所/经纪商
- ③现价必须标注期货/现货 + 来源括号
