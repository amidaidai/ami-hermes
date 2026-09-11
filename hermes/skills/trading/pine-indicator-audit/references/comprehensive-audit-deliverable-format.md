# Comprehensive Pine Audit Deliverable Format

> 适用场景：用户要求"全方位/多维度/联网社区全面查/10 条优化建议/推荐增强"且**不要回测/复盘**，只看指标本身。覆盖 2026-08-08 用户对 SVP+ICT+VWAP+CVD 主指标 + Volume Aggregated Spot & Futures 副指标的实际审计交付。

## 一、为什么需要这个模板

之前 pine-indicator-audit 的输出格式是"问题→证据→修法"的纵向列表（P0→P1→P2），适合"修代码"导向。但用户问"指标本身怎么样 + 联网查 + 给我 10 条建议 + 你看看还有要优化的吗"时，需要的是**全景对比 + 优先级排序 + 增量候选**的多维度报告，不是逐项修补清单。

两者的区别：
| 维度 | 修代码清单 | 多维度审计 |
|---|---|---|
| 触发 | "修这个 bug" | "指标整体怎么样" |
| 输出 | P0/P1/P2 + 行号 + 修法 | 量化基线 + 社区对标 + 10 条建议 + 增量候选 |
| 长度 | 中等 | 长（8 段） |
| 联网 | 可选 | 必须（社区基准对比） |
| 决策 | 修哪几条 | 挂哪份 / 加什么 / 砍什么 |

## 二、8 段输出骨架（缺一段不算合格）

### 1. 量化基线表（必须）

行数 / 字符数 / token 估算 ÷ 2.33 / request 静态调用点 / plot 总数 / series-color plot / alertcondition / alert() 事件化 / fill / bgcolor / line / label / box / polyline / MCP Data Window plot 字段数 / 死变量精确数 / type 前向引用 / UDT 字段 vs .new() 实参数对齐。

**2026-08-08 双指标实测**：

| 项 | 主指标 SVP+ICT+VWAP+CVD | 副指标 AggVol |
|---|---|---|
| 行数 | 3034 | 656 |
| 字符数 | 199282 | 49238 |
| token（÷2.33，仅参考） | ≈85500 | ≈21100 |
| request.*() 调用点（静态） | 9 | 8 |
| plot() 调用点 | 41 | 40 |
| series-color plot（计2） | 4（仅4个EMA） | **11**（Volume/Delta/CVD/SP/EX×5 等核心列） |
| 真实最坏 plot count | **45/64**（+2 fill×2 +4 bgcolor = 51） | **51/64** |
| alertcondition() | 0 ✓ | 0 ✓ |
| alert() 事件化 | 3 | 3 |
| MCP Data Window plot | 27 | 22 |
| 死变量（精确扫描） | **5 个** | **2 个** |
| type 前向引用 | 无 | 无 |

### 2. P0 致命级（编译失败 / 重绘 / 可执行性）

每条含：问题 → 行号命令证据 → 修法。

**典型 2026 P0 类型**：
- HTF `lookahead_off` 配合未偏移 expression → 未来函数泄漏
- 死 alertcondition（免费档 = 0 时纯死重）
- type 前向引用（`OBZone` 定义在 `array<OBZone>` 引用之后）
- UDT 字段新增后 `.new()` 实参未对齐
- 函数插入导致 return 行孤儿
- 表格消费链断裂（`actionCvdText` 算 8 次但 `f_pnl_row("CVD")` = 0）

### 3. P1 决策完整性（核心功能缺口）

每条标社区证据标签：
- **官方事实**：TV 官方文档/release notes
- **平台教学**：Bookmap/ATAS 订单流解释
- **社区实现**：TradingView 开源脚本
- **开源架构**：GitHub 仓库

**典型 2026 P1 类型**：
- 副指标"共振"行存在状态票 ≠ 方向票陷阱
- 副指标 freshness 用 `ta.barssince(not na(v))` 永久为 0
- 主指标 OB 检测只看最近反向 K，不看最深极端
- 主指标缺 iFVG / Mitigation Block / EQL 三件套
- 副指标 `Coverage Feed Mode` plot 用 0/1/-1 歧义编码

### 4. P2 性能 / UX / 可读性（不致命可选）

- KillZone 默认窗口是否对齐 ICT 官方
- 副指标 EX_NO 槽缺 tooltip
- liqTxtA plot tooltip 缺诚实口径
- 主指标 SVP 桶宽整数化是否已带 minBuckets 保底

### 5. 联网社区 2026 新增能力清单（必须）

增量候选表，列 来源 / 实施成本 / 决策价值 / 推荐星标。

**2026-08-08 社区 Top SMC 基准**：

| 脚本 | URL 关键词 | 差异化卖点 | 当前主指标缺口 |
|---|---|---|---|
| Quant SMC Pro [JOAT] | `ugOBLSa3-Quant-SMC-Pro-JOAT` | 自适应 ATR pivot + iFVG + Mitigation Block + EQL + AVWAP PD + Confluence Score 0-100 | 缺 iFVG / MB / EQL 三件套 |
| Unicorn ICT Signals [TradingFinder] | `9uGRHvXH-Unicorn-ICT-Signals` | Breaker Block + FVG Zones + Mitigation Level FVG | 已有 BRK 变色，缺 MB 标签 |
| ICT Sessions + SMT Divergence | `rGyFTcVW-ICT-SMC-Sessions-SMT-Divergence` | RTH Gap + 25/50/75% quartile + 实时 SMT + DST 锚定 | 缺 RTH Gap（股票用户升级后做） |
| Order Block Detector [SMC ChartSense] | `1ORCJ6hv-Order-Block-Detector-SMC-ChartSense` | FVG 必现 OB 锚（3-bar gap requirement）+ mitigation mode 可选 | OB 检测不验 FVG，可加 |
| Swing Reversal Auto Targets | `CKpLwLIZ-Swing-Reversal-Auto-Targets-JPT-Module-1` | 自适应 Swing HH/HL/LH/LL + 动态 S/R + 非重绘 pivot | 主指标已有等价，但没独立 Swing Label |

### 6. 10 条优化建议（必须）

按优先级排序。每条标 P0/P1/P2 + 一句话修法 + 涉及行号。

**模板**：
```
1. 【P0-2/P1-2 合一】HTF 双 pack 收敛 —— 删未确认版 htfBull/htfBear（L784/786-787），
   把 FVG/OB HTF 的 lookahead_off 改 lookahead_on；净省 1 个 request（9→8），
   图表视觉提前一根 K 看到 HTF 区域。
   ⚠ 20260910 修正：**单改 lookahead_on 是错的**——必须同时在 pack 内对返回值加 [1]。
   只改 lookahead 而不加 [1] = 把"重绘"换成真正的未来函数泄漏（更糟）。
   非重绘只有两种合法写法：lookahead_off + [1]，或 lookahead_on + [1]。
   同一脚本内所有 HTF 请求必须同口径，否则"高周趋势"与"高周 FVG/OB"会打架。
2. ...
```

**禁忌**：
- ❌ 把 10 条都堆在同一 P0（没优先级）
- ❌ 没行号引用（用户无法核对）
- ❌ 只给修法不给原因（用户不知道为什么）

### 7. 推荐增强（不只是修复）

A/B/C/D/E/F 真正能涨决策质量的增量。每条独立、聚焦、给出落地点。

**2026-08-08 推荐增强清单**：
- A. Mitigation Block 标签（低成本高收益）—— BOS 后第一个 OB 文字从 `OB↑ A` 改 `MB↑ A`，box 颜色不变，文字 1 行 `str.replace`，**零 plot cost**
- B. Equal High/Low 检测（社区 #1 扫线增强）—— 加 1 个轻量函数 `f_eqh_eql(arr, atr_tol, depth)`，0 新 plot
- C. 副指标 Coverage Feed Mode plot 改名 + 位图 —— 避免 0 误读
- D. 加 R:R 1.5 阈值提示给 B/C 人工 —— 行动格进场行加 `(B挂价... R:R1.8R)`
- E. 把 `setupTotalScore` 拆成 `locationScore/confirmScore/extensionScore` 三列展示
- F. 主指标加 `MCP Regime Pack` 注释说明 —— auto_card 解析需文档化

### 8. 决策（直接推荐）

立刻落地哪几条 / 不推荐做的（带原因）/ 指标本身已多扎实。

**模板**：
```
立刻落地：
1. P0-2 HTF lookahead_on
2. P0-3 删 7 个死变量
3. P1-4 加 iFVG + MB 标签（社区差异化）
4. P2-7 Coverage Feed Mode 位图

不推荐做的：
- � 加 request.footprint() 到生产脚本 —— Premium/Ultimate 门槛 + 单调用限制
- ❌ 加 alertcondition() —— 免费档 = 0 死重
- ❌ 重写 OB 检测为 ATR-adaptive ZigZag —— 收益边际、破坏现有 MCP OB Score 编码

指标本身已经很扎实。下一步最大价值不是"再加模块"，而是清理 + 加 2 个社区共识增量（iFVG + MB + EQL）。
```

## 三、用户开放追问陷阱

**触发**："还有你看看有什么需要优化的吗 / 还有别的吗 / 还有什么"

**陷阱**：用户问的"还有"是开放追问，必须在末段主动给出"额外观察点"，不能仅复述已列条目。

**正确做法**（2026-08-08 实案）：
- 已列 10 条建议 → 用户问"还有吗" → 加一节"额外观察点"，列 3-5 条未列入主表但有价值的项（如 R:R 1.5 阈值提示给 B/C 人工、setupTotalScore 拆三列、MCP Regime Pack 注释、KillZone 时区对齐 ICT 官方等）
- 不要再开"主指标还有这些功能 / 副指标还有这些功能"的复述 —— 那只是把 10 条用不同顺序再说一遍

## 四、消费链 = 0 误报陷阱（静态扫描器盲区）

`pine_static_scan.py` 只检查 `panelDirVal` / `panelConclusionVal` / `panelEntryVal` 三变量的依赖。但 Pine 实际声明方式有两种：
- `string panelConclusionVal = ...`（直接赋值，无 `:=`）
- `panelConclusionVal := ...`（重赋值）

静态扫描脚本如果用 `re.findall(r'(\w+)\s*:=', src)` 数"声明次数"，会把 `panelConclusionVal` 报告为 0 次声明 —— **但实际有 1 次声明（用 `=`）**，消费链是完整的。

**修法**：扫描脚本要把两种声明方式都识别
```python
declared = set(re.findall(r'(?:var\s+)?(?:float|int|bool|string|color)\s+(\w+)\s*=', src))  # = 声明
declared |= set(re.findall(r'(\w+)\s*:=', src))  # := 重赋值
```

**症状**：报告 `panelConclusionVal 声明 0 次`，但实际文件有 `string panelConclusionVal = ...` 行 —— 这是扫描器 bug，不是代码缺陷。

## 五、execute_code 静态扫描完整模板

```python
import re

def scan_indicator(path, name):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    lines = src.split("\n")
    print(f"=== {name} ===")
    print(f"行数: {len(lines)}  字符数: {len(src)}  估算token(÷2.33): {len(src)/2.33:.0f}")
    
    # 1. request / plot / alertcondition 静态计数
    reqs = re.findall(r'request\.\w+\(', src)
    plots = re.findall(r'(?:^|\s|;)plot\s*\(', src, re.M)
    alcon = src.count("alertcondition(")
    alert_dyn = src.count("alert(") - alcon
    print(f"request.*() 调用点: {len(reqs)}  plot(): {len(plots)}  alertcondition: {alcon}  alert(): {alert_dyn}")
    
    # 2. series-color plot 精确定位
    series_plots = []
    for i, l in enumerate(lines):
        if not re.search(r'(?:^|\s|;)plot\s*\(', l): continue
        m = re.search(r'color\s*=\s*([^,)\n\)]+)', l)
        col_expr = m.group(1).strip() if m else ""
        is_series = ("?" in col_expr or any(k in col_expr for k in ["color.","cGood","cBad","cWarn","cLabel","cVal","PNL_"]))
        if is_series:
            series_plots.append((i+1, col_expr[:60]))
    print(f"series-color plot: {len(series_plots)} 个（每个计2）")
    
    # 3. 死变量精确扫描（声明次数 ≥ 1 且 读取次数 = 0）
    declared = set(re.findall(r'(?:var\s+)?(?:float|int|bool|string|color)\s+(\w+)\s*=', src))
    declared |= set(re.findall(r'(\w+)\s*:=', src))
    dead = []
    skip_patterns = {"i","j","k","m","s","e","v","w","t","b","f","n","x","y","z","h","l","c","o","p","q","r","cnt","sz","txt","tmp","res","ret","val","col","src"}
    for v in sorted(declared):
        if len(v) <= 2 or v.startswith("_") or v in skip_patterns: continue
        def_count = sum(1 for l in lines if re.search(rf'(?:^|\s)(?:var\s+)?(?:float|int|bool|string|color)\s+{re.escape(v)}\s*=', l) or re.match(rf'\s*{re.escape(v)}\s*:=', l))
        read_count = sum(1 for l in lines if re.search(rf'\b{re.escape(v)}\b', l) and not re.search(rf'(?:^|\s)(?:var\s+)?(?:float|int|bool|string|color)\s+{re.escape(v)}\s*=', l) and not re.match(rf'\s*{re.escape(v)}\s*:=', l) and not l.strip().startswith("//"))
        if def_count >= 1 and read_count == 0:
            dead.append(v)
    print(f"死变量: {len(dead)} 个")
    if dead: print(f"  {dead[:10]}")
    
    # 4. type 前向引用
    types = re.findall(r'type\s+(\w+)\s*\n', src)
    for t in set(types):
        def_line = next((i+1 for i, l in enumerate(lines) if re.match(rf'\s*type\s+{t}\b', l)), None)
        if def_line:
            for j, l in enumerate(lines):
                if j+1 >= def_line: break
                if re.search(rf'\b{t}\.', l) or re.search(rf'array<{t}>', l):
                    print(f"  ⚠ P0 type 前向引用: {t} 在 L{j+1} 使用，L{def_line} 定义")
                    break
    
    # 5. UDT 字段数 vs .new() 实参数
    for udt_name in ["OBZone", "FVG", "ICTLevel", "VolumeProfileEngine", "VwapAccumulator", "NakedPOC", "SessionState"]:
        # 找 type 定义
        in_type = False
        fields = []
        for i, l in enumerate(lines):
            if re.match(rf'\s*type\s+{udt_name}\b', l):
                in_type = True; continue
            if in_type:
                m = re.match(r'\s*(bool|float|int|string|color)\s+(\w+)', l)
                if m: fields.append(m.group(2))
                if l.strip() == "}" or (i > 0 and "type" in l and udt_name not in l):
                    in_type = False; break
        # 数 .new( 实参
        new_calls = []
        for i, l in enumerate(lines):
            if f"{udt_name}.new(" in l:
                after = l[l.index(f"{udt_name}.new("):]
                depth, n = 0, 1
                for ch in after[after.index("(")+1:]:
                    if ch in "([{": depth += 1
                    elif ch in ")]}":
                        if depth == 0: break
                        depth -= 1
                    elif ch == "," and depth == 0: n += 1
                new_calls.append((i+1, n))
        if new_calls:
            flag = "✓" if all(c[1] == len(fields) for c in new_calls) else "✗"
            print(f"  {flag} {udt_name} 字段={len(fields)} .new()实参={[c[1] for c in new_calls]}")
    
    # 6. HTF lookahead 模式 + expression 偏移
    for i, l in enumerate(lines):
        if "request.security" in l and "lookahead" in l:
            lookahead_off = "lookahead_off" in l
            has_offset = "[" in l.split("lookahead")[0] or any(f"[{n}]" in l for n in [1,2,3])
            if lookahead_off and not has_offset:
                # 语义纠正（20260910）：lookahead_off 不含未来数据，因此这不是"未来泄漏"，
                # 而是"读到仍在形成的 HTF K" → 随 HTF K 走完而变（重绘），且与同脚本
                # lookahead_on+[1] 的 Confirmed 版口径分叉。P1 而非 P0，修法=改 Confirmed。
                print(f"  ⚠ P1 L{i+1}: lookahead_off + 无偏移 = 重绘（读到未收线 HTF 值），非未来泄漏")
            elif lookahead_off and has_offset:
                print(f"  ⚠ L{i+1}: 合法（延迟非重绘）；核对是否与同脚本 lookahead_on+[1] 版口径分叉")
    
    print()

scan_indicator("主指标.txt", "主指标 SVP+ICT+VWAP+CVD")
scan_indicator("副指标.txt", "副指标 AggVol")
```

## 八、变体 B：历轮修改后的验证型详细审计（20260813 实案）

**触发**：用户说\"审计主副指标，详细一点\"——且双指标已历经多轮修改（回踩位路径/瘦身/CE10116 修复/input 恢复/行动格布局）。此时审计的核心不是\"找新 bug\"而是\"验证所有历史修改是否完整保留 + 现状健康度\"。

### 变体 B 的 8 段结构（与主模板差异处加粗）

1. **总览评级表**：行数/字节/函数数/死变量/括号平衡/**TV 计数** 五列 + 评级（✓/⚠）。重点标出**TV 计数余量**——主指标 252/254 余量 2（⚠ 加任何 input/plot 就超限）、副指标 87/254 余量 167（✓ 未来增强放副指标）。
2. **配额审计**：input 分型明细（bool/int/float/string/color/source/tf/session 各自计数）+ plot（DW/价格轴/其他分类）+ alert/request + bgcolor/fill/table.cell。**TV 计数公式 = input 数 + plot 数 + alert 数 + request 调用数 + input.source 数 + input.timeframe 数**（六项和，作为预算工具；报错真因是函数传递闭包见 ce10116-refactor 七次实战，但六项和是保守预算）。
3. **结构审计**：type/const/函数总数 + 最重函数 TOP（扫描器加权排序）。本次最重 f_panel_checks 50、f_panel_risktxt 46、f_watch_invalid 44——全部健康。
4. **行动格审计**：主指标 12 行完整性（正则 `array.push(rowLabs, "X")` 列出全部行）+ 副指标行动格（加密 7 行/非加密 3 行；标签重复=两模式分支，正常）。
5. **市场适配审计**：**锚定矩阵（主 vs 副 逐格核对）**——场景×主指标 CVD/副指标 CVD 表格（加密 <1h/1h-4h/4h+、非加密 <4h/4h+），全 ✓ 才过；市场判定同源检查（主 autoMetal vs 副 f_is_metal_ticker）。
6. **修改点验证清单**（变体 B 核心）：把历轮所有修改的**关键字符串**列成 grep 清单逐一确认保留——本会话 14 项：KZ倒计时(D修正)、回踩位路径、进场行瘦身、信号年龄、入场距离、波动率分位、CE10116 内联（`f_render_action_panel() =>` 不存在）、PnlPalette、COMPLETED 默认3、14个input恢复、方向行定稿、零线参数化、总线线默认隐藏、SHOW_BUS_LINES 前置声明。**任何一项 False = 修改丢失需重做**。
7. **问题清单**：P1/P2/P3 分级 + 影响列。本次 P1：主指标 TV 余量仅 2。P2：总线线 data_window 的 input.source 兼容性未实测；MCP 29 个 DW plot 是计数大头。
8. **建议（按优先级）**：预留计数空间（转 2 个 input 为 const / 合并 MCP 冗余 DW plot）、实测总线线、新功能优先加副指标。

### 变体 B 的执行工具序列

1. 跑 `pine_external_elements_scan.py`（两文件，看脚本级 TV 估算 + 函数级超限）
2. python 统计：行数/字节/plot/alert/bgcolor/fill/table.cell/input 分型/request/lower_tf/const/type/死变量
3. python 验证 12 行行动格完整 + 关键修改点 grep 清单
4. 锚定矩阵核对（主 `cvdAnchorTf` vs 副 `cvdAnchorEff` 的市场维度分支）
5. 汇总输出变体 B 8 段

### 用户偏好（本变体专属）

- 用户说\"详细一点\" = 上面 8 段**一段都不能省**（尤其修改点验证清单，用户在意历轮修改是否还在）
- **主指标 TV 余量紧（≤5）是长期约束**——后续任何加功能/加参数的请求，先算六项和，超了就转 input 为 const 或减 MCP DW plot，并明确告诉用户\"加了 X 后余量剩 Y\"
- 副指标 TV 余量充足——新增强（KZ 倒计时/波动率分位等）优先放副指标，避免主指标再挤

## 九、写作风格铁律（棠溪偏好）

- **中文为主，专有名词用英文**：FVG/OB/MSS/VWAP/CVD/OI/KillZone 等保留英文
- **数字格式**：中文日期「2026年8月8日」+ 全角冒号「：」不用半角
- **不用装饰分隔线**：`══════`、`━━━` 一律不用
- **表格驱动**：分析卡用 markdown 表格，多周期定位 / 关键位矩阵 / 多源交叉验证 / 预案
- **缺失须注明**：量化数据缺失时必须写"缺失"而非省略
- **直接推荐**：用户问"怎么样"时必须末尾给"挂哪份 / 加什么 / 砍什么"，不只罗列模块
- **证据标签**：每条 P1/P2 标社区证据来源（官方事实 / 平台教学 / 社区实现 / 开源架构）

## 十、避坑清单

1. ❌ **不要堆 8 段但跳过其中一段** —— 用户会问"为什么没看到 X"
2. ❌ **不要把审计当开发** —— 用户明确说"不要回测/复盘"时，只看指标本身
3. ❌ **不要漏掉用户偏好** —— 用户偏好已在 pine-indicator-audit 顶层列明（中文、币安、快进快出、SVP 等），报告必须遵循
4. ❌ **不要给"编译通过"措辞** —— 没有 TV 服务器编译回执时，只能写"静态未发现 P0"
5. ❌ **不要静默删减用户要求的 5 所成交量或 4 所 OI** —— 腾配额只能合并 MCP 字段
6. ❌ **不要混淆"重绘"与"延迟"** —— `lookahead_off + 已收柱偏移` 是延迟不是重绘
7. ❌ **不要把"computed-but-unused"当死代码删** —— 应该接回表格消费，不是删
8. ❌ **不要把"共振"行加回来当增强** —— 方向票 ≠ 状态票陷阱已记入技能
9. ❌ **不要推荐 alertcondition** —— 免费档 = 0 死重
10. ❌ **不要建议硬编码 `calc_bars_count=1000`** —— SVP D 分布图需 1440 根 1m，会截断 30%
11. ❌ **不要把服务器编译回执当成客户端通过** —— `translate_light` 的 errors2/warnings2 清空**不校验 IL 上限**；CE10117(100256) 只在客户端"添加到图表"时暴露。无客户端 `pine_get_errors` 回执就写"服务器编译通过、客户端未复验"。
12. ⚠ **审计默认不改动用户图表/编辑器** —— 挂 study 是外部状态写入。静态 + 服务器编译 + 合同反例即可交付；要跑客户端 CE10117 / Data Window 验收，先要授权（一次挂载 + 验完移除 + 还原编辑器源码）。
13. ❌ **不要把"算而不用(computed-but-unused)"只当死代码** —— 它包两类问题：①功能丢失（`liqOIDropA`/`perpSpotBasisPct`/`sweepCntText` 算完从不渲染）②CE10117 的 IL 削减杠杆。报告里要分别写清"接回消费"还是"删字段"。
14. ⚠ **扫描器抓不到 tuple 返回元素** —— `rdyGauge`/`sweepCntText`/`guidePrevRowText` 的读取只出现在 `[a, b, c] = f()` 返回行与解构行，死变量扫描会漏。对 `f_panel_*` 这类多返回值 UDF 逐个 grep（声明+return+解构=3 次、无第 4 次消费 = 死）。
15. ⚠ **开工前先读现场状态** —— `chart_get_state` + 云端源码哈希。20260910 实测：现场XAUUSD 15m 只挂内置 Volume，且 TV 云端 SVP 源码与本地候选 `candidate_match:false`（候选从未编译过）。这类状态必须写进报告，不得假称已上线。

## 十一、可复用探针（scripts/）与增量参考

审计时直接跑，不要手敲：

| 脚本 | 作用 | 关键边界 |
|---|---|---|
| `scripts/pine_static_audit_scan.py` | 行数/字符/SHA256、request、plot(series-color·DW·价格轴)、input 分型、TV 六项和、死变量、type 前向引用、lookahead 风险 | 命令：`python scripts/pine_static_audit_scan.py a.pine b.pine` → `static_scan_result.json` |
| `scripts/pine_cloud_compile_check.py` | `translate_light` 服务器编译回执 | **0 错 0 警 ≠ 客户端 IL 通过**；不返回 IL 大小 |
| `scripts/pine_packed_bus_roundtrip.py` | Packed Bus 编解码边界+随机往返、2^53 上界、旧合同拒解 | 命令：`python scripts/pine_packed_bus_roundtrip.py 22002 13600`；退出码非 0 = 合同不可交付 |
| `scripts/pine_plot_budget.py` | **绘图槽位预算闸门**：按 TV 内部口径（series 色×2 + 常量色 + table）估算，而不是数 `plot()` 个数 | 命令：`python scripts/pine_plot_budget.py a.pine b.pine`；退出码非 0 = 已逼近 64 上限，先省槽。**新增任何视觉元素前必跑**；实测偏移 TV ≈ estimate + 4，安全线 estimate ≤ 59 |
| `scripts/pine_gap_scan.py` | **computed-but-unrendered 可达性扫描**：以「渲染点」为根反向可达，找「算了但用户看不到」的行内容缺口 | 根集合须含 `table.cell` **与** `array.push(rowVals/rowLabs)`；声明须覆盖 `var` 前缀。输出量大、有 UDT/循环假阳性，**先人工筛再交付** |

本节与探针均来自 2026-09-10 双指标全面审计（含审计执行边界、副票制反向CVD、HTF FVG/OB 未收线、算而不用清单）：详见 `references/dual-indicator-audit-20260910.md`。
注：该次审计时 SKILL.md 已贴 100,000 字符上限，新增参考只能挂在 references 下，并在此处登记入口。

**20260910 增补两个入口**（SKILL.md 仍在上限，仍只能挂这里）：

| 资源 | 何时读 |
|---|---|
| `references/pine-live-main-sub-verification.md` | 用户问「主副一致吗 / 你看看一致吗」、主表写「副S0未接」、或要证明面板显示=代码算出 —— 读图核验三步、总线解码验真、症状→根因表、fail-closed 口径 |
| `references/pine-static-scan-false-positives.md` | **写任何审计报告之前** —— 三类高发误报（UDF 内 `[1]` 被误判重绘、除零扫到字符串斜杠、块守卫开关被误判失效）与可靠判据 |

### 修复 + 本地交付 + 验证 闭环（同日第二轮，用户说"修复之后给我，我自己来验证"）

| 资源 | 作用 |
|---|---|
| `references/pine-fix-delivery-and-verification-20260910.md` | 删 vs 接回的判定表、三个必踩坑（Windows CRLF、连锁死变量、往返测试自比自）、交付物清单与验证脚本 6 组断言 |
| `templates/pine_linelevel_transform.py` | 3000+ 行文件的**安全变换骨架**：行级断言 + 降序应用 + 字符串唯一命中 + 残留/接回检查 + LF 写盘 |

交付硬约束（用户偏好，已确认）：不挂图 / 不改编辑器 / 不替用户跑客户端 CE10117；
落盘到桌面 `hermes下载文件/<任务名>_YYYYMMDD/`，**先副后主**，主指标 input.source 指名选副指标那条总线 plot 标题。
`scripts/pine_packed_bus_roundtrip.py` 已于 20260910 修正为比对**解码值**（旧版把输入搬回 got，只有 oiPct 真被验证过）。

### 表格内容优化 + 大文件插入坑 + 锚定/连续裁定（同日第三、四轮，用户问"表格要优化吗 / 副指标怎么每日重置"）

| 资源 | 作用 |
|---|---|
| `references/pine-panel-row-optimization-and-patch-pitfalls-20260910.md` | 第三~五轮。最坏行宽枚举与跨行重复审法、"合同写了但代码没落实"的三类实证、**授权等级写进行标签**模式、`pendingPlan` 观察价边界、插入四个前向引用/对齐坑、**片段文件法绕开转义**、LF 写盘、版本容忍断言、锚定 vs 连续最终裁定与**落地实现**、**pane 量级可比规则**（背景线必须与主线同量级，否则压平主线）、净增配额**放行表**、抽行逐行比对不变量、**EN SPACE(U+2002) 匹配坑** |

四条可直接复用的结论：
1. 表格审法用两把尺子——**最坏行宽**（宽度瓶颈常在结论行/磁吸行，不在路径行）与**跨行重复**（最高产的 P1 来源是"用户自己定的逐行职责合同没落实"）。
2. 往面板插代码：前向引用按原式内联；标签变量必须在 `array.push(rowLabs, X)` 之前声明；`rowLabs/rowVals/rowCols` 三个计数必须相等；改语义必须同时改相邻注释。
3. 锚定分工**不要改**：仅累计 CVD 锚定，OI/成交量保持连续；锚初期"本锚样本N/M"与"滚NK"不可比，已在表格分别标注；连续累计只能当背景看形状。
4. 叠加第二条曲线前先做**量级检查**：pane 只有一条线性轴，量级差 1~2 个数量级的同类曲线叠加会压平主线；
   背景线取「一个锚长度」的滚动窗口（量级可比 + 不随加载点漂移），**不要用无限累计**。
   经批准净增配额要写进旧脚本的**放行表**，并用「抽掉新增行后逐行比对」证明其余一字未动。

### 视觉症状定位 + 版本容忍验证链（同日第七轮，用户报「这两条线丫的好平啊」）

| 资源 | 作用 |
|---|---|
| `references/pine-visual-symptom-triage-and-version-tolerant-verify-20260910.md` | 用户报**视觉症状**（好平/被压扁/看不到了）时的四步定位法：读现场 → 用真实行情逐字复现指标数学建基线 → 用「这个版本能不能渲染」反推用户装的是哪版 → 三次证据同层才改代码；震荡窗格坐标量纲禁令 + 机械 grep 自检；**`verify_vN` 版本容忍链**（OR 容忍 / 代码串旁路 / 配额改为只卡上限 / 事故检查固化成永久断言） |

### 绘图槽危机：65/64 与正确计数口径（同日第六轮）

| 资源 | 作用 |
|---|---|
| `references/aggvol-plot-slot-crisis-20260910.md` | **必须按 `series 色 ×2` 计数**，不是数 `plot()` 个数；实测偏移 +4 可预估；四级省槽优先序（复用同模式闲置槽 → 删零消费者 DW plot → line 替 bgcolor〔y 坐标严禁价格量纲〕→ 色常量/DW 打包）＋不可删清单；副指标槽位现状（46 声明 ≈ 62/64）与"服务器编译不能证明没超限"的口径 |

三条硬结论：
1. **估算器 + 4 ≈ TV 实际**（AggVol v4 估 59→实 63、v5 估 61→实 65、v6 估 58→预计 62）。
   任何新增视觉元素前跑 `scripts/pine_plot_budget.py`（常驻位置，退出码即闸门），**目标 estimate ≤ 59**，否则先省槽。
2. 省槽优先：复用同模式闲置 plot 槽（0 槽）→ 删零消费者 DW plot（−1）→
   `line.new` 替 `bgcolor`（0 槽，**但 y 坐标绝不能传 `low`/`high`**：震荡窗格会被价格量纲撑开、
   把全部曲线压平，20260910 真实事故）；
   色常量化和 DW 打包有用户可见代价，**必须先问**。
3. `translate_light` **不检查 64 绘图上限**，`errors2=[]` 不等于没超限；
   该限制只在 TV 客户端挂图/保存时触发 → 交付必须声明"此项只能由用户挂图验证"。

### Pine 数字格式：`#` 会吃掉前导零（20260910 实案）

Pine 的 `#` 是**可选**数字位、`0` 是**必填**位。所以：

| 写法 | 0.5376 渲染成 | 结论 |
|---|---|---|
| `str.tostring(v, "#.2")` | `.54` | ✗ 用户实测「`.54%`」 |
| `str.tostring(v, "#.00")` | `-.03`（负值同理） | ✗ 用户实测「`基差-.03%`」 |
| `str.tostring(v, "0.00")` | `0.54` | ✓ |
| `str.tostring(hour, "#00")` | `09` | ✓ **HH:MM 补零时 `#00` 才是对的**，别一起改错 |

**两类要分清**：小时/分钟/固定宽度的整数用 `"#00"`；任何可能 <1 的小数一律用 `"0.0"` / `"0.00"`。
自检脚本：`scan_numfmt.py`（正则 `['\"]#[.][0-9]*['\"]` 应零命中；`#00` 不算）。
**连带坑**：修完格式串会让所有「断言里写死了旧格式串」的历史 verify 脚本集体失败 ——
要在同一次提交里把这些断言改成 `新格式 or 旧格式` 的容或式，否则回归链会误报。

### 副图视觉密度 + 视图选型（同日第八轮，用户说「有点难看 / 线多了 / 和 OI 比选哪个」）

| 资源 | 作用 |
|---|---|
| `references/pine-panel-visual-density-contract-20260910.md` | **契约级用户偏好**：一个视觉元素＝一个开关；新增曲线默认 OFF（默认关 ≠ 删掉）；不为省槽牺牲观感；问"选哪个"时给唯一默认 + 操作口径。**视图选型判据 = 与表格的信息重叠度**；按 mode 诊断"线多了"的机械方法 |
| `references/pine-panel-row-optimization-and-patch-pitfalls-20260910.md` §4.1（新增） | 括号/反斜杠敏感字面量用变量拼；**断言「生成的语义」而不只是「替换发生了」** |

四条硬结论：
1. **默认状态必须是最干净的可读状态**：新增的第二条线一律默认 OFF，需要时手动开；
   默认 ON 的门槛是"它不是线"（如 `bgcolor` 竖带）。把两个视觉新增绑在同一个 bool 上
   ＝ 逼用户"全开或全关"，必被投诉。
2. **pane 只承载表格给不了的东西**：表格已用文字+数字说全的量（方向/幅度/共识度）画进 pane 就是噪声；
   只能靠形状判断的量（斜率、背离、节奏）才值得占 pane。
   同一指标的多个视图在同一 mode 下拉里 → 切换零成本 → "选一个默认 + 需要时切"成立。
3. **视觉记账与槽位记账分开**：`display=display.data_window` 的 plot **不进窗格**（不算视觉噪声）
   但**仍占 64 绘图槽**；"线多了"必须**按 mode 诊断**，不能横向统计整个脚本。
4. **按模板生成代码时，断言对象是生成结果的性质**（默认值、开关方向、单位、箭头、正负号），
   不是替换动作本身 —— "替换成功" ≠ "生成正确"。服务器编译是第二道闸门，不能替代断言。

### 行动格「内容 + 解析契约」审计（同日第九轮，用户问「表格有什么优化的吗？」）

| 资源 | 作用 |
|---|---|
| `references/pine-panel-content-contract-and-legibility-audit-20260910.md` | **第三、第四把尺子**：视觉权重（决策格有没有语义色）与声明尺寸 vs 填充行数；`str.startswith(既有文本)` 零成本上色法；**整行替换分支丢字段**通用规则；**解析契约**（auto_card `sub_keys` 按行标签解析 → 禁改名调序）；DW 字段删除前的消费者扫描表（含“无 Python 消费者 ≠ 可删”）；整行片段必须配整行锚点 |

四条硬结论：
1. 表格审计的尺子变成**四把**：最坏行宽 → 跨行重复（v3）→ **视觉权重** → **声明尺寸 vs 填充行数**。
   用户用了一阵子后再问“表格怎么优化”，答案往往不在宽度（已压过），而在后两把。
2. **每张表都查一次“唯一没有语义色的那一格是不是决策格”**。实案：副表六行里只有闸门行（操作）
   是中性灰，灯行反而有底纹抢眼 → 视觉权重与决策权重反了。修法用 `str.startswith` 从**既有文本**派生
   颜色：0 绘图槽 / 0 input / 文本零改动 / 解析不受影响。
3. **`cond ? A : B` 的整行替换分支必须查“A 丢掉了 B 独有的风险字段吗”**。实案：爆仓分支替掉 `volTxtA`，
   连带吞掉 `⚠单所主导`，而爆仓那几根正是主导风险最高的时刻；同时量能行变绿与结论行的
   “涨势衰竭/去杠杆”语气矛盾。**补回最风险的那一个词，不是全补。**
4. **行标签与闸门文本是解析契约**：`scripts/auto_card.py` 的 `sub_keys` 按行标签解析副表 →
   禁止改名、禁止调序。改字要先查消费者；`sub_keys` 的超集容忍**不是删行的许可证**。

### 回合定性修正 + 内容优先（同日第十、十一轮，用户说「颜色不太行，改回去，是内容要优化」）

**这是本会话最重要的一条用户偏好修正，覆盖上一段的"用颜色解决视觉权重"建议：**

- 第九轮的**闸门配色（`opCol/opBg`）与爆仓行改黄被用户明确回退** → v10 已撤掉，只保留其中的
  **内容**修复（爆仓分支补 `⚠主导`、`table.new` 尺寸 2×10→2×6）。
- 用户原话：**「颜色不太行，改回去，是内容要优化。」**
  → 结论：**配色改动一律先问，不要擅自动手；用户要的是补信息缺口。**
- 正解是**第五把尺子：内容完备性** —— 跑 `scripts/pine_gap_scan.py` 找「算了没渲染」；
  用户就某行问「这里只有 X，我想知道 Y」时，Y 大概率**已经算着没渲染**（实案：`lastWatchSide`
  声明后从未进表，而它正是「前位到那里算支持还是阻力」的答案）。

| 资源 | 作用 |
|---|---|
| `references/pine-panel-content-contract-and-legibility-audit-20260910.md` §1 修正 + §9~§12 | 用户回退记录；**第五把尺子（内容完备性）+ gap scan 根集合**；三处可复用补法（量比倍数 / 净流强度 / 缺票全列）；「某行只有 X 想知道 Y」的定位法与角色判定对照表；**三个新语法坑**（多行三元 CE10013、二次缩进 CE10013、半行锚点 CE10156）与 `rep_line` 整行锚骨架 |

四条硬结论：
1. **配色只诊断、不擅自交付**（用户会回退）；**内容缺口才是要改的**。
2. 表格审计的尺子按优先级重排：**内容缺口 > 声明尺寸 > 跨行重复 > 视觉权重**。
3. 用户问某行的"另一种信息"时，**先去源码找那个已存在但未渲染的变量**，不要新造指标。
4. 往面板插代码：**单行三元**、**片段不带缩进**、**整行锚替换**（三个坑本轮各踩一次，均由
   `translate_light` 服务器编译抓到，不需要客户端）。

### 变体 C：复审型审计（同日第十二轮，12 轮改动后再问「审计一下这两个指标怎么样」）

**触发**：同一对指标已经过 N 轮修改，用户再次要求"审计"。

**不要重放首轮审计** —— 首轮的 P0/P1/P2 大多已修完，重放等于交白卷。
复审要换目标：**证明 N 轮改动没引入回归**，并回答"还剩什么"。

骨架（比 8 段短，但一不能省）:

1. **结论行**：评分 + **"无 P0"** 一句话（本轮：SVP A- · 副指标 B+ · 无 P0）
2. **量化基线对比表**：绘图槽位（含余量警告）/ request / input / alertcondition /
   **死码数** / **零引用 input 数** —— 后两项是复审专属新增列
3. **P0 段**：只列"重绘 / 编译 / 可执行性"三项，全过就写明**怎么过的**
   （如"4 个 `lookahead_on` 的 `[1]` 全在 UDF 内"）
4. **P1 段**：**先否定自己怀疑过的项** —— 如"两个闸门看起来没接，查证后发现是冗余包装，不是缺口"。
   复审作废一次假警报，比再列 10 条更有价值
5. **P2 段**：死码清单（行号 + 是否带内嵌字符串）、槽位余量
6. **实盘交叉验证段（复审强制）**：把**刚读图**的结果与代码结论并列成表 ——
   哪几项落地了 ✓、哪项还没 ✗。复审不读现场等于没审
7. **建议**：必做（配置类，零风险）/ 建议做（清死码换 IL）/ 暂不动（余量），并明确问"要不要我做"

**要害**：复审的典型结论是「**问题不在代码，在配置或使用方式**」。
本轮实盘三条：`基差-0.03%` ✓ 前导零已修、前位行 `19:45定` ✓ 时刻已挂、
`协同 | 副S0未接` ✗ 总线仍是默认 `close` —— **只靠改代码能修的项已经归零**。

**必读**：`references/pine-live-main-sub-verification.md`（读图核验三步 + 总线解码 + 症状→根因表）、
`references/pine-static-scan-false-positives.md`（三类高发误报，写报告前先过一遍）。
