# MTF Action Panel Linkage Notes

Use this reference when reviewing or modifying TradingView/Pine action panels that the user uses as an entry decision aid.

## Durable lesson from session

The user rejected panels that only say generic labels such as `5m/15m执行`, `1h/4h结构`, or `1D背景`. Those labels are obvious and do not answer the trading question. The panel must explain the linkage between layers.

## Community-aligned baseline

For intraday BTC/XAU/FX-style dashboards, default to a stable three-layer top-down chain unless the user gives a different trading style:

- Background / bias: `1D`
- Structure / zone: `1h/4h`
- Execution / trigger: `5m/15m`

Preferred wording pattern:

```text
联动：低周触发 · 背景1D→结构1h/4h→执行5m/15m · 上级4h↑ · 看CVD+资金
```

For structure charts:

```text
联动：本级定结构 · 背景1D→结构1h/4h→执行5m/15m · 上级1D↓
计划：多路径 / 空路径 · 上级1D↓ · 下放5m/15m触发
```

For background charts:

```text
联动：高周定方向 · 背景1D→结构1h/4h→执行5m/15m
计划：只做多头结构，等1h/4h回踩
```

## Pitfalls

- Do not present timeframe labels as the answer. `执行/结构/背景` is only a role label; the decision aid must state what to do with the role.
- Do not make every timeframe produce an unrelated plan. Lower timeframe entries must inherit the upper timeframe bias, and structure timeframe plans must explicitly downshift to execution triggers.
- Avoid saying `高周` when the actual relationship is simply the current chart's parent timeframe. Prefer `上级` for dynamic parent-bias wording (`上级4h↑`, `上级1D↓`).
- Do not treat `15m` as the default structure layer for gold just because it feels faster. In the user's panel, 15m belongs with execution/trigger; 1h/4h is the safer structure layer.
- If an LTF plan opposes the parent bias, mark it as degraded rather than silently allowing it: `上级逆风降级`.

## Verification checks

After edits, statically confirm:

- Header/action line contains a chain like `背景1D→结构1h/4h→执行5m/15m`.
- Execution plan contains both the concrete trigger and context phrase like `上看结构1h/4h 下按本K确认`.
- Structure plan contains `下放5m/15m触发`.
- Conflict text uses `上级逆风降级` or equivalent.
- Plan remains at the bottom of the panel if the user's current format expects that.
- Parentheses/brackets are balanced because Pine syntax errors often surface only after upload.
