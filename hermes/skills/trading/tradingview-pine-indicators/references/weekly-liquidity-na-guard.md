# Weekly Liquidity `na` Object Guard

## Trigger

Use this note when iterating Pine indicators that store drawn levels in user-defined objects, especially ICT-style objects such as `ICTLevel` with fields like `.swept`, `.ln`, `.lb`, `.price`, or `.name`.

## Problem

Pine can still throw runtime errors when a condition combines an object existence check and a field access in one expression:

```pine
if not na(prevWeekHighObj) and not prevWeekHighObj.swept
```

On early bars, `prevWeekHighObj` may still be `na`. Do not assume `and` safely short-circuits object field access in all runtime paths. TradingView can report errors like:

```text
Cannot access the 'ICTLevel.swept' field of an undefined object. The object is 'na'.
```

## Safe Pattern

Split object existence checks from field reads. Read fields only inside a guarded block, then use primitive booleans in later conditions:

```pine
bool prevWeekHighSwept = false
if not na(prevWeekHighObj)
    prevWeekHighSwept := prevWeekHighObj.swept

if not showPrevWeekHigh and not na(prevWeekHighObj) and not prevWeekHighSwept
    f_remove_level_from_array(prevWeekHighObj)
    line.delete(prevWeekHighLine)
    label.delete(prevWeekHighLabel)
    prevWeekHighObj := na
    prevWeekHighLine := na
    prevWeekHighLabel := na
```

Apply the same pattern for low-side objects and any optional user-defined object fields.

## Weekly Liquidity Sweep-Line Context

For previous-week high/low pools:

- Keep unswept labels default `size.small` and swept labels default `size.tiny`.
- Let weekly pool labels use a weekly-specific unswept size input when present.
- If weekly high/low is swept, keep the faded dashed sweep line even on H1+ charts.
- ATR distance filters should only remove unswept far weekly levels; once swept, retain the sweep evidence until normal retention cleanup.

## Verification Checklist

- Search for direct `not na(obj) and obj.field` patterns around user-defined objects.
- Confirm all object field reads occur after a standalone `if not na(obj)` guard.
- Confirm the weekly sweep line path still calls `line.set_style(..., line.style_dashed)` and `updateLabel(..., true)`.
- Run text checks for alert count, table count, long lines, and unwanted feature regressions before handing off.
