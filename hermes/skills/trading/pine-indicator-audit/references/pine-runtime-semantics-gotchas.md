# Pine 运行时语义陷阱（编译通过但行为不符预期）

与「编译陷阱」（CE10xxx 系列）区分：这一类的脚本**编译 0 错 0 警**，
但在图上安静地做错事。全部为 2026-09-11 实盘取证。

排错原则：**当某个字符串变换“只生效了一半”，先怀疑“只替换第一处”，
不要先怀疑数据源**。

## 1. `str.replace` 只替换【第一处】——全部替换要用 `str.replace_all`

官方签名：

```text
str.replace(source, target, replacement, occurrence) → string   // 只替换一处
str.replace_all(source, target, replacement) → string           // 全部替换
```

**现场证据**：磁吸行动格把档位名 `"周四 纽 高"`（两个空格）做
`str.replace(name, " ", "")` 期望去掉全部空格，实际渲染成 `周四纽 高`
—— 只吃掉了第一个空格。用户直接看到了这个残留。

同一缺陷在该脚本里**已存在更久**的另一处：现位行的回踩/反抽档位名也用
`str.replace(x, " ", "")`。它一直没暴露，只因为那些档位名恰好
只有一个空格（`"VAH 76837.8"`）—— 一旦档位名自带空格就会露出同样的半个空格。

**判据**：要「删除全部某字符」时，唯一正确写法是 `str.replace_all`。
只有在明确知道目标子串**最多出现一次**时（去后缀 `.P`、把 `亚洲盘` 换成 `亚`）
才可以用 `str.replace`；这类用法应加注释说明“此处只可能有一处”，
避免后人机械地把 `str.replace_all` 装满全库。

**改动代价**：写成 `str.replace_all` 会多一点字符，在 CE10117 余量紧张时
不要图这点便宜——`str.replace` 的误用代价是可见的错值。

**排错动作**：遇到「字符串处理后只对了一半」时，按顺序查
① 是否用错函数（第一处 vs 全部）② 分隔符是不是同一个码点
（普通空格 U+0020 / EN SPACE U+2002 / 全角 U+3000 会被终端渲染成一样）。
码点用 `[hex(ord(c)) for c in s]` 打印，不要靠眼睛看。

## 2. 打包总线：**不能靠位移加字段**

合同号 ×1e10 上移到 ×1e12 会越过 `2^53` 精确整数上限
（`22003×1e12 = 2.2e16 > 9.007e15`），整数精度直接崩。

新增「字段是否存在」的正确做法是**值域哨兵**：
选择正常编码域取不到的值（例如定点数编码域是 `1..19999`，则 `0` 天然不可达）
来表示「缺失」，合同号只升不位移，主端同时接受新旧两版。

必须断言：最大合法包 `< 2^53`。

## 3. 三元表达式不能返回元组（CE10163）

```pine
// ✗ 编译报 CE10163
[x, y] = cond ? request.security(sym, tf, [open, close], ...) : [na, na]

// ✓ 让请求【无条件执行】，用三元只选品种
string refSym = cond ? sym : syminfo.tickerid
[x, y] = request.security(refSym, tf, [open, close], ignore_invalid_symbol=true)
```

副作用提示：这会真的多一个 request 上下文（配额 +1），
需要在 `request.*` 预算里算进去；不要为了省这一个请求把它塞进 `if` 块
（`request.*` 在局部作用域不可靠）。

## 4. 函数内局部变量不能用历史引用（CW10018）

`int k = ...` 在函数内声明后再写 `k[1]` 会触发 CW10018，
且运行时取不到真正的上一根值。
把需要跨根记忆的量提到**全局**（`var` 或普通全局）再在函数里只读。

实测：给 `manageSession()` 加「交易日 key 变化」判据时中招；
提到全局 `gSessDayRolled` 后正常。

## 5. 方法/函数必须先定义后调用（CE10271）

`method storeBatchBars(...)` 内部调用 `this.storeSingleBar(...)` 时，
后者定义在**下方** → `Could not find method`。
复用既有函数做减重时，要把被调方**整块上移**到调用点之前。

## 6. 类型定义插入点：锚在字段中段会把类型切成两半（CE10198）

`type SessionState` 的字段列表末尾不是看起来的最后一个字段。
例如末尾实际是 `bool ended = false`，而 `ICTLevel lvlLowObj` 之后还有字段；
锚在 `lvlLowObj` 插函数，会把类型截断，报
`Object has no field "ended"`。
**插入点必须锚在该类型定义的真正最后一行**，并在改完后回读类型块确认完整。

## 7. 命名常量提取：先替换用法，再插定义

```python
# ✗ 先插入 color LBL_BG = color.new(A, B)，再全局 replace(default_expr → LBL_BG)
#   → 定义行自己被替换成  color LBL_BG = LBL_BG
# ✓ 先 replace 掉所有用法，再把定义行按原文拼回
```

## 8. 验证纪律

- 每个锚点替换都要 `assert count == expected`；静默 no-op 是最隐蔽的错误。
- 替换串**必须沿用锚点的行首缩进**，否则会打断 `if` 块（CE10013）。
- 改完仍要**看真实渲染**：编译 0 错 ≠ 行为正确。§1 的 bug 就是
  编译全绿、面板上肉眼可见地错。
