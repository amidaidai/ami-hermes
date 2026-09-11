# Pine Script Deep Audit Checklist

Repeatable methodology for auditing multi-factor Pine Script trading indicators. Developed from the 2026-06-24 SVP+ICT+VWAP+EMA+CVD audit session.

## Phase 1: Structural Scan

1. Map module boundaries by line ranges (Inputs, SVP engine, VWAP core, CVD, ICT, DMI, Decision, Output)
2. Count total output series: `grep -c "= plot\(|= fill\(|= bgcolor\(|table\.new\("` — must stay under 64 (TV Free limit), aim for <40
3. Identify `request.security()` and `request.security_lower_tf()` calls — each adds latency
4. Check for `barmerge.lookahead_on` usage — flag any that reference current-bar data (lookahead is OK for previous-period data)

## Phase 2: Data-Flow Tracing

1. Trace every `input.*` variable to its usage — flag unused/single-use inputs (dead settings panel controls)
2. Trace CVD state text through all overwrite points — multiple reassignments create confusing data flow
3. Trace score accumulation — confirm clamping at both ends: `math.min(math.max(score, 0), 10)`
4. Verify grade stability logic — A-grade should have confirmation delay, X-risk should be immediate

## Phase 3: Decision Engine Verification

1. Map all 22+ state branches in the decision cascade — confirm no unreachable branches
2. Verify structure conflict detection covers all four dimensions (EMA, sweep, DMI, CVD)
3. Check that CVD absorption/distribution signals are gated by key-level proximity (not standalone)
4. Verify sweep reclaim/reject logic handles all edge cases (same-bar touch, gap-through, inactive levels)

## Phase 4: Community Alignment

1. KillZone naming: `伦敦开盘`/`纽约开盘` (never `白银`/`伦窗`/`纽窗`)
2. CVD notation: `+/-/~` (never `↑↓→`)
3. No chart markers (`plotshape`/`plotchar`) unless explicitly requested
4. No trade controls (RR gating removed per v8.2.9)
5. No FVG/OB concepts
6. Settings panel order: 市场→SVP→ICT→VWAP→EMA→CVD→执行/风控
7. Action panel header format: `品种：TICKER · 看FOCUS1+FOCUS2 ⚡KILLZONE` — must include `品种：` prefix before the ticker symbol (not bare `TICKER · ...`)
8. Action panel row labels use `：` (Chinese colon), not `｜` (full-width pipe): `结论：`, `结构：`, `确认：`, `资金：`, `执行：`
9. Action panel row order: 结论→结构→确认→资金→[条件checklist]→执行
10. KillZone no bgcolor — text markers only via `actionKillZoneLine`

## Phase 5: Verified Pitfall Catalog

| ID | Pitfall | Fix |
|----|---------|-----|
| P0 | `request.security()` with `gaps_off` for prev-period data | Use `gaps_on` to forward-fill completed-bar values |
| P0 | SMT auto-pair maps wrong ticker across market types | Each mode branch only checks its own ticker(s) |
| P1 | `ta.vwap()` in HTF bias pack — daily-reset, not structural | Use `ta.sma(hlc3, 50)` for structural bias |
| P1 | Sweep detection misses gap-through | Add `gapThrough` check: full bar on other side with prev bar within level |
| P1 | Dead `else na` blocks in method-based code | Delete; `if` without `else` is valid Pine |
| P1 | Function returns unused value | Remove return statement |
| P1 | Unused/dead helper function defined but never called (e.g. `f_level_short()`) | Search for references and delete if orphaned |
| P1 | Redundant ternary `? "" : ""` that always evaluates to the same value | Replace with bare literal |
| P1 | Prev day/week liquidity levels gated by ICT session `show_ict_lines` (false on 4h+) → invisible on HTF charts | Decouple with `allowDrawRefLevels = SHOW_ICT_LEVELS` (no timeframe restriction). Also update sweep loop, label merge, and cleanup guards to `(show_ict_lines or showDayPool or showWeekPool)` |
| P1 | `COLOR_DAY_LIQUIDITY` = `#0F0F0F` (near-black) invisible on TV dark theme (#131722 bg) | Use visible blue-grey like `#78909C`; always verify ALL color inputs against both dark/light TV themes. **NOTE: user uses WHITE theme — `#0F0F0F` IS visible, do not flag as P0 without confirming theme** |
| P0 | `dayofweek(ts, "Asia/Shanghai")` for day-name labels when `ts` is in chart timezone → wrong day name (周四 instead of 周三) | Use `dayofweek(ts, syminfo.timezone)` for day labels. Only use session-specific TZ for session day names. See `references/pine-v5-runtime-pitfalls.md` §1 |
| P0 | Label price duplication: `f_make_liquidity_level` creates with price AND `updateLabel` appends price → `周三 高 2345.6: 2345.6` | Create label WITHOUT price (`"周三 高"`), let `updateLabel` own the full display string (`"周三 高: 2345.6"`). See `references/pine-v5-runtime-pitfalls.md` §2 |
| P0 | `na(prevDayLowObj)` in if-condition causes infinite loop: when creation is skipped (overlap), na() is true every bar → delete/recreate high every bar, low never created | Only enter creation block on `newDayPool` event, always create both unconditionally. See `references/pine-v5-runtime-pitfalls.md` §3 |
| P1 | Overlap threshold `currATR * 0.15` too large: Gold=$3, BTC=$120, EUR=4.5pips → most levels overlap → nothing drawn | Remove overlap detection between different-date levels (prevDay vs today's session). Only merge same-week day vs week levels with tight threshold (`mintick * 8`). See `references/pine-v5-runtime-pitfalls.md` §4 |
| P1 | `POC_COLOR` = `#0F0F0F` (same class of bug as COLOR_DAY_LIQUIDITY) — POC is the most important volume profile line | Use `#FFD700` (gold) or another high-contrast color visible on dark theme |
| P1 | Sweep counter uses `isActive` (session-in-progress flag) instead of `swept` (actual price-cross flag) | Count `evLvl.swept` for swept levels and `not evLvl.swept` for unswept; `isActive` is set to `false` when a session ends, regardless of whether the level was touched |
| P1 | `SHOW_OPEN_ONLY_ACTIVE` default `true` hides active session labels on `barstate.islast` merge | Default to `false`; `true` means "hide labels in active sessions" which is counter-intuitive |
| P1 | `SHOW_DO_LINE` default `false` means Daily Open line never shows by default | Default to `true` — DO is a basic reference level |
| P2 | Bubble sort on small arrays | Acceptable for n<20, but insertion sort is simpler |
| P2 | Polyline delete/recreate on every `barstate.islast` | Acceptable for polyline API limitations |

## Phase 6: Settings Default Audit

After structural and logic audit, review ALL `input.bool()` defaults for rendering visibility:

1. **Systematic scan**: `grep "input\.bool("` to list every boolean input with its default value
2. **Hidden-by-default check**: Flag any `input.bool(false, ...)` — is the feature expected to be visible on first load? If so, flip to `true`
3. **Color visibility**: For every `input.color(...)`:
   - Check against TV dark theme (~`#131722`) — near-black (≤ `#1A1A1A`) invisible
   - Check against TV light theme — near-white (≥ `#F0F0F0`) invisible
   - Safe floor for dark theme: `#3A3A3A` minimum; safe ceiling for light: `#C0C0C0` maximum
4. **SHOW_OPEN_ONLY_ACTIVE gating**: When `true`, active session labels are excluded from `barstate.islast` label merge → invisible on the current bar. This input's name ("活跃会话仅显示开盘价") is confusing — it HIDES labels, not shows them. Default should be `false`
5. **Label size floor**: `size.tiny` labels with dark colors are doubly invisible — bump to `size.small` for critical reference levels
6. **Cross-reference with action panel**: If a feature is listed in the action-panel format spec but defaults to off, it's a mismatch
