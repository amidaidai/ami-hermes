# Community 2026 Order-Flow Upgrade Pattern

Use this reference when enhancing a TradingView Pine dashboard that combines SVP / ICT / VWAP / EMA / DMI / CVD and the user asks to adapt it to current market conditions or improve analysis accuracy.

## Core Lesson

Do not treat CVD as an independent direction generator. In current community practice, CVD is strongest as a confirmation layer at key auction levels:

- VAH / VAL / POC / nPOC
- Session VWAP and VWAP bands
- Liquidity sweep and reclaim/reject points
- Accepted breaks outside value, confirmed over several bars

Away from those areas, CVD divergence or absorption should downgrade to a weak/diagnostic state rather than upgrade trade grade.

## Pine Implementation Pattern

Add explicit toggles and parameters instead of hardcoding market assumptions:

- `REQUIRE_SWEEP_OR_ACCEPT_FOR_A`: A-grade requires liquidity sweep reclaim/reject or VWAP+VA acceptance.
- `REQUIRE_KEY_LEVEL_FOR_CVD_CONFIRM`: CVD confirmation only upgrades signals near key levels or after accepted breaks.
- `VWAP_EXTENDED_ATR`: parameterized no-chase threshold for VWAP extension.
- `ATR_STOP_MULT`: ATR buffer around structural invalidation.
- `RISK_PER_TRADE_PCT`, `DAILY_MAX_LOSS_PCT`, `WEEKLY_MAX_LOSS_PCT`: data-window risk protocol outputs.

Define qualified CVD signals after key-level checks:

- `cvdBullConfirmQualified`
- `cvdBearConfirmQualified`
- `cvdAbsorbBuyQualified`
- `cvdDistributeSellQualified`

Then use qualified signals in scoring and A-grade gating. Keep raw CVD states available only as weak/diagnostic text such as `吸收弱`, `派发弱`, `顶背离弱`, `底背离弱`.

## Grade Gating

A-grade should satisfy all of:

1. Score separation remains strong (`>= 8` and at least 2 points above opposite side).
2. Price is on the correct side of VWAP.
3. Acceptance is confirmed over `ACCEPT_BARS`.
4. HTF filter does not oppose the setup.
5. Location is near a key level.
6. CVD confirmation is qualified.
7. The setup originates from sweep reclaim/reject or accepted value migration when the community filter is enabled.
8. ADX/VWAP extension is not in no-chase state.

B-grade may remain available, but should still require either key-level proximity or sweep/acceptance. C-grade reversals should require sweep, qualified absorption/distribution, or VA reclaim/reject rather than mere oversold/overbought scoring.

## Risk Layer

Risk rules should be represented as explicit parameters/outputs, not implied by signal confidence:

- Single-trade risk default around 1%.
- Daily stop default around 3%.
- Weekly reduce/stop default around 5–6%.
- Structure invalidation should get an ATR buffer so the stop is behind the thesis invalidation zone, not exactly on a crowded level.

## Verification Checklist

After generating an enhanced variant:

- Confirm no removed visual component APIs remain if the user asked to remove them (`table.`, `plotshape`, etc.).
- Confirm qualified CVD booleans exist and are used in score/setup rules.
- Confirm original alerts and Data Window diagnostics remain.
- Confirm risk parameters plot to `display.data_window` if they are not visually drawn.
- State that TradingView Pine Editor compile is still required; local text checks cannot prove Pine syntax.

## When to Save a New File

For uploaded user scripts, preserve the previous working version and write a new versioned file such as `_community_2026.pine` unless the user explicitly asks to overwrite in place.
