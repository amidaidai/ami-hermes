# Pine UDT `na` Guard: SVP Sweep Alert Pattern

## When It Triggers

TradingView runtime error on the first bar or early history:

```text
Error on bar 0: Cannot access the 'ICTLevel.swept' field of an undefined object. The object is 'na'.
```

Common trigger in SVP/ICT dashboards:

```pine
bool svpHighNowSwept = not na(svpHighObj) and svpHighObj.swept
bool svpLowNowSwept = not na(svpLowObj) and svpLowObj.swept
```

Even though the expression appears guarded, Pine v5 can still evaluate the UDT field access and throw when the object is `na`.

## Safe Replacement

Use primitive defaults and explicit guarded assignment:

```pine
bool svpHighNowSwept = false
if not na(svpHighObj)
    svpHighNowSwept := svpHighObj.swept

bool svpLowNowSwept = false
if not na(svpLowObj)
    svpLowNowSwept := svpLowObj.swept
```

Then use the primitives in alert edge detection:

```pine
bool alertSvpHighSwept = ENABLE_PRO_ALERTS and svpHighNowSwept and not svpHighWasSwept
bool alertSvpLowSwept = ENABLE_PRO_ALERTS and svpLowNowSwept and not svpLowWasSwept
```

## Verification

Search for UDT field access chained behind `not na(...) and` before delivery:

```bash
grep -nE 'not na\([^)]*(Obj|obj)[^)]*\) and .*\.(swept|ln|lb|price|name|isHigh|isHidden|isActive|priority)' <file>
```

Expected result after fixing this class: no matches.

## Scope Note

Array elements returned by `array.get(levels, i)` are usually safe when the array only stores constructed `ICTLevel` objects. Optional `var ICTLevel ... = na` handles are the main danger zone, especially `svpHighObj`, `svpLowObj`, `prevDayHighObj`, `prevWeekLowObj`, and session-state object fields before initialization.
