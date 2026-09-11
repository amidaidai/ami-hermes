# Pine v6 批量改写的编译错误清单 + 打包总线位宽约束（2026-09-10）

一次改 3000+ 行 Pine 踩到的 4 类编译错误 + 1 类数值设计约束。
每条都是**真实报错 → 真实修法**，全部在本日实际发生并修复。

> 本文件只写编译/改写工程层。`na` 语义、三态 plot 指纹、外部审计取证、
> Pine 缺陷模式表 → 一律见 `references/pine-na-semantics-and-external-audit-verification-20260910.md`，不在此重复。

## 一、脚本化改写 Pine 的纪律

用 Python 做行替换时**每个替换必须断言锚点唯一**：

```python
def sub(old, new, tag, count=1):
    n = t.count(old)
    assert n == count, f"[{tag}] 锚点命中 {n} 次，应为 {count}"
    t = t.replace(old, new, count)
```

锚点不唯一时（实测 `    int   bornBar` 在 2 个 type 块里都出现），
**把前几行一起写进锚点**消歧，不要 replace_all。

`ast.parse()` 只能查 Python 语法，**查不出 Pine 语法** → 每批改完必须过一次云编译，
不能攒到最后一次性验。

⚠️ 带特殊空格的锚点精确匹配会失败 —— 本项目的输入标签前缀是 EN SPACE `U+2002`。
改用正则锚：

```python
_pat = re.compile(r"^universalen\s+= input\.int\s+\(14,[^\n]*\)$", re.M)
assert len(_pat.findall(a)) == 1
```

## 二、CE10013 `Mismatched input 'X' expecting end of line without line continuation`

**根因：替换串丢了行首缩进。**

在替换里插入多行注释时，若锚点本身带缩进（例如 `if` 块内 4 空格），
替换串的**每一行都必须带同样缩进**；否则注释落到第 0 列，
Pine 认为 `if` 块已结束，下一行 `array.push(...)` 就成了非法语句。

```python
# 错：锚点带 4 空格，注释行不带
sub('    string sweepCntTag = ...',
    '// 说明\n'                     # ← 落到第 0 列，打断 if 块
    '    string sweepCntTag = ...')

# 对：每行都带锚点的缩进
sub('    string sweepCntTag = ...',
    '    // 说明\n'
    '    string sweepCntTag = ...')
```

**识别特征**：报错行号指向你插入块**之后**的那一行（本例报在 `array.push`），
不是你改的那一行。看到「报错行自己看着没问题」就先怀疑前面插进去的块的缩进。

⚠️ 锚点若是**长表达式内部**的片段（如三元续行），替换串里**不要插 `\n`** ——
只换函数名/字面量，保持单行。

## 三、CE10163 `Ternary operations cannot return tuples`

**Pine 禁止三元返回元组。** 常见踩法：想让 `request.security` 带条件。

```pine
# 错
[a,b,c,d] = cond ? request.security(sym, tf, [open,high,low,close], ...) : [na,na,na,na]

# 对：请求本身无条件执行，用三元只选【品种】
string refSym = cond ? sym : syminfo.tickerid
[a,b,c,d] = request.security(refSym, tf, [open,high,low,close], ignore_invalid_symbol=true)
```

附带好处：请求无条件执行 → **历史预取不会被条件分支延后**到实时才首次访问。
代价：request 上下文 +1（免费档 40，通常有余量）。
**不要**试图用 `if` 块包 `request.security` 绕过 —— 那是另一条限制。

## 四、CW10018 局部变量不能用于历史引用

**函数内声明的变量不支持 `[1]` 这类历史引用。**

```pine
f(int x) =>
    int key = dayofmonth(time)      // ← 局部
    bool rolled = key != key[1]     // ✗ CW10018

# 对：提到全局，用 var 保存上一根
int gKey = dayofmonth(time)
var int gKeyPrev = na
bool gRolled = not na(gKeyPrev) and gKey != gKeyPrev
gKeyPrev := gKey

f(int x) =>
    ... gRolled ...                 // 全局可读
```

## 五、CE10272 `Undeclared identifier`

**改名不彻底。** 把变量从 A 改成 B 时，若 A 在别处仍被引用就报这个。
实测：`sessDayRolled` 在起点判据改成了 `gSessDayRolled`，**终点判据**却忘了改。
→ 同一个改动要**全局搜一遍旧名**再收工。

## 五-bis、CE10271 `Could not find method` —— `method` 必须先声明后调用

复用已有 `method` 来消重时（把内联的方法体换成 `this.storeSingleBar(h, l, v)`），
若该方法的定义在**调用点之后**，就报 CE10271。

→ Pine 的 `method` 与普通函数一样**必须先定义后使用**。
消重时把被复用的 `method` 定义**整段提到调用点之前**，再删内联副本。

```python
# 先摘掉定义 → 再插到调用方之前 → 最后替换内联体
t = t.replace(SINGLE_DEF, "", 1)
t = t.replace(BATCH_HEAD, SINGLE_DEF + BATCH_HEAD, 1)
t = t.replace(INLINE_BODY, "        this.storeSingleBar(h, l, v)", 1)
```

⚠️ 复用会把被复用方法自带的守卫（如 `if array.size(...) < MAX_ARRAY_SIZE`）
一并引入到原内联路径上 —— 这是**行为变化**，要在注释里写明并向用户披露。

## 五-ter、CE10198 `Object has no field` —— 插入点把 `type` 定义切断了

给某个 `type` 后面插 UDF 时，若锚在**看起来像结尾的字段**上，会把类型**从中间切断**，
后半字段变成游离语句 → 引用它们的地方报 `Object has no field`。

实测：`SessionState` 类型锚在 `    ICTLevel lvlLowObj`，
但它后面还有 `    string dayName = ""` 和 `    bool ended = false` →
`st.ended := false` 报 CE10198。

→ **锚在类型真正的最后一个字段上**；不确定就先打印整个类型块的范围再定锚点。

```python
TAIL = '    string dayName = ""\n    bool ended = false\n'
assert t.count(TAIL) == 1
t = t.replace(TAIL, TAIL + UDF, 1)
```

## 五-quater、命名常量提取：先替换用法，再插入定义

把重复表达式提取成命名常量时，若**先插入定义行再全局替换**，
定义行自己也会被替换成自引用：

```pine
color LBL_BG = LBL_BG      // ✗ 直接坏掉
```

→ 顺序必须是**先 `replace(用法)` → 再插入定义行**，定义行里写原始表达式。

## 六、打包整数的位宽硬约束：不能靠「上移合同号」加字段

用一条十进制总线塞多字段时（`contract*1e11 + state*1e10 + ...`），
**加新字段不能把合同号上移一位**：

```
22003 * 1e12 = 2.2003e16  >  2^53 ≈ 9.007e15   ✗ 整数精度崩
```

**改用「值域哨兵」**：挑一个**正常编码取不到**的值当「缺失」标记。
本项目实例：OI 变化率正常编码域 `10000±9999 = 1..19999`，取不到 0 →
`0` 就是天然的「无 OI」哨兵，**零位移、零新增位**。

改语义时**升级合同号**（22002 → 22003），且**解码端同时接受两版**：

| 组合 | 行为 |
|---|---|
| 旧主 + 新副 | 合同不匹配 → fail-closed（正确，不静默误读） |
| 新主 + 旧副 | 按旧语义解，行为不变 |

**交付前必算** `最大合法包 < 2^53`，并把这条写进注释 —— 它是设计约束，不是巧合。

## 七、验收断言怎么写

- **全组合往返**：pack 每个字段（含负值域、边界 999、布尔两态）都跑编码→解码回等。
- **对照「修复前的错误包」**：把旧编码产出的那个具体数值喂进新解码器，
  确认它解出的是错的（例如 `1099899 → 998/9/6`）。
  **这比断言新包正确更有说服力** —— 它证明这个修复确实改变了原本出错的路径。
- **边界必测**：`0.0001` 量级价格（只测 BTC 看不出格式串问题）、缺失/零/正/负四种 OI、
  以及 `最大包 < 2^53`。
- **旧断言要容或式放宽**：写死了旧版本号的测试（如 `CONTRACT_VERSION == "v13"`）
  在升级时会全部报错 → 改成 `in ("v13", "v14")` 并注明「版本升级时需同步放宽」。
