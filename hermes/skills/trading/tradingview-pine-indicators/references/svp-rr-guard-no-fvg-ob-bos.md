# SVP v10 RR Guard Without FVG/OB/BOS

Session lesson: when upgrading this user's mature SVP+ICT+VWAP+EMA+CVD Pine indicator, do **not** add FVG, Order Block, BOS, or similar ICT decoration modules unless explicitly requested. The user rejected that class of feature and prefers the existing sweep/VWAP/VA/CVD/DMI framework to remain clean.

## Accepted upgrade pattern

Use this pattern when the user wants the right-top action panel to be more executable:

1. **R:R hard gate for A-grade only**
   - Compute `rrRatio` from plan price, invalidation price, and same-direction target.
   - `bool rrHardOk = not na(rrRatio) and rrRatio >= 2.0`
   - `bool rrHardBlock = (displayLongA or displayShortA) and not rrHardOk`
   - If blocked, panel state should become `X R:R不足` and execution line should say `不做，R:R不足2，等更好价`.
   - A-grade alerts should include `and rrHardOk`.

2. **Directional Magnet target**
   - Track both sides separately:
     - `magnetAbovePrice/Dist/Score/Name`
     - `magnetBelowPrice/Dist/Score/Name`
   - Long plans use only the above target.
   - Short plans use only the below target.
   - Do not use the nearest target regardless of side for R:R; it can be behind the trade and inflate reward.

3. **B/C grades wait only**
   - A-grade may show concrete entry, stop, target, R:R.
   - B/C grades must not show an executable entry price.
   - Use texts such as:
     - `等回踩确认，不给价`
     - `等反抽确认，不给价`
     - `等站回确认，不给价`
     - `等跌回确认，不给价`
   - B/C alerts should say waiting/confirmation, not “入场”.

4. **HTF check must be side-aware**
   - Long plan: `htfAllowLong ? "HTF✓" : "HTF✗"`
   - Short plan: `htfAllowShort ? "HTF✓" : "HTF✗"`
   - Avoid generic `htfAllowLong and htfAllowShort` checks.

5. **CVD market weighting**
   - Keep CVD as a hard A-grade gate mainly for crypto/perp markets.
   - For XAU/forex/stocks/futures, downweight CVD and treat it as auxiliary confirmation because TradingView CVD is an approximation, not Bookmap-grade bid/ask delta.
   - For metals/forex, A-grade can use `cvdLongOk/cvdShortOk` rather than requiring `cvdBullConfirmQualified/cvdBearConfirmQualified`.

## Verification checklist

Run text-level checks after patching:

- No new `FVG`, `Order Block`, `OB`, or `BOS` module strings.
- `rrHardBlock` and `R:R不足2` exist.
- A alerts include `rrHardOk`.
- Directional target variables exist for above/below magnet.
- B/C execution text contains `不给价`.
- No `入場` or full-width `｜` remains in user-facing text.
- Plot/request counts did not materially increase.

Final Pine syntax still requires TradingView Pine Editor validation; local checks are text-only.