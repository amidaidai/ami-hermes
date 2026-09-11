# Pine UDT `na` Short-Circuit Pitfall

## Problem

In Pine Script v5, `not na(obj) and obj.field` does NOT reliably short-circuit when `obj` is a User Defined Type (UDT).

```pine
// ❌ BROKEN — runtime error on bar 0
bool svpHighNowSwept = not na(svpHighObj) and svpHighObj.swept
// Error: Cannot access the 'ICTLevel.swept' field of an undefined object. The object is 'na'.
```

Even though `svpHighObj` is declared as `var ICTLevel svpHighObj = na`, the `and` operator evaluates both sides. Pine's short-circuit evaluation for UDT field access is not guaranteed by the language spec.

## Fix

Use explicit `if` blocks instead of `and` chains:

```pine
// ✅ CORRECT
bool svpHighNowSwept = false
bool svpLowNowSwept = false
if not na(svpHighObj)
    svpHighNowSwept := svpHighObj.swept
if not na(svpLowObj)
    svpLowNowSwept := svpLowObj.swept
```

## Pattern

For any UDT field access guarded by a `na()` check:

```pine
// ❌ Always broken for UDTs
bool result = not na(myObj) and myObj.someField

// ✅ Always safe
bool result = false
if not na(myObj)
    result := myObj.someField
```

## Affected UDTs in this codebase

- `ICTLevel` (`.swept`, `.price`, `.isHigh`, `.name`, `.col`, `.isActive`, `.ln`, `.lb`, `.createdAt`, `.isHidden`)
- `VolumeProfileEngine` (`.hPrices`, `.lPrices`, `.volumes`, `.lastPocPrice`, etc.)
- `NakedPOC` (`.price`, `.active`, `.ln`)
- `SessionState` (`.sHigh`, `.sLow`, `.sOpen`, `.ended`)

## Discovery

2026-06-24: `svpHighNowSwept = not na(svpHighObj) and svpHighObj.swept` threw `Cannot access the 'ICTLevel.swept' field of an undefined object` on bar 0 during v9.5 compilation. Fixed by splitting into `if not na()` blocks.
