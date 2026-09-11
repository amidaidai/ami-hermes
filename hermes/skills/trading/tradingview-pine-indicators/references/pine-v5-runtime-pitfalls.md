# Pine v5 Runtime Logic Pitfalls

Durable logic bugs that pass compilation but produce wrong runtime behavior. These are NOT syntax errors — they require understanding Pine's execution model.

## 1. Timezone mismatch in `dayofweek()` for day labels

### Problem
`f_day_name_from_time()` hardcoded `"Asia/Shanghai"` timezone, but the timestamp passed (`prevDayTime`) is in the chart's timezone (`syminfo.timezone`). When the chart is set to UTC, a Wednesday 23:00 UTC bar gets labeled as "周四" (Thursday in Shanghai = UTC+8).

### Symptom
User reports: "今天周四，你就显示周四的高低点了，应该是周三的高低点才对" (Today is Thursday but you're showing Thursday's high/low — should be Wednesday's).

### Broken code
```pine
f_day_name_from_time(int ts) =>
    int dow = dayofweek(ts, "Asia/Shanghai")  // WRONG: ts is in chart timezone
```

### Fixed code
```pine
f_day_name_from_time(int ts) =>
    int dow = dayofweek(ts, syminfo.timezone)  // CORRECT: match chart timezone
```

### Rule
When converting a bar timestamp to a day name for labels, ALWAYS use `syminfo.timezone` — the timestamp came from the chart's bar data, not from a specific session timezone. The `"Asia/Shanghai"` timezone is correct for session naming (Asian session IS Shanghai time) but NOT for day-of-week labels of arbitrary timestamps.

### Exception
Session day names (e.g., "周一 亚洲盘") should use the session's own timezone (`"Asia/Shanghai"` for Asia, `"Europe/London"` for London, etc.) because the session is defined in that timezone.

---

## 2. Label price duplication — create + update both add price

### Problem
`f_make_liquidity_level()` creates the label with price in the name (`"周三 高 2345.6"`), then `updateLabel()` appends `": " + str.tostring(price, format.mintick)` → result: `"周三 高 2345.6: 2345.6"`.

### Symptom
Labels show duplicated prices: `周三 高 2345.6: 2345.6`

### Fix
Create the label WITHOUT price. Let `updateLabel()` be the single source of price display:
```pine
// CREATION — no price in name
prevDayHighObj := f_make_liquidity_level(prevDayHigh, true, prevDayName + " 高", ...)
// updateLabel adds: "周三 高: 2345.6"
label.set_text(lb, dispName + ": " + str.tostring(price, format.mintick))
```

### Rule
Pick ONE place to format the label text. If `updateLabel()` runs on every bar to refresh position/text, it should own the full display string. Creation should only set the base name without dynamic data.

---

## 3. `na()` condition causes infinite delete/recreate loop

### Problem
```pine
if showDayPool and (newDayPool or na(prevDayHighObj) or na(prevDayLowObj))
    f_delete_liquidity_pair(...)  // deletes BOTH high and low
    if not dayHighOverlapsSession
        prevDayHighObj := f_make_liquidity_level(...)  // maybe created
    if not dayLowOverlapsSession
        prevDayLowObj := f_make_liquidity_level(...)  // maybe NOT created (overlap)
```

When `dayLowOverlapsSession` is true, `prevDayLowObj` stays `na`. On the NEXT bar, `na(prevDayLowObj)` is true → re-enters the if-block → `f_delete_liquidity_pair` deletes the high line just created → recreates high → low still not created → **infinite loop**: high line flickers, low line never appears.

### Symptom
"黄金显示日高点，但是低点为什么不显示？" (Gold shows day high but why not the low?). On other markets: nothing shows at all because the overlap threshold (0.15 ATR) is too large.

### Fix
Only enter the creation block on `newDayPool` (the actual day transition). Always create both lines unconditionally:
```pine
if showDayPool and newDayPool
    f_delete_liquidity_pair(...)
    prevDayHighObj := f_make_liquidity_level(prevDayHigh, true, ...)
    prevDayLowObj := f_make_liquidity_level(prevDayLow, false, ...)
```

### Rule
Never use `na(someObj)` as a condition to re-enter a creation block that might skip creating `someObj`. The `na()` will always be true if creation was skipped, causing an infinite loop. Use a discrete event (`newDayPool`, `newWeekPool`, `barstate.isfirst`) as the only entry condition.

---

## 4. Overlap threshold too large causes everything to be hidden

### Problem
```pine
float overlapThreshold = currATR * 0.15
```
0.15 ATR is too large for most markets:
- Gold (ATR ~$20): $3 threshold → most day highs overlap with session highs
- BTC (ATR ~$800): $120 threshold → almost everything overlaps
- EUR/USD (ATR ~0.0030): 4.5 pips → nearly all levels overlap

### Fix
Remove the overlap detection entirely if it's between different-day levels. Previous day high/low and today's session high/low are DIFFERENT liquidity pools from different dates — they should NOT be merged. Only merge same-week day vs week levels (using a tight threshold like `syminfo.mintick * 8` or `price * 0.00012`).

### Rule
Overlap merging should only apply to levels from the SAME period (e.g., prevWeek vs prevDay when they're in the same week). Different-date levels (prevDay vs today's session) should always be drawn separately — they represent different liquidity targets.
