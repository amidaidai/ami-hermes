#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pine 跨行表达式机械合并工具（2026-08-09 审计教训固化）
把"行尾是运算符（? : + - * / , ( = 等 或 and/or）"的跨行表达式合并为单行，
规避 Pine v6 行尾续行规则的 CE10156 风险。

用法: python merge_multiline_pine.py <file.pine> [more.pine ...]
输出: 原文件原地改写（先备份 .bak），行尾统一 LF。

注意:
- Pine v6 续行只保证"行尾 \\、括号内、开放括号、逗号、二元运算符"；
  三元运算符 ?/: 行尾续行不可靠，会报 CE10156，且语法错误会连带误报
  "Undeclared identifier / Could not find function"（官方 API 如
  sourcetostring/barstate.isreplay 报错时先查语法错误）。
- CRLF 行尾会让行尾运算符续行在 TV 编译器下必报 CE10156，文件必须 LF。
- 本脚本会跳过 // 注释行（注释不会被拼进表达式；若"运算符行尾+下一行注释"
  出现则拆开保留，但此时表达式仍跨行——需人工处理）。
- 函数定义 "x()=>" 行尾的 => 不是续行问题，脚本自动跳过。
"""
import re, sys, os, shutil

SINGLE_OPS = set('?:+-*/,(=><!&|^~')


def ends_with_op(line):
    t = line.rstrip()
    if not t:
        return False
    if t.endswith('\\'):
        return True
    if t[-1] in SINGLE_OPS:
        return True
    if re.search(r'\s(and|or)$', t):
        return True
    return False


def is_comment(line):
    return line.strip().startswith('//')


def merge_file(path):
    raw = open(path, encoding='utf-8').read()
    had_crlf = '\r\n' in raw
    lines = raw.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    out, i, merged = [], 0, 0
    while i < len(lines):
        line = lines[i]
        if is_comment(line) or not ends_with_op(line):
            out.append(line)
            i += 1
            continue
        buf = line.rstrip()
        if buf.endswith('\\'):
            buf = buf[:-1].rstrip()
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if is_comment(nxt):
                # 注释不能拼进表达式：拆开保留（此时表达式仍跨行，需人工处理）
                out.append(buf)
                out.append(nxt)
                buf = None
                j += 1
                break
            buf = buf + ' ' + nxt.strip()
            j += 1
            if not ends_with_op(nxt):
                merged += 1
                break
            if buf.endswith('\\'):
                buf = buf[:-1].rstrip()
        if buf is not None:
            out.append(buf)
        i = j
    shutil.copy2(path, path + '.bak')
    open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
    print(f"{os.path.basename(path)}: 合并 {merged} 处, {len(lines)} -> {len(out)} 行"
          f"{' (原CRLF已转LF)' if had_crlf else ''}")


if __name__ == '__main__':
    for p in sys.argv[1:]:
        merge_file(p)
