#!/usr/bin/env python3
"""Check .pine source files for CRLF/mixed line endings that break TradingView compilation (CE10156).

Usage:
    python check_line_endings.py <file.pine> [...]

Exit 0 = all files clean LF; exit 1 = at least one file has CRLF or bare \\r (auto-print fix command).
"""
import sys


def check(path: str) -> bool:
    with open(path, "rb") as f:
        d = f.read()
    crlf = d.count(b"\r\n")
    lf = d.count(b"\n") - crlf
    has_bare_cr = b"\r" in d
    ok = crlf == 0 and not has_bare_cr
    print(f"{'OK ' if ok else 'BAD'} {path}: CRLF={crlf} LF={lf} bare\\r={has_bare_cr}")
    return ok


def main(argv) -> int:
    if len(argv) < 2:
        print("usage: python check_line_endings.py <file.pine> [...]")
        return 2
    results = [check(p) for p in argv[1:]]
    if not all(results):
        print("\nFix (LF normalize):  sed -i 's/\\r$//' <file>.pine   # or:  sed -i 's/\\r$//' *.pine")
        print("Verify again after fix — CRLF must be 0 and bare \\r must be False.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
