# 契约漂移守卫：一处权威、零手写白名单（2026-09-11 实战）

来源：用户上传定版双指标（主 `空格修正` / 副 `最终版`）后对全系统的对齐审计。
本文记的是**可复用的类级方法论**，不是那一天的流水账。

## 0. 症状→根因的固定判据

**症状**：指标面板上明明有 13 行，卡片只能读到 4 行；某个 DW 字段永远为空。

**根因**（本仓真实发生过，且同时存在 4 份）：同一份「DW 名/行名 → 内部键」映射
被写在多个模块里，各自漂移。查法：

```bash
grep -rn "MCP \|OI Total\|HALDRO " --include="*.py" scripts/ | grep -v tv_indicator_contract  # 示意名/检测用
```

只要同一批字段名出现在两个以上文件里，就是在埋雷。

## 1. 唯一权威的边界（本仓落地形态）

| 层 | 位置 | 职责 |
|---|---|---|
| 人读 | `docs/tv-indicator-field-map.md` | 字段映射、授权态语义、分析流程 |
| 代码契约 | `scripts/tv_indicator_contract.py` | 行名/DW 名/别名表/解码器，**改字段先改这里** |
| 守卫 | `scripts/tv_indicator_alignment_check.py` | 源码 ↔ 契约 自动对齐，退出码 0 |
| 回归 | `tests/test_indicator_alignment_20260911.py` | 把守卫变成测试 |

**消费方（auto_card / tv_data_bridge / 渲染器 / 技能 references）一律不写字段清单**，
全部从契约取。技能侧的字段清单文档应改为**指针**，否则就是第 N 份漂移源。

## 2. 守卫怎么判（关键设计：不靠白名单）

不要维护「哪些标题算字段」的手写清单 —— 它会和契约一起腐烂。改用 Plotly/Pine 自身的语义：

每个 `plot*()` 调用按 `display=` 参数分三类：

| `display=` | 归类 | 必须进契约？ |
|---|---|---|
| `display.data_window` | 导出型 | **是**（否则消费方静默丢） |
| `display.price_scale` | 价格轴/结构线 | **是**（卡片读关键位） |
| 其它（默认 `display.all`） | 纯视觉 | 否，列出来但不报错 |

反向也查：契约里有、源码里一个 plot 都找不到 = 死字段。

行动格行名同理：`array.push(rowLabs, "位置")` 取字面量；
`array.push(rowLabs, riskLabelText)` 这种动态标签用**契约里的字面量**做存在性校验，
并单独断言「动态行名恰好 1 个」。**行序也是契约的一部分**（卡片按契约顺序输出），必须比对。

## 3. Pine 源码静态扫描的四个坑（踩过）

1. **`^\s*plot` 锚点会漏掉赋值形态**：`pEma1 = plot(..., "EMA 9", ...)` 行首是变量名。
   不要锚行首，直接搜 `\bplot(?:shape|char|candle|arrow)?\s*\(`。
2. **标题位置的判定**：优先 `title=` 关键字；否则取**第 2 个位置参数**。
   不要「取第一个字符串字面量」——表达式里可能先出现别的字符串（如 `str.contains(s,"x")`）。
3. **参数切分必须括号/引号感知**：写一个 depth+quote 扫描器按顶层逗号切，
   别用正则 `[^)]*` —— 字符串里、嵌套调用里都有右括号。判据是 `display=` 出现在**该调用自己的参数列表**里。
4. **`array.push` / `table.cell` 的标签不在第 1 个参数**：
   `array.push(rowLabs, <label>)` → 参数下标 **1**；
   `table.cell(<t>, 0, <row>, <label>)` → 下标 **3**。
   若正则已经把前面的参数吃掉了，就要从该调用的 `(` 起重新切，不能从 `m.end()` 起切。

## 4. 授权态：标签 vs 值（一次真实的契约写错）

旧契约/旧技能把「风控」行写成**四个标签**。逐字读定版源码才发现只有 **3 个标签**，
第四个是**行值**：

```pine
string riskLabelText = setupX ? "风控" : aggGateConflict ? "风控·未授权" : pendingPlan ? "风控·观察" : "风控"
string riskValText   = setupX ? "禁做·不出价" : riskPriceText
```

→ 用**动态标签变量名 + 行值变量名**去源码里定位，别依赖任何二手文档。
→ 守卫里加一条：契约声明的授权态字面量必须在指标源码中真实存在，否则报错。

Python 侧配套（fail-closed，键缺失=旧载荷兼容）：

```python
if "risk_label" in main:
    if label == "风控":        # 唯一授权出口，仍须 A级+三件套+几何有效
        ...
    elif label in SVP_FORBIDDEN_LABELS:   # 禁做·不出价（标签位或值位都算）
        hard.append("svp_authorization")  # NO-GO
    else:
        wait.append("svp_authorization")  # WAIT，观察价只进候选
```

`gates["risk"]`：禁做红 / 观察·未授权黄 / 授权绿。**键缺失时不加任何阻断**（否则 700+ 旧测试全红）。

## 5. 分析卡候选价三铁律（跨渲染器共享一份实现）

推送卡 `render_tv_card.py` 与完整报告卡 `render_v96.py` **必须共用同一个候选判定**
（本仓用 `render_tv_card.candidate_view` 对外暴露，v96 import 它）。两份实现必然漂移。

1. 候选价**只读 `FinalVerdict.watch_*`**，永不回落到原始 `entry/stop/target`；
2. watch 元组不完整 → 卡面写「候选数据不完整」，**不补半个订单**；
3. R:R 由元组**现算**（`|标-入|/|入-止|`），不信上游 `rr` 字段。

配套两条容易漏的：
- **未授权行的价位要主动剥掉**：`风控`/`路径` 两行里的 `入/止/标/候选` 数字与 `x.xA`/`x.xR`
  用正则剥除；**磁吸/结构/现位里的价位是行情事实，不剥**（否则误伤正常读数）。
- **失效价 = 止损价**，同属订单三件套。完整报告卡的 `inv_line` 也必须挂 `final_executable` 闸，
  否则 NO-GO 卡面照样打印计划失效价。

## 6. 收尾必做

```bash
python scripts/tv_indicator_alignment_check.py   # 退出码 0
python -m pytest tests/ -q                        # 全量
python outputs/pine_20260905/e2e_card_20260911.py # 真实 TV 数据端到端出卡
```

端到端脚本走的是**生产同一条链**（表 → DW → `_build_tv_main_data` → `resolve_final_verdict` → `render_tv_card`），
所以卡面里每个价位都能追到指标行或 DW 字段；末尾自带「泄漏检查」断言。
手写单元测试只能证明你写的规则自洽，**必须跑一次真实数据的端到端**才能发现
「字段名对但取不到值」这类静默失败。

## 7. 卡面质量：别把内部枚举丢给用户

`FinalVerdict.reason` 是机器码（`location` / `trigger` / `bar_closed` / `svp_wait_language` …）。
实测直接把 `treatment = final.reason` 拼进卡面，用户会看到：

```
SVP：C等待 等待：location/trigger/bar_closed/svp_wait_language/...
```

**修法**：卡面优先用中文原因链（契约 `NO_TRADE_BITS` 解出的 `no_trade_reasons`），
机器码只留在 JSON/日志里。任何「内部字段直接上图」的地方都要按这条复查。
