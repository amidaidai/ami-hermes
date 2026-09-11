# Fix Pattern: Write It Right, Don't Post-Patch

**Discoverer**: 2026-06-21 P0-2 prediction verification fix session  
**Applicability**: Any time you need to persist data with correct values

## The Pattern

When a function writes data to disk, and callers need to supply a value that's not available at the call site of the writer function's constructor:

❌ **DON'T** write with a placeholder, then read the file back and patch it:

```python
# BAD: race condition + silent failure
pred = log_prediction(sym, m, r)       # writes with price_at_prediction=0
pred["price_at_prediction"] = price     # modifies in-memory copy only
_patch_pred_price(sym, px)              # reads entire file, searches backward, rewrites
```

This fails because:
1. `pred` is a local dict — modifying it doesn't modify the file
2. `_patch_pred_price` reads the whole file, searches, rewrites — TOCTOU race
3. If another process writes between read and write, data is lost
4. Bare `except Exception: pass` hides all failures

✅ **DO** modify the function signature to accept the value at write time:

```python
# GOOD: writes correctly on first attempt
def log_prediction(symbol, merged, results, price=0):
    pred = {"price_at_prediction": price, ...}  # correct from the start
    write_to_file(pred)

# Caller:
log_prediction(sym, m, r, price=px)  # one call, no post-processing
```

## Signs You're Post-Patching

- A function writes to disk, then the caller modifies the return dict
- A separate `_patch_*` function reads the file and rewrites it
- Comments like "filled by caller" or "补真实价格"
- File read-backt-rewrite patterns (read → json.loads → modify → write)

## Real Case (2026-06-21)

**Symptom**: `prediction_log.jsonl` had 112 predictions, 0 verified. `monitor.log` claimed 99.8% win rate with 491 verified. Two data sources completely disconnected.

**Root cause**: `log_prediction()` wrote with `price_at_prediction=0`. Two callers had different post-patch strategies:
- `multi_model_engine.py`: set `pred["price_at_prediction"] = price` on return dict (memory only, not file)
- `system_data_bridge.py`: called `_patch_pred_price()` which read the whole file, searched, rewrote (race-prone)

**Fix**: Added `price` parameter to `log_prediction()`. Both callers pass price at call time. Removed `_patch_pred_price` completely. Cleared corrupted old data.

## Verification

```bash
# After fix, new predictions should have price set correctly
python -c "
from prediction_tracker import log_prediction, aggregate_stats
# Old predictions with price=0 should NOT accumulate
# New predictions should have actual price
s = aggregate_stats()
print(f'Verified predictions: {s[\"total_predictions\"]}')
"
```
