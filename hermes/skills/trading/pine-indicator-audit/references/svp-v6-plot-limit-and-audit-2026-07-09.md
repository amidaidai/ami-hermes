# SVP v6 plot limit 71→64 + audit notes (2026-07-09)

## Incident
TradingView compile: `脚本创建了太多绘图(71)。限制为64` on production `SVP_v6.pine` (`//@version=6`, desktop == upload).

## Count that matched 71
Static inventory before fix:
- `plot(` ≈ 30–31 (16 series-color from `input.color`/ternary, 15 const/no-color DW)
- `fill(` 2 (series ternary cloud colors)
- `bgcolor(` 3 (session + Silver Bullet + Macro)
- `table.new(` 1

Formula that reproduced **71**:
```
plots*2 + fills*2 + bgs*2 + table = 30*2 + 2*2 + 3*2 + 1 = 71
```
Optimistic series-only doubling under-counted (~53). When user reports N near 64–72, **also compute the all-plot×2 worst case**.

## Fix stack (order of impact)
1. **Const-hex plot colors** (largest win): replace `color=VWAP_COLOR` / `color=POC_COLOR` / EMA ternary colors with literal `#00BCD4`, `#0F0F0F`, `#00FF6A`, etc. matching input defaults. Chart `line.new`/`box` may still use input colors.
2. **Merge bgcolor 3→1**:
   `bgcolor(inMacroAm ? color.new(#FFD700,70) : inSilverBullet ? color.new(#00FFFF,85) : ictSessionBg)`
3. **Fill colors fixed** (drop bull/bear dynamic cloud tint if needed): `fill(..., color=showCloud ? color.new(#00FF6A,70) : na)` — ternary on show flag may still be series; prefer value `na` gate + const color when possible.
4. **MCP packing without breaking auto_card classic titles**:
   - Keep: `MCP Side Code`, `MCP Grade Code`, `MCP Setup Score`, `MCP Entry/Stop/Target Price`, `MCP CVD Value`, `MCP Quality Code`, `MCP Bull/Bear FVG CE`
   - Pack new structure into one:
     `MCP StructPack (FvgQ*10000+(OB+1)*100+(BOS+2)*10+(LV+1))`
   - Side encoding must stay: long=1, short=**-1**, X=9 (not short=2)
5. **Declare before pack**: when folding `mcpFvgQualityCode` into StructPack, keep its full definition + nearest-FVG helpers. Forgetting the assign → `Undeclared identifier 'mcpFvgQualityCode'`.

## Post-fix targets
- raw `plot(` ≤ ~28–30
- series-color plots = 0 on visual/axis plots
- worst-case estimate ≤ 63 (margin 1+)
- est_tokens still < 80000 (~77800 after this pass)

## Also fixed in same pass
- `line.set_x2(doLine, bar_index + 1)` (was `bar_index`)
- nPOC create `endBar + 1`; `line.set_x2(np.ln, bar_index + 1)`

## Remaining P1 (not plot-limit)
- **BOS/CHoCH display priority**: `chochBull` is subset of `bosBull` conditions, but `bosChochText` / MCP used `bos first` → CHoCH almost never labels. Prefer CHoCH then BOS. StructPack encode already uses CHoCH-first for `mcpBosCode`.
- `cvdBearStars`/`cvdBullStars` still stubbed at 0
- Risk inputs `RISK_PER_TRADE_PCT` etc. still dead
- Sweep panel text still abstract `扫2/5` → prefer `已扫2/剩5`

## Authority map
| File | Role |
|------|------|
| Desktop/upload `SVP_v6.pine` | Production main (v6 + OB/BOS/CHoCH/LV) |
| `SVP_fixed.pine` | v5 repair baseline, no OB layer — rollback only |

## Delivery paths
- Desktop: `C:/Users/Administrator/Desktop/SVP_v6.pine`
- Upload: `C:/Users/Administrator/.hermes-web-ui/upload/default/SVP_v6.pine`
- Always `cp`/write both after edits; verify sha equal.

## Pre-paste checklist
1. `grep -c "plot("` / series-color audit
2. worst-case slot estimate ≤ 63
3. `mcpFvgQualityCode` has assign + StructPack read
4. classic MCP titles present for auto_card
5. User compiles in TV Pine Editor (no local compiler)
