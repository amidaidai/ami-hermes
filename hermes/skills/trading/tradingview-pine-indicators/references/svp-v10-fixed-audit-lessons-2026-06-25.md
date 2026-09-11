# SVP v10 Fixed Audit Lessons (2026-06-25)

Use when auditing the user's uploaded `指标svp_v10_fixed.txt`-style production Pine indicator after community benchmarking.

## Durable findings

1. **Audit the freshly uploaded file, not prior desktop/patched versions.** Verify line count and key markers first. In this session the production upload had 2569 lines and already included many previous fixes.
2. **Session CVD Asia channel default:** community/default execution logic is crypto = 3 channels; metals/forex = London+NY primarily. If source contains `cvdUseAsiaChannel = ... marketCrypto or marketMetal or marketForex`, flag as P1 unless the user explicitly confirms Asia CVD for metals/forex.
3. **Day/session overlap contradiction:** if code comments say previous-day levels should never merge with current Asia/London/NY session levels, this conflicts with the user's preference: when day liquidity overlaps session high/low, reuse the session line/color rather than drawing duplicate day lines. Check around day-pool creation logic, not just line display toggles.
4. **Zero-length line audit applies to all structural lines, not only liquidity pools.** Search every `line.new(x, y, x, y)` pattern. nPOC creation can still use `line.new(endBar, price, endBar, price)` even after liquidity lines were fixed with `bar_index + 1`. Prefer non-zero initial length and extend with `bar_index + 1` where appropriate.
5. **Action-panel CVD dominant-session hint:** if `cvdDirectionHint` computes `亚主+ / 伦主- / 纽主~` but `actionCvdText` only appends `cvdSessionSuffix` (`亚主`) then the HUD lost the useful direction sign. Flag as P2/P1 depending on panel importance.
6. **Legacy narrative dead-code remains common after compact HUD migration.** Keep `stateText`, `watchText`, and `invalidText` if consumed by the panel; candidate-delete old card variables (`cardLine1-3`, `detailText`, `directionGuideText`, `actionGuideText`) only after grep proves they have no live references.
7. **White-theme color audit:** near-black values like `#0F0F0F` are not invisibility P0 on this user's white TradingView theme. Treat duplicates such as POC+day line or Asia+monthly VWAP as semantic color-collision issues, not visibility blockers.

## Suggested verification snippets

- Count output budget and series-color doubling risk before recommending new Data Window plots.
- Grep for all zero-length structural lines, including nPOC and completed profile lines.
- Confirm `request.security` count stays well below 40 and Data Window CD exports remain encoded rather than split into many plots.
