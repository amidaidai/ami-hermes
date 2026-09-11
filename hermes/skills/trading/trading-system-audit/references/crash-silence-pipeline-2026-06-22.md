# Crash→Silence Pipeline (P0 · 2026-06-22)

## Pattern

When `auto_card.py` has a runtime NameError (undefined function/variable), the chain:

```
1. Monitor detects expired levels → tries to call auto_card to refresh
2. auto_card crashes with NameError → levels NOT refreshed
3. All levels expire → no alerts can trigger → COMPLETE SILENCE
4. User asks "警报是没有触发了吗？" — root cause invisible from process/heartbeat
```

## Real Cases

1. `_near_key_level` undefined — renamed but caller not updated
2. `qty_unit` undefined — should be `_qty_unit(symbol)`

Both survived: syntax compile() ✅ · static audit ✅ · pytest 101/101 ✅
→ Only revealed by actually running `python auto_card.py BTCUSDT`

## Diagnosis

```bash
# Check for expired levels
python -c "import json; d=json.load(open('data/monitor_levels.json')); 
  [print(f'{k}: {sum(1 for l in v[\"levels\"] if l[\"status\"]==\"active\")}') for k,v in d['symbols'].items()]"
# → All 0 active = P0 crash→silence

# Test card generation
python hermes/scripts/auto_card.py BTCUSDT
# → NameError = confirmed root cause

# Check monitor log for the gap
grep "活跃关键位少于" data/monitor.log | tail -5
```

## Audit Iron Rule

**静态扫描之后必须实测跑管线** — at minimum `python auto_card.py BTCUSDT` + `XAUUSD` once each.
Static analysis (compile, pytest, lint) cannot catch undefined names introduced by rename/copy-paste.

## Prevention

After ANY change to auto_card.py:
1. `python -c "compile(open('hermes/scripts/auto_card.py').read(),'a','exec')"`
2. `python hermes/scripts/auto_card.py BTCUSDT` (real run, not just import)
3. Verify `monitor_levels.json` has active levels after run
