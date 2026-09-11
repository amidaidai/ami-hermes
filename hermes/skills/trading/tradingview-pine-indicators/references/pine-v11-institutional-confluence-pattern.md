# Pine v11 Institutional Confluence Iteration Pattern

Use when the user asks to optimize/reconstruct a TradingView Pine indicator to prove it is community-grade, especially for the SVP+ICT+VWAP+EMA+CVD family.

## Trigger

User language like:
- “继续优化更新重构”
- “证明你的实力”
- “完美适应各个市场”
- “结构关键位准确或者两者结合”
- “右上角标签一眼就能决策辅助下单”
- “社区最棒的指标”

## Pattern

1. Read the uploaded Pine source itself. Web UI upload paths are authoritative; do not assume a desktop/patched copy is current.
2. Preserve the original and write a clearly versioned output, e.g. `指标svp_v11_institutional_confluence.txt`.
3. Do a targeted community check before changing logic. Current high-quality SMC/ICT/volume-profile dashboards emphasize:
   - liquidity sweep/rejection,
   - displacement or value acceptance,
   - VWAP/SVP location,
   - CVD/order-flow confirmation,
   - HTF alignment,
   - R:R gates,
   - session/KillZone timing,
   - live dashboard decision at a glance.
4. Prefer decision synthesis over visual clutter. If the existing indicator already has SVP, ICT levels, VWAP, EMA, CVD, SMT, and an action panel, the strongest iteration is usually a **top-right institutional confluence/opportunity score** rather than adding FVG/OB/BOS drawings just to look complex.
5. Keep `indicator()` unless explicitly asked to build a strategy.
6. Preserve the user’s critical invariants:
   - top-right action panel is the primary manual-entry decision aid;
   - Data Window encoded outputs must remain available for external CD scripts;
   - R:R ≥ 1:2 is a hard gate;
   - B/C waiting states should not emit fake precise entries;
   - previous-day levels always visible;
   - previous-week levels ATR-filtered;
   - Chinese labels use `：`;
   - market emphasis differs: crypto=CVD+sweeps, metals=ICT+SVP, forex=VWAP+EMA, stocks=SVP+VWAP+volume.

## v11 Opportunity Score Template

Score 0–100 from:
- Location: near VAH/VAL/POC/VWAP/day-week liquidity.
- Structure: A/B/C setup or trend/reversal score.
- Flow: CVD confirm, absorption/distribution, divergence.
- HTF: higher timeframe allows or agrees with the trade side.
- R:R: ≥3R strongest, ≥2R acceptable, <2R blocks A execution.
- Timing: KillZone/session active.
- SMC: sweep reclaim/rejection or value acceptance.

Subtract penalties for:
- setupX,
- R:R hard block,
- CVD conflict,
- low-liquidity session,
- VWAP extension/chase risk,
- structure conflict.

Panel wording should be direct:
- `机会：82 · A执行 · 多 · 共振够`
- `机会：64 · B等待 · 空 · 等触发`
- `机会：38 · X禁做 · 等 · R:R不足`

Add a compact gate breakdown line:
- `闸门：位20 结20 流18 HTF12 RR11 时5 -0`

## v11.1 Real-Time Decision Cockpit Pattern（2026-07-06）

For Tangxi's live decision-support use case (not backtesting/replay), prefer a compact TradingView cockpit that answers what/where/can-do/when-invalid in the top-right panel.

Panel base rows should be:
1. `结论` — A/B/C/X + side + highest risk suffix.
2. `机会` — `Opportunity Score · A执行/B等待/C观察/X禁做 · 多/空/等 · 市场状态`.
3. `当前` — current structure summary: VA state + VWAP state + POC proximity + PD zone + nearest support/resistance prices.
4. `联动` — fixed five-layer MTF bias `5m/15m/1h/4h/1D`; append `高周逆风降级` when 4h/1D opposes the active side.
5. `方向` — directional bias + total score + DMI/PD/KillZone/sweep count.
6. `进场` / `止损` / `目标` — executable only when R:R and plan gates pass.
7. `解除` — if no executable plan, state exactly what fixes the no-trade state (`等R:R≥2R`, `等CVD/SMT转同向`, `等4h/1D不逆风`, `等伦敦/纽约开盘`, etc.); if executable, show invalidation text.

Implementation notes:
- Add fixed MTF requests using the existing HTF trend pack: `request.security(syminfo.tickerid, "5"/"15"/"60"/"240"/"D", f_htf_trend_pack())`; 5 extra requests are acceptable when the script remains <40.
- Encode `MCP MTF Bias Pack` as five digits where each TF code is `bias+1` (0=down, 1=neutral, 2=up), and add `MCP NoTrade Reason Code`, `MCP Nearest Key Price`, and `MCP Nearest Key Side Code` for downstream Hermes analysis cards.
- Add high-signal alerts only: opportunity ≥80 executable long/short, opportunity upgrade, R:R recovered, near key level, and decision conflict. Avoid noisy raw indicator alerts.
- This pattern is for discretionary analysis/decision aid, not strategy backtesting.

## Required outputs

Any new decision layer should have:
1. Human-visible table/panel text.
2. `plot(..., display=display.data_window)` encoding for downstream scripts.
3. `alertcondition()` for actionable transitions such as “v11多头可执行”, “v11空头可执行”, “v11等待升级”.

## Verification checklist

Before returning:
- output file exists;
- line count and byte size are sane;
- no accidental `read_file` line prefixes (`123|`) are present;
- parentheses and brackets balance;
- new variables are not duplicate-defined;
- key variables are defined before use;
- explicitly state that TradingView compile/upload is still the final check if not performed in-session.
