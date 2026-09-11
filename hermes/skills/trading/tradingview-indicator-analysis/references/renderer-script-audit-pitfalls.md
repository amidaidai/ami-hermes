# 渲染器/脚本代码审计陷阱

当棠溪让"看一下模板/分析策略/监控/脚本自动更新逻辑怎么样"时，是**代码审计**，不是出卡。
按 P0/P1/P2 找真实 bug，每条用真实工具验证（跑脚本、核对数学、AST 检查），不要泛泛夸"很完整"。

## 核心方法论：先分清"应然代码"和"实然运行"

- **改过的脚本必须重新生成产物再判断**。审计 `data/auto_card_*.md` 时，先 `python hermes/scripts/auto_card.py <SYM>` 重新生成，
  再读文件。旧的 saved 卡可能是几个 commit 前的残留，带着早已修掉的问题（如 `交易所：` 前缀、超长正文）。
  对着 stale 卡报问题 = 误报，浪费双方时间。本会话 21:21 的旧 BTC 卡就是这种残留。

## 陷阱① 修复代码被 broad try/except 静默吞掉 → 死代码（从没运行过）

- 症状：你写了一段"修复"逻辑（如快照质量交叉验证），但它从上线起就从未执行。
- 真因：变量名 typo（`DATA_DIR` 而文件只定义了 `DATA`）抛 `NameError`，但整段被 `try: ... except Exception: pass` 包住，
  异常被吞，功能静默跳过，脚本 `exit=0` 看起来正常。
- 诊断：`python -c "import ast; ..."` 解析脚本，对比"被引用的名字"和"被赋值的名字"，找出引用了但从未定义的变量。
  ```python
  import ast
  tree = ast.parse(open(path, encoding='utf-8').read())
  referenced = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
  assigned = {t.id for node in ast.walk(tree) if isinstance(node, ast.Assign)
              for t in node.targets if isinstance(t, ast.Name)}
  print('引用未定义:', referenced - assigned)  # 候选 NameError
  ```
- 铁律：**任何写进 broad try/except 的"修复"，必须验证它真的执行了**（看有无预期 print/side-effect），
  不能因为脚本 `exit=0` 就以为修复生效。try/except 静默吞 NameError 是最隐蔽的死代码来源。

## 陷阱② 显示用 R:R 必须用"算止盈时同一个止损"，不能重新推导

- 症状：卡片止盈价正确（1:2、1:3），但 R:R 标签错成 1:6、1:9（放大约 3 倍）。
- 真因：`_tp_reason()` 计算显示 R:R 时调 `_plan_stop({}, {}, ...)` 传了**空 klines**，
  止损取了默认近距离值 → 分母变小 → R:R 虚高。而 `_plan_targets()` 用的是真实止损算的目标。
  两个函数用了不同的止损 → 止盈价对、R:R 标签错。
- 铁律：R:R = |目标-入场| / |止损-入场|，分子分母的止损必须是同一个。
  渲染 R:R 标签时复用算目标时的 stop 变量，绝不重新调一次 stop 计算函数（尤其别传空 klines）。
- 核对方法：`python -c "entry,stop,tp=...; print((abs(tp-entry))/abs(stop-entry))"` 手算对比卡面标注。

## 陷阱③ B等待状态严禁给具体入场价（渲染器占位符陷阱）

- 铁律已知：B等待 → 操作段不给入场/止损/止盈具体价，只写触发条件。只有 A做多/A做空才给价。
- 渲染器违规形态：B等待卡的"入场"字段直接填了 `_fmt_price(price)`（当前价占位），
  且入场价恰好等于现价 → 一眼可辨是占位符而非真实计划价。
- 审计时盯：B等待卡的 ② 入场价 == ③ 现价 → 几乎一定是渲染器拿现价兜底，违反铁律。

## 陷阱④ 包装脚本(wrapper)引用的子脚本必须确认真实存在

- `持仓与信号.py` 是 wrapper，`STEPS` 里串行调 `持仓监测.py` + `信号巡检.py`，智能更新由信号巡检触发。
- 子脚本缺失 = 静默失败（subprocess 报错被 except 吞，wrapper 继续）。审计 wrapper 时务必逐个 `[ -f ]` 确认。
- 自动更新链路：持仓与信号(5m·cron) → 信号巡检检测 `needs_structure_refresh` 或活跃位<2 → 调 `智能更新结构.py` 重算近端位 → 写回 `monitor_levels.json`。
