# Execution Card v3.4 Audit Pattern

Session lesson from iterating a TradingView Pine overlay dashboard for the user's SVP+ICT+VWAP+EMA+CVD indicator. The user wanted no chart buy/sell markers, a table that does not cover recent candles, and a final execution-card audit.

## Durable UX Rules

- Do not add chart buy/sell markers for this user. Keep `plotshape()` and `plotchar()` absent; if labels remain, they must be structural labels only (POC/VAH/VAL, ICT session high/low, precision warnings), not `BUY/SELL/买/卖/做多/做空` signals.
- Default table placement should avoid the latest candle/price axis: add `自动避让` and map it to `position.bottom_left`; keep `右下` only as an explicit manual choice.
- Table backgrounds should be opaque by default so candles cannot show through text.
- Compact mode should read as an execution card: `等级`, `处理`, `背景`, `位置`, `量能`, `CVD`, `执行`, `风控`.
- For X/no-trade states, the `执行` row should say what to wait for (`不追，等回踩VWAP/POC`, `不追，等VWAP/VA确认`), and the `风控` row should show the解除条件 (`解除:ADX降温+回VWAP`, `解除:高周同向/回POC`) instead of fake stop-loss text.
- For CVD, avoid displaying large internal CVD numbers in the table. Use readable state text such as `CVD破近低`, `CVD回近高`, `CVD抬高`, `CVD不弱`, `CVD走低`, `CVD不强`.
- CVD should be a guard, not just a score bonus: long plans require CVD to stay above a recent low; short plans require CVD to stay below a recent high. If the guard fails, downgrade the plan to waiting rather than showing B/C as executable.
- Detailed mode should add review/debug value with a `过滤` row: examples include `过滤:通过`, `过滤:不靠关键位`, `过滤:高周冲突`, `降级:CVD破近低`, `降级:CVD回近高`, or an X解除 condition.

## Implementation Notes

- Define concise CVD wait and guard text before plan rendering:
  - `cvdLongWaitText`: `CVD抬高` / `CVD不弱` / `CVD吸收` / `等CVD转强`.
  - `cvdShortWaitText`: `CVD走低` / `CVD不强` / `CVD派发` / `等CVD转弱`.
  - `cvdLongGuardText`: `CVD破近低`; `cvdShortGuardText`: `CVD回近高`.
- Use previous-bar windows for the guard threshold so the current bar can actually break the guard:

```pine
float cvdLongGuardLevel = ta.lowest(cvdValue[1], CVD_SLOPE_LEN)
float cvdShortGuardLevel = ta.highest(cvdValue[1], CVD_SLOPE_LEN)
bool cvdLongGuardOk = not SHOW_CVD_CONFIRM or na(cvdLongGuardLevel) or cvdValue >= cvdLongGuardLevel or cvdBullDivQualified or cvdAbsorbBuy
bool cvdShortGuardOk = not SHOW_CVD_CONFIRM or na(cvdShortGuardLevel) or cvdValue <= cvdShortGuardLevel or cvdBearDivQualified or cvdDistributeSell
```

- Add a user-facing input for guard behavior, but describe actual behavior accurately:

```pine
bool CVD_GUARD_DOWNGRADE = input.bool(true, "CVD失效时降级", tooltip="多单需要CVD维持抬高，空单需要CVD维持走低；不满足时计划转等待，避免CVD已坏还硬做。", group=CVD_GROUP)
```

- Make X execution and release conditions explicit:

```pine
string xWaitText = xHot ? "不追，等降温+回VWAP" : xHtfConflict ? "不追，等高周同向/回POC" : xConflict ? "不追，等VWAP/VA确认" : vwapExtendedUp ? "不追，等回踩VWAP/POC" : vwapExtendedDn ? "不追，等反抽VWAP/POC" : "不追，等关键位"
string xReleaseText = xHot ? "解除:ADX降温+回VWAP" : xHtfConflict ? "解除:高周同向/回POC" : xConflict ? "解除:站稳/跌破VWAP" : vwapExtendedUp ? "解除:回踩VWAP/POC" : vwapExtendedDn ? "解除:反抽VWAP/POC" : "解除:关键位确认"
```

- For high-timeframe filter text, only report a conflict when the strong current trend conflicts with HTF, not merely because HTF has a direction:

```pine
bool filterHtfActive = USE_HTF_FILTER and ((trendLongScore >= 7 and htfBear) or (trendShortScore >= 7 and htfBull))
```

## Final Audit Checklist

Run a deterministic text audit before reporting final status:

- Confirm `plotshape(` count is `0` and `plotchar(` count is `0`.
- Search for buy/sell marker labels (`买入`, `卖出`, `BUY`, `SELL`, `做多`, `做空`) and distinguish structural words like `买盘`/`卖盘` from actual markers.
- Count unused `input.*` variables; target `0` unused inputs.
- Confirm `DMI_TABLE_POS` defaults to `自动避让` and maps to `position.bottom_left`.
- Confirm table cell backgrounds pass through an opaque helper when `DMI_TABLE_OPAQUE` is true.
- Confirm compact mode uses `focusedPlanText` and `invalidSpecificText`.
- Confirm detailed mode includes a `过滤` row and that it is not just duplicating compact mode.
- Confirm `alertcondition()` remains short ASCII positional calls to avoid Pine parser issues.
- Check balanced parentheses/brackets and run Pine static analysis; still tell the user TradingView Pine Editor is the final compiler.
