# Pine 未定义变量引用审计（2026-07-09 实案）

## 问题

主指标 `SVP+ICT+VWAP+CVD` L2126 在 `cvdStateText` 赋值的三元表达式中引用了 `cvdBearStars` 和 `cvdBullStars`，但这两个变量在整个 3225 行代码中**从未被声明或赋值**。

TradingView 编译报 `Undeclared identifier 'cvdBearStars'` → 指标完全无法加载。

## 病代码（L2126）

```pine
cvdStateText := cvdDistributeSell and not cvdDistributeSellQualified ? "派发弱" :
  cvdAbsorbBuy and not cvdAbsorbBuyQualified ? "吸收弱" :
  cvdBearDiv and not cvdBearDivQualified ? "顶背离弱" + (cvdBearStars > 0 ? str.tostring(cvdBearStars) + "★" : "") :
  cvdBullDiv and not cvdBullDivQualified ? "底背离弱" + (cvdBullStars > 0 ? str.tostring(cvdBullStars) + "★" : "") :
  cvdStateText
```

`cvdBearStars` / `cvdBullStars` 在全文只出现这一次，无 `int cvdBearStars = ...` 声明、无 `cvdBearStars := ...` 赋值。

## 根因分析

推测设计了 CVD 背离"星级"评分逻辑（用★数量表示背离强度），但只写了消费端（三元表达式内引用），没写计算端（星级赋值）。

## 修复

### 最小修复（通过编译）

在 `cvdBearDiv` / `cvdBullDiv` 定义之后（约 L974 后）补两行：

```pine
int cvdBearStars = 0
int cvdBullStars = 0
```

指标即可编译加载，背离星级显示为空白（`0 > 0` 为 false，不输出★）。

### 完整修复（补星级计算）

如果要让背离星级生效，需要在 CVD 背离检测逻辑处补充计算。例如按 pivot 摆动幅度或背离次数评分：

```pine
// 示例：按 CVD 背离的 pivot 距离差评分
float _bearDivMag = not na(_pp) and not na(_ppp) ? _pp - _ppp : 0.0
int cvdBearStars = cvdBearDiv ? (_bearDivMag > currATR * 2 ? 3 : _bearDivMag > currATR ? 2 : 1) : 0
float _bullDivMag = not na(_pl2) and not na(_plp) ? _plp - _pl2 : 0.0
int cvdBullStars = cvdBullDiv ? (_bullDivMag > currATR * 2 ? 3 : _bullDivMag > currATR ? 2 : 1) : 0
```

需注意 `currATR` 在 L959 定义，`cvdBearDiv` 在 L973 定义，星级计算应放在 L974 之后。

## 检测方法

### 快速 grep（审计时必跑）

```bash
# 对每个被引用的变量，确认有对应的声明
grep -c "cvdBearStars" 主指标.txt   # 输出 1 = 只被引用
grep -c "cvdBearStars\s*=" 主指标.txt  # 输出 0 = 无声明 → 致命
grep -c "cvdBearStars\s*:= " 主指标.txt  # 输出 0 = 无赋值 → 致命
```

### 用 execute_code 批量扫描未定义变量

```python
import re
code = open('指标文件.txt', encoding='utf-8').read()
# 所有声明/赋值的变量名
declared = set(re.findall(r'(?:var\s+)?(?:float|int|bool|string|color)\s+(\w+)\s*=', code))
declared |= set(re.findall(r'(\w+)\s*:=', code))
# 所有被引用的标识符（粗筛）
referenced = set(re.findall(r'\b([a-zA-Z_]\w*)\b', code))
# 减去 Pine 内置函数/关键字/输入参数
builtins = {'na','nz','close','open','high','low','volume','time','bar_index','str','math','ta','array','color','plot','line','label','box','polyline','table','request','syminfo','timeframe','input','display','size','position','format','xloc','yloc','text','barstate','alertcondition','hline','fill','bgcolor','dayofweek','chart','fixnan','ticker','order','dayofweek','color','true','false','and','or','not','if','else','for','while','switch','var','type','method','export','import','this'}
undefined = referenced - declared - builtins
# 手动排除函数参数名、Pine 内置变量等
```

## 未定义变量 vs def-before-use 的区别

| | 未定义变量 | def-before-use 顺序错 |
|---|---|---|
| 本质 | 变量根本不存在 | 变量存在但声明在使用之后 |
| 错误信息 | `Undeclared identifier 'X'` | `Cannot use 'X' as an argument...` 或运行时 na |
| 严重度 | **致命**（指标无法加载） | 致命或静默 na |
| 检测 | grep 变量名只出现引用无声明 | pine_static_scan.py ORDER_CHAIN 检查 |
| 修法 | 补声明/赋值 | 调整声明顺序到引用之前 |

## 审计清单新增项

在审计清单 §2 代码质量首项加入：
- [ ] **未定义变量引用**（致命）：变量被引用但全文无声明/赋值 → `Undeclared identifier` 编译失败

检查方法：对每个在三元表达式/条件中引用的非内置变量名，grep 确认有 `VAR =` 或 `VAR :=` 声明存在。