# Table-Safe Dashboard Pattern

Use when a Pine overlay dashboard table blocks the latest candles, price axis, or right-side execution area.

## Problem

In `overlay=true` scripts, `position.bottom_right` often covers the most recent candles and price action. Transparent table backgrounds make the overlap worse because candles show through the text.

## Durable Fix

1. Add an explicit safe default table position option:

```pine
string DMI_TABLE_POS = input.string("自动避让", "表格位置(默认避开K线)",
     options=["自动避让", "左下", "左中", "左上", "中下", "中上", "右上", "右中", "右下"],
     tooltip="自动避让固定在左下，避开右侧最新K线/价格轴。若手动选右下，仍可能挡住最新K线。", group=DMI_TABLE_GROUP)
```

2. Map `自动避让` to `position.bottom_left`, not bottom-right:

```pine
f_dmi_pos(string p) =>
    switch p
        "自动避让" => position.bottom_left
        "右上" => position.top_right
        "右中" => position.middle_right
        "右下" => position.bottom_right
        "左上" => position.top_left
        "左中" => position.middle_left
        "左下" => position.bottom_left
        "中上" => position.top_center
        "中下" => position.bottom_center
        => position.top_right
```

3. Make opacity user-controllable but default opaque:

```pine
bool DMI_TABLE_OPAQUE = input.bool(true, "表格不透明",
     tooltip="开启后表格背景完全不透明，K线不会透到文字下面。", group=DMI_TABLE_GROUP)

f_table_bg(color c) =>
    DMI_TABLE_OPAQUE ? color.new(c, 0) : c
```

4. Apply the background helper to both the table and every cell:

```pine
var table dmiPathTable = table.new(f_dmi_pos(DMI_TABLE_POS), 2, 18,
     border_width=1, frame_width=1, frame_color=color.new(color.black, 0),
     bgcolor=f_table_bg(DMI_TABLE_CELL_BG))

f_dmi_cell(int col, int row, string txt, color bg, color tc) =>
    table.cell(dmiPathTable, col, row, txt,
         bgcolor=f_table_bg(bg), text_color=tc, text_size=f_dmi_size(DMI_TABLE_SIZE))
```

## Verification

- Search for exactly one `table.new` and confirm it uses `f_dmi_pos(DMI_TABLE_POS)`.
- Confirm `自动避让` exists in the input options and maps to `position.bottom_left`.
- Confirm `DMI_TABLE_OPAQUE` exists and `table.cell()` uses `bgcolor=f_table_bg(bg)`.
- Run TradingView MCP static analyzer when available; server-side Pine compilation is still the final syntax check.
