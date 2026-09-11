# TradingView Decision-Panel v3.1: Price-Specific Plans and Invalidations

Session lesson from a TradingView Pine dashboard iteration where the user challenged two issues: `失效` did not say whether it invalidated the long or short plan, and `详细` mode did not add enough value over `简洁` mode.

## Durable UX Rules

- `计划` and `失效` must be tied to the same side.
  - Good: `计划 = 多:回踩VWAP 67120`, `失效 = 多失效:破VWAP 66880`.
  - Good: `计划 = 空:反抽VAL 66880`, `失效 = 空失效:回VWAP 67120`.
  - Bad: `计划 = 多:...｜空:...`, `失效 = 破VWAP` when the table also has a dominant side.
- For no-trade/risk states (`X`, overextended, conflict), do not show a fake stop condition. Use `计划 = 不追，等关键位` and `失效 = 禁追，不谈失效`.
- When there is no active side, it is acceptable to show both `多` and `空` plans, but the invalidation should say `等触发后设失效` rather than pretending a trade exists.
- `详细` mode should not merely duplicate the compact table. It should add review/debug value: split `多计划` and `空计划`, show score diagnostics, event/CVD/high-timeframe context, and keep the compact mode execution-focused.

## Implementation Pattern

Build side-specific plan text before rendering the table:

```pine
string longBreakName = not na(resPrice) ? resName : not na(curVah) ? "VAH" : not na(sVwap) ? "VWAP" : "前高"
float longBreakPrice = not na(resPrice) ? resPrice : not na(curVah) ? curVah : sVwap
string shortBreakName = not na(supPrice) ? supName : not na(curVal) ? "VAL" : not na(sVwap) ? "VWAP" : "前低"
float shortBreakPrice = not na(supPrice) ? supPrice : not na(curVal) ? curVal : sVwap

float longPlanPrice = priceAboveS ? pullbackLevelPrice : longBreakPrice
float shortPlanPrice = priceBelowS ? reboundLevelPrice : shortBreakPrice
string longPlanAction = priceAboveS ? "回踩" + pullbackLevelName : "破" + longBreakName
string shortPlanAction = priceBelowS ? "反抽" + reboundLevelName : "破" + shortBreakName
string longPlanText = "多:" + longPlanAction + " " + f_fmt_price(longPlanPrice)
string shortPlanText = "空:" + shortPlanAction + " " + f_fmt_price(shortPlanPrice)
```

Then choose the compact table's active plan from the setup side:

```pine
bool activeLongPlan = displayLongA or setupLongB or setupLongC
bool activeShortPlan = displayShortA or setupShortB or setupShortC
string focusedPlanText = setupX ? "不追，等" + watchText : activeLongPlan ? longPlanText : activeShortPlan ? shortPlanText : longPlanText + "｜" + shortPlanText
```

Make invalidation side-specific and price-aware:

```pine
float longInvalidPrice = invalidText == "跌回VWAP" or invalidText == "破VWAP" ? sVwap : invalidText == "跌回VA内" ? curVah : invalidText == "跌回扫低" ? curVal : invalidText == "等回踩接受" ? longPlanPrice : na
float shortInvalidPrice = invalidText == "收回VWAP" ? sVwap : invalidText == "收回VA内" ? curVal : invalidText == "收回扫高" ? curVah : invalidText == "等反抽承压" ? shortPlanPrice : na
string longInvalidText = "多失效:" + invalidBaseText + " " + f_fmt_price(longInvalidPrice)
string shortInvalidText = "空失效:" + invalidBaseText + " " + f_fmt_price(shortInvalidPrice)
string invalidSpecificText = setupX ? "禁追，不谈失效" : activeLongPlan ? longInvalidText : activeShortPlan ? shortInvalidText : "等触发后设失效"
```

`f_fmt_price(float price)` should return a blank/placeholder such as `--` for `na`, and `str.tostring(price, format.mintick)` otherwise.

## Verification Checklist

- Search for `plotshape(` when the user requested no chart markers; it should be absent.
- Scan `input.*` variables and ordinary variables for single-use declarations after refactors; stale settings create user confusion in TradingView's Settings panel.
- Verify compact mode uses `focusedPlanText` and `invalidSpecificText`.
- Verify detailed mode has separate `多计划` and `空计划` rows, not only one combined plan row.
- Verify final alert lines still use short ASCII positional `alertcondition(...)` calls if earlier Pine parser issues occurred.
- Pine cannot be fully compiled locally; tell the user to paste into TradingView Pine Editor and return exact line errors.
