# Pine v5 Literal Syntax Traps

Date: 2026-06-26  
Context: SVP v10 refactor after community audit. Three compile-time blockers surfaced when restructuring the compact action panel and adding MTF bias helpers.

## 1. Multi-line string literals are illegal

Pine v5 string literals must close on the same line. A real newline character inside quotes is a syntax error.

### Error
```
错误于 2305:35 mismatched character '\n' expecting '"'
```

### Broken code
```pinescript
string actionText = headerLine + "
" + actionLine1 + "
" + actionLine2 + "
" + actionLine3 + "
" + actionLine4 + "
" + actionLine5
```

### Fixed code
```pinescript
string actionText = headerLine + "\n" + actionLine1 + "\n" + actionLine2 + "\n" + actionLine3 + "\n" + actionLine4 + "\n" + actionLine5
```

### Rule
Use `"\n"` as a normal escape sequence inside one continuous source line. Never break the string literal across physical lines.

## 2. Array type annotation position

Pine v5 accepts `type[] identifier = ...`. It does **not** accept `type identifier[] = ...`.

### Error
```
错误于 787:5 'string' is not a valid type qualifier. Possible values: 'const', 'simple', 'series'
```

### Broken code
```pinescript
f_mtf_bias_str() =>
    string tfs[] = array.from("15", "60", "240", "D")
    string labels[] = array.from("15m", "1h", "4h", "1D")
```

### Fixed code
```pinescript
f_mtf_bias_str() =>
    string[] tfs = array.from("15", "60", "240", "D")
    string[] labels = array.from("15m", "1h", "4h", "1D")
```

### Rule
Put the brackets on the type side: `string[]`, `int[]`, `float[]`, `bool[]`, and UDT arrays like `array<MyType>`.

## 3. `request.security()` requires a function CALL (with parentheses)

**CORRECTION (2026-06-26):** The original version of this section advised passing `f_htf_pack` without parentheses. That advice was **wrong** — it causes `Undeclared identifier 'f_htf_pack'` because Pine v5 treats a bare name as a variable lookup, not a function reference. This was confirmed in a live session where line 825 `f_htf_pack` (no parens) produced a compile-blocking error.

### Error (bare reference, no parens)
```
错误于 825:89 Undeclared identifier 'f_htf_pack'
```

### Broken code (causes Undeclared identifier)
```pinescript
[htfClose, htfEmaFast, htfEmaSlow, htfVwap] = request.security(syminfo.tickerid, htfTf, f_htf_pack, ignore_invalid_symbol=true)
```

### Fixed code (add parentheses)
```pinescript
[htfClose, htfEmaFast, htfEmaSlow, htfVwap] = request.security(syminfo.tickerid, htfTf, f_htf_pack(), ignore_invalid_symbol=true)
```

### Warning: "should be called on each calculation" — caused by loop/conditional, NOT by parens

The `should be called on each calculation` warning is triggered when `request.security()` is placed inside a `for` loop or `if` block — NOT by using parentheses. The fix is to unfold the loop into separate top-level calls, keeping `f_htf_pack()` with parens.

### Warning text
```
The function 'f_htf_pack' should be called on each calculation for consistency. It is recommended to extract the call from this scope
```

### Broken code (loop causes warning, not the parens)
```pinescript
f_mtf_bias_str() =>
    string[] tfs = array.from("15", "60", "240", "D")
    for i = 0 to array.size(tfs) - 1
        string tf = array.get(tfs, i)
        [c, e21, e55, v] = request.security(syminfo.tickerid, tf, f_htf_pack(), ignore_invalid_symbol=true)
        bool bull = not na(c) and c >= v and e21 >= e55
        // ...
```

### Fixed code (unfold loop to separate top-level calls)
```pinescript
f_mtf_bias_str() =>
    [c15, e21_15, e55_15, v15] = request.security(syminfo.tickerid, "15", f_htf_pack(), ignore_invalid_symbol=true)
    [c60, e21_60, e55_60, v60] = request.security(syminfo.tickerid, "60", f_htf_pack(), ignore_invalid_symbol=true)
    [c240, e21_240, e55_240, v240] = request.security(syminfo.tickerid, "240", f_htf_pack(), ignore_invalid_symbol=true)
    [cD, e21_D, e55_D, vD] = request.security(syminfo.tickerid, "D", f_htf_pack(), ignore_invalid_symbol=true)
    bool bull15 = not na(c15) and c15 >= v15 and e21_15 >= e55_15
    // ... compute bull/bear/arrow per TF, then concatenate
    "15m" + arrow15 + " 1h" + arrow60 + " 4h" + arrow240 + " 1D" + arrowD
```

### Rules
1. **ALWAYS use `f_htf_pack()` (with parens)** as the `request.security()` expression — Pine v5 requires a function call, not a bare reference. A bare name produces `Undeclared identifier`.
2. **The "should be called on each calculation" warning comes from loop/conditional placement**, not from parens. Fix by unfolding to separate top-level `request.security()` calls.
3. **Pine v6** allows `request.security()` inside loops with `series string` arguments, but v5 does not. If migrating to v6, dynamic requests become possible.

## 4. Multi-line boolean expressions are illegal

Pine v5 does NOT allow a boolean/ternary expression to span multiple lines inside parentheses — unlike Python/JavaScript. A line break inside an unclosed `(` produces a syntax error.

### Error
```
错误于 1109:57 Syntax error at input 'end of line without line continuation'
```

### Broken code (multi-line parenthesized expression)
```pinescript
bool smtBearDiv = SHOW_SMT and not na(smtRefClose) and (
    (not smtIsNegative and smtMyNewHigh and smtRefClose < nz(smtRefSwingHigh[1], smtRefClose)) or
    (smtIsNegative and smtMyNewHigh and smtRefClose > nz(smtRefSwingHigh[1], smtRefClose))) and close > close[3]
```

### Fixed code (split into intermediate booleans, each on one line)
```pinescript
bool smtBearPos = not smtIsNegative and smtMyNewHigh and smtRefClose < nz(smtRefSwingHigh[1], smtRefClose)
bool smtBearNeg = smtIsNegative and smtMyNewHigh and smtRefClose > nz(smtRefSwingHigh[1], smtRefClose)
bool smtBearDiv = SHOW_SMT and not na(smtRefClose) and (smtBearPos or smtBearNeg) and close > close[3]
```

### Rule
Every Pine v5 statement must complete on a single line. To express a complex `or`/`and` chain, declare each clause as a named `bool` variable on its own line, then combine them in a final single-line statement. This is more readable AND patchable than a long inline ternary.

### Pre-delivery grep check
```bash
# Lines ending with (, or, or and (excluding comments) = likely multi-line expression
grep -nE '^\s*[^/].*(\(|or|and)\s*$' svp_v10.txt | grep -v '//'
```

## Pre-delivery grep checks

Run these on the final `.txt` / `.pine` before copying to the desktop:

```bash
# 1. Multi-line string literals (real newline between quotes)
grep -n '"$' svp_v10.txt

# 2. Wrong array declarations
grep -nE '\b(string|int|float|bool)\s+\w+\s*\[\s*\]\s*=' svp_v10.txt

# 3. request.security with bare function reference (no parens) — causes "Undeclared identifier"
#    Matches f_<name> followed by , or ) but NOT followed by ( (which would be a correct call)
grep -nE 'request\.security\([^,]+,\s*[^,]+,\s*f_\w+\s*[,)]' svp_v10.txt
```

All three patterns should return zero matches.

## Related pitfalls

- `references/pine-udt-na-short-circuit.md` — UDT field access after `na()` guard.
- `references/pine-bulk-edit-python-workaround.md` — when `patch` fails on `"` escapes, use Python bulk edits.
- `references/pre-delivery-settings-checklist.md` — full pre-flight checklist.
