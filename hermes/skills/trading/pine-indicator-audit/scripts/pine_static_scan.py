#!/usr/bin/env python3
"""Pine 指标静态扫描 — 审计第 0 步，一次性输出所有客观指标。
用法: python pine_static_scan.py <指标文件.txt> [更多文件...]

输出: request.security 调用点 / plot 计数 / line-box-label 计数 /
      typed-def 重复(注意函数内局部变量是误报) / 关键变量 def 顺序 / 重绘信号 /
      未定义变量引用(致命)。
人工只需对照阈值判读, 不必逐行通读。"""
import re
import sys

DEFPAT = re.compile(
    r'^\s*(?:var\s+)?(?:float|int|bool|string|color|line|box|label|table)\s+([A-Za-z_]\w*)\s*=')

# Known declaration dependencies that Pine must satisfy (dependency before consumer).
ORDER_DEPS = {
    'panelDirVal': ['pdShort', 'kzShort', 'sweepCntText', 'dmiCompact', 'actionBiasWord'],
    'panelConclusionVal': ['actionStateText', 'panelRiskOne'],
    'panelEntryVal': ['rrHardBlock'],
}

# Pine 内置标识符（不需声明即可使用）
PINE_BUILTINS = {
    'na','nz','close','open','high','low','hl2','hlc3','ohlc4','volume','time','time_close','timenow',
    'bar_index','barstate','str','math','ta','array','color','plot','line','box',
    'label','polyline','table','request','syminfo','timeframe','input','display',
    'size','position','format','xloc','yloc','text','dayofweek','chart','fixnan',
    'ticker','order','color','true','false','and','or','not','if','else','for',
    'while','switch','var','type','method','export','import','this','return',
    'continue','break','string','int','float','bool','color','line','box','label',
    'table','array','const','hline','linefill','indicator','strategy','library','fill','bgcolor','plotchar','plotshape',
    'plotcandle','plotbar','alertcondition','alert','barmerge','lookahead',
    'ignore_invalid_symbol','ignore_invalid_ticker','dot','dash','dotted','dashed',
    'solid','solid','curved','smooth','ascending','descending','maxval','minval',
    'step','inline','group','options','tooltip','title','shorttitle','overlay',
    'max_bars_back','max_lines_count','max_labels_count','max_boxes_count',
    'max_polylines_count','dynamic_requests','format','precision','force_overlay',
    'force_overlay','display','editable','show_last','offset','show_last',
    'dayofweek','sunday','monday','tuesday','wednesday','thursday','friday',
    'saturday','isconfirmed','isfirst','islast','ishistory','isrealtime',
    'isnew','lastbarindex','lastbarvalue','bar_index','n','net','sum','avg',
    'median','variance','stdev','round','floor','ceil','abs','max','min','pow',
    'sqrt','log','exp','sin','cos','tan','atan','sign','random','range',
    'tostring','tonumber','tobool','contains','replace','substring','length',
    'lower','upper','split','concat','format','printf','split','from','get',
    'set','push','pop','shift','unshift','clear','size','new','new_float',
    'new_int','new_bool','new_string','new_color','new_line','new_label',
    'new_box','new_table','sort','sort_indices','reverse','index','includes',
    'every','some','find','fill','copy','slice','remove','insert','first',
    'last','binary_search','binary_search','binary_search','binary_search',
    'avg','sum','min','max','median','variance','stdev','mode','percentile',
    'percentile_linear_interpolation','percentile_nearest_rank',
    'cross','crossover','crossunder','change','highest','lowest','highestbars',
    'lowestbars','barssince','valuewhen','cum','sma','ema','wma','rma','vwma',
    'swma','alma','hma','rvi','vwma','stdev','correlation','atr','sar',
    'supertrend','cci','dmi','adx','di','dmi_plus','dmi_minus','sma',
    'macd','rsi','stoch','mom','roc','willr','sar','bb','bbw','kc','kcw',
    'psar','donchian','donchian_width','mfi','obv','vwap','vwma','linreg',
    'median','percentile','percentile_linear_interpolation',
    'percentile_nearest_rank','pivothigh','pivotlow','rise','fall',
    'fall','highest','lowest','sum','cum','avg','median','variance','stdev',
    'correlation','atr','tr','rma','wma','swma','alma','hma','linreg',
    'change','cross','crossover','crossunder','barssince','valuewhen',
    'pivothigh','pivotlow','atr','tr','cc','cci','dmi','dmi_plus','dmi_minus',
    'dmi_plus','dmi_minus','macd','rsi','stoch','mom','roc','willr','sar',
    'bb','bbw','kc','kcw','psar','donchian','donchian_width','mfi','obv',
    'vwap','vwma','linreg','percentile','percentile_linear_interpolation',
    'percentile_nearest_rank','rvi','supertrend','dema','tema','wma',
    'rma','hma','alma','swma','linreg','sma','ema','rma','wma','vwma',
}


def strip_strings_and_comments(line):
    """Remove single/double-quoted strings and // comments, preserving code tokens."""
    out = []
    i = 0
    quote = None
    while i < len(line):
        ch = line[i]
        if quote is not None:
            if ch == '\\' and i + 1 < len(line):
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ('"', "'"):
            quote = ch
            i += 1
            continue
        if ch == '/' and i + 1 < len(line) and line[i + 1] == '/':
            break
        out.append(ch)
        i += 1
    return ''.join(out)


def estimate_expanded_requests(lines, clean_lines):
    """Approximate request.* expansion through local Pine helper calls.

    A raw grep under-counts helpers such as GetExchange() -> GetRequest() ->
    request.security(). Identical contexts may still be deduplicated by TradingView,
    so this is explicitly an estimate rather than a guaranteed unique-call count.
    """
    def_pat = re.compile(r'^\s*(?:method\s+)?([A-Za-z_]\w*)\s*\([^)]*\)\s*=>')
    defs = []
    for idx, clean in enumerate(clean_lines):
        m = def_pat.match(clean)
        if m:
            defs.append((idx, m.group(1), len(clean) - len(clean.lstrip())))

    ranges = {}
    owned = set()
    for start, name, indent in defs:
        end = start + 1
        while end < len(clean_lines):
            clean = clean_lines[end]
            if clean.strip() and len(clean) - len(clean.lstrip()) <= indent:
                break
            end += 1
        ranges[name] = (start, end)
        owned.update(range(start, end))

    fn_names = set(ranges)
    req_pat = re.compile(r'\brequest\.security(?:_lower_tf)?\s*\(')

    def scope_stats(text):
        direct = len(req_pat.findall(text))
        calls = {}
        for fn in fn_names:
            n = len(re.findall(r'\b' + re.escape(fn) + r'\s*\(', text))
            if n:
                calls[fn] = n
        return direct, calls

    stats = {}
    for name, (start, end) in ranges.items():
        first = clean_lines[start].split('=>', 1)[1]
        text = '\n'.join([first] + clean_lines[start + 1:end])
        stats[name] = scope_stats(text)

    top_text = '\n'.join(clean_lines[i] for i in range(len(clean_lines)) if i not in owned)
    top_direct, top_calls = scope_stats(top_text)

    memo = {}

    def fn_cost(name, stack=()):
        if name in memo:
            return memo[name]
        if name in stack:
            return 0
        direct, calls = stats.get(name, (0, {}))
        total = direct
        for callee, count in calls.items():
            if callee != name:
                total += count * fn_cost(callee, stack + (name,))
        memo[name] = total
        return total

    total = top_direct
    breakdown = []
    for fn, count in sorted(top_calls.items()):
        cost = fn_cost(fn)
        if cost:
            total += count * cost
            breakdown.append((fn, count, cost, count * cost))
    return total, top_direct, breakdown


def scan(path):
    lines = open(path, encoding='utf-8', errors='replace').read().splitlines()
    clean_lines = [re.sub(r'#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})\b', '', strip_strings_and_comments(line)) for line in lines]
    print(f"\n===== {path}  ({len(lines)} lines) =====")

    reqs = [(i, l.strip()) for i, l in enumerate(lines, 1)
            if 'request.security' in l and not l.strip().startswith('//')]
    print(f"[配额] request.security 调用点: {len(reqs)}  (上限 40; 函数被调 N 次 = N×函数内 req 数)")
    for i, l in reqs:
        print(f"   L{i}: {l[:100]}")
    expanded, top_direct, req_breakdown = estimate_expanded_requests(lines, clean_lines)
    print(f"   展开估算: {expanded} (顶层直接 {top_direct}; TradingView 可能对完全相同上下文去重)")
    for fn, calls, per_call, subtotal in req_breakdown:
        print(f"      {fn}: 顶层调用 {calls} 次 × 每次展开 {per_call} = {subtotal}")

    plots = [i for i, l in enumerate(clean_lines, 1)
             if re.search(r'(?<![A-Za-z0-9_])plot\s*\(', l)]
    fills = [i for i, l in enumerate(clean_lines, 1)
             if re.search(r'(?<![A-Za-z0-9_.])fill\s*\(', l)]
    bgcolors = [i for i, l in enumerate(clean_lines, 1)
                if re.search(r'(?<![A-Za-z0-9_.])bgcolor\s*\(', l)]
    alerts = [i for i, l in enumerate(clean_lines, 1)
              if re.search(r'(?<![A-Za-z0-9_.])alertcondition\s*\(', l)]
    min_plot_counts = len(plots) + len(fills) + len(bgcolors) + len(alerts)
    objs = sum(1 for l in lines if re.search(r'line\.new|box\.new|label\.new', l))
    print(f"[绘制] plot: {len(plots)}; fill: {len(fills)}; bgcolor: {len(bgcolors)}; alertcondition: {len(alerts)}")
    print(f"   最低 plot-count 估算: {min_plot_counts}/64（series color 可能再加计数；以 TV 编译结果为准）")
    print(f"   line/box/label.new 调用点: {objs} (动态对象各<500)")

    # typed-def 重复 —— 函数内/循环内局部变量会误报, 需人工按行号判别作用域
    seen, dups = {}, []
    for i, l in enumerate(lines, 1):
        m = DEFPAT.match(l)
        if m:
            v = m.group(1)
            if v in seen:
                dups.append((v, seen[v], i))
            else:
                seen[v] = i
    print(f"[重复def] {dups if dups else 'none'}")
    print("   ⚠ 单字母/局部名(i,j,sec,v,eFast...)落在 f_xxx()=> 或 for 内 = 合法局部, 误报勿改")

    pos = {}
    tracked = set(ORDER_DEPS)
    for deps in ORDER_DEPS.values():
        tracked.update(deps)
    for v in tracked:
        for i, l in enumerate(lines, 1):
            if re.match(r'\s*(?:var\s+)?(?:float|int|bool|string|color)\s+' + re.escape(v) + r'\b', l):
                pos[v] = i
                break
    bad = []
    for consumer, deps in ORDER_DEPS.items():
        if consumer not in pos:
            continue
        for dep in deps:
            if dep in pos and pos[dep] > pos[consumer]:
                bad.append((dep, pos[dep], consumer, pos[consumer]))
    found = sorted(pos.items(), key=lambda x: x[1])
    print(f"[def顺序] {found}")
    print(f"   def-before-use 违例: {bad if bad else 'none'}")

    rep = [(i, l.strip()[:90]) for i, l in enumerate(lines, 1)
           if re.search(r'lookahead|closeReclaim', l) or 'isSwept :=' in l]
    print(f"[重绘] lookahead/closeReclaim/isSwept 信号点: {len(rep)}")
    for i, l in rep:
        print(f"   L{i}: {l}")
    print("   规则: lookahead_on + [1]/[3] 已收柱偏移 = 非重绘正确写法, 勿标 P0")

    # ===== 新增：未定义变量引用扫描（致命编译错误） =====
    code = '\n'.join(clean_lines)
    # 所有声明的变量名（typed def + := 赋值 + 函数参数 + input.* 返回）
    declared = set()
    for m in re.finditer(r'(?:var\s+)?(?:float|int|bool|string|color|line|box|label|table)\s+([A-Za-z_]\w*)\s*=', code):
        declared.add(m.group(1))
    for m in re.finditer(r'([A-Za-z_]\w*)\s*:=', code):
        declared.add(m.group(1))
    # Untyped assignments such as `pEma1 = plot(...)`.
    for m in re.finditer(r'^\s*([A-Za-z_]\w*)\s*=\s*(?!=)', code, re.MULTILINE):
        declared.add(m.group(1))
    # Tuple destructuring: collect every identifier inside [a, b, c] = ...
    for m in re.finditer(r'\[([^\]]+)\]\s*=', code):
        declared.update(re.findall(r'\b([A-Za-z_]\w*)\b', m.group(1)))
    # Loop variables.
    for m in re.finditer(r'\bfor\s+([A-Za-z_]\w*)\s*=', code):
        declared.add(m.group(1))
    for m in re.finditer(r'\bfor\s*\[([^\]]+)\]\s+in\b', code):
        declared.update(re.findall(r'\b([A-Za-z_]\w*)\b', m.group(1)))
    # input.* 返回的变量
    for m in re.finditer(r'(?:float|int|bool|string|color)\s+([A-Za-z_]\w*)\s*=\s*input\.', code):
        declared.add(m.group(1))
    # 函数/方法定义参数：每个逗号分段取默认值前的最后一个标识符。
    for m in re.finditer(r'(?:method\s+)?\w+\s*\(([^)]*)\)\s*=>', code):
        for piece in m.group(1).split(','):
            lhs = piece.split('=', 1)[0].strip()
            pm = re.search(r'([A-Za-z_]\w*)\s*$', lhs)
            if pm:
                declared.add(pm.group(1))

    # 收集所有被引用的标识符（排除注释行）
    referenced = set()
    for i, l in enumerate(clean_lines, 1):
        for m in re.finditer(r'\b([a-zA-Z_]\w*)\b', l):
            referenced.add(m.group(1))

    # 排除 Pine 内置 + 声明的变量 + 单字符 + 全大写常量
    candidates = referenced - declared - PINE_BUILTINS
    candidates = {c for c in candidates if len(c) > 2 and not c.isupper()}

    # 进一步排除函数名（后面跟 `(` 的）和类型名
    func_defs = set(re.findall(r'(?:method\s+)?(\w+)\s*\([^)]*\)\s*=>', code))
    candidates -= func_defs
    type_defs = set(re.findall(r'^type\s+(\w+)', code, re.MULTILINE))
    candidates -= type_defs
    # Members (`obj.field`, `namespace.method`) and named arguments are not variables.
    member_names = set(re.findall(r'\.\s*([A-Za-z_]\w*)', code))
    named_args = set(re.findall(r'\b([A-Za-z_]\w*)\s*=\s*(?!=)', code))
    candidates -= member_names
    candidates -= named_args

    if candidates:
        print(f"[未定义变量] 可疑引用 (致命编译错误候选): {len(candidates)}")
        for c in sorted(candidates):
            # 找引用行
            refs = [(i, lines[i-1].strip()[:80]) for i, l in enumerate(clean_lines, 1)
                    if re.search(r'\b' + re.escape(c) + r'\b', l)]
            if refs:
                print(f"   ⚠ {c}: {refs[0][0]}处引用, 首次 L{refs[0][0]}: {refs[0][1]}")
        print("   ⚠ 注意：此为粗筛，可能有误报（函数参数名、字段访问等）。无声明=致命。")
    else:
        print(f"[未定义变量] none ✓")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for p in sys.argv[1:]:
        scan(p)