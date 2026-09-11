# Pine 编译 token 上限削减实案（2026-07-09）

## 问题

主指标 `SVP+ICT+VWAP+CVD` 编译报：
```
Compiled code contains too many tokens: 81303. The limit is 80000
```

源码 189,427 字符 / 3,225 行 → 81,303 tokens，超出 1,303 tokens。

同时存在 `cvdBearStars`/`cvdBullStars` 未定义变量（致命编译错误），两问题需一并修复。

## token 密度基准

实测：189,427 字符 → 81,303 tokens → **2.33 字符/token**。
安全线：源码 ≤ ~186,400 字符（80,000 × 2.33）。

## 削减步骤

### Step 1: 修未定义变量（+2 行，+30 字符，可忽略）
在 `cvdBullDiv` 定义后补：
```pine
int cvdBearStars = 0
int cvdBullStars = 0
```

### Step 2: 批量删除死变量（-141 行, -7,828 字符）

用 execute_code 扫描所有"只赋值从未读取"的变量：

```python
dead_vars = [
    'stateText', 'cardLine1', 'cardLine2', 'cardLine3',
    'detailText', 'directionGuideText', 'actionGuideText',
    'nowAdviceText', 'treatmentText', 'valueText', 'vwapText',
    'emaText', 'valuePosText', 'barConfirmText',
    'trendScoreText', 'reversalScoreText'
]
# 对每个变量，删除所有匹配 ^\s*(string\s+VAR\s*=|VAR\s*:=) 的行
```

关键验证：
- `watchText` 和 `invalidText` 仍被面板消费 → **保留**
- `invalidText` 驱动止损价推导（L2689-2706）→ **保留**
- `watchText` 用于面板等待文案（L2927）→ **保留**

### Step 3: 删空 if/else 链（-6 行）

`nowAdviceText` 的 6 分支赋值被删后，if/else 链条件行变空 → 整条删除：
```pine
# 删除前（空分支）：
if dmiHot or vwapExtendedUp or vwapExtendedDn
else if trendLongScore >= 7 and trendLongScore >= trendShortScore + 2
else if trendShortScore >= 7 and trendShortScore >= trendLongScore + 2
...
# 删除后：整条消失
```

### Step 4: 删连带死变量（-1 行）

`valuePos` 只服务于 `valuePosText`（已删），`valueRange` 只服务于 `valuePos` → 连带删除。

### Step 5: 精简面板档位（-4 行）

`ACTION_PANEL_DETAIL` 从三档减到两档：
- `options=["精简", "标准", "完整"]` → `options=["精简", "标准"]`
- 删 `panelDetailFull` 变量及 `完整` 档独有代码路径
- 清理 tooltip 中的"完整"描述

### Step 6: 清理残留注释

- `// —— 标准区（标准/完整显示）——` → `// —— 标准区（标准显示）——`
- `// —— 完整区（可选）——` → 删除

## 最终结果

| 指标 | 原始 | 修复后 | 节省 |
|------|------|--------|------|
| 行数 | 3,225 | 3,072 | 153 行 (4.7%) |
| 字符 | 189,427 | 180,462 | 8,949 (4.7%) |
| 预估 token | 81,303 | ~77,455 | ~3,848 |
| vs 80000 限制 | 超出 1,303 | 余量 2,545 | ✓ |

## 验证清单

- [x] cvdBearStars/cvdBullStars 已定义
- [x] if-else 链 17 分支完整，每分支 watchText + invalidText 赋值在
- [x] 无空 if/else 分支
- [x] MCP Data Window 11 个 plot 全在
- [x] 14 个 alertcondition 不变
- [x] 10 个 request.security 不变
- [x] 28 个 plot() 不变
- [x] 无残留死变量引用
- [x] 预估 token ~77,455 < 80,000

## 死变量检测脚本（可复用）

```python
import re

code = open('indicator.txt', encoding='utf-8').read()
declared = set(re.findall(r'(?:var\s+)?(?:float|int|bool|string|color)\s+(\w+)\s*=', code))
declared |= set(re.findall(r'(\w+)\s*:=', code))

for var in sorted(declared):
    reads = []
    for i, line in enumerate(code.split('\n'), 1):
        s = line.strip()
        if re.search(r'\b' + re.escape(var) + r'\b', line):
            if (s.startswith(var + ' :=') or
                s.startswith('string ' + var + ' =') or
                s.startswith('float ' + var + ' =') or
                s.startswith('int ' + var + ' =') or
                s.startswith('bool ' + var + ' =') or
                s.startswith(var + ' =') or
                s.startswith('//')):
                continue
            reads.append(i)
    if len(reads) == 0:
        print(f"DEAD: {var}")
```