# Liquidity Label Controls + Week Pool Distance Filter

Session lesson from SVP+ICT+VWAP+EMA+CVD v8.2.6.

## When Optimizing Label Readability

- Do not hard-force merged structural labels to `size.tiny` unless the user explicitly asks for fixed tiny labels.
- Preserve user control: merged labels should usually follow the main unswept label input, e.g. `ICT_UNSWEPT_LABEL_SIZE`.
- For this user's ICT/liquidity indicators, practical defaults are:
  - 未扫标签大小: `size.normal`
  - 已扫标签大小: `size.tiny`
  - 前日/前周池标签大小: separately configurable, often `size.tiny`
- If labels feel too large, first add or verify real Settings controls; do not silently override those controls in rendering logic.

## Week High / Low Pool Filtering

Previous-week high/low are useful liquidity pools, but far-away weekly levels can compress or clutter the chart.

Recommended pattern:

```pine
float WEEK_LIQUIDITY_SHOW_ATR = input.float(4.0, "前周池显示距离ATR", minval=0.5, maxval=20.0, step=0.5)
bool showPrevWeekHigh = showWeekPool and math.abs(prevWeekHigh - close) <= currATR * WEEK_LIQUIDITY_SHOW_ATR
bool showPrevWeekLow = showWeekPool and math.abs(prevWeekLow - close) <= currATR * WEEK_LIQUIDITY_SHOW_ATR
```

Render high and low independently:

- If only 上周高 is too far, hide/remove only 上周高.
- If only 上周低 is near, keep 上周低 visible and active.
- When hiding a weekly pool, remove its `ICTLevel` object from the shared `levels` array as well as deleting its line/label, otherwise hidden far levels can still affect sweep/key-level logic.
- Keep weekly retention separate from ICT intraday lookback, but distance filtering should decide whether a retained level is drawn/active now.

## Pitfall

Avoid leaving Pine dead-code placeholders like `if false` after patching. They may compile, but they confuse future audits and can preserve stale assumptions in a live trading indicator.
