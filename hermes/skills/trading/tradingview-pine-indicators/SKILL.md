---
name: tradingview-pine-indicators
description: Build, review, and enhance TradingView Pine Script indicators, especially multi-factor trading dashboards that combine volume profile, VWAP, EMA, ICT/session levels, DMI, and CVD/order-flow confirmation.
---

# TradingView Pine Indicators

Use this skill when the user asks to analyze, modify, combine, or create TradingView Pine Script indicators.

3. When auditing a Pine indicator, load `references/pine-indicator-audit-checklist.md` (8-dimension systematic checklist: quotas, repainting, logic, colors, action panels, multi-market, CVD, dead code).

**⚠ 改 plot 标题 / 行动格行名之前先读** `tradingview-indicator-analysis` -> `references/indicator-contract-drift-guard.md`。
本仓的 Python 消费方是按 **plot 标题字符串与行动格行名**取数的（契约 `scripts/tv_indicator_contract.py`），
改一个字符串就会在卡面/告警上**静默丢字段**（历史事故：13 行行动格只吃到 4 行）。改完必跑
`python scripts/tv_indicator_alignment_check.py`，退出码 0 才算对齐；同一批字段名一旦出现在两个文件里就是漂移源。 For multi-community cross-audits, also load `references/multi-community-cross-audit-template.md`. When you are **editing / refactoring** (not only auditing), also load the sibling skill `pine-indicator-audit` -> `references/pine-v6-correctness-and-ce10117-budget-20260911.md`: `str.replace` replaces only the FIRST occurrence (use `str.replace_all`), `array.sum` returns na only when EVERY element is na (so aggregate with per-element `nz`), ternaries cannot return tuples (CE10163 — request unconditionally and pick the symbol in the ternary), function-local vars cannot use history (CW10018), a type-definition insert point must anchor on the true last field (else CE10198), and CE10117's 100,256-token cap is plan-independent (comments don't count; embedded constants and repeated code do). When the audit is an **external report someone handed you** (or when you need `na` semantics / pack-encoding traps), also load the sibling skill `pine-indicator-audit` -> `references/pine-na-semantics-and-external-audit-verification-20260910.md`: exact `array.sum` na rule, the "three-state plot falling outside its design = look for na" tell, the four-step method for verifying another AI's audit claims, and a 10-pattern Pine defect checklist (duplicate HTF offset, negative low-digit in packed ints, compact format strings used for executable prices, `nz(x,0)` masking missing data, display toggles mutating business state...).
4. For right-top action panels that drive entries, use the MTF linkage notes in `references/mtf-action-panel-linkage.md`: don't merely label timeframes as execution/structure/background; show how HTF bias, MTF structure, and LTF trigger relate in the current plan.
5. When an action panel says `守HL/LH` or `等新HL/LH`, read `references/structure-label-semantics-and-decision-panel.md`: a last confirmed swing is not automatically HH/HL/LH/LL; either implement a real two-pivot classifier or use honest “确认摆动高/低” wording. Generic `等触发` must become a concrete position→trigger→close→CVD/OI chain. The same reference includes the P0 SVP value-area threshold invariant.
6. For SVP-first dashboards with prior-day/week liquidity labels, read `references/svp-anchored-trading-day-boundaries.md`: define "day/week ended" by the matching SVP anchor period completing and the next SVP starting, not blindly by `time("D")` or display-timezone midnight.
6. BEFORE proposing to add/remove any `request.security` call (especially to free quota or add OI/CVD/aggregation sources), read `references/request-security-quota-rules.md`. Pine v6 dynamic requests are execution/context based: one call site can activate zero, one, or many unique contexts, while identical executed requests usually reuse one slot. A toggle only saves quota if it prevents the request call itself from executing; hiding the fetched result does not. Count default and worst-case executed contexts and validate in TradingView.
6. When auditing or pairing the HALDRO "Volume Aggregated Spot & Futures" 副指标 with the SVP v10 主指标 (用户的双指标决策体系), read `references/haldro-aggregated-volume-pairing.md`: covers the request.* default 40-unique-call ceiling (Ultimate 64), non-crypto symbol corruption (gate with `syminfo.type=='crypto'`), the dual-CVD口径冲突 (main `request.security_lower_tf` estimate has finer granularity than HALDRO wick-ratio estimate), CVD anchor alignment, and action-panel slimming. Always read the user's Web UI-uploaded current version before editing — don't assume desktop/patched files are latest.
7. For free-tier dual-indicator work, read `references/free-tier-dual-indicator-contract-audit-20260822.md`: enforce explicit quality/contract packs, distinguish feed validity from cross-venue consensus, dynamically encode CVD method, gate non-crypto/None requests before request execution, and never use `close` as an input.source wiring sentinel.
8. For live client acceptance after compile/add-to-chart, read `references/live-dual-indicator-runtime-acceptance-20260826.md`: verify study values and Pine tables, prove Packed Bus wiring from S0→S1–S4, audit conclusion/direction/structure/action consistency, enforce B/C R:R boundaries, and clean duplicate studies or maximized panes by entity/state rather than appearance alone.
9. When Entry/Stop/Target, scoring, risk, panels, or MCP outputs can see both long and short candidates, read `references/pine-single-plan-direction-contract.md`: establish one grade-first `selectedPlanDir`, use long-first only for same-grade anomaly fallback, and route every downstream consumer through that direction.

## Core Workflow

1. Read the provided Pine files before making claims.
2. Identify Pine version and compatibility constraints first (`//@version=5` vs `//@version=6`).
3. Map each indicator's role before merging:
   - Overlay/主图: structure, levels, bands, labels, tables.
   - Separate pane/副图: oscillators, CVD, momentum, histograms.
4. Preserve the main script's version unless there is a strong reason to migrate everything.
5. When merging a pane indicator into an overlay dashboard, avoid plotting raw oscillator values on the main price chart unless explicitly requested; expose values through `display.data_window`, labels, or table rows instead.
6. Add user-facing inputs under a dedicated group, with Chinese labels if the source indicator uses Chinese.

## Compile-Fix Pitfalls

When fixing Pine compiler errors, check these recurring failure classes before changing logic:

1. **Declaration order is strict**: Pine cannot reference identifiers declared later in the file. If a derived string/score uses market flags (`marketCrypto`, `marketMetal`, `marketForex`, `marketStock`, `marketIndex`) or calculated targets (`magnetNearestPrice`, `magnetScore`), move the consuming expression below the declarations/calculation block rather than duplicating variables.
2. **`alertcondition()` messages must be const strings** in Pine v5. Do not concatenate `series string` values such as prices, labels, scores, or formatted dynamic text into the `message` argument. Keep `title` and `message` fixed; expose dynamic detail through plots/Data Window/table text or use runtime `alert()` only if the script design explicitly supports it.
3. **`ta.highest()` / `ta.lowest()` consistency warnings**: call these on every calculation, outside ternaries/conditional scopes, then gate the resulting value with booleans afterward. Example: compute `float refHigh = ta.highest(refSeries, len)` unconditionally, then use `SHOW_X and not na(refSeries) ? refHigh : na` downstream.
4. After patching, run a text-level verification for declaration order and dynamic `alertcondition` remnants before returning the file path.


## 用户偏好 — 行动面板术语必须直白中文（棠溪铁律）

棠溪多次反馈"扫2存5 近0.8A 这个看着很迷茫"——**禁止用 1-2 字抽象代号**，右上角行动格每一项必须一眼读懂。

| 错（抽象代号） | 对（直白中文） | 含义 |
|---|---|---|
| `扫2存5` | `已扫2/剩5` | 已扫2个流动性池/剩5个未扫 |
| `近0.8A` | `磁距0.8A` | 离最近磁吸目标0.8个ATR |
| `VWAP 延/延下` | `VWAP上方过远/下方过远` | 价格偏离VWAP过远 |
| `VWAP 上/下/均` | `VWAP上方/下方/贴VWAP` | 价格与VWAP相对位置 |
| `位3/确5/延0` | `位置3/确认5/延展0` | 位置/确认/延伸风险评分 |
| `止损1.5A` | `止损1.5ATR` | 止损距离1.5个ATR |
| `磁78↑` | `磁吸78↑` | 磁吸分数78，方向↑ |
| `位✓/位~/位✗` | `位置✓/位置~/位置✗` | 核对行位置评分 |

**规则**：右上角行动格是用户入場决策的唯一依据——"迷茫"的代号等于读不懂信号。任何新加的指标/评分/距离必须用完整中文词汇，不可缩成单字（A/位/磁/扫/存/延）。单位 `A`（ATR）必须写成 `ATR`，单位 `R`（R:R）可以保留因为是社区通用。

**陷阱**：社区指标（LuxAlgo、Trading IQ 等）常用缩写节省空间——不要照抄，棠溪要的是可读性优先于紧凑。hinese labels.
7. Integrate new signals into the existing decision system, not just as standalone calculations:
   - table/status row
   - scoring weights
   - validation/conflict logic
   - optional data-window diagnostics
8. Save enhanced versions as a new file rather than overwriting the original upload unless the user explicitly asks to edit in place.
9. Verify by searching for inserted anchors and line references, checking file existence/size, and reviewing changed snippets. Pine syntax must still be compiled in TradingView because there is no local TradingView compiler.

## CVD Integration Pattern

When fusing a TradingView CVD pane into a Pine v5 overlay script:

- Do not import a Pine v6-only helper into a v5 script.
- Reimplement a lightweight CVD approximation with `request.security_lower_tf()` and a local delta function when compatibility matters.
- Use an anchor reset (`D`/`W`/`M`) for cumulative state.
- Derive compact states such as `顺多确认`, `顺空确认`, `买盘回升`, `卖盘回落`, `顶背离`, `底背离`, `中性`.
- Add CVD to existing scoring carefully and clamp scores after both positive and negative adjustments.
- Treat CVD divergence as a conflict/confirmation modifier, not an automatic trade signal.
- Plot CVD internals to Data Window only for overlay dashboards to avoid price-axis compression.

## Pro Dashboard Upgrade Pattern

For mature multi-factor dashboards, improve execution quality without deleting existing features:

- Add a compact setup grade such as `A多`, `A空`, `B多`, `B空`, `C反多`, `C反空`, `C等待`, `X` instead of adding more raw indicator rows.
- Add a short `处理` row that translates the state into execution posture (`回踩做多`, `反抽做空`, `轻仓等多`, `轻仓等空`, `站回再多`, `跌回再空`, `观望`). Prefer `处理` over vague `操作` when the user wants an actionable table.
- Keep the real-time table narrow and readable: default to a `简洁` table mode with `等级`, `处理`, `高周`, `结构`, `量能`, `CVD`, `计划`, `失效`; keep `详细` mode for audit/replay rows such as `市场`, `趋势`, `事件`, `倾向`.
- Do not cram volume, event, and CVD into one row or rely on cryptic abbreviations (`C多`, `量↑强`) when the user values readability. Split them into separate rows with short but human-readable Chinese labels.
- Make `计划` specify the actual level, not just `上破/下破`: e.g. `破VAH`, `破POC`, `破VWAP`, `破VAL`, or `VWAP/POC` for pullback/throwback plans.
- Add high-timeframe bias, acceptance confirmation, CVD key-level divergence filtering, A-grade key-level gating, and grade stability before adding more indicators; these reduce false positives without expanding the visual system.
- Add `alertcondition()` for only high-signal states: A-grade long/short, sweep reclaim/reject with CVD confirmation, and no-chase/conflict. Use short ASCII alert titles/messages if TradingView reports odd syntax errors around alert strings.
- Avoid chart markers by default for this user; they distract from chart reading. If marker code is not needed, remove it rather than leaving dead switches. If kept for generic users, make it opt-in.
- After deleting or replacing visual features, audit the Inputs panel for dead controls. Remove orphaned inputs, unused helper functions, and stale "visual clean/detail/marker" toggles that no longer control behavior; a clean TradingView settings panel is part of the deliverable.
- Prefer a small set of live controls over a large legacy control surface. Scan input variables for single-use definitions, then remove those that are only declared and never referenced by calculations/rendering.
- Add performance modes (`完整` / `标准` / `轻量`) that reduce heavy drawing while preserving calculations and price-axis/table outputs, but only keep the input if it actively changes rendering/calculation behavior.
- Add visual-clean inputs for line/object density only when they actually control live logic; otherwise make the simplified behavior the default and delete the dead switch.
- For this user, prefer a single plain-language action label over a table when the goal is fast execution. The label should answer four questions in order: what it is, why it matters, what to do next, and what invalidates it.
- For this user, prefer a single right-top one-cell `table` with `size.small` text. **v9.5+ compact 6-line format:** header (`KZ窗口 · 看焦点`), 结论 (includes direction bias + HTF + DMI + structure verdict), 结构 (VA/VWAP/EMA + pools + sweep count), 确认 (ICT/CVD clean + compact session funding + SMT), 核对 (checklist + calibration), 执行 (action + invalidation). **No ticker name in header** — the chart already shows it. Row labels use `：` (Chinese colon). Module prefixes (SVP/ICT/CVD) live in the row template, NOT in the value text — avoid duplication. Lines use ` · ` (middle dot) separator. Session dominant terms: `亚主`/`伦主`/`纽主`. Signal text is compressed: `A多 回踩` (not `A多：回踩做多`), `失效:破VWAP 62300` (not `多失效:破VWAP`). See `references/action-panel-v95-compact.md` for the complete pattern.
- **v9.6 audit HUD upgrade pattern:** when auditing an already-compact action panel, do not add another table or chart markers. Enrich the same one-cell panel with: `结论` = state + bias + long/short trend score + reversal score + DMI; `结构` = VA/VWAP/EMA + structure verdict + SVP pool + sweep count; `位置` = nearest resistance/support prices + MTF arrows; `确认` = ICT event + CVD state/quality + SMT + leading session; `核对` = HTF/EMA/CVD/location + calibration; `执行` = active plan text + execution/invalidation sentence. Keep it one cell, black text, color-coded background, no ticker name. See `references/action-panel-v96-audit-hud.md`.
- For multi-market use, keep the structural backbone unified but vary the explanation emphasis by market: crypto leans more on CVD/sweeps, forex on VWAP/EMA, metals on ICT/VP sweeps, stocks/index on VP/VWAP/EMA. **v9.0+ header format**: `TICKER · 看FOCUS1+FOCUS2 ⚡KILLZONE`. Focus hint is market-adaptive: `看CVD+扫点` (crypto), `看ICT+SVP` (metals), `看VWAP+EMA` (forex), `看SVP+VWAP` (stocks/indices), `看综合` (other). This tells the trader what matters for the current instrument — not what market type it is. Drop standalone market type tags entirely.
- ICT action-panel labels must name the **specific swept level**: use `lastEventName` (which includes day name, e.g. `周四亚高`) rather than bare `ictEventName` (only session abbreviation, e.g. `扫亚高`). The richer form `ICT：周四亚高后收回` gives the trader context without using extra space. Fall back to `ictEventName` only when `lastEventName` is stale or from a non-sweep event.
- KillZone labels must use **professional community-standard naming, unified across all markets**: `伦敦开盘` / `纽约开盘`. This matches ICT "London Open Killzone" / "NY Open Killzone". **Never** use `白银`, `伦窗`, `纽窗`, `伦敦高波`, or any emoji flags (`🇬🇧`/`🇺🇸`). "白银" is a mistranslation — Silver Bullet is the specific 10-11am window, not the broader KillZone. The input group and tooltip must also say "开盘窗口", not "白银时刻". KillZone bgcolor is forbidden — text markers only.
- This user prefers an **iterative collaboration pattern** for Pine Script work: they take the initial output file, modify it themselves on their local machine, then return it to the agent for review, absorption assessment, community benchmarking, and further optimization. When receiving a self-modified file, first compare against what was previously delivered to identify what the user absorbed/improved, acknowledge their improvements explicitly, then apply optimizations on top of their version.
- When improving readability, translate the decision engine into execution language rather than adding more technical rows. Preferred compact format: line 1 `等级/方向｜看关键位｜CVD状态`; line 2 `多/空:关键位｜失效条件`. Avoid wide 4-line labels that block candles.
- Treat CVD as a confirmer at key levels, not as a standalone directional source; gate CVD scoring and absorption/distribution to VAH/VAL/POC/VWAP/sweep proximity before letting it influence grade or action. If a separate official TradingView CVD pane is present, use it as visual confirmation only; the main indicator's key-level-gated CVD state remains the execution source.
- Do not make ADX overheat alone a blanket no-trade state for this user's live indicator. Prefer `overheat + VWAP extension` as no-chase, while single overheat downgrades to pullback/throwback watch text so strong trends do not display `没有好机会` all session.
- Preserve the user's preference for no multi-row table output in the live TradingView indicator unless they explicitly asks to restore a table; a single right-top action cell is acceptable when requested.

## nPOC Price-Axis Pattern

When the user wants nPOC shown in the price scale, only expose active/untouched nPOCs:

```pine
float show_npoc_val = na
if array.size(npocList) > 0
    int i = array.size(npocList) - 1
    while i >= 0
        NakedPOC n = array.get(npocList, i)
        if n.active
            show_npoc_val := n.price
            break
        i -= 1

float axisNpoc = SHOW_AXIS_VP_LEVELS and SHOW_NPOC ? show_npoc_val : na
float axisNpocPlot = (SHOW_RIGHT_PRICE_AXIS and SHOW_AXIS_VP_LEVELS and SHOW_NPOC) ? axisNpoc : na
plot(axisNpocPlot, title="nPOC Price", color=NPOC_COLOR, show_last=1, display=display.price_scale)
```

On touch, set `active := false`; the axis value becomes `na` automatically. If the touched nPOC line should not distract, make it fully transparent or delete it depending on whether historical evidence is desired.

## Live Decision Panel Rules

- Keep live tables small: each row should express one concept such as `等级`, `处理`, `高周`, `结构`, `量能`, `CVD`, `计划`, `失效`.
- Make `计划` and `失效` direction-specific and price-aware. Prefer `多:回踩VWAP 67120` + `多失效:破VWAP 66880`, or `空:反抽VAL 66880` + `空失效:回VWAP 67120`. Add order-flow wait conditions to execution rows when CVD is available, e.g. `多:回踩VWAP 67120 + CVD维持抬高` or `空:反抽POC 66880 + CVD不转强`. For `X` / no-trade states, use `禁追，不谈失效` in risk and put a concrete wait instruction in execution, e.g. `不追，等回踩VWAP/POC`.
- In compact/live mode, show the active side's plan only when the setup has a dominant side; show both sides only when there is no active side yet.
- Separate live and review modes. `简洁` mode should be directly executable; `详细` mode should add real diagnostic value with rows like `多计划`, `空计划`, `评分`, `事件`, and high-timeframe context.
- For this user, default the table to a safe left-side position with fully opaque header/cell backgrounds unless asked otherwise. If the script has a position input, add a default `自动避让` option that maps to `position.bottom_left`; keep `右下` only as an explicit manual choice because it often covers the latest candles/price action.
- For the user's execution-card indicators, avoid chart buy/sell markers by default. Keep `plotshape()` and `plotchar()` absent unless explicitly requested, and make any remaining labels structural rather than trade-signal labels.
- Treat CVD confirmation as an execution guard, not just a score: if CVD invalidates a long/short plan, show waiting/downgrade text instead of leaving the plan executable.
- Avoid unexplained abbreviations in Chinese table text; use readable trading language.
- After deleting chart markers or detail rows, also delete their related `input.*` settings and stale variables so the Settings panel stays clean.

## Pine源码 + TV实时数据交叉验证（2026-06-21新增能力）

当用户上传 Pine Script 源文件时，不仅要读懂代码结构，更要**将源码逻辑与 TV MCP 实时数据交叉验证**：

1. `read_file` 源码 → 识别评分公式、分级规则、冲突检测、CVD状态机
2. `chart_get_state` → 确认 study 列表
3. `study_values` + `pine_labels` + `pine_lines` + `pine_tables` → 获取全量实时数据
4. 源码规则 × 实时信号 → 得出确定结论
5. 结论嵌入分析卡博弈段或直接替代 auto_card 自算逻辑

**关键发现（2026-06-21 SVP v6 源码审计）：**
- DMI 决策表（`pine_tables`）是完整的决策引擎，含顺势/反转 0-10 评分 + A/B/C/X 分级 + 稳定K确认 + 四维冲突检测 + 市场差异化权重
- DMI 表的 grade/treatment/cvdState/invalid 比 auto_card 自算准确 3 倍
- CVD 吸收/派发信号优先级最高，覆盖普通增/减信号
- 两个 CVD 同时读取（SVP内 Session CVD + 独立窗格 1D CVD）交叉解读时间尺度矛盾

详见 `tradingview-indicator-analysis` 技能的 `references/pine-source-live-crossref.md` 和 `references/dmi-table-truth-source.md`。

## Pitfalls

- **🔴 用户可能上传了新版指标文件（2026-06-26）**: 用户工作区可能有旧的 `svp_indicator.txt` 文件，但用户会主动上传更新的版本（如 `指标svp_v10_优化版.txt`）。**永远以用户主动上传的文件为准**，不要假设磁盘上的文件是当前版本。用户说"这个才是我的指标"时，立即放弃之前读的文件内容。
- 当用户说"分析 X"时，先确认 TV 上的研究列表（通过 `chart_get_state` 中的 `studies` 列表），与用户的指标文件比对，确认版本一致。
- 用户的当前生产双指标为：SVP+ICT+VWAP+CVD (主；标题不含EMA但源码含EMA/FVG/MCP Data Window) + Volume Aggregated Spot & Futures (副；聚合量能/OI/CVD/覆盖率/Composite)。不要再假设还有独立 Open Interest 研究；先以 chart_get_state 实际 studies 为准。

- Pine version mismatch is common: a v6 CVD script cannot be pasted directly into a v5 overlay script.
- `plot()` of large oscillator values in `overlay=true` scripts can crush the price scale.
- Multi-object dashboards can hit TradingView object/performance limits; prefer table/data-window outputs for non-price diagnostics.
- `request.security_lower_tf()` improves precision but reduces available history and increases computation cost.
- If subtracting score weights, clamp with `math.min(math.max(score, 0), 10)`, not only `math.min(score, 10)`.
- Long one-line boolean/ternary expressions are fragile in Pine and hard to patch. Split key-level checks into helper functions (`f_near_level`) and intermediate booleans.
- **Pine Script is single-pass sequential.** Variables must be declared before any code that references them — this is unlike Python/JavaScript where function hoisting or import ordering can paper over declaration order. When inserting new logic blocks into an existing script, check the declaration line of every referenced variable (`grep -n`), and place the new block AFTER the last dependency, not just after the section that feels semantically related. Classic failure: inserting Session CVD (uses `isAsia`, `isLondon`, `isNY`) before the ICT session declarations at the bottom of the session block — and then doing the same for `bgcolor(isKillZone)` before `isKillZone` is defined. Fix: move the entire block past all its dependencies, even if that means breaking up a themed section.
- `alertcondition()` can produce misleading syntax errors with complex named arguments or non-ASCII messages; fall back to positional arguments and short ASCII titles/messages.
- **Unescaped quote compile blocker in inputs (2026-06-24):** When reviewing uploaded Pine without editing, still scan `input.*(..., tooltip="...")` and label strings for nested raw double quotes. A Chinese tooltip like `tooltip="右侧价格栏由"轴标: 日线开盘价"单独控制。"` looks visually harmless but breaks Pine parsing before any logic runs. Fix by removing the inner quotes, using Chinese corner quotes (`“轴标: 日线开盘价”`), or escaping if Pine accepts the context. Add this to the pre-delivery checklist alongside output count and banned-visual scans.
- **Narrative card dead code (v9.0+):** The compact action panel superseded the old narrative card output, but ~150 lines of `stateText`, `cardLine1-3`, `directionGuideText`, `actionGuideText`, `detailText`, `trendMiniText`, `volumeMiniText`, `eventMiniText`, `cvdMiniText`, `structureShortText`, `nowAdviceText`, and `focusedPlanText` assignments may still be present. Only `invalidText` and `watchText` from that block are consumed by the v9.0 action panel. Audit with `grep -c` on each variable and remove dead assignments.
- **SVP level creation timing (v9.3+):** When creating SVP extreme levels inside the `isNewPeriod` block, you MUST read `profileEngine.maxProfilePrice`/`minProfilePrice` BEFORE `profileEngine := VolumeProfileEngine.new().initialize()` replaces the old engine. `f_clearVpObjects/Data` only clears arrays, so scalar fields survive — but only until the engine reference is overwritten.
- Pine Script allows at most **64 plot counts per script on every plan**, including plots shown only in the Data Window or hidden with `display.none`. `plot*()` outputs, `alertcondition()`, `bgcolor()`, and `barcolor()` consume counts; `fill()` consumes one only when its color is series-qualified. `hline()`, `line.new()`, `label.new()`, `box.new()`, and `table.new()` consume zero plot counts. A `plot(series, color=seriesColor)` consumes two counts (value series + color series); `plotcandle()` can consume up to seven. Do not multiply all fills/backgrounds or count tables. Validate by compiling/commenting calls because TradingView reports the actual total.
- **Series-color plot counting (officially corrected 2026-08):** A basic `plot(series)` uses one count for its value series. A genuinely **series-qualified** `color` argument adds one, so `plot(series, color=seriesColor)` uses two. Do not treat every `input.color` as a series color automatically. `bgcolor(seriesColor)` uses one count, not two; `fill(..., color=seriesColor)` uses one count, while a fill with non-series color uses zero; `table.new()` uses zero. `plotbar()`/`plotcandle()` start with four OHLC series and add one for each series-qualified color/wick/border argument, up to seven. `display.data_window` and `display.none` change visibility, not quota. Use the compiler-reported total/comment-out method as final authority. See official Limitations page and `references/pine-plot-limit-quick-triage.md`.
- **Zone labels FVG/OB/BRK/LV (2026-07-09 final):** English only. **BOTTOM-RIGHT INSIDE box**: `x=right-inset`, `y=bot+ATR*lift`, `style_label_right`. User: 「改回英文」「是在框里面，不是在外面」. Not mid-center/outside. LV=Liquidity Void. Inputs `ZONE_LABEL_SIZE`/`ZONE_LABEL_X_IN`/`ZONE_LABEL_Y_ATR`.
- **EMA fill-only + write-disk (2026-07-09):** Transparent constant EMA plot colors for fill; claim fixed only after Desktop+upload+ready sha/grep. User 「文件没有改到」.
- **`for … by -1` (2026-07-09):** size=1 runtime step error → while reverse; guard empty loops.
- After encoding Data Window values into composite floats, document the decode formula in the plot title (e.g. `"Risk (R*1e4+D*1e2+W)"`) so future agents and external scripts can recover the individual components.
- If the user asks for opaque table styling, audit all dynamic state/highlight colors too (`color.new(..., 35)` can remain after header/cell defaults are opaque).
- **Background-color distinction for this user:** active ICT session background coloring is desired and should be preserved when already present; it helps distinguish the current Asia/London/NY session. KillZone background coloring is still rejected because it overlaps with session backgrounds — keep KillZone as text/action-panel context only. Do not add `plotshape()` or extra chart highlights without explicit approval. When in doubt, expose data through the action-panel table or Data Window only.
- **Trade controls were explicitly removed (v8.2.9).** Do not re-add `MIN_TRADE_RR`, `MAX_STOP_ATR`, `SHOW_TRADE_CONTROL_LINE`, or `tradeControlBlocked`/`tradeControlReason`/`tradeControlText`. The action-panel checklist also lost its `ckRr` entry. Risk protocol parameters (`RISK_PER_TRADE_PCT` etc.) remain as standalone Data Window exports but no longer gate trades.
- **Session bgcolor removal trap (2026-06-24):** When removing `bgcolor()` for ICT session backgrounds, carefully isolate what to delete. The session color inputs (`COLOR_ASIA`, `COLOR_LONDON`, `COLOR_NY`, `COLOR_LONDON_NY_OVERLAP`, `COLOR_ASIA_LONDON_OVERLAP`) and label background inputs (`ICT_LABEL_BG_COLOR`, `ICT_LABEL_BG_TRANS`) are still consumed by ICT session line/label rendering, SVP extreme sweep color matching, and merged labels. Only `ICT_BG_TRANSPARENCY` (dead after bgcolor removal) and the `bgcolor()` call itself are safe to delete. In one audit session, a `patch` old_string inadvertently included session colors, deleting 6 actively-used inputs that had 13 downstream references. Verify with `grep -c` on every deleted input — zero remaining references is the gating criterion. See `references/pre-delivery-settings-checklist.md`.
- **KillZone naming (v8.2.9+, 2026-06-24):** Use unified `伦敦开盘` / `纽约开盘` across all markets. **Never** use `白银`, `伦窗`, `纽窗`, `伦敦高波`, `纽约高波`, or emoji flags (`🇬🇧`/`🇺🇸`). Input groups and tooltips use "开盘窗口", not "白银时刻". "白银" is a mistranslation of "Silver Bullet" which is specifically the 10-11am window, not the broader KillZone.
- **`actionKillZoneLine` declaration order (v9.0, 2026-06-24):** `headerLine` concatenates `actionKillZoneLine`, but Pine is single-pass sequential. If `actionKillZoneLine` is defined at the action panel section (~L2297) and `headerLine` at ~L2208, the result is `Undeclared identifier`. **Fix**: define `actionKillZoneLine` immediately after `killZoneLabel` in the Session CVD block (~L983), and remove the duplicate definition from the action panel section.
- **`FINAL_ROWS` declaration order (v8.1, 2026-06-24):** `FINAL_ROWS = MARKET_ADAPTIVE_ENGINE ? (marketCrypto ? ...)` fails with `Undeclared identifier 'marketCrypto'` if market detection booleans (`marketCrypto`, `marketForex`, etc.) are defined AFTER `FINAL_ROWS`. **Fix**: move the entire market detection block (ticker parsing + market booleans) above `FINAL_ROWS` and `chartLineWindowMs`/`proLightMode`. This is the same single-pass sequential pitfall as `actionKillZoneLine` — all dependencies must be declared first.
- **Dark-theme invisible colors (2026-06-24, expanded 2026-06-25):** TradingView's dark theme background is ~`#131722`. Colors below `#1A1A1A` are essentially invisible as lines/labels on dark charts. Common victims include: `POC_COLOR = #0F0F0F` (the main structural POC line disappears into the background), `COLOR_DAY_LIQUIDITY = #0F0F0F` (near-black on black background). **Fix**: use visible mid-tones like `#78909C` (blue-grey), `#607D8B`, or `#FFD700` (gold) that work on both dark and light themes. During audit, verify ALL `input.color()` defaults against both dark and light TV themes. Safe floor for dark: `#3A3A3A`. Safe ceiling for light: `#C0C0C0`. Also check label sizes — `size.tiny` + dark color = doubly invisible. **Pre-delivery**: run `references/pre-delivery-settings-checklist.md` which includes a color visibility audit script. **⚠ White-theme trap (2026-06-25)**: do NOT flag `#000000` or near-black colors as P0 without first confirming the user's theme. `#000000` is perfectly visible on white theme. Ask before asserting a color bug — a wrongly-flagged P0 erodes trust and wastes time.
- **SHOW_OPEN_ONLY_ACTIVE 会话结束后不显示高低点 P0 bug (2026-06-25 修复):** 设计意图：`true`=会话进行中隐藏高低点，结束后自动创建。但存在4个致命缺陷导致高低点永不出现：(1) `barstate.islast` merge 块 L1251 `label.set_style(lvl.lb, style_none)` 将所有独立标签隐藏→原标签不可见；(2) 合并标签创建后原位置漂移，若 level 被排他则消失；(3) 会话结束时若价格已穿越高低点→同根K线扫掠→标签40%透明→实际看不到；(4) `f_cutoff_ms` 在实时K线用 `time`（K线打开时间）而非 `timenow`（当前时间）→ cutoff 可能偏移。**修复（v2026-06-25）：** ① ICTLevel/SessionState UDT 加 `isSessionEnd`/`sEndBar` 字段；② 会话结束创建时标 `isSessionEnd=true`；③ 扫掠检测加3根K线保护窗口（`barsPassed <= 3.0`）；④ merge 块跳过 `isSessionEnd` 级别，保留原独立标签并延长线；⑤ `f_cutoff_ms` 实时K线优先用 `timenow`；⑥ 6条 `plot()` 后备水平线（`display=display.pane`）独立于对象系统。DST 验证：`Asia/Shanghai`=UTC+8全年无夏令时✓；`Europe/London`/`America/New_York`=IANA自动处理✓。完整修复模式见 `references/session-hl-delayed-display-fix.md`。
- **SHOW_DO_LINE default to `false` (2026-06-24):** Daily open (DO) line is hidden by default. Users who expect it to show will think the feature is broken. Default should be `true` — the line is a commonly-used structural reference.
- **Default-visibility audit methodology (2026-06-24):** When any feature "doesn't show," audit ALL `input.bool()` defaults in a single pass — not just the one the user reported. In one session, three separate visibility kill-switches were found: `COLOR_DAY_LIQUIDITY=#0F0F0F` (invisible color), `SHOW_OPEN_ONLY_ACTIVE=true` (hid labels), and `SHOW_DO_LINE=false` (hid daily open). Scan with `grep "input\.bool"` and verify every default against expected behavior. **Pre-delivery**: run the full checklist in `references/pre-delivery-settings-checklist.md` before copying to desktop — catch invisible colors, bad defaults, and banned features before the user imports.
- **Day/week pool integration into action panel (2026-06-24):** Previous-day and previous-week high/low levels should appear in the top-right action panel so the trader sees structural proximity at a glance. Append to the `结构：` line as compact labels: `日↑` (above day high), `日↓` (below day low), `近日高` (near day high within 0.8 ATR), `近日低` (near day low), `周↑`, `周↓`, `近周高`, `近周低`. Compute with `prevDayHigh`/`prevDayLow`/`prevWeekHigh`/`prevWeekLow` from `request.security("D"/"W", high[1], ...)` using `barmerge.gaps_on, barmerge.lookahead_on`. Only show when the respective `SHOW_DAY_LIQUIDITY`/`SHOW_WEEK_LIQUIDITY` is enabled and data is not `na`. See `references/action-panel-day-week-pool.md` for the complete code pattern.
- **Sweep counter in action panel (2026-06-24, corrected 2026-06-25):** Append `N扫/M待` to the `确认：` line by iterating the global `levels[]` array and counting `evLvl.swept` (not `evLvl.isActive`). `isActive` means "session still in progress" — it is set to `false` when a session ends, regardless of whether the level was actually touched by price. Counting `isActive` as "unswept" incorrectly treats ended-but-untouched sessions as swept. Use `swept` (the boolean set by the sweep detection loop when price crosses the level): `evLvl.swept → sweptCount, else → unsweptCount`. Insert the counter computation AFTER the sweep detection loop but BEFORE `actionStateText` in the action panel section. See `references/sweep-counter-action-panel.md` for the complete implementation.
- **Lightweight Magnet Score — nearest unswept target (2026-06-26):** Community indicators like Liquidity Magnet score each resting liquidity pool 0-100. A lightweight alternative: iterate `levels[]`, find the nearest unswept ICT level by ATR-normalized distance, and expose `magnetNearestPrice` / `magnetNearestDist` (in ATR) to Data Window. In the action panel 结构 line, append `近0.8A` (0.8 ATR to nearest target). This tells the trader where price is most likely to be drawn next without the complexity of a full 0-100 scoring system. Also expose `ictSweptCount` / `ictActiveCount` to Data Window for external CD system consumption. **v10.2 upgrade (2026-06-26):** upgraded to full three-factor 0-100 score: distance 40% (5ATR=0, 0ATR=100) + freshness 30% (50hr=0, using `time - lvlC.createdAt` in ms) + priority 30% (`lvlC.priority * 20`, week=100, day=80, session=20-60). Selects highest-scoring level, not just nearest. Data Window encoding updated to `Mag*1e6+DistA*1e3+Score/1e3+ICT/1e6`. See `references/indicator-svp-v10-optimization-2026-06-26.md` §14.
- **Action panel trend scores + grade-based color (2026-06-26):** Add compact `多7空3` trend scores to the 结论 line (replaces verbose `actionSentimentText`). For background color, use grade-based transparency: A-grade=0 (most opaque, strongest signal), B-grade=30, C-grade=50. This lets the trader gauge signal strength at a glance without reading text. `color actionBgColor = displayLongA ? color.new(color.green, 0) : setupLongB ? color.new(color.green, 30) : setupLongC ? color.new(color.green, 50) : ...`. See `references/indicator-svp-v10-optimization-2026-06-26.md` §6.
- **Action panel 6th risk row (2026-06-26):** Add `风险：止损1.5A · 位3/确5/延0 · 磁78` as a 6th line using existing variables (`replayStopAtr`, `locationScore`, `confirmScore`, `extensionRiskScore`, `magnetScore`). Gives trader a complete risk snapshot: stop distance in ATR, location/confirmation/extension scores, and Magnet Score. No new calculations needed — reuses variables already computed for Data Window exports. See `references/indicator-svp-v10-optimization-2026-06-26.md` §16.
- **定调 line implementation (2026-06-24):** The v9.0 spec requires a `定调：` row synthesizing direction bias + HTF bias + DMI momentum + key structure verdict into one sentence. Variables: `actionBiasWord` (from active plan direction), `htfBiasText` (existing at L815), `dmiVerifyText` (existing at L1616), `actionStructureVerdict_tone` (priority: sweep reclaim/reject > active sweep > VWAP extreme > VA boundary > EMA alignment). See `references/action-panel-v90-with-labels.md` for the complete implementation.
- **Multi-TF bias in 定调 (2026-06-24):** The user explicitly wants ALL periods visible in the 定调 line — not just one selected HTF. Use `f_mtf_bias_str()` with `request.security()` per TF (15m/1h/4h/1D), reusing `f_htf_pack()` → `[close, ema(close,21), ema(close,55), sma(hlc3,50)]`. Output arrows: `↑`=bull (price≥VWAP & EMA21≥55), `↓`=bear, `→`=neutral, `—`=no data. Compact format: `"15m↑ 1h↑ 4h→ 1D↑"`. Place `f_mtf_bias_str()` near L815 after `htfBiasText` so it's declared before the action panel section. See `references/action-panel-v90-with-labels.md` for the complete implementation.
- **This user prefers `：` (Chinese colon) for action panel labels**, NOT `｜` (full-width pipe). The `action-panel-v90-no-labels.md` reference was loaded but the user explicitly reverted `｜` → `：`. The label prefixes (`结论：`/`结构：`/`确认：`/`执行：`) are KEPT — no-label mode is rejected for this user.
- **H1 label abbreviation gate (2026-06-24):** `updateLabel()` abbreviates `高→H` / `低→L` for ICT session labels on H1 charts, but this catches non-ICT labels that also contain ` 高`/` 低` (e.g. SVP `"周三 高"`). Gate the replacement: only apply when the name already contains session indicators (`亚`,`伦`,`纽`). Without this gate, SVP labels display as `"周三H"` instead of `"周三 高"`.
- **SVP extreme sweep lines (v9.3, 2026-06-24; corrected 2026-06-25):** From the SVP profile's `maxProfilePrice`/`minProfilePrice`, create ICT-style sweep lines extending right. Push into the same `levels[]` array for shared sweep detection, merged labels, and sweep counter. Labels use `f_svp_direction_name()` adapting to anchor: D→`"周三 高"`, W→`"上周 高"`, M→`"上月 高"`. Color matches the session that produced the extreme on D anchors; default `#555555` otherwise. Priority 6. NOT on right price axis per user preference. **Do not gate SVP level maintenance, merge labels, sweep detection, or cleanup behind `show_ict_lines` (`tf < 4H`)** — on 4H+ only hide/clean non-SVP ICT session lines, keep `lvl.priority == 6` SVP lines visible and updating. If `HIDE_SWEEPS_ON_HTF` is true, apply it only to non-SVP (`lvl.priority != 6`) so SVP swept lines remain visible on higher timeframes. SVP label size: unswept `size.small`, swept `size.small`; ordinary ICT unswept uses `ICT_UNSWEPT_LABEL_SIZE` (default small) and swept uses `ICT_SWEPT_LABEL_SIZE` (default tiny). Auto SVP and S-VWAP anchors for this user's dashboard must use the fixed shared rule: `<1H → D`, `1H to <4H → W`, `>=4H → M`; do not add market-specific exceptions (metal/stock/forex forced D/W) unless the user explicitly asks. See `references/svp-extreme-sweep-lines.md`.
- **Dead code audit (2026-06-24):** Compact v9.0 action panel renders old narrative card variables dead (`stateText`, `cardLine1-3`, `directionGuideText`, `actionGuideText`, `detailText`, plus mini text vars and `focusedPlanText`/`nowAdviceText`). Audit pattern: `grep` each variable, if defined once and never referenced outside its own block → dead. Narrative block can be trimmed ~150 lines by keeping only `watchText`+`invalidText` (both consumed by `lineAction` and invalidation pricing). See `references/dead-code-audit.md`.
- **Module prefix duplication (v9.0, 2026-06-24):** When row templates include module names (e.g. `"结构：SVP " + value + " · VWAP " + value + " · EMA " + value`), the value text MUST NOT also include the module name. Otherwise `VWAP VWAP延` appears. **Fix**: strip module names from value texts (`"VWAP延"` → `"延"`, `"EMA多"` → `"多"`) and let the row template provide them.
- **CVD session notation (v8.2.9+, 2026-06-24):** Use `+/-/~` (universal financial standard), **not** `↑↓→` arrows. `+` = net buying, `-` = net selling, `~` = neutral. **v9.0+ addition**: CVD session values now include actual numeric magnitude via `f_fmt_cvd()` (see `references/action-panel-v90-with-labels.md`).
- **Action panel row labels (v8.2.9+, 2026-06-24):** CVD session row is `CVD分时` (not `CVD会话`). Checklist row is `条件` (not `核对`). CVD anchor style is `主D`/`主W`/`主M` (not `本日`/`本周`/`本月`).
- **Complete feature removal means all four layers**: remove (a) `input.*` declarations, (b) calculation variables, (c) all action-panel/table branch references, and (d) orphaned Data Window `plot()` calls. Follow with `grep -c <identifier>` to confirm zero residuals — one leftover reference produces `Undeclared identifier`.
- **User prefers files on Desktop as `.txt`.** When delivering a Pine Script file, copy to `C:/Users/Administrator/Desktop/<name>.txt` and share that path. The web UI upload path is not directly downloadable. After each edit round, sync both locations.
- Local checks can validate text/file structure, but final syntax validation must happen in TradingView Pine Editor.
- When adding Pro features, do not overwrite the user's prior enhanced file; save a new versioned output unless the user asks for in-place edits.
- **Pine normalization + community refactor (2026-06-25):** When the user asks to normalize/refactor a mature dashboard, search community patterns before editing, preserve the user's anchor preferences and scoring weights, remove only proven dead/display-only controls, and verify with unused-input/output-count scans. For a true compact action panel, keep one cell, no ticker header, no duplicated module/direction prefixes, and merge `资金/核对` rather than adding another row. See `references/pine-normalization-community-refactor.md`.
- **`request.security()` for prev day/week high/low returns na on crypto (2026-06-26, critical):** `request.security(syminfo.tickerid, "D", high[1], barmerge.gaps_on, barmerge.lookahead_on)` can return `na` on crypto 7×24 markets due to exchange timezone mismatches and bar boundary alignment. When the data source is `na`, no line is created — the level is permanently invisible regardless of draw gate, axis gate, or extension loop fixes. **Fix: replace with chart-based tracking** using `var` state variables + `ta.change(time("D"))`: track `curDayHigh`/`curDayLow` each bar, save to `prevDayHigh`/`prevDayLow` on day boundary. Same pattern for week. This eliminates 5 `request.security` calls (13→6), works 100% on crypto, and updates in real-time. See `references/indicator-svp-v10-optimization-2026-06-26.md` §11. **When to still use request.security:** different symbol data, or chart TF >= daily where `ta.change(time("D"))` fires every bar.
- **SMT cross-exchange matching (2026-06-24, v9.4 fix):** The old auto-pair used hard `==` ticker checks (`stdTicker == \"BINANCE:BTCUSDT\"`) which silently failed on BYBIT/OKX/KUCOIN exchanges. **v9.4 fix:** Replaced with `f_is_btc_pair()` and `f_is_xau_pair()` helper functions matching across all major exchanges via `str.contains(t, \"BTCUSDT\") or str.contains(t, \"BTC/USDT\")`. Also separated `stdTickerUpper` for case-insensitive matching. Each mode branch now only handles its own ticker(s); cross-market mapping belongs in the auto/fallback branch. == \"BTC/ETH\"` branch contains `syminfo.tickerid == \"OANDA:XAUUSD\" ? \"BINANCE:ETHUSDT\" : ...` — gold accidentally maps to ETH. Fix: each mode branch should only check its own ticker(s); cross-market mapping belongs in the auto/fallback branch. **v10.2 exchange-prefix auto-detection (2026-06-26):** Extract exchange from `syminfo.tickerid` via `str.contains()` and construct `EXCHANGE:ETHUSDT` so SMT compares BTC vs ETH from the **same exchange** (OKX:ETHUSDT for OKX users, BYBIT:ETHUSDT for Bybit users, etc.). Supports BINANCE/OKX/BYBIT/COINBASE/KRAKEN, falls back to BINANCE. See `references/indicator-svp-v10-optimization-2026-06-26.md` §15.
- **SMT divergence detection: swing pivot vs fixed-window (2026-06-26):** Using a fixed N-bar change rate (`(close - close[5]) / close[5]`) for SMT divergence produces false signals when the window doesn't align with actual swing pivots. **Better approach**: use `ta.highest(high, 10)` / `ta.lowest(low, 10)` to detect actual swing extremes, then require the reference instrument to fail to confirm: `bool smtBearDiv = smtMyNewHigh and smtRefClose < nz(smtRefSwingHigh[1], smtRefClose)`. Add `close > close[3]` / `close < close[3]` as short-term momentum confirmation. This fires only on real swing extremes, not arbitrary window endpoints. See `references/indicator-svp-v10-optimization-2026-06-26.md` §3.
- **ICT SMT standard pairs + positive/negative correlation logic (2026-06-26):** ICT defines a specific set of correlated pairs for SMT divergence — NOT just "BTC vs ETH". Using the wrong pair (e.g. ES vs RTY instead of ES vs NQ) or applying positive-correlation logic to a negative-correlation pair produces inverted signals. **Standard pairs**: positive correlation = BTC/ETH, ES/NQ (NOT ES/RTY — Russell 2000 is not the ICT standard), EUR/USD↔GBP/USD, XAU/XAG; negative correlation = BTC/DXY, XAU/DXY, EUR/USD↔DXY. **Divergence logic differs by correlation type**: positive-correlation bear div = I make new high but reference does NOT (reference weakness); negative-correlation bear div = I make new high and reference ALSO makes new high (DXY should fall when BTC rises — if DXY rises too, that's the divergence). The `smtIsNegative` boolean flag gates which logic branch fires. **Auto-mode mapping**: BTC→same-exchange ETH, XAU→XAG, EURUSD→GBPUSD, GBPUSD→EURUSD, ES→NQ. See `references/ict-smt-standard-pairs.md` for the full pair table, correlation-direction logic, and the Pine implementation pattern with intermediate booleans (avoids the multi-line expression syntax error).
- **HTF structural bias via `ta.vwap()` (2026-06-24):** Do not use `ta.vwap(hlc3)` inside a `request.security()` HTF pack for structural bias. `ta.vwap()` is daily-reset, so its value inside a 4h/D HTF context varies by time-of-day rather than reflecting a stable structural reference. Use `ta.sma(hlc3, 50)` instead — a 50-period SMA on 4h ≈ 8 days of structural context. The main-chart anchored VWAP bands are unaffected; this only changes the HTF bias filter. **Naming hygiene (2026-06-26):** When the HTF pack returns `sma(hlc3, 50)` as its fourth value, name the receiving variable `htfSma50` (not `htfVwap`) and the function `f_htf_trend_pack()` (not `f_htf_pack()`). A misleading name like `htfVwap` causes maintainers to think VWAP is used for HTF bias when it's actually SMA50 — this led to incorrect "add real VWAP to HTF" suggestions in one session. Use `replace_all=true` since the function is called in 6 places.
- **Sweep detection gap-through blind spot (2026-06-24):** `sameBarTouch` only catches sweeps where price touches the level on the current bar (`high > level and high[1] <= level`). When price gaps entirely through a level without touching it (`low > level` for highs, `high < level` for lows), the sweep is missed. Add a `gapThrough` check: bar is fully on the other side AND previous bar was still within the level. Combine: `if sameBarTouch or gapThrough`.
- **SVP extremes label spacing (v9.3+, 2026-06-24):** When adding SVP high/low sweep lines, the `f_svp_direction_name()` helper must insert a space between day-name and direction: `f_day_name_from_time(endTime) + \" \" + dir` → `\"周三 高\"`, NOT `f_day_name_from_time(endTime) + dir` → `\"周三高\"`. This user explicitly corrected the concatenated form — they want ICT-style spacing matching session labels like `\"周二 亚高\"`. Same applies to W/M anchors: `\"上周 高\"`, `\"上月 低\"`. See `references/svp-extremes-sweep-lines.md` for the complete pattern.
- **Dead `else na` code block (2026-06-24):** In method-based Pine code, `if not na(obj) ... else na` is common after refactoring from `if/else` to `if`-only. The standalone `else na` compiles without error but produces a no-op — 11 such blocks were found in `f_clearVpObjects()`. Delete them; `if` without `else` is valid Pine.
- **Calibration feedback into decision system (v9.3+, 2026-06-24):** Forward calibration data (`calLongRate/calShortRate/hit counts`) exists but was display-only. Add `calWeak` flag when hit rate <40% with ≥5 samples, and append ` ⚠低` to `定调` line via `calibrationTextFull`. The `calLongWeak`/`calShortWeak` booleans gate by `not na(calLongRate) and calLongTotal >= 5 and calLongRate < 40`. When `calWeak` is true, the calibration suffix warns the trader that recent signal quality is poor — this prevents over-trusting a stale scoring model.
- **CVD quality guard pattern (2026-06-24):** Add `CVD_QUALITY_GUARD`, `CVD_MIN_LTF_SAMPLES`, and `CVD_SIGNAL_HALFLIFE_BARS`. Compute `cvdLtfSamples`, `cvdHasVolume`, `cvdSampleOk`, `cvdQualityOk`, `cvdQualityText`, and `cvdEventFresh`; require `cvdQualityOk` and freshness for absorption/divergence qualified booleans. Show weak states (`估算弱`, `样本少`, `信号旧`) rather than upgrading A/B signals. Export `CVD Quality (OK*100+LTF samples)` to Data Window.
- **前日/上周池独立显示规则（2026-06-24, corrected 2026-06-25, root-caused 2026-06-26）:** `SHOW_DAY_LIQUIDITY` / `SHOW_WEEK_LIQUIDITY` must directly govern whether PDH/PDL/PWH/PWL are created. Do **not** gate them through `show_ict_lines` or any ICT session visibility switch; users expect liquidity pools to remain visible even when session lines are hidden. Keep separate delete branches for day/week pools so turning the input off removes objects immediately. For day/week pools use `request.security(..., barmerge.gaps_on, barmerge.lookahead_on)` so HTF prices persist on intraday bars. **Root cause (2026-06-26):** `line.new(bar_index, price, bar_index, price)` creates a **zero-length line** — it's invisible until `line.set_x2(lvl.ln, bar_index)` extends it on each subsequent bar. If the sweep/extend loop is gated behind `if SHOW_ICT_LEVELS`, lines created by `f_make_liquidity_level()` stay at zero length and never appear. **Fix (two parts):**
1. **Ungate three layers:** (1) the sweep/extend loop itself, (2) sweep event detection (`sweptHighNow`/`sweptLowReclaimed`), (3) Magnet Score computation. All three must run with only `array.size(levels) > 0` as their condition, not `SHOW_ICT_LEVELS and array.size(levels) > 0`.
2. **Use `bar_index + 1` not `bar_index` for line endpoints:** `line.new(bar_index, price, bar_index, price)` creates a **zero-length line** (same start and end bar) that is invisible on TradingView. Even after ungateing the extension loop, the first bar's line is still zero-length until the next bar fires `line.set_x2`. **Fix:** create with `line.new(bar_index, price, bar_index + 1, price, ...)` (1-bar initial length = immediately visible) and extend with `line.set_x2(lvl.ln, bar_index + 1)` (not `bar_index`) so the line always extends one bar into the future and remains visible even on the last/current bar. This applies to ALL `f_make_liquidity_level()` calls and the extension loop for both swept and unswept branches.

This adds a **fourth visibility layer** to the "level doesn't show" audit: (1) data source, (2) draw gate, (3) axis gate, (4) **line-extension loop** — check that `line.set_x2()` is called on every bar regardless of unrelated feature toggles, AND that the initial `line.new()` has non-zero length. See `references/indicator-svp-v10-optimization-2026-06-26.md` §10.
- **Multi-market CVD session channel adaptation (2026-06-25, ⚠ partial reversal 2026-06-26):** The 3-channel Session CVD (Asia/London/NY) is designed for 24/7 crypto markets. **Community consensus** (ICT, Reddit r/InnerCircleTraders): crypto=keep 3 channels, forex=London+NY only (disable Asia CVD), metals=XAUUSD uses London+NY only (gold barely trades in Asia). **⚠ 2026-06-26 correction:** In one session, `cvdUseAsiaChannel` was proactively expanded to `marketCrypto or marketMetal or marketForex` during an audit — this **contradicts** the community consensus above. The user did not explicitly request this expansion. If the user reports noisy/incorrect CVD signals on forex or metals, **revert** to `marketCrypto` only. The expansion should only stay if the user explicitly confirms they want Asia CVD on all markets.
- **Asian KillZone missing (2026-06-26):** ICT defines four KillZones: Asian (20:00-22:00 NY = ~09:00-12:00 Shanghai), London (02:00-05:00 ET = 07:00-09:30 London), NY AM (08:20-11:30 NY), NY PM. Many indicators only implement London + NY KillZones and miss the Asian one entirely. **Fix:** add `KILLZONE_ASIA_TIME = input.session("0900-1200", "亚洲KillZone时间", ..., group=KILLZONE_GROUP)` using `TZ_ASIA` for the timezone. Add `effKzAsiaTime` to the market-adaptive layer (crypto/metal: 0900-1200, forex: 0900-1100, other: 0900-1200). The action panel `killZoneLabel` must include `"亚洲开盘"` as the first option in the priority chain. Without this, the Asian session open — a significant liquidity event for crypto and metals — has no KillZone marking.
- **Cross-element hex color collision audit (2026-06-26):** When changing any element's color, scan ALL other elements for the same hex value — not just the one being changed. In one session, EMA 55 default `#FF9800` collided with Monthly VWAP `#FF9800` AND Asia session `#FF9800` — three different elements with identical colors, making them indistinguishable when overlapping. **Audit pattern:** before final delivery, extract all `input.color(#XXXXXX)` defaults, group by hex value, and flag any hex appearing in 2+ elements that could visually overlap. Common collision pairs: EMA lines vs VWAP lines vs session background colors. Fix by assigning distinct hexes per visual category: trend indicators (greens/reds), volume indicators (cyans/purples), session markers (orange/green/red), structural levels (blue-grey/purple).
- **Input group `const string` consolidation (2026-06-26):** Pine Script inputs are organized by `group=` parameter. The `const string GROUP = "..."` definitions should ALL be declared at the top of the file in a single block (lines 9-23), not scattered throughout the input section. Scattered definitions (e.g. `const string KILLZONE_GROUP` at line 246, `const string CVD_SESSION_GROUP` at line 244) cause maintenance confusion and duplicate-definition risk when refactoring. **Audit pattern:** `grep -n "^const string.*_GROUP"` — all hits should be in the first 25 lines. If any appear later, move them to the top block and delete the scattered definitions.

- **CVD divergence swing magnitude filter (2026-06-25):** NikaQuant's Quantum Liquidity Map uses a 3-condition gate for CVD divergence: (1) price prints new swing extreme, (2) CVD fails to confirm, (3) swing itself exceeds 1.5× 14-bar ATR. Without condition (3), minor price wiggles that happen to correlate with CVD noise produce false divergence signals. **Implement**: `cvdDivQualified = (newSwingExtreme and cvdNonConfirm and swingMagnitude > 1.5 * ta.atr(14))`. This is the single highest-impact false-signal reduction pattern in the community. Audit source for raw `cvdBearDiv`/`cvdBullDiv` that only check new extreme + non-confirm and add the magnitude gate before letting divergence influence grade or alerts.
- **CVD divergence slope-direction confirmation (2026-06-26):** A third gate beyond swing magnitude: require CVD slope to confirm the divergence direction. Bear divergence (price new high, CVD lower high) → `cvdSlope <= 0` (CVD must be falling or flat). Bull divergence (price new low, CVD higher low) → `cvdSlope >= 0` (CVD must be rising or flat). Without this, divergences where CVD is still accelerating in the divergence direction fire as false signals. **Implement**: `bool cvdBearDiv = cvdBearDivRaw and cvdDivSwingOk and cvdSlope <= 0`. See `references/indicator-svp-v10-optimization-2026-06-26.md` §4.
- **ICT overlap merging for day/week pools — DEPRECATED (2026-06-26, reverted same day):** A previous version of this skill recommended merging prev-day high/low with today's session high/low when they overlap within `max(mintick*8, ATR*0.15)`, skipping the day pool line creation. **This was wrong on three counts and has been reverted:** (1) **Infinite delete-recreate loop** — the creation block used `if showDayPool and (newDayPool or na(prevDayHighObj) or na(prevDayLowObj))` with conditional creation (`if not dayHighOverlapsSession`). When the low overlaps and isn't created, `na(prevDayLowObj)` stays true → every bar re-enters the if → `f_delete_liquidity_pair` deletes the high too → high flickers, low never appears. (2) **Threshold too large** — 0.15 ATR = $3 on gold, $120 on BTC, 4.5 pips on EURUSD → most of the time everything "overlaps" → nothing displays. (3) **Conceptually wrong** — prev-day high/low and today's session high/low are DIFFERENT-DATE liquidity pools. They are different targets even if prices coincide. Merging them loses information. **Correct approach:** always create both prev-day high and low unconditionally on `newDayPool`. Only merge prev-day vs prev-WEEK (same historical period, `weekHighDuplicatesDay` dedup is correct). See `references/indicator-svp-v10-optimization-2026-06-26.md` §12 (marked SUPERSEDED) and §17 for the revert.
- **ICT overlap merging for day/week pools (2026-06-26):** When prev day high/low overlaps a session high/low within `max(mintick*8, ATR*0.15)`, skip creating the day pool line — let the session line (with its color: Asia orange, London green, NY red) mark that level instead. Check `stAsia.sHigh`/`stLondon.sHigh`/`stNY.sHigh` (SessionState UDT fields) after `manageSession()` runs. Only apply to day pools; week pools have their own `weekHighDuplicatesDay` dedup. See `references/indicator-svp-v10-optimization-2026-06-26.md` §12.
- **Day/session overlap inheritance must preserve weekday-price label (2026-06-25 user correction):** When skipping a duplicated previous-day high/low because it overlaps Asia/London/NY session high/low, do **not** merely omit the day line. Re-label the inherited session `ICTLevel.name` to the day-pool name (`"周三 高 65420.5"` / `"周三 低 64100.0"`) so the chart still shows weekday + side + price while retaining the session line color. Pattern: compute `inheritedDayHighName = prevDayName + " 高 " + str.tostring(prevDayHigh, format.mintick)`, then if `f_near(prevDayHigh, stAsia.sHigh, threshold) and not na(stAsia.lvlHighObj)` set `stAsia.lvlHighObj.name := inheritedDayHighName` (same for London/NY and lows); otherwise create the standalone day pool with `f_make_liquidity_level()`. Also update `updateLabel()` to avoid duplicated prices: if `dispName` already contains `str.tostring(price, format.mintick)`, render `dispName` directly instead of appending `": price"`.
- **Day/week liquidity swept labels stay small (2026-06-25 user correction, expanded 2026-06-26):** Previous-day and previous-week high/low pools should use their own label-size inputs for both unswept and swept states, defaulting to `size.small`. Do not route day/week swept pools through generic `ICT_SWEPT_LABEL_SIZE` when it defaults to `size.tiny`, because the user expects day/week swept lines to remain readable. **2026-06-26 broader correction:** The user explicitly said **ALL swept labels** (not just day/week) should be `size.small` — `ICT_SWEPT_LABEL_SIZE` default changed from `size.tiny` to `size.small`. The user said "扫线应该也是small" — swept liquidity lines are important structural references, not secondary decorations. In `updateLabel()`, detect day pools by weekday names without session abbreviations (`亚/伦/纽`) and week pools by `"上周"`, then set `activeSize` and `sweptSize` from `DAY_LIQUIDITY_LABEL_SIZE` / `WEEK_LIQUIDITY_LABEL_SIZE`. For the simpler and more robust detection pattern, use `isDayPool = str.contains(name, " 高") or str.contains(name, " 低")` — this catches all day-pool labels regardless of which weekday name is embedded, without needing to enumerate session abbreviation exclusions.
- **Day liquidity color distinct from POC (2026-06-25 user correction):** On the user's white TradingView theme, near-black is visible, but previous-day high/low should not share `#0F0F0F` with POC. Use a distinct blue-grey such as `#455A64` for `COLOR_DAY_LIQUIDITY`; keep POC near-black if desired. This is a semantic collision issue, not a dark-theme invisibility bug.
- **Session CVD Asia channel default (2026-06-25 user correction):** For market-adaptive mode, default the Asia Session CVD channel to crypto only (`not MARKET_ADAPTIVE_ENGINE or marketCrypto`). Do not include metals/forex by default; community guidance and the user's market emphasis treat metals/forex as London+NY-dominant. If the user explicitly wants Asia CVD on XAU/FX, make it an opt-in input rather than hardcoding `marketMetal or marketForex`.
- **NPOC zero-length line consistency (2026-06-25):** Apply the same non-zero-length rule to nPOC lines as to liquidity lines: create with `line.new(endBar, price, endBar + 1, price, ...)` and extend with `line.set_x2(np.ln, bar_index + 1)`. Otherwise nPOCs can be briefly invisible on the creation/current bar even though the later extension loop eventually updates them.
- **Labels with embedded prices — REVERTED (2026-06-26):** A previous instruction said to embed prices in label names (`"周三 高 65420.5"`). This was WRONG because `updateLabel()` already appends `: price` to the display name — embedding the price at creation produces `周三 高 65420.5: 65420.5` (duplicated price). **Correct approach:** create labels WITHOUT the price (`"周三 高"`, `"上周 低"`), and let `updateLabel()` handle the price display uniformly: `label.set_text(lb, dispName + ": " + str.tostring(price, format.mintick))`. This applies to ALL `f_make_liquidity_level()` calls — day pools, week pools, and any other liquidity level. The user explicitly reported the duplication as a bug ("价格重复了").
- **Multi-timeframe linked action panel (2026-06-26):** Do not waste the right-top HUD header on obvious taxonomy like `5m/15m执行 · 1h/4h结构 · 1D背景`. The user strongly corrected this: the panel must explain how the current timeframe links to higher/lower timeframes. Header should use `联动：低周触发/本级定结构/高周定方向 · 高周1D→结构1h/4h→执行5m/15m · 当前高周4h↑ · 看...`. Keep `计划：` as the last line and make it timeframe-linked: execution charts say `上看结构... 下按本K确认`; structure charts show both long/short route plans and hand off to execution TF; background charts only define preferred side and wait for structure. Add `高周逆风降级` when active side conflicts with HTF bias. Also ensure `磁吸` names exact levels and `评估` includes total score + stop + R:R + target magnet. See `references/action-panel-mtf-linked-plan.md`.


- **Action-panel value-text prefix duplication (v9.0+, 2026-06-25):** When row templates include module names (e.g. `"确认：" + actionIctText + " · " + actionCvdText`), the value variables MUST NOT also carry the module prefix. Common failure patterns: `actionIctText = "ICT " + lastEventName + "收回"` renders as `确认：ICT ICT 周四亚高收回`; `actionCvdText = "CVD " + cvdAnchorLabel + cvdStateText` renders as `... · CVD CVD 日买盘`. **Fix**: strip `"ICT "` and `"CVD "` from the value builders and let the row template supply them once. Same rule applies to `"结构：SVP " + actionValueText` — if `actionValueText` already contains `VAH上`/`VAL下`, keep the template prefix only.

- **CVD session direction notation inconsistency (v8.2.9+, 2026-06-25):** Session CVD numeric values should use the universal financial standard `+/-/~` via `f_fmt_cvd()`. The dominant-session hint (`cvdDirectionHint`) must use the same notation, not arrows (`↑↓→`). A mismatch like `亚+15K 伦-3.2K 纽~0` plus `亚主↑` is visually confusing. **Fix**: `cvdDirectionHint := " " + cvdLeadSession + (cvdLeadSlope > 0 ? "+" : cvdLeadSlope < 0 ? "-" : "~")`.

- **DST/timezone Pine verification checklist (2026-06-25):** When auditing a Pine indicator with ICT sessions, verify timezone handling: (1) `Asia/Shanghai` → UTC+8 year-round, no DST transition → session timing always correct; (2) `Europe/London` and `America/New_York` → TradingView's `time()` function uses IANA timezone DB which auto-handles DST; (3) `f_cutoff_ms` should use `timenow` (not `time`) on `barstate.islast` to prevent off-by-one-bar cutoff drift; (4) session overlap tooltips must explain summer/winter shift (London 08:00 BST=Beijing 15:00 summer, 08:00 GMT=Beijing 16:00 winter). Never hardcode UTC offsets — always use IANA timezone strings with `time()`.

- **Output plot-count audit before delivery (officially corrected 2026-08):** Start with one count for each value series generated by `plot()`/`plotchar()`/`plotshape()` etc.; add one for each genuinely series-qualified color/textcolor argument. `plotbar()`/`plotcandle()` use four OHLC counts plus series color arguments (up to seven). `alertcondition()`, `bgcolor()`, and `barcolor()` use one each. `fill()` uses one only for a series color. `table.new()` uses zero. Data Window-only and `display.none` plots still count. Prefer compressing low-priority Data Window diagnostics into documented packed values and use drawings/tables where semantics allow, but never use a blanket `plots*2 + fills*2 + bgcolors*2 + tables` estimate. When near 64, compile and comment out one call at a time; the compiler-reported delta is authoritative.
- **🔴 一条 `na` 腿毒化整条聚合链，且静默走进「不该发生」的分支（2026-09-10 实战 P0）:** 跨来源求和（成交量/OI/多所价格）用 `array.sum()` 或裸 `+` 链。Pine 的 `array.sum` **遇任一 na 返回 na**；而 `request.security(..., ignore_invalid_symbol=true)` 对不存在的腿（例：**COINBASE 没有永续合约**）返回 `na` 是**设计行为**。于是 `AggregatedVolume` 变 na，而 `na > 0` 与 `na <= 0` **在 Pine 里都是 false** → 两个互补分支同时落空 → 代码静默落入「异常态」分支（本例 `Coverage Feed Mode = 4`）→ 状态机把「数据缺失」误判为「指标无效」→ 下游 A 级授权永久被禁。**全程零报错**，所以极难发现。
  - **修法**：所有跨来源求和一律 `nz()` 逐元素累加（`Type = 0.0` + `for` 循环 `Type += nz(array.get(type, i))`）。缺失的腿只降级自己，不毒化整条链；全缺时落到设计内的回退分支（回退单图），而不是异常态。覆盖率行仍照实报 `聚合4/5`，**不违反「不静默削源」**。
  - **审计动作**：同一文件里对称的两条链（例 OI 聚合 vs 成交量聚合）要**放在一起比对 nz 覆盖率** —— 常见病态是「OI 侧用了 nz、成交量侧漏了」。凡是代码里有 `x > 0` / `x <= 0` 这类互补判断，都要追问一句「x 为 na 时会怎样」。
  - **验收不能信源码**：用「旧版必然为 X、新版不可能为 X」的行为判据（本例 `Feed Mode = 4` + `Dominance = 0` 只可能出现在 na 分支 → 等同「装的还是旧版」）。修好后实测 `Feed Mode 4→1`、`Dominance 0→40`、`Valid Code 0→2`。
  - 完整现场证据链、通类自检规则与 grep 筛查见 `references/pine-na-aggregate-poisoning-20260910.md`。
- **Pine UDT `na` short-circuit pitfall (2026-06-24, reinforced 2026-06-25):** In Pine Script v5, `not na(obj) and obj.field` does NOT reliably short-circuit when `obj` is a User Defined Type. Even with the `na()` guard, accessing `.field` on a `na` UDT variable causes `Cannot access the '<Type>.field' field of an undefined object. The object is 'na'.` at runtime. **Fix**: use explicit `if not na(obj)` blocks instead of `and` chains: `bool swept = false; if not na(obj) -> swept := obj.field`. This applies to all optional UDT handles — `ICTLevel`, `VolumeProfileEngine`, `NakedPOC`, `SessionState`, etc. Never chain `na()` guard + field access in the same `and` expression for UDTs. Before delivering, grep for `not na(...Obj...) and ... .field`; SVP sweep alerts commonly fail on `svpHighObj.swept` / `svpLowObj.swept` at bar 0. See `references/pine-udt-na-short-circuit.md` for the general pattern and `references/pine-udt-na-svp-alerts.md` for the SVP alert-specific fix.
- **Pine v5 literal syntax traps — multi-line strings, array declarations, and function references in `request.security()` (2026-06-26):** Three concrete compile-time blockers encountered during a live v10 indicator refactor:
  1. **Multi-line string literals are illegal.** Pine v5 strings must close on the same line. Concatenating table rows with real line breaks like `headerLine + "\n" + ...` must use the escaped `\n` inside the quotes; writing the actual newline between quotes produces `mismatched character '\n' expecting '"'`. **Pattern**: build multi-line `table.cell()` text with `line1 + "\n" + line2 + "\n" + line3` on a single source line.
  2. **Array type annotation position matters.** Use `string[] tfs = array.from(...)` (type first, then identifier). Writing `string tfs[] = array.from(...)` produces `'string' is not a valid type qualifier. Possible values: 'const', 'simple', 'series'`. Same rule for `int[]`, `float[]`, `bool[]`, and UDT arrays.
  3. **`request.security()` requires a function CALL (with parentheses), not a bare reference.** Pass `f_htf_pack()` as the expression argument. Passing `f_htf_pack` (no parens) triggers `Undeclared identifier 'f_htf_pack'` because Pine v5 treats the bare name as a variable lookup, not a function reference. The `should be called on each calculation` warning is caused by placing `request.security()` inside a `for` loop or `if` block — NOT by using parentheses. Fix the warning by unfolding the loop into separate top-level `request.security()` calls, each with `f_htf_pack()`. (CORRECTION 2026-06-26: a previous version of this pitfall advised removing parens — that was wrong and causes the exact compile error it was supposed to prevent.) See `references/pine-v5-literal-syntax-traps.md` for the before/after pattern.
  - See `references/pine-v5-literal-syntax-traps.md` for before/after snippets and a grep-based pre-delivery check.
  - See `references/community-sweep-rejection-action-panel-gaps-2026-06-26.md` for the community audit findings on sweep rejection confirmation (P0 gap), action panel missing R:R + target price (P0), OTE 62-79% zone (P1), the 10-point pre-trade checklist standard from 6 community sources, and the full feature comparison matrix vs LuxAlgo/Trading IQ/JOAT/Liquidity Magnet.
- **Pine v5 multi-line parenthesized expressions are illegal (2026-06-26):** Unlike Python/JavaScript, Pine v5 does NOT allow a boolean/ternary expression to span multiple lines inside parentheses — e.g. `bool x = cond and (\n    (a and b) or\n    (c and d))` produces `Syntax error at input 'end of line without line continuation'` at the first line break. Pine requires each statement to complete on a single line. **Fix pattern**: split the multi-line `or`/`and` chain into named intermediate booleans, one per line, then combine them on a final single line: `bool part1 = a and b` / `bool part2 = c and d` / `bool x = cond and (part1 or part2)`. This is readable, patchable, and compiles. **Pre-delivery grep check**: search for lines ending with `(`, ` or`, or ` and` (excluding comments) — any hit is a likely multi-line expression that will fail to compile. See `references/pine-v5-literal-syntax-traps.md` § "Multi-line boolean expressions" and `references/ict-smt-standard-pairs.md` for a worked example from the SMT divergence fix.
- **`dayofweek()` timezone for day-name labels (2026-06-26):** `f_day_name_from_time(prevDayTime)` was hardcoded to `dayofweek(ts, "Asia/Shanghai")` but `prevDayTime` is assigned from `nz(time[1], time)` — the **chart's timezone**, not Shanghai. On a UTC chart, Wednesday's last bar (Wed 23:00 UTC = Thu 07:00 Shanghai) would display "周四" instead of "周三". **Fix:** use `dayofweek(ts, syminfo.timezone)` for any function that converts a chart-derived timestamp to a weekday name for display. The 3 other `dayofweek(time, "Asia/Shanghai")` calls in session management code ARE correct — they name the day for ICT Asian session display, which is defined in Shanghai time. See `references/indicator-svp-v10-optimization-2026-06-26.md` §18.
- **Sweep rejection confirmation gap (2026-06-26, P0 community audit):** The current sweep detection `isSwept := lvl.isHigh ? (high > lvl.price) : (low < lvl.price)` counts ALL price crossings as sweeps — including genuine breakouts where price closes beyond the level and continues. Every high-quality community sweep indicator (Quantum Algo, JOAT Sweep+Cluster, FluxCharts, Zeiierman, Alchemy Markets) distinguishes true sweeps (wick through + **close back inside** = rejection) from breakouts (close outside = continuation). Without this filter, `ictSweptCount` is inflated, Magnet Score is corrupted, and the 确认 line reports false sweep events. **Recommended fix**: `isSwept := lvl.isHigh ? (high > lvl.price and close < lvl.price) : (low < lvl.price and close > lvl.price)`. See `references/community-sweep-rejection-action-panel-gaps-2026-06-26.md` §1.
- **Action panel missing R:R + target price (2026-06-26, P0 community audit):** The 6-row action panel covers bias, structure, confirmation, checklist, execution, and risk — but the 执行 row only shows entry + invalidation, and the 风险 row only shows stop ATR multiple. Community pre-trade checklist standards (KMF 10-point, SMC Trade Checklist, TradingFinder ICT, TFlab) all require **R:R ratio (≥1:1.5)** and **target price (next liquidity pool / TP1)** before entry. Variables `replayStopDistance` (stop price) and `magnetNearestPrice` (target) already exist — only display formatting is needed. Recommended: 执行 row adds `· 目标67200(2.1R)`, 风险 row adds `R:R 2.1R` and stop price `(63800)`, Magnet score adds direction arrow `↑`/`↓`. See `references/community-sweep-rejection-action-panel-gaps-2026-06-26.md` §2.
- **Action panel execution-order + evaluation-row refinement (2026-06-26 user correction):** For this user's top-right Pine HUD, the final actionable row must be **last**. Assemble the panel in analysis→execution order: `层级 → 结论 → 结构 → 确认 → 关键 → 评估 → 计划`. Do not put `计划：` above risk/quality context. Rename `风险：` to `评估：` when the row mixes checklist quality, stop, R:R, target, and scores; show a **total score** (e.g. `总分7/10`) before sub-scores. Recommended score pattern: `总分 = clamp(位置分 + 确认分 + R:R分 - 延展扣分, 0, 10)`, with `R:R分 = 2` for `>=2.0R`, `1` for `>=1.5R`, else `0`. The row should read like: `评估：总分7/10 · 止损62100(1.5ATR) · R:R 2.1R · 目标磁吸82↑ · 位置3/3 确认4/5 R:R分2/2 延展扣1`.
- **SVP v10.1 B/C direct-order gate + risk merge (2026-07-02 user correction):** The user allows B/C states to display as directly placeable orders, but only when the setup is materially more certain. A still requires `R:R >= 2.0`; B/C direct mode requires `R:R >= 1.5` plus HTF alignment, no CVD/SMT conflict, key-level proximity, structure trigger (FVG/HTF FVG/sweep/MSS/acceptance), and no ADR/low-liquidity downgrade. Otherwise B/C must show wait text (`B多 等确认`, `C空 等跌回`) and avoid executable price rendering. Standard action-panel mode should merge the highest-priority risk summary into `结论` (`⚠HTF逆`, `⚠CVD冲突`, etc.) and hide the standalone `风险` row; full mode may keep the complete risk row for review. Full implementation pattern: `references/svp-v10-bc-risk-merge-2026-07-02.md`.
- **Magnet wording must name the target level (2026-06-26 user correction):** Do not display Magnet as only `磁吸78↑`, `磁距0.8ATR`, or a bare price. The user needs to know **magnet to where**. Include the liquidity pool name, price, distance, and score where space permits: structure line `磁吸上周 高 64200 距0.8ATR`; key line `磁吸上方:上周 高 64200 分82 / 磁吸下方:周二 低 61500 分76`; plan/target text `标↑上周 高 64200(2.1R)`. Preserve readability over compactness; this correction supersedes any shorthand-only Magnet display.
- **Complete day/week liquidity removal (2026-06-24, updated 2026-06-24):**
- **Production file ≠ last-patched file (2026-06-26):** When the user uploads a Pine Script file, it may be a DIFFERENT version from the one previously worked on in this or past sessions. Do NOT assume the desktop file or a previously-patched file is current. **Always read the freshly uploaded file first** and compare line counts / key features against what you think is "current" before making any claims or patches. In one session, 12 patches were applied to `桌面/no_day_week_fixed.txt` — only for the user to upload `指标svp.txt` (a completely different version with different features and bugs) as their real production indicator. Verify first: `wc -l`, grep for distinctive patterns, and confirm with user if unsure. When a design question arises (e.g. "how to optimize the action panel"), do NOT propose a design and ask the user. Instead, run 4-6 targeted web searches first to gather community consensus, then present findings alongside the proposed design. Key sources: TradingView script library (LuxAlgo, AGPro, PineCoders), Reddit r/TradingView, Pine Script documentation, and community indicator descriptions. Summarize community principles in a comparison table before presenting the aligned design. This user explicitly asked "联网社区看看怎么说" before approving any implementation.
- **Community advice filtering (2026-06-25):** NOT all community "best practices" apply to mature dashboards. Many community suggestions (e.g. "force daily VWAP for forex/metals") target simple single-anchor indicators without SMART_HIDE, manual override, or multi-TF confidence systems. Before applying: check whether the dashboard's existing guard rails already solve the problem the community advice addresses. If so, applying the simpler rule is over-optimization and may break the user's established workflow. See `references/community-audit-vwap-anchor-2026-06-25.md` for the specific VWAP anchor case study. The cross-reference rule: community suggestion is INPUT, not a mandate; the dashboard's maturity gates whether it applies.
- **DMI/ADX non-standard DI_LEN=10 (2026-06-24):** This indicator uses `DMI_DI_LEN=10` and `DMI_ADX_SMOOTH=10` instead of Wilder's classic 14/14. The shorter period produces more responsive but noisier signals — DI crossings fire earlier but with lower conviction. The market-adaptive ADX thresholds (crypto 25→45, forex 18→35) partially compensate by raising the bar for noisier markets. **v9.4 fix (2026-06-24):** Added `input.string("激进(短周期)", "DMI风格", options=["标准(Wilder14)", "激进(短周期)"])` toggle. Derived `finalDmiDiLen` / `finalDmiAdxSmooth` select 14 vs 10 based on mode. Default kept as 激进 for backward compatibility; 标准 mode available for Wilder-classic fidelity. Code pattern: `DMI_MODE == "标准(Wilder14)" ? 14 : DMI_DI_LEN`.
- **Forward calibration TF-agnostic horizon (2026-06-24):** `CAL_HORIZON_BARS=12` is a fixed forward lookback regardless of chart timeframe. On a 5-minute chart, 12 bars = 1 hour — reasonable for intraday signal validation. On a 4-hour chart, 12 bars = 2 days — the calibration window spans a completely different market regime. **v9.4 fix (2026-06-24):** Replaced with TF-adaptive formula: `_tfSec = timeframe.in_seconds(); CAL_HORIZON_BARS = _tfSec < 60 ? 48 : _tfSec < 300 ? 24 : _tfSec < 900 ? 12 : _tfSec < 3600 ? 8 : _tfSec < 14400 ? 6 : _tfSec < 86400 ? 4 : 3`. This gives 48 bars on sub-1m, 24 on <5m, 12 on <15m, 8 on <1H, 6 on <4H, 4 on <1D, 3 on D+.
- **VP_MIN_TICK_MULT market-adaptive gap (2026-06-24):** The `VP_MIN_TICK_MULT=20` setting multiplies the minimum tick size to determine the smallest SVP bucket width. BTC (mintick=0.01 → bucket=0.2) is well-served. XAUUSD (mintick=0.01 → 0.2) creates aggressively coarse buckets on a $3000 instrument. EURUSD (mintick=0.00001 → 0.0002) creates absurdly narrow buckets on a ~1.0 instrument — nearly every bar spans hundreds of buckets, diluting volume per bucket. **v9.4 fix (2026-06-24):** Added `finalVpMinTickMult` with market-adaptive floors: crypto defaults to user-set 20, stock ≥30, forex ≥40, metal ≥50. Used in `processAndRender(): minStep = syminfo.mintick * finalVpMinTickMult`. Gated behind `MARKET_ADAPTIVE_ENGINE`; falls back to raw `VP_MIN_TICK_MULT` when engine disabled.
- **Hermes `patch` tool escape-drift on Pine `\"` strings (2026-06-25):** The `patch` tool's fuzzy matching fails with "Escape-drift detected" when `old_string` contains Pine Script's literal `\"` sequences (common in `input.*()` tooltips and `str.replace()` calls). The tool misinterprets the backslash-quote as a JSON-level escape. **Workaround**: for bulk edits involving 5+ changed lines or any `\"`-containing strings, use `terminal` with a Python script that reads the file, processes lines in memory, and writes back. For single-line edits without `\"`, individual `patch` calls still work. When using the Python fallback, always follow with a `grep -c` verification pass on every removed identifier.

## Multi-Community Cross-Audit Workflow (2026-06-25)

When the user requests "全面审计" or "联网社区对照", do NOT just read the file and report issues. Run parallel searches across ALL community platforms first, then cross-reference findings against the source code.

### Search Matrix (run ALL in parallel, not sequentially)

| Platform | Query pattern | Purpose |
|----------|--------------|---------|
| TradingView | `site:tradingview.com <indicator-type> best practice 2025` | Peer indicator design patterns |
| Reddit | `r/pinescript OR r/TradingView "<topic>" best practice pitfall` | Real-world gotchas, user complaints |
| GitHub | `"pine-script" "<feature>" adaptive OR multi-asset OR multi-market` | Open-source implementation patterns |
| Medium/DevTo | `"Pine Script" "multi-asset compatibility" OR "adaptive thresholds"` | Architecture articles |
| X/Twitter | `"Pine Script" OR "TradingView" <technique> optimization` | Practitioner tips |

### Audit Dimensions (the 8-dimension rubric)

1. **Core Structure** — SVP/VWAP/EMA correctness, anchor logic, bucket width
2. **Session/ICT** — KillZone naming, DST handling, session-end label lifecycle
3. **CVD/Order Flow** — Divergence gate conditions, key-level filtering, swing magnitude filter
4. **Multi-Market Adaptation** — Per-asset parameter matrix, session channel config, VWAP anchor per market
5. **DMI/Decision Engine** — ADX thresholds per market, Wilder standard vs aggressive, grade stability
6. **Action Panel HUD** — Line count (≤6), prefix dedup, color grading, market-adaptive focus text
7. **Performance** — Output series count (<40 target), request.security tuple bundling, object lifecycle
8. **Settings Hygiene** — Dead controls, group ordering, default correctness, visibility kill-switches

### Output Format
Use the 3-tier format: `✅ 正确` / `⚠️ 需加强` / `🟢 可优化`, with P0/P1/P2 priority and a **多品种适应性矩阵** table (Asset × Module = Grade). See `references/multi-community-cross-audit-template.md` for the full framework.

### Key Community References (2026-06-25)
- **NikaQuant Quantum Liquidity Map**: 3-condition CVD divergence gate (swing extreme + CVD non-confirm + swing > 1.5×ATR), VP+VWAP+CVD confluence pattern
- **Betashorts Multi-Asset Guide**: `syminfo.mintick` for precision, `syminfo.type` for detection, ATR-normalized stops, `format.mintick` for prices
- **ICT KillZone Standards** (Reddit r/InnerCircleTraders): crypto=3 sessions, forex=2 (no Asia CVD), metals=2 (London+NY only), KillZone ≠ Silver Bullet
- **LuxAlgo/AGPro Dashboard Standards**: ≤6 lines, no ticker name, color-by-state-not-indicator, single-cell table, `：` labels
- **StackOverflow `request.security` limit**: max 40 calls, tuple-bundle 7 values per call

## Pine Indicator Iteration Workflow

When the user asks to review, debug, or iterate an existing Pine Script indicator (not build a new one from scratch), follow this workflow:

### Production replacement workflow

When the user uploads updated main/sub indicator files and says to replace the originals, use the full replacement workflow in `references/pine-production-replacement-workflow.md`. Key requirements: treat the fresh uploads as source of truth, back up old production files, replace `svp_indicator.txt` / `haldro_indicator.txt`, sync Desktop `.txt` copies, run static Pine audit, attempt TV save/compile without claiming transient editor failures as success, then verify `tv_data_bridge.py` and BTC/XAU `auto_card.py` still work. For HALDRO short-title warnings, `shorttitle='AggVol'` is the safe display-only fix.

### 1. Understand Current State
- If CDP is available, first check the current chart state and Pine source via MCP tools.
- If `tv_health_check` shows CDP connected, use `mcp_tradingview_pine_get_source()` to read the current editor contents.
- If CDP is unavailable (Windows Store MSIX blocks `--remote-debugging-port`), ask for the Pine code directly.
- **⚠ BEFORE any color audit: confirm the user's TradingView theme (dark/white).** `#0F0F0F` is visible on white theme but invisible on dark. `#FFFFFF` is visible on dark but blinding on white. A wrongly-flagged P0 erodes trust — ask first, audit second. This is the single most common false-positive in audit sessions (2026-06-25 reinforcement).

### 2. Preserve the Original
Save the user's working script to `projects/tradingview-indicators/<name>.pine` before making changes. Create a new versioned output file for substantial changes (e.g. `*_v3_1.pine`), do not overwrite the original unless explicitly asked.

### 3. Analyze
- Identify Pine version (`//@version=5` vs `//@version=6`).
- Map inputs, table rendering, alertcondition calls, plot/plotshape usage, and `request.security()` calls.
- Check for unused `input.*` variables and single-use remnants.

### 4. Edit Carefully
- Prefer short helper functions over long nested ternaries.
- Keep `alertcondition()` in conservative positional form: `alertcondition(cond, "Title", "Message")`.
- Avoid Chinese strings in alert titles (can cause parser errors).
- Define helper functions before use or Pine errors out.
- After deletion of chart markers or table rows, also delete orphaned `input.*` controls and stale variables.

### 5. Verify & Report
- Run text-level verification: search for removed constructs (`plotshape(`, obsolete inputs, unused helper names).
- Scan for very long lines that may trigger Pine parser problems.
- Tell the user plainly that final syntax must still be verified in TradingView Pine Editor (no local compiler available).

- **Settings Panel Hygiene**
When optimizing settings layout:
- Put most-used decision controls first, then confirmation inputs, then drawing/appearance.
- Prefer numbered group names for predictable ordering (e.g. `00 Pro - 市场模式`, `01 决策表 - 实盘`).
- Remove settings that no longer control any logic.
- Shorten setting names where possible.
- Audit visibility controls as a pair: if a feature has both a chart-line toggle and a right-axis toggle, make sure they are intentionally decoupled and both are honored. Common examples in this class of script: `SHOW_DO_LINE` vs `SHOW_AXIS_DO_LEVEL`, and `SHOW_ICT_LEVELS` vs `show_ict_lines`/pool rendering. Users often want a feature hidden on-chart but still visible on the price scale.
- When the user says a level "doesn't show," check **five layers** before changing logic: (1) **data source** (`request.security` can return na on crypto — prefer chart-based `ta.change(time("D"))` tracking for same-instrument prev day/week), (2) **draw gate** (`show_ict_lines`, timeframe filters, weekend filters), (3) **axis gate** (`SHOW_RIGHT_PRICE_AXIS`, `SHOW_AXIS_*`), (4) **line-extension loop** (`line.set_x2()` must be called on every bar, not gated behind an unrelated feature toggle like `SHOW_ICT_LEVELS` — `line.new()` creates zero-length lines that are invisible until extended), and (5) **line initial length** (`line.new(bar_index, price, bar_index, price)` = zero-length = invisible; use `bar_index + 1` for both creation and `set_x2`). A value can be correctly computed yet still invisible because one of those layers is off or the extension is gated.
- Keep structural reference levels independently controllable from session drawings. In practice, previous-day/week high/low often need their own axis toggle and should not disappear just because intraday ICT session lines are hidden.
- If the user requests a specific default display behavior, apply that default in the input itself rather than only in downstream code. Examples from this session: `SHOW_DO_LINE=false` by default while `SHOW_AXIS_DO_LEVEL=true`, `SHOW_OPEN_ONLY_ACTIVE=true`, `POC_COLOR=#0F0F0F`, `WEEK_LIQUIDITY_SHOW_ATR=5.0`, `DAY_LIQUIDITY_LABEL_SIZE=size.small`, and `ICT_SWEPT_LABEL_SIZE=size.tiny`.
- After adding or changing an axis-scale plot, recount total outputs and keep a margin under TradingView’s 64-series limit. Prefer encoded `plot()` values over adding more raw visual series when possible.

### User Preference: Practical Decision Panels
For this user's TradingView indicator iterations:
- Default to a concise table, not chart markers.
- Table rows should be few, readable, one concept per row.
- Default table position: lower-left for practical live-trading view.
- Use fully opaque table header/cell backgrounds.
- Preferred rows: `等级`, `处理`, `结构`/`高周`, `量能`, `CVD`, `计划`, `失效`.
- Make `计划` direction-specific, `失效` direction-specific.
- For `X`/no-chase states, explain the reason.

### Backup Existing Indicators to Workspace
When MCP/CDP is available:
1. `mcp_tradingview_pine_list_scripts()` → find the script
2. `mcp_tradingview_ui_open_panel("pine-editor")` → open editor
3. `mcp_tradingview_pine_open(name)` → open specific script
4. `mcp_tradingview_pine_get_source()` → read source
5. Extract from double-nested JSON, save to `projects/tradingview-indicators/<name>.pine`

### Common Pine Pitfalls
- Price display helpers: if you add `f_fmt_price(...)`, also add the helper function.
- If you remove `plotshape` markers, also remove dead input toggles.
- If detailed table mode exists, make it genuinely useful (split rows).
- If concise mode exists, avoid showing both sides when grade indicates one active side.

## v10/v6 Indicator: Action panel + MCP Data Window dual-read (2026-07-02; v6 update 2026-07-09)

⚠️ **定版主指标（2026-09-11）= `SVP_主指标_空格修正_20260911.pine`（3557 行·sha256[:24]=68a34fc3，仓内 `outputs/pine_20260905/SVP_audit_fixed17_20260910.pine`）；副指标 = `AggVol_副指标_最终版_20260911.pine`（966 行·c4c563ef）。** `SVP_v6.pine` / `SVP_fixed.pine` 都是历史基线。Action panel = human truth; Data Window = machine fallback；字段清单以 `docs/tv-indicator-field-map.md` v3.0 为准。

**What to read now:**
- **Live MCP tables:** `data_get_pine_tables(study_filter="SVP")` → action panel v2 rows
  `位置/结论/方向/路径/风控/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位`. Grade often inside `结论`.
- **Classic study values (do not rename):** `MCP Side Code` (long=1 / short=**-1** / X=9),
  `MCP Grade Code`, `MCP Setup Score`, `MCP Entry/Stop/Target Price`, `MCP CVD Method Code`,
  `MCP Quality Code`, `MCP RR Ratio`, `MCP Entry Valid Code`, `MCP NoTrade Reason Code`.
  （`MCP CVD Value` / `MCP Bull FVG CE` / `MCP Bear FVG CE` / `MCP FVG Quality Code` 已废止，读不到）
- **结构打包字段**：当前 DW 名就是 `MCP StructPack`（旧长名 `MCP StructPack (FvgQ…)` 已废止）
  replaces separate OB / BOS-CHoCH / LiqVoid / FVG-Quality plots.
  Decode: FvgQ=pack//10000; rem=pack%10000; OB=rem//100-1; BOS=(rem//10)%10-2; LV=rem%10-1
  (BOS code prefers CHoCH ±2 over BOS ±1).
- **Price-axis:** POC/VAH/VAL/nPOC/W·M VWAP/DO (stroke colors may be fixed hex for quota).
- **Sub:** HALDRO AggVol — OI/CVD/Coverage/Confirm/Composite…
- **auto_card:** panel text overrides codes; use classic titles; add StructPack decode when OB needed.

Regression tests: `tests/test_tv_action_panel_decode.py` and `tests/test_render_tv_card.py`.

## References

**Pine审计与安全**: `pine-indicator-audit-checklist.md` · `pine-security-quota-pitfall.md` · `multi-community-cross-audit-template.md`
**会话审计存档**: `session-audit-findings-archive.md`
**CDP/MCP 设置**: `tradingview-mcp-hermes-setup.md` · `tradingview-mcp-bridge.md` · `tradingview-windows-msix-cdp.md` · `tv-bridge-action-panel-decode-2026-06-27.md`(数据桥解码链/CDP target探测/行动格v2字段映射)
**仪表板模式**: `cvd-overlay-fusion.md` · `pro-dashboard-upgrade.md` · `table-safe-dashboard.md` · `no-table-dashboard-variant.md` · `action-panel-single-cell.md`
**执行卡/行动格**: `execution-card-v34-audit.md` · `pro-dashboard-v3-lessons.md` · `settings-panel-audit.md` · `decision-panel-v31-price-plans.md` · `execution-cvd-guard.md` · `cvd-quality-hud-hardening.md` · `execution-panel-multimarket-cvd.md` · `action-panel-v90-no-labels.md` · `action-panel-v95-compact.md` · `action-panel-v90-with-labels.md` · `action-panel-v95-color-grading.md` · `action-panel-funding-narrative.md` · `action-panel-trade-control-removal-cvd-sweep.md` · `panel-settings-cleanup.md` · `trade-controls-cvd-alignment.md`(废止)
**市场自适应**: `market-adaptive-orderflow-v81.md` · `multi-market-parameter-matrix.md` · `multi-market-full-stack-execution-panel.md`
**ICT/SVP/CVD**: `session-cvd-killzone-smt.md` · `svp-extremes-sweep-lines.md` · `svp-extremes-removal.md` · `liquidity-pools-axis-dedupe.md` · `liquidity-label-controls-week-filter.md` · `weekly-liquidity-sweep-lines.md` · `weekly-liquidity-na-guard.md` · `ict-smt-standard-pairs.md`
**社区审计**: `community-2026-orderflow-upgrade.md` · `community-audit-scoring.md` · `multi-channel-audit-methodology.md` · `compact-dashboard-community-standards.md` · `community-source-code-audit-v95.md`
**历史归档（v10 时代，⚠产物已废止，仅作取证）**: `v10-data-window-encoding.md`(⚠已废止·v10删除Data Window导出,见 tv-bridge-action-panel-decode-2026-06-27.md) · `indicator-svp-v1-audit-2026-06-26.md` · `indicator-svp-v10-implementation-2026-06-25.md` · `indicator-svp-v10-session-audit-2026-06-26.md` · `indicator-svp-v10-optimization-2026-06-26.md` · `svp-v10-fixed-audit-lessons-2026-06-25.md` · `pine-v10-1-fvg-haldro-upgrade-2026-07-02.md`
**Pine编辑工具**: `pine-plot-limit-quick-triage.md` · `data-window-output-compression.md` · `pine-v5-runtime-pitfalls.md` · `pine-bulk-edit-python-workaround.md` · `pine-na-aggregate-poisoning-20260910.md`(na 毒化聚合链 + 行为判据验收)
**v6 生产急救（历史记录·跨 skill）**: `pine-indicator-audit/references/svp-v6-plot-limit-and-audit-2026-07-09.md` · `svp-v6-vs-fixed-audit-2026-07-09.md`

## Critical Pitfalls

### TradingView Delta / VP / Footprint 语义边界（P0 · 2026-07-21官方复核）

- TradingView 官方 CVD 与 Volume Delta 都是根据低周期价格变化对成交量分类后得到的**估算值**，不是交易所逐笔 bid/ask aggressor tape。
- 普通 Volume Profile 的 up/down volume 由低周期K线方向分类；POC/VAH/VAL可作结构，但VP买卖颜色不能宣称为真实主动买卖。
- `request.footprint()` 虽提供 buy/sell、delta、POC、VA、imbalance，官方当前文档仍说明其基于低周期 intrabar price action 分类。**不得把它写成“真实交易所逐笔Delta”或“无误差订单流”。** Premium/Ultimate限定、单脚本一个唯一调用、无数据可返回`na`。
- 所有相关字段必须诚实命名：`Estimated CVD` / `估算CVD`、显示LTF/覆盖交易所/确认状态。需要真实逐笔流时，架构边界应转到交易所WebSocket或专业订单流平台，而不是继续堆Pine近似。
- 非重绘与准确性是两件事：confirmed-bar稳定只说明历史/实时呈现可复现，不会把估算Delta变成真实Delta。

完整证据矩阵与URL见 `references/orderflow-community-evidence-2026-07-21.md`。

### `request.security` 配额铁律（P0 · 2026-08 官方复核）

Pine v6 默认按需启用 dynamic requests。非 Ultimate 为 **40 个已执行的唯一 `request.*()` 上下文**，Ultimate 为 64；动态循环可在第 41 个不同上下文处报运行时错误。相同函数+相同参数通常复用一次；库内调用仍单独计。开关只有在它阻止请求调用本身执行时才可能节省额度；请求后再把结果设为 `na` 不省。实时阶段不能首次引入历史阶段从未请求过的新上下文。见 `request-security-quota-rules.md`。

### 两套 CVD 共存规则

主指标（`request.security_lower_tf`子K价格方向估算Delta，粒度较细）与副指标（影线/实体比例估算Delta，更粗）共存时：两者都不是真实bid/ask逐笔。冲突时以主指标的关键位门控CVD作为优先背景，副指标“流向”只作聚合量能佐证。

### 行动格格式偏好（棠溪）

- 磁吸保持两行：`磁吸↑`（多色）和 `磁吸↓`（空色）各自一行，不合并
- 默认模式为"标准"（含 位置/结论/方向/路径/风控/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位）
- 副指标非加密自动门控（`syminfo.type == 'crypto'`）

### 方向行三层信息密度（2026 ICT 社区共识 · 2026-06-27 落地）

标准档"方向"行应承载三层下单前必读信息，而非仅显示方向偏向：

```pine
// 之前（仅方向）
string panelDirVal = actionBiasWord + "  " + dmiVerifyText
// 偏多  EMA多头

// 之后（方向+溢价折价+KillZone+扫位计数）
string panelDirVal = actionBiasWord + "  " + dmiVerifyText 
    + (pdZone != "" ? " · " + pdZone : "") 
    + (isKillZone ? " ⚡" + killZoneLabel : "") 
    + (sweepCntText != "" ? " · " + sweepCntText : "")
// 偏多  EMA多头  · 折价偏下  ⚡伦敦开盘  · 已扫3/剩5
```

**注意**：pdZone 必须在 panelDirVal 之前定义（Pine 单遍顺序），切勿留两份定义。

### 副指标 CVD 背离标注（Bookmap/Reddit 共识 · v2.1）

副指标"流向"行不应只显示买盘/卖盘占比。当价格与估算 CVD 出现 HH/LH 或 LL/HL 背离时，替换为 `估算CVD ⚠卖背离` / `估算CVD ⚠买背离`，并对 Confirm Score 扣 1。注意：HALDRO 的 CVD 是影线/实体比例估算，不是真逐笔 Delta；显示与 Data Window 必须诚实标注为估算口径。

三重过滤必须同时满足：
1. 价格新高/新低；
2. CVD 不确认（新高时 CVD 低于前高，新低时 CVD 高于前低）；
3. 摆动幅度 `> 1.5 * ATR(14)` 且 CVD slope 方向确认（卖背离 slope≤0，买背离 slope≥0）。

Data Window 命名（定版）：`CVD Value` 为当前字段（另有 `CVD Method Code (1=当前所K线方向/2=当前所1m方向)` / `CVD Quality Code`）。**`Estimated CVD Value` 已废止** —— 旧的「优先读 Estimated CVD Value」规则作废。

精简模式保持手机可读 5 行：`信号 / 结论 / 流向 / 持仓 / 操作`，不要退回只剩 3 行。

完整落地记录见 `references/pine-v10-1-fvg-haldro-upgrade-2026-07-02.md`。

### OI 聚合化模式（HALDRO 副指标 v2 · 2026-06-27 实操完整流程）

1. **砍交易所物理删代码**：GetExchange 函数中移除不需要的交易所行（从9所→5所），删掉对应的数组元素/循环范围/EXv变量/plot调用。**三元/input开关不减配额，必须物理删除。**
2. **加 OI 聚合**：4个 f_oi() 函数 + 1个回退单源。聚合值 >0 时使用，否则回退。
3. **验证配额**：确认 ≤40（5所×4=20 + EUR/RUB 2 + OI聚合4 + OI回退1 = 27/40）。
4. **tooltip 诚实**：开关关闭不省 quota，注明"静态计数不省配额"。

详见 `references/haldro-aggregated-volume-pairing.md`。
