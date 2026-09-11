# Action Label Dashboard Pattern

Use when a TradingView Pine overlay indicator needs to be read at a glance during live trading.

## Goal
Convert a dense decision engine into a single plain-language action label that answers:
1. What is it?
2. Why does it matter?
3. What do I do next?
4. What invalidates it?

## Recommended format
- `结论`: `↑ A多`, `↓ A空`, `○ 等待`, `× 不做`
- `原因`: combine structural context and order-flow confirmation in one short line
- `下一步`: one specific action, e.g. `等回踩VWAP`, `等反抽VAH`, `不追，等扫点`
- `失效`: the concrete invalidation price or condition

## Rendering rules
- Use one `label.new()` anchored near the latest bar instead of a table.
- Keep the label opt-in with a single `SHOW_ACTION_LABEL` input.
- Update the same label on `barstate.islast`; do not create a new label every bar.
- If the setup is no-trade, the label should still explain why and what to wait for.

## Trading heuristics
- CVD should be framed as a confirmer, not a standalone directional source.
- Prefer explicit plan wording over abbreviations.
- If a setup is X / no-chase, say the reason first, then the waiting condition.
- Keep live indicator outputs separate from any backtest companion file.

## Example phrasing
- `↑ A多｜等回踩确认`
- `原因：VAH上方｜VWAP上方｜CVD抬高`
- `下一步：等回踩VWAP，CVD不转弱`
- `失效：跌回VWAP`
