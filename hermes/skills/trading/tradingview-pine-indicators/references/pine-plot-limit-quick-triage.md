# Pine plot-limit quick triage: 65/64 overflow

Session pattern: user reported TradingView compile error `脚本创建了太多绘图(65)。限制为64` after adding Data Window diagnostics to a mature SVP/ICT/VWAP/EMA/CVD overlay.

## Durable fix pattern

1. Inventory all count-producing calls:
   - `plot*()` / `plotbar()` / `plotcandle()` / `plotchar()` / `plotshape()` / `plotarrow()`
   - `alertcondition()`
   - `bgcolor()` / `barcolor()`
   - `fill()` only when its `color` argument is series-qualified
2. Apply the official argument rule:
   - a basic `plot(series)` = 1 count for the value series
   - each genuinely series-qualified color/textcolor argument adds 1
   - `plotbar()` / `plotcandle()` start at 4 OHLC counts and can reach 7
   - `bgcolor()` / `barcolor()` = 1 each
   - `fill(seriesColor)` = 1; a non-series-color fill = 0
   - `hline()` / `line.new()` / `label.new()` / `box.new()` / `table.new()` = 0
   - `display.data_window` and `display.none` do not exempt a plot
3. Remove or merge **non-critical Data Window plots first**. Do not remove visible structural chart lines or price-axis outputs unless necessary.
4. Prefer dropping duplicated diagnostics already available elsewhere:
   - If weekly/monthly VWAP have right-price-axis plots, separate `Weekly VWAP Data` / `Monthly VWAP Data` data-window plots are redundant.
   - If stop/ATR encoded replay data exists, a separate `Replay Plan Distance` plot is usually lower-value.
5. Recompile and use TradingView’s reported total. Near the cap, comment out one call at a time to measure its exact delta. Keep practical margin below 64.

## Concrete example from this session

Removed 3 data-window plots:

```pine
plot(SHOW_WEEKLY_VWAP ? vwapWeekly : na, "Weekly VWAP Data", color=WEEKLY_VWAP_COLOR, display=display.data_window)
plot(SHOW_MONTHLY_VWAP ? vwapMonthly : na, "Monthly VWAP Data", color=MONTHLY_VWAP_COLOR, display=display.data_window)
plot(replayPlanDistance, title="Replay Plan Distance", display=display.data_window, color=color.new(color.blue, 100))
```

Kept:
- `W VWAP Price` and `M VWAP Price` right-axis outputs.
- replay side/grade, plan price, invalid price, stop encoded, score encoded.
- key CD-system encoded outputs: CVD session, Magnet+ICT+Score, risk/effective params.

Resulting inventory from that historical case: 28 `plot()` calls, 16 plots believed to use series-qualified colors, 2 fills, 1 background, and 1 table. Under the corrected official rule the table contributes zero; each fill contributes only if its color is series-qualified; and the background contributes one. Treat the old ≈48 estimate as non-authoritative and use the TradingView compiler total for that exact source version.

## Preferred report to user

Be concise and concrete:
- Say which exact plots were removed.
- Say what remains available instead.
- Provide the output file path.
- Remind that final validation is TradingView Pine Editor compile.
