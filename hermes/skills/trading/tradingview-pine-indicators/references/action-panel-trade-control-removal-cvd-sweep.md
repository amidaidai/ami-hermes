# Action Panel Trade-Control Removal + CVD/Sweep Clarity

Use this reference when the user asks to remove trade controls from the SVP/ICT/VWAP/EMA/CVD right-top action panel, or complains that CVD / sweep wording is too vague.

## Trigger

- User says to delete `交易控制` from the action panel, settings, and code.
- User asks why CVD is too simple, whether it is current session vs previous session, or whether it is still trading-session aware.
- User asks what `扫低` / `扫高` actually swept.
- User asks for a full audit of a Pine overlay after prior trade-control additions.

## Remove Trade Controls Completely

Do not only hide the panel row. Remove the whole control chain:

- Inputs: `ALLOW_LONG_TRADES`, `ALLOW_SHORT_TRADES`, `MIN_TRADE_RR`, `MAX_STOP_ATR`, `SHOW_TRADE_CONTROL_LINE`.
- Grade gates: remove `tradeAllowLong` / `tradeAllowShort` from A/B/C setup booleans.
- Panel priority: remove `tradeControlBlocked`, `tradeControlReason`, and `不做：RR不足/止损过宽` branches.
- Data Window: remove `Replay RR Unit`, `Trade Control Blocked`, and any explicit RR export.
- Checklist: remove `RR✓/RR✗` from the action checklist.
- Search verification must show zero occurrences of the removed names and zero `交易控制` text.

Keep any generic replay/risk diagnostics that are still useful and not branded as trade controls, such as `replayStopDistance`, `replayStopAtr`, and `Replay Plan Distance`, if referenced by other audit plots.

## Action Panel Defaults

When requested, set the right-top action cell font default to small:

```pine
string ACTION_PANEL_SIZE = input.string(size.small, "行动格字号", options=[size.tiny, size.small, size.normal, size.large, size.huge], group=DMI_GROUP)
```

Keep the input live unless the user explicitly asks for no size setting.

## CVD Clarity Pattern

Explain and display two CVD layers separately:

- Main overlay CVD: v5-compatible execution CVD, built from `request.security_lower_tf()` when lower timeframe is available, and reset by the main anchor (`D`/`W`/`M` auto or manual).
- Session CVD: Asia/London/NY sub-accumulators, normally daily-reset, used to explain which session is currently driving active buy/sell pressure.

Panel text should include:

- main anchor label, e.g. `主1D`, `主1W`, `主M`;
- qualified state, e.g. `关键位吸收`, `关键位派发`, `买盘跟随`, `卖盘跟随`, `底背离修复`, `顶背离转弱`;
- session leader, e.g. `亚洲主导买盘`, `伦敦主导卖盘`, `会话均衡`;
- whether CVD is near a key level when reporting divergence.

Important: the overlay CVD is not numerically identical to TradingView's official Pine v6 CVD pane. Treat it as an execution-confirmation layer gated by SVP/VWAP/ICT key levels; use an official CVD pane for visual cross-check when available.

## Sweep Wording Pattern

`扫低` and `扫高` are unacceptable when they do not identify the swept liquidity pool.

When detecting a sweep from `ICTLevel evLvl`, carry the level name forward:

```pine
string sweepLevelName = evLvl.name
ictEventName := "扫" + sweepLevelName
ictEventPrice := evLvl.price
```

Panel and invalidation text should say things like:

- `ICT：扫周二低后收回`
- `ICT：扫伦敦高后拒绝`
- `重新站回扫周二高 67210 则失效`
- `跌回扫上周低 65880 下方则失败`

Avoid doubled wording such as `已扫扫周二低`.

## Verification Checklist

Run text-level verification after writing a versioned output:

- removed trade-control token counts are all zero;
- `ACTION_PANEL_SIZE` default is `size.small` when requested;
- exactly one `table.new(` and one `table.cell(` remain for the single-cell panel;
- `unused_inputs == 0` using a regex reference-count scan;
- no long Pine lines over ~320 characters;
- bracket and parenthesis counts balance;
- final TradingView syntax must still be checked in Pine Editor because there is no local Pine compiler.
