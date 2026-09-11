# Liquidity Pools + Axis Dedupe Pattern

Use this when improving a multi-factor Pine overlay that already has ICT session levels, CVD key-level gating, and right price-axis helper plots.

## Durable Pattern

- Add previous-day and previous-week liquidity pools as first-class ICT-style levels, not as a separate visual system.
- Compute levels with `request.security(syminfo.tickerid, "D", high[1]/low[1])` and `request.security(syminfo.tickerid, "W", high[1]/low[1])`.
- Label previous-day pools with weekday names (`周一 高`, `周一 低`) and previous-week pools as `上周 高`, `上周 低`.
- Reuse the existing ICT level array/type when available so sorting, nearby-label merging, swept-state styling, and sweep detection remain consistent.
- Give day/week pools higher priority than intraday session levels when merged near the same price.
- Feed these levels into nearest support/resistance selection, A-grade key-level checks, and CVD key-level gating.
- Do not add FVG/OB unless explicitly requested; for this user's live overlay, structure clarity is more valuable than more boxes.

## Low-Liquidity Downgrade

For non-crypto symbols, add a downgrade state when no configured Asia/London/NY session is active:

- Treat as no-chase/risk state, not just a panel note.
- Show clear action text such as `降级｜等伦敦/纽约`.
- Preserve crypto 7x24 behavior by excluding `isCrypto` from the downgrade.

## Right Price-Axis Dedupe

When users report duplicate right-axis prices:

- Search for multiple `display=display.price_scale` plots for the same logical level.
- Centralize all price-axis helper plots in one final section.
- Remove earlier duplicate axis plots while keeping data-window plots intact.
- Add a small de-duplication helper that suppresses secondary labels when two levels are within a tiny threshold, e.g. `max(syminfo.mintick * 4, abs(close) * 0.00005)`.
- Prioritize structural levels in this order: SVP/POC/VAH/VAL/nPOC first, then W/M VWAP, then DO.

## Verification Checklist

- `//@version=5` or the original script version is preserved.
- `alertcondition()` count stays unchanged unless user asks otherwise.
- The live output remains a single compact action cell if that was the existing UX.
- New day/week pools appear in key-level gating variables (`nearCvdKeyLevel`, `nearAKeyLevel`).
- No new FVG/OB code appears unless explicitly requested.
- Text-level check confirms old duplicate axis labels are removed and new unified axis plots exist.
