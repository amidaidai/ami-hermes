# Alert Rendering v7.5 · 2026-06-21 Fix Session

## Root Cause

`monitor_levels.json` stores two name fields per level:
- `name`: Internal technical ID (e.g., `R1_reclaim_accept`, `S1_retest`) — **for program use only**
- `display_name`: Chinese human-readable name (e.g., `阻1·近端收复接受位`, `支1·回测位`) — **for user display**

`行情守望.py::render_message()` was using `item.get("name")` instead of `item.get("display_name")`, causing technical IDs to leak into Telegram alerts.

## Changes Made

1. `display_name` priority in render_message: `item.get("display_name") or item.get("name", "?")`
2. Fixed "引擎引擎" double-prefix: removed `f"引擎{model_dir_text}"` since `model_dir_text` already starts with "引擎"
3. Changed separators: `" · "` for indicator/risk lines, `"  "` (double space) for panorama line
4. Taker direction: `buy→买` `sell→卖` `neutral→平` — Chinese directions with English "Taker" prefix
5. Fixed REPORT_TOPIC from non-existent 846 → existing 416

## Before/After

```
BEFORE:                                  AFTER:
R1_reclaim_accept `64192` 距0.1%       阻1·近端收复接受位 `64192` 距0.1%
S1_retest `63936` 距0.3%               支1·回测 `63936` 距0.3%
引擎引擎判方向不明/震荡                   引擎判方向不明/震荡
CVD买 · Takerbuy 1.40·B级               CVD 买 · A级 · Taker 买 1.40·A级
○R2`64448`●R1`64192`                    ○阻2·上沿 `64448`  ●阻1·近端收复 `64192`
风控 允许 常规 最大风险 3.0U              风控 允许 · 常规 · 最大风险 3.0U · CVD C级→半仓
```

## Files Modified

- `scripts/行情守望.py::render_message()` — v7.1 → v7.5
- `scripts/行情守望.py::ALERT_TOPIC_BY_SYMBOL` — added ETHUSDT/SOLUSDT
- `scripts/行情守望.py::REPORT_TOPIC` — 846 → 416
- `scripts/daily_learn.py` — v2.0: 14 categories, 42 topics, date-driven rotation
- `scripts/zh_locale.py` — Chinese localization module (方向/状态/术语/Kill Zone)
- `scripts/tv_screenshot.py` — TV MCP screenshot pipeline
- `scripts/topic_router.py` — Telegram topic router
