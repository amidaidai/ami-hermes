# 图表层（脚本/研究）故障恢复

共享 TV 图表在分析中途「坏了」时的分层诊断、恢复阶梯与重装流程。与「被 cron 抢图」区分：抢图是读到的数据短暂错位，重读即好；本文件处理的是**读表持续为空/报错**的脚本层故障。

## 先分层，再动手

| 症状 | 层次 | 处置 |
|---|---|---|
| `study_count:0` 偶发，重读即好 | 抢图争用 | 按被抢图协议重读 |
| 读表持续空 ＋ 图例带**红色感叹号** ＋ 自定义脚本无输出（内置 Volume 正常） | 脚本层故障 | 走恢复阶梯，**不要继续重读** |
| 打开/添加脚本 X，却出现脚本 Y 的内容或研究名 | 云端槽被覆盖 | 重装权威源码（见下） |
| 表格能读但格式/锚定词属于别的周期或品种 | 图被切走 | 复位：set_symbol→set_timeframe→复核→**重读行动格** |

判据：读表持续为空时，先 `capture_screenshot(region="full")` ＋ 看图（vision_analyze）确认图例红叹号——一次判定层次；无限重读是最大的时间坑。

## 恢复阶梯（单级最多试一次，无效立即升级）

1. `ui_keyboard key="r" modifiers=["ctrl"]` 页面刷新。
2. 品种/周期往返（`chart_set_symbol` 出去再回来），复位后必须重读指标表。
3. `indicator_toggle_visibility` 对每个失联研究关→开各一次。
4. `tv_launch(kill_existing=true)` **重启 TradingView Desktop**（最后手段）。重启有代价：后台任务断一轮、图表回到 owner 持久状态——确认没有其他自动化在跑再执行。重启后：
   - 图表常回到 `BTCUSDT.P / 4h`（owner 持久状态），**需重设到工作周期**（BTC 15m / XAU 5m）并复核；
   - 自定义研究可能全部掉出图表（只剩内置 Volume）→ 走「重新挂载」；
   - 内置指标正常、只有自定义脚本失联时，问题在脚本/研究实例层，重启能清掉坏状态。

## 重新挂载研究（重启后 / 研究掉图）

- 路线：点顶栏「指标」按钮（aria-label `指标、衡量标准和策略`，data-name `open-indicators-dialog`）→「我的脚本」→ 点脚本条目。`ui_find_element` 取坐标 → `ui_mouse_click` 点击。
- 比编辑器路线（`pine_open` + Ctrl+Enter/「添加到图表」）可靠：编辑器路线依赖「编辑器当前指向的保存脚本」正确，而该状态可能陈旧/错乱；对话框添加不依赖编辑器状态。
- 挂完 `chart_get_state` 复核 studies（id+name 逐条），再读表验证输出。
- 重复实例（重复添加、修复后重编译出现两个）用 `chart_manage_indicator(action="remove", entity_id=…)` 去重，保留一个。
- **重挂后立即重接主副总线**：新实例 `input.source` 默认回 `close`，主指标会显示「副S0未接·A禁」——按 SKILL.md「指标接线也是图表状态」的 recipe 重接（值形如 `<副指标id>$49`）并回读验收。

## 云端脚本槽被覆盖（名/内容不符）

发生：在 Pine 编辑器里对「当前绑定的保存脚本」直接 `pine_set_source` + Update on chart，会把生产脚本源码顶掉（详见 SKILL.md 同名节）。

诊断：
- `pine_open(name)` 返回 `opened:true` **不代表编辑器已加载该脚本内容**——用 `ui_evaluate` 读编辑器前几行验证：`Array.from(document.querySelectorAll('.monaco-editor .view-line')).slice(0,5).map(l=>l.textContent).join(' | ')`；编辑器工具条 h2 的脚本名可能滞后，别单看它。
- 决定性证据：从指标对话框添加脚本 X，挂上来的研究名是 Y；或 `pine_open("X")` 后 Monaco 首行是 Y 的 indicator 声明。

重装（已验证流程）：

```bash
python scripts/install_pine_source.py <本地权威源码.pine> "<TV 脚本名>"
```

- 磁盘直读经 MCP stdio 写入（大源码不过模型上下文），流程 = open→set_source→保存→回读比对→编译错误检查；**成功判据 = 行数回读一致 ＋ `has_errors:false`**。
- 权威版本路径见 `outputs/readonly_uploaded_pine_audit_*.json`（按 role 列出 svp/aggvol 的 authority 路径与 sha256）——别用来源不明的本地副本。
- 重装后重新挂载；**槽被覆盖期间误添加的实例会在脚本修好后自动重编译为正确脚本**（研究名随之变化）→ 挂完逐条比对去重。

## 验收

- [ ] `chart_get_state` studies 与目标（主＋副＋内置）逐条一致（id+name）
- [ ] 两张行动格可读，主「协同」S-code = 副「信号」S-code（总线已接）
- [ ] full 截图含价格轴＋副窗格，身份（品种/周期）同轮复核
- [ ] `pine_list_scripts` 与编辑器无残留，交付说明写明遗留项
