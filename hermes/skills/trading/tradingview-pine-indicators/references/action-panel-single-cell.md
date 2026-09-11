# Pine Action Panel: Single-Cell Top-Right Pattern

Use this pattern when a live TradingView overlay needs a plain-language decision output but chart labels obstruct candles or price action.

## When to Use

- User wants a direct live execution summary, not a full dashboard.
- On-chart `label.new()` output is visually distracting, too wide, or blocks candles.
- The preferred display is a small, fixed panel in the top-right corner.

## Pattern

Prefer a one-cell table over a floating label:

```pine
bool SHOW_ACTION_PANEL = input.bool(true, "显示右上角行动格", group=DMI_GROUP)
string ACTION_PANEL_SIZE = input.string(size.normal, "行动格字号", options=[size.tiny, size.small, size.normal, size.large, size.huge], group=DMI_GROUP)

string actionText = actionHeadline + "\n" + actionNext + "｜" + actionInvalid
color actionBgColor = setupX ? color.new(color.red, 5) : activeLongPlan ? color.new(color.green, 5) : activeShortPlan ? color.new(color.maroon, 5) : color.new(color.gray, 10)
var table actionPanel = table.new(position.top_right, 1, 1, border_width=1)
if barstate.islast
    if SHOW_ACTION_PANEL
        table.cell(actionPanel, 0, 0, actionText, text_color=color.white, bgcolor=actionBgColor, text_size=ACTION_PANEL_SIZE, text_halign=text.align_left)
    else
        table.clear(actionPanel, 0, 0, 0, 0)
```

## Text Rules

- Keep it to one cell and ideally two lines.
- Use `结论` in the first line, then `计划｜失效` in the second line.
- Remove filler prefixes like `做法:` / `失效:` if the text is too wide.
- Avoid wide multi-factor explanations in the cell; put diagnostics in Data Window instead.

## Pine Safety Notes

- Do not put literal newlines inside strings. Use `"\n"`.
- Avoid long nested ternaries with Chinese strings; assign defaults, then use `if/else` blocks.
- If replacing a label with a table, remove stale inputs such as `ACTION_LABEL_OFFSET`, `ACTION_LABEL_SIZE`, and `SHOW_ACTION_LABEL`.
- A one-cell table is acceptable even when the user asked to remove the old decision table; it is a compact action panel, not a multi-row dashboard.
