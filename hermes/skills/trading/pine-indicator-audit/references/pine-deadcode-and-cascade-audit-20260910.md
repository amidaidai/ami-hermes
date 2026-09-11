# Pine 死码审计与级联安全（20260910 实案）

## 一、两个精确判据（别用传递闭包）

想找「失效开关」时，**不要**用「input 的可达变量能否摸到 sink」这种闭包——
`if SHOW_ACTION_PANEL` 这种「守卫一整个块」的写法会让闭包全链断开，一次误报 13 个 input。
只用这两条：

1. **零引用 input** —— 变量在代码里（去注释后）除了声明行外 0 次出现 → 铁板钉钉的失效开关。
2. **零引用变量** —— 声明后 0 次出现 → 真死码（白占 IL）。

判据 2 就够抓绝大部分问题，且无误报。

## 二、必须逐行整行删除，锚点唯一

```python
hit = [i for i, l in enumerate(lines) if l.strip() == anchor.strip() or anchor in l]
assert len(hit) == 1, f"锚点命中 {len(hit)} 行"
lines.pop(hit[0])
```
锚点不唯一就停下来改锚点，不要退化成 `replace`。删完把连续空行压到最多一行。

## 三、级联安全：删之前先问「它上游还有别的消费者吗」

实测坑（AggVol）：删掉死变量 `oiCloseA` 后，它的上游 `oiAggRawA`（四所 OI 水平和）也变成死叶子。
**这种级联必须人工核实，不能顺手删** —— 一旦上游是数据源聚合，删它可能级联杀死 `request.*`，
等于静默削源。核实方法：逐个看那些变量除了死链之外还有没有独立消费者。

本例结论：`oiBinA/oiBybA/oiOkxA/oiBgA` 各有 `f_oi_pct()` 与 `f_oi_bar_pct()` 两路消费者，
删 `oiAggRawA` 不影响任何请求 → 安全。**但结论必须写进交付说明**，因为用户对「削源」是零容忍的。

## 四、改完之后回归链一定会红，这是预期的

历史 verify 脚本里有三类断言会被这种清理打断，全部改成容或式而不是删掉断言：

| 断言的写法 | 清理后 | 改法 |
|---|---|---|
| `inp_new == inp_old` | 少了一个死 input | `inp_new <= inp_old` |
| `sha == "<旧版本 sha>"` | 文件变了 | 白名单元组追加新 sha |
| `"<旧格式串>" in code` | 格式串被换掉 | `新格式 in code or 旧格式 in code` |

**验尸经验**：一次改格式串会让 3–4 个历史脚本集体红，逐个 patch 比事后怀疑「是不是改坏了」快得多。

## 五、收益怎么表述

按官方 CE10117 口径，**内嵌常量字符串才是 token 上限的主要占用**，删注释/空白不算。
所以清理报告要专门数「删掉了几条内嵌字符串」（如 `"VAH"` / `"前高"` / `"计算方式"`），
而不是只报「删了几行」。该上限只在客户端触发，`translate_light` 查不出来。

## 六、本仓库改源码的两个机械坑（每次都会撞）

### 6.1 CRLF 会让 patch 工具的多行锚点失败

`D:/Hermes agent` 里 `auto_card.py` 等文件在工作区是 **CRLF**，而 HEAD 里是 **LF**。
表现：`patch` 工具对两三行以上的 `old_string` 报 “Could not find a match”，单行锚点却好使。

**可靠做法**：不跟工具较劲，写一个一次性 Python 驱动脚本：

```python
def sub_once(text, old, new, tag):
    n = text.count(old)
    assert n == 1, f"[{tag}] 命中 {n} 次应为 1"
    return text.replace(old, new, 1)
```

- 但**改完写回时必须保持原换行风格**，否则整份文件在 git 里显示成全文改动：
  ```python
  raw = p.read_bytes(); crlf = b"\r\n" in raw
  body = t.replace("\r\n", "\n")          # 先统一成 LF 再按需还原
  p.write_bytes(body.replace("\n", "\r\n" if crlf else "\n").encode("utf-8"))
  ```
- 驱动脚本自己也要断言：`assert t != orig, "没有任何替换生效"`，否则静默不匹配最坑。
- 每次大批量改之前先 `cp` 一份带 `_pre-<版本>` 后缀的备份，事后用它算「我的真实改动行数」，
  与 `git diff` 的差距就能立刻看出是不是行尾/历史遗留造成的假差异。

### 6.2 提交前把行尾对齐 HEAD，否则 diff 全是噪声

工作区可能是历史会话留下的 CRLF（而非本次改动）。提交前把每个待提交文件与 `git show HEAD:<path>`
比对，取 HEAD 的换行风格写回：

```python
head = subprocess.run(["git","show",f"HEAD:{f}"],capture_output=True).stdout
crlf = head.count(b"\r\n") > head.count(b"\n") - head.count(b"\r\n")
```

实测效果：`auto_card.py` 的 git diff 从「700 行」降到只剩本次真实改动，审阅时不会被淹没。

### 6.3 别把工作区里的在飞改动一起提交

本仓库常年有几十个文件的未提交改动（其它会话在飞的工作）。
**只 `git add` 本次真正动过的文件**，commit message 里显式说明“其它文件非本次”，
不要把未验证的工作捆进自己的提交。可用 `git diff --stat -- . | tail -3` 先看清规模。
