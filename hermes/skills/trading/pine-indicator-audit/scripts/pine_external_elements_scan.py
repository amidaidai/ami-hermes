#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pine 函数外部元素(CE10116)扫描器 — 20260810 实战验证，20260811 升级 UDF 调用计数，20260812 确认脚本级口径

用法: python pine_external_elements_scan.py <file.pine>
输出: 每个用户函数的加权外部元素数 + **脚本级 TV 估算**（input 总数 + request 返回元素数）。

【20260814 公式修正】TV 的 CE10116 是**脚本级口径**，与函数无关：
- TV 数字 = **全部 input（含 input.source / input.timeframe）+ plot + alert + request**（四类，剥字符串/注释后计数）
- 20260814 实测：主指标上传版 198 input + 43 plot + 1 alert + 8 request = **250/254**（pine_check 编译 0 错 0 警确认）
- 早期文档"260 = 202+43+1+8+2+4"把 source/tf 在 input 之外重复加了（input 正则已含它们）→ 本脚本旧版会虚报超限（报 257 实为 250）。source/tf 计数保留为展示信息，不再计入总和。
- 函数名只是报错锚点；**拆函数/瘦身/转 const/删 const 全部无效——只有真正删除 input.*() 调用**（或 plot/alert/request）才单调降数字
- 最安全减量 = 删低频外观 input（颜色/透明度/宽度，引用处内联默认值，功能不变）
- 函数级加权（本脚本原逻辑）仅供内部一致性参考，TV 报错预测看脚本级估算

函数级规则（保守口径，仅参考）:
- 外部元素 = 函数内引用的全局标识符 + 函数参数 + UDF 调用数；int/float/bool 计 2，string/color 计 1
- 上限 254（TV 实测，20260812 更新；旧文档 60 已过时）
"""
import re
import sys

def scan(path):
    lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
    funcs = []
    for i, ln in enumerate(lines):
        m = re.match(r'^([A-Za-z_]\w*)\((.*?)\)\s*=>', ln)
        if m:
            s = i
            e = len(lines)
            for j in range(s + 1, len(lines)):
                if lines[j] and not lines[j].startswith((' ', '\t')):
                    e = j
                    break
            funcs.append((m.group(1), m.group(2), s, e))
    gdef = {}
    for i, ln in enumerate(lines):
        if any(s <= i < e for _, _, s, e in funcs):
            continue
        m = re.match(r'\s*(?:const\s+)?(?:var\s+)?(string|float|int|bool|color)\s+([A-Za-z_]\w*)\s*=', ln)
        if m:
            gdef[m.group(2)] = m.group(1)
        m2 = re.match(r'\s*([A-Za-z_]\w*)\s*=\s*input\.', ln)
        if m2:
            gdef[m2.group(1)] = 'input'
    BUILT = set('close open high low volume time timenow bar_index barstate syminfo na nz ta str '
                'math array line label box table color position xloc yloc text size input request '
                'timeframe format plot if else for while var const type switch and or not true false '
                'break continue return float int bool string rsi sma ema rma wma vwap atr change '
                'highest lowest crossover crossunder pivothigh pivotlow barssince cum avg max min abs '
                'sqrt pow log exp floor ceil round sign sin cos tan contains replace tostring tofloat '
                'toint toupper tolower split trim length style width left right center middle top '
                'bottom isconfirmed islast isfirst period in_seconds'.split())
    def wt(t):
        return 2 if t in ('float', 'int', 'bool') else 1
    def pw(params):
        w = 0
        for p in params.split(','):
            m = re.match(r'\s*(string|float|int|bool|color)\s+\w+', p)
            if m:
                w += wt(m.group(1))
        return w
    bad = []
    udf_names = [f[0] for f in funcs]
    LIMIT = 254  # 20260812 实测 TV 上限（旧 60 已过时）
    for name, params, s, e in funcs:
        names = set()
        for ln in lines[s:e]:
            names |= set(re.findall(r'[A-Za-z_]\w*', ln))
        ext = {n: gdef[n] for n in names if n in gdef and n not in BUILT
               and not n.startswith(('color.', 'position.', 'text.', 'size.', 'array.', 'str.',
                                     'math.', 'ta.', 'barstate.', 'syminfo.', 'linefill.'))}
        w = sum(wt(t) for t in ext.values()) + pw(params)
        # 20260811 升级：UDF 调用计数（本脚本定义的函数名出现在函数体内，每调用计 1）
        body = '\n'.join(lines[s + 1:e])
        udf_calls = 0
        for u in udf_names:
            if u != name:
                udf_calls += len(re.findall(r'(?<![\w.])' + re.escape(u) + r'\s*\(', body))
        w += udf_calls
        flag = f'  <-- 函数级超限(>={LIMIT})!' if w >= LIMIT else ''
        print(f'{name}({params[:60]}): 加权={w} 标识符={len(ext)} UDF调用={udf_calls}{flag}')
        if w >= LIMIT:
            bad.append((w, name))
    # 20260814 脚本级 TV 估算（修正后四类口径：全部 input 含 source/tf + plot + alert + request）
    code_all = '\n'.join(lines)
    code_clean = re.sub(r'"[^"]*"', '""', re.sub(r'//.*', '', code_all))
    def cnt(pat):
        return len(re.findall(pat, code_clean))
    input_count  = cnt(r'input\.\w+\(')
    plot_count   = cnt(r'\bplot\(')
    alert_count  = cnt(r'\balert\(')
    req_count    = cnt(r'request\.\w+\(')
    source_count = cnt(r'input\.source\(')     # 展示用；已含在 input_count，不重复计
    tf_count     = cnt(r'input\.timeframe\(')  # 展示用；已含在 input_count，不重复计
    tv_est = input_count + plot_count + alert_count + req_count
    tv_flag = '  <-- TV 超限(>254)!' if tv_est > 254 else ''
    print(f'\n[脚本级 TV 估算] input(含source/tf)={input_count} + plot={plot_count} + alert={alert_count} + request={req_count} = {tv_est} / 254{tv_flag}')
    print(f'  (其中 input.source={source_count}、input.timeframe={tf_count} 已含于 input，不计入总和)')
    print(f'函数总数: {len(funcs)} | 函数级超限: {bad if bad else "无 ✓"}')
    return bad

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python pine_external_elements_scan.py <file.pine>')
        sys.exit(1)
    scan(sys.argv[1])
