# SVP-Anchored Trading-Day Boundaries

Use this note when auditing Pine indicators where SVP/volume-profile periods define the user's trading context and the chart also displays previous-day/week liquidity pools or ICT session levels.

## Lesson

For SVP-first dashboards, "day end" should usually mean **the active SVP anchor period has completed and the next SVP has begun**, not necessarily natural midnight in the exchange timezone or display timezone.

This matters because prior-day/weekly liquidity labels such as `周五 高` / `周五 低` can appear too early or feel "not past yet" when they are keyed to `time("D")` or a display-timezone day boundary while the current SVP period is still forming.

## Recommended pattern

1. Derive a single shared profile-period transition flag near the SVP timeframe selection:

```pine
string targetProfileTF = AUTO_PROFILE_TF ? autoProfileByMarket : MANUAL_PROFILE_TF
bool isNewProfilePeriod = ta.change(time(targetProfileTF)) != 0
```

2. Reuse that same flag for SVP archiving/rendering:

```pine
bool isNewPeriod = isNewProfilePeriod
```

3. For previous-day/week liquidity pools, prefer SVP completion when the profile anchor is `D` or `W`; only fall back to display-calendar day/week when the active SVP anchor is not the matching period:

```pine
int dispDayKey = year(time, DISP_TZ) * 10000 + month(time, DISP_TZ) * 100 + dayofmonth(time, DISP_TZ)
int dispPrevDayKey = nz(dispDayKey[1], dispDayKey)
bool newCalendarDayPool = dispDayKey != dispPrevDayKey
bool newDayPool = targetProfileTF == "D" ? isNewProfilePeriod : newCalendarDayPool
bool newWeekPool = targetProfileTF == "W" ? isNewProfilePeriod : (newCalendarDayPool and dayofweek(time, DISP_TZ) == dayofweek.monday)
```

## Pitfalls

- `ta.change(time("D"))` follows the symbol/exchange daily boundary. On crypto symbols this can differ from the user's perceived trading day and can make weekday-labelled pools appear unexpectedly.
- A display timezone (`DISPLAY_TZ`) fixes label names but not necessarily the trading-day definition. If SVP is the primary structure, align pools with the SVP anchor.
- ICT session high/low logic is separate: active sessions should stay hidden or marked `(进行中)` and should not enter magnet/target selection until the session ends.
- Use one shared period flag for both SVP completion and liquidity-pool rollover to avoid off-by-one disagreements between the profile and labels.
