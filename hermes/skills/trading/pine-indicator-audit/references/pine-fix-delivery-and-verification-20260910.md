# 双指标「修复 → 本地交付 → 验证」闭环（2026-09-10 实案）

适用触发：审计出 P0/P1/P2 之后，用户说 **"修复指标之后给我，我自己来验证"**。
交付物不是一个补丁说明，而是：**两份可直接上机的 .pine + 一份可复跑的验证脚本 + 一份交付说明**。

## 0. 用户偏好（硬约束，先记住）

- 用户说"我自己来验证" = **不要挂图、不要改编辑器、不要替用户跑客户端编译**。改完落盘交付即可。
- 交付目录固定：桌面 `hermes下载文件/<任务名>_YYYYMMDD/`，文件名带修改日期，保留旧版。
- 交付文件格式：UTF-8、**LF**、无 BOM（与上游源文件一致）。
- 报告必须把「已验证 / 未验证」分开写。服务器 `translate_light` 通过 **不等于** 客户端 CE10117 通过。
- 上机顺序写清楚：**先副指标、再主指标**；主指标 `input.source` 要指名选副指标那条总线 plot 的标题
  （本例是 `Basic Packed Bus (唯一主副连接)`），不要让用户猜。

## 1. 3000+ 行 Pine 的安全变换：行级 + 字符串级两段式

手敲 `patch` 在 3400 行文件上很容易因上下文漂移失败；一次性 `write_file` 覆盖整个文件又无法审阅。
用一段脚本，**每一步都带断言**，产出可 diff 的新文件：

```
阶段 A 行级编辑（按 1-based 行号）
  EDITS = [(start, end, 首行必须包含, 末行必须包含, 替换块), ...]
  1) 先对全部条目做断言（首行/末行 needle 命中），任何一条不符立刻报错并打印实际内容
  2) 再按起始行**降序**应用，行号不会漂移
阶段 B 字符串级编辑（行号已变，改用唯一子串）
  STRING_EDITS = [(old, new[, 期望出现次数]), ...]
  期望次数默认 1；返回行/解构行同时命中时显式写 2
阶段 C 残留检查（去注释后 count == 0）
  对每个"应被删除"的标识符断言零残留；对每个"应被接回"的标识符断言 ≥2 次出现
```

要点：
- **降序应用**是关键，不要边算边改。
- 行号来源必须是自己刚读过的原文（用户上传的副本），不要复用上一轮的旧行号。
- 残留检查要**先去注释**（`l.split("//")[0]`），否则自己写的解释性注释会把断言打挂。
- 断言文案里带上实际内容切片（`lines[a-1][:110]`），失败时一眼看出错在哪一行。
- 模板：`templates/pine_linelevel_transform.py`。

## 2. 必踩的三个坑

### 2.1 Windows 上 `Path.write_text` 会把 `\n` 翻译成 `\r\n`

`Path.write_text()` 以 text 模式打开（`newline=None`），Windows 下把 `\n` 写成 `\r\n`。
交付要求是 LF，结果文件悄悄变成 CRLF，且 `read_text()` 读回来又被规范化，**本地自检看不出差异**，
直到比对 `read_bytes()` 的 sha256 才暴露（同一份内容两个哈希）。

修法：
```python
DST.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))
```
并在交付前用 `read_bytes()` 复核：字节数、`raw.count(b"\r\n") == 0`、BOM 不存在、sha256。

### 2.2 删掉一个变量后，它的上游刚变成死变量

删 `rdyGauge` 之后，只喂给它的 `rdyWord`（五分支字符串三元）也就没人消费了。
同理删 `volume_buy/volume_sell` 之后，整棵 `price_spread/safe_spread/upper_wick/lower_wick/body/*_percent` 子树一起变死。

做法：**每轮删改后重跑死变量扫描**，并对"刚删掉的下游"反查一次上游；
一次清理往往能连出 3-20 行的连锁死链（本例最长的一条是 21 行 `invalidBaseText` 阶梯）。
先查引用行号（`[i+1 for i,l in enumerate(lines) if v in l]`）确认整棵子树只服务于被删项，再动手。

另注：`name` 出现在"字符串里"（如 `magnetTargetName` 里的 `magnetTarget`）会让子串 grep 误报，
定位行号时用 `in l` 扫行，计数时用 `\b` 词边界。

### 2.3 合同往返测试最容易"自比自"而全绿

错误写法（看着像在验证，其实只有 1 个字段被验证过）：
```python
got  = (state, pc, od, agree, round(d["oiPct"], 1), bg)   # ← 输入原样搬回来
want = (state, pc, od, agree, exp_pct, bg)
```
正确写法：`got` 六项**全部取自 decode() 的返回值**，并且注意语义偏移
（编码端 `dir + 1`，解码端 `% 10 - 1`，所以往返 `want` 用 `pc - 1 / od - 1`）。
自检手段：把 want 改成任意错值，如果测试仍然全绿，说明比对无效。
`scripts/pine_packed_bus_roundtrip.py` 已在 20260910 修正为比对解码值。

## 3. 「删掉」还是「接回消费」的判定规则

对整个文件 grep 出"算完没消费者"的标识符后，逐个分类，不要一刀切：

| 类别 | 判据 | 动作 |
|---|---|---|
| 语义重复路径 | 同一信息已由另一行/另一个函数渲染（`panelEntryVal` vs 路径行；`rdyGauge` vs 方向行"条件x/10"；`magnetTargetText` vs `f_mag_text`；`chartTfSec` vs `curTfSec`） | **删** |
| 明确功能丢失 | 该字段承载的是一块独立信息，只是被改版时漏接（`liqOIDropA` 去杠杆 OI 收缩幅度、`perpSpotBasisPct` 基差、`htfTxtA` 上级方向、`atrPctile` 波动率分位、活扫位计数） | **接回消费**，且限定"异常态才显示"避免常态撑宽 |
| 已废弃规格 | 注释里写明自某日起不再展示（`long/shortInvalidText` 的"多失效:/空失效:"） | **删** |
| 写错的死链 | 条件与取值不匹配等逻辑错误 | **删**（并在报告里写明"正确写法应取 X"） |
| 纯配额浪费 | 只有一个选项的 input、未消费的常量分组 | **删** |

接回时注意：接回的字段要挂在**已经存在**的行上（位置行/CVD行/结构行/结论行），不新增行、不新增 plot。
新增字符串只有几处时，先把它们写成短变量（`atrPctTag`/`cvdBgTag`/`basisTag`/`sweepCntTag`/`coverageTagA`），
行的拼装保持一行，便于以后审计。

## 4. 交付验证脚本该断言什么（可直接抄成一份 test）

分 6 组，53 条左右，全部 `check(name, cond)` 收集后统一汇总，失败列出名字：

1. **文件身份**：行数 / 字符 / sha256（LF 归一）。
2. **修复项语义断言**：每条 P0/P1/P2 对应一个**字符串级**断言（不是"我记得改了"）。
   例：`has(svp, "bool signalNowLong = selectedPlanLong")`；
   `svp.index("bool signalNowLong") > svp.index("int selectedPlanDir =")`（顺序也要断言）。
3. **结构性保证**：配额六项和各分量不变、request/plot/input/alert 计数不变、
   五所成交量（4 后缀 × 5 所 = `GetExchange` 4 次调用 + `GetRequest(GetTicker(` 5 处）与四所 OI 名单在场、
   表格行数不变（主 `array.push(rowLabs,` 计数、副 `table.cell(actT,` 计数）、A 级授权链逐字未变、
   唯一 `input.source(` 仍为 1。
4. **死链零残留**：需要"验证目标已消失"的才用**去注释**后的文本计数（保留版本说明的注释会误伤）。
5. **合同一致性**：编码式/位段式/合同号/`nz(…,0)` 防护**逐字**断言未变，再跑往返。
6. **反例闭环**：把审计期发现的决策反例（反向 CVD 强支持、逆高周漏判、OI 缺失仍写"OI升"）用**修复后逻辑**
   重跑一遍，断言已翻转；同时留一条正例断言，防止"修成永不触发"。

## 5. 本轮修复动作索引（供下次同类修改对表）

| 级别 | 问题 | 代码动作 |
|---|---|---|
| P0-1 | 客户端 CE10117 IL 超限未闭环 | 删语义重复路径 + 连锁死链（主指标约 16 处），**不承诺**已低于 100256；服务器端点不返回 IL |
| P1-5 | HTF FVG/OB 用未收线值 | `lookahead_off` → `lookahead_on` **且** pack 内四个返回值各加 `[1]`（两者缺一不可，见下） |
| P1-6 | 信号年龄用原始 setup 并集 | 改为 `= selectedPlanLong/Short`，整块状态机移到唯一方向仲裁之后 |
| P1-7 | 总线字段解码后无消费者 | 接回：仅在与本图 CVD 确认方向相反时追加短标记 |
| P2-3 | 副 S3 冲突下仍打印可执行价位 | X→`禁做·不出价`；S3→`未授权·止…`（保留观察价但标注） |
| P2-6 | 后缀未去重导致成交量双计 | 加 `spot2SuffixOn/perp2SuffixOn` 短路 + 覆盖诊断标注 |
| P2-5 | 支配度画的是每根重排名次 | 改按配置槽位输出 `array.get(percform, i)`，颜色同步去排序 |

**P1-5 的陷阱**：只把 `lookahead_off` 改成 `lookahead_on` 而不在 pack 内加 `[1]`，
等于把"重绘"换成了真正的**未来函数泄漏**，比原来更糟。
非重绘的标准写法只有两种：`lookahead_off + [1]` 或 `lookahead_on + [1]`（官方文档 + PineCoders "Higher-timeframe requests"）。
同一脚本内不同 HTF 请求必须同口径，否则 "高周趋势" 与 "高周 FVG/OB" 会打架。
