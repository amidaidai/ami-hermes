# Dead Code Audit (v9.0+ Compact Action Panel)

When the action panel switched from narrative cards to compact v9.0 format, old narrative variables became dead.

## Audit methodology
```bash
# 1. List all string variables around the narrative block
grep -n "^string \|^    string " file.txt

# 2. For each, check if referenced elsewhere
grep -c "variableName" file.txt
# count=1 → defined once, never used → DEAD

# 3. Special: check if/else chains where variable is both defined AND used in same block
```

## Known dead variables (v9.0 context)
| Variable | Reason dead |
|----------|-------------|
| `stateText` | Was old card title, now unused |
| `cardLine1-3` | 3-line narrative card, replaced by 8-line compact panel |
| `directionGuideText` | Was direction paragraph, now in 定调 line |
| `actionGuideText` | Was action paragraph, now in 执行 line |
| `detailText` | Was detail paragraph, now unnecessary |
| `trendMiniText` | Was detailed table row |
| `volumeMiniText` | Was detailed table row |
| `eventMiniText` | Was detailed table row |
| `cvdMiniText` | Was detailed table row |
| `structureShortText` | Compact mode superseded |
| `nowAdviceText` | Replaced by `actionStateText` |
| `focusedPlanText` | Was focused plan display |
| `planShortText` | Compact mode superseded |

## What to KEEP (actively consumed)
- `watchText` → used in `lineAction` ("不追，等" + watchText)
- `invalidText` → used in `longInvalidRaw`/`shortInvalidRaw` → `longInvalidText`/`shortInvalidText`

## Cleanup pattern
The narrative block (~L1958-L2138, ~180 lines) is an if/else chain setting 9 variables per branch.
Rewrite to only compute `watchText` + `invalidText` (~60 lines), keeping all branch logic intact.

## Post-cleanup verification
```bash
grep -c "deadVarName1\|deadVarName2\|..." file.txt
# Should return 0 or exit code 1 (no matches)
```
