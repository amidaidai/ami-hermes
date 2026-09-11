# Compact Liquidity Labels + Weekly Pool Retention

Use this when a TradingView Pine overlay with ICT-style liquidity pools becomes visually too loud or the user reports that `上周 高/上周 低` is missing.

## Durable Pattern

- Keep day/week liquidity pools as ICT-style `ICTLevel` objects, but give them independent label-size inputs:
  - `DAY_LIQUIDITY_LABEL_SIZE`, default `size.tiny`
  - `WEEK_LIQUIDITY_LABEL_SIZE`, default `size.tiny`
- Set the general ICT unswept label default to `size.tiny` when the chart feels crowded. Keep swept labels `size.tiny`.
- Set the one-cell execution panel default to `size.small` rather than `size.normal` when the user says the text is too large.
- Pass the label size into the liquidity-level factory instead of reusing `ICT_UNSWEPT_LABEL_SIZE` blindly:
  - `f_make_liquidity_level(..., int prio, string labelSize)`
  - use `label.new(..., size=labelSize)`
- Make merged labels tiny as well. A merged multi-line label is visually larger than a single label even at the same size.
- Reduce nearby-label merge threshold when labels are too dense, e.g. from `max(mintick * 8, abs(close) * 0.0002)` to around `max(mintick * 6, abs(close) * 0.00012)`.

## Weekly Pool Retention Fix

If `上周 高/上周 低` is added to the same `levels` array as intraday ICT levels, do not let the ordinary ICT lookback cleanup delete it after 1-3 days.

Add a dedicated input:

```pine
int WEEK_LIQUIDITY_KEEP_DAYS = input.int(8, "前周池保留天数", minval=3, maxval=14)
```

Then adjust cleanup by level name/type:

```pine
int levelMaxDuration = str.contains(lvl.name, "上周") ? WEEK_LIQUIDITY_KEEP_DAYS * 86400 * 1000 : max_duration
if (time - lvl.createdAt) > levelMaxDuration
    line.delete(lvl.ln)
    label.delete(lvl.lb)
    array.remove(levels, i)
```

## Verification Checklist

- Defaults: `ICT_UNSWEPT_LABEL_SIZE=size.tiny`, `ACTION_PANEL_SIZE=size.small`.
- Inputs exist: `DAY_LIQUIDITY_LABEL_SIZE`, `WEEK_LIQUIDITY_LABEL_SIZE`, `WEEK_LIQUIDITY_KEEP_DAYS`.
- Day/week pool creation passes the independent label-size input.
- Weekly labels still render as `上周 高` and `上周 低`.
- `alertcondition()` count remains unchanged unless the user asked to change alerts.
- The live output remains one compact table cell if that was the current UX.
