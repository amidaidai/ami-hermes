#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""棠溪 Pine 指标静态量化扫描 — 用于审计基线对比。
用法: python static_scan.py <file1.pine> [file2.pine ...]
规则(与记忆一致): series-color plot 计 2(含 ?/变量/color.XXX/cGood/cBad/cWarn/cLabel/cVal/PNL_),
常量 #hex 或无色计 1。最坏式 = Σplot + alertcondition + bgcolor + Σfill (免费档上限 64)。
"""
import re, sys

def scan(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        src = f.read()
    lines = src.split('\n')
    n_lines = len(lines)
    n_chars = len(src)
    n_tokens = int(n_chars / 2.33)

    plots = []
    for i, ln in enumerate(lines, 1):
        if re.search(r'\bplot\(', ln):
            m = re.search(r'color\s*=\s*([^,\)]+)', ln)
            ce = m.group(1).strip() if m else None
            is_series = bool(re.search(r'color\s*=\s*[^#,\)]', ln))
            plots.append((i, ln.strip()[:80], ce, is_series))
    n_plot = len(plots)
    n_series = sum(1 for p in plots if p[3])
    worst = sum(2 if p[3] else 1 for p in plots)
    n_bgcolor = len(re.findall(r'\bbgcolor\(', src))
    n_fill = len(re.findall(r'\bfill\(', src))
    n_alertcond = len(re.findall(r'\balertcondition\(', src))
    n_alert = len(re.findall(r'\balert\(', src))
    worst_total = worst + n_alertcond + n_bgcolor + n_fill

    n_req_sec = len(re.findall(r'\brequest\.security\(', src))
    n_req_ltf = len(re.findall(r'\brequest\.security_lower_tf\(', src))
    n_input = len(re.findall(r'\binput\.(string|int|float|bool|color|timeframe|session|source)\b', src))
    n_table_cell = len(re.findall(r'\btable\.cell\(', src))
    # 死变量启发式: 顶层 "name = " 定义后全文出现 ≤1 次
    defined = re.findall(r'^(?:float|int|bool|string|color|var\s+\w+|\w+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=', src, re.M)
    dead = sorted({d for d in set(defined) if len(re.findall(r'\b' + re.escape(d) + r'\b', src)) <= 1})[:40]
    tf_strings = sorted(set(re.findall(r'["\'](\d+S?|1|3|5|10|15|30|60|240|D|W|M|12M)["\']', src)))

    print(f"===== {path} =====")
    print(f"行数: {n_lines} | 字符: {n_chars} | token估算: {n_tokens}")
    print(f"plot: {n_plot} (series-color: {n_series}) | 最坏式: {worst} + alertcond {n_alertcond} + bgcolor {n_bgcolor} + fill {n_fill} = {worst_total} / 64 (余 {64-worst_total})")
    print(f"request.security: {n_req_sec} | security_lower_tf: {n_req_ltf} | input: {n_input} | table.cell: {n_table_cell}")
    print(f"alert(): {n_alert} | alertcondition(): {n_alertcond}")
    print(f"锚定TF字符串: {tf_strings}")
    print(f"疑似死变量(出现≤1次): {dead}")
    print()
    for i, txt, ce, s in plots:
        if s:
            print(f"  [series] L{i}: {txt}  color={ce}")
    return {'lines': n_lines, 'chars': n_chars, 'plots': n_plot, 'series': n_series,
            'worst': worst_total, 'req_sec': n_req_sec, 'req_ltf': n_req_ltf,
            'inputs': n_input, 'cells': n_table_cell, 'alerts': n_alert}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python static_scan.py <file.pine> [...]")
        sys.exit(1)
    results = [scan(p) for p in sys.argv[1:]]
    print("RESULT_JSON:", __import__('json').dumps(results, ensure_ascii=False))
