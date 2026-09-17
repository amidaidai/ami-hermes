# 版本指纹验证与「图表新码 / 云端旧码」缺口（2026-09-17 实案）

适用：指标改动只新增了**位**（如 CVD 样本拆位：noTrade bit2048、quality bit128）后，需要在不改图、
不重新编译的前提下，验证「图表实际跑的是哪版」，并识别「编辑器改了但没保存」。

## 1. 新位值指纹（读 DW 即可判定运行版本）

- 判据：**旧位域上限 = 全部旧位之和**。本案例 noTrade 旧上限 2047、quality 旧上限 127；
  任何超出上限的读数（2048 / 128）只可能由新码产生 ⇒ 图表已运行新版 ⇒ 客户端编译已通过。
- 操作：目标品种在**新 K 线开立后 1–4 分钟**读 `data_get_study_values`：
  新版应出现 128 / 2048（可与 1024 等叠加）；旧版同刻只会是 2 / 32。
- 窗口：CVD 样本位只在每根 K 线前段置位（15m 图约前 5 分钟；实测 +1.5min 置位、K 中段已清零）。
- 对照：K 线中段再读一次应为 0（样本长好自动清零），可同时验证「自动解除」。

## 2. 「图表运行新码、云端仍是旧码」= 编辑器改动未 Save

- 识别：pine-facade 只读读回（list + get）云端 sha ≠ 本地新版，而图表指纹 = 新版；
  saved 列表无同标题副本（排除多 Monaco 污染）。可复用脚本：
  `scripts/tv_cloud_readback.mjs`（技能自带，只读，node 跑：列 saved → 按 scriptId 取回 → norm 对比候选 → 落盘读数与摘要）。
- 语义：Pine Editor「更新图表」编译的是编辑器缓冲；「保存」是独立动作，不点不落云端。
- 处置顺序：① 提示用户点保存；② 复跑 readback 验证三方一致（上传=仓库=云端）；
  ③ 再更新 `tv_indicator_contract.py` docstring 定版 pin / alignment 脚本 pin / field-map。
  **保存前不动任何 pin。**
- 风险：不保存 → 缓冲丢失即丢改动；下次从云端旧码「更新图表」会静默回退逻辑。

## 2b. 编辑器缓冲直读（保存前核验：点保存将落什么版本）

云读回回答「云端现在是什么」；缓冲直读回答「保存后会变成什么」。保存前两者都核，用户一键即可确认不会存错版本。

步骤（只读）：
1. 打开编辑器面板（Monaco 未挂载时 finder 找不到）：MCP `ui_open_panel` `{"panel":"pine-editor","action":"open"}`。
2. `node scripts/tv_editor_buffer_read.mjs [outFile] [candidateFile]` —— 源码写盘、只打印长度/sha/对比摘要。
3. 判据：`getValue()` 返回 **LF 归一**文本 ⇒ 编辑器 sha 与候选文件的 LF 归一等值即逐字一致。
4. 收尾关闭面板（MCP close）。

实现要点（为何自写脚本而不用 `pine_get_source`）：
- MCP `pine_get_source` 把全量源码返回进上下文（大脚本 200KB+），**对大脚本禁用**；自写脚本写盘 + 摘要。
- 页面上下文**无** `window.monaco` 全局；用 React fiber 遍历找编辑器：
  `.monaco-editor.pine-editor-monaco` → `__reactFiber$` 键 → 上溯 ≤15 层 → `memoizedProps.value.monacoEnv.editor.getEditors()` 取可见/聚焦最优者
  （片段源自 `tools/tradingview-mcp/src/core/pine.js` 的 FIND_MONACO）。
- 面板开关判定用底栏高度（`[class*="layout__area--bottom"]`.offsetHeight > 50）；**不要**用 Monaco 容器是否存在/rect——面板收起后容器仍挂 DOM 且 rect 非零（TV 缓存 Monaco 实例）。
  `bwb.hideWidget('pine-editor')` 依赖 `window.TradingView.bottomWidgetBar`，部分 evaluate 上下文没有该对象、关闭会静默无效；以底栏度量复核收尾状态，必要时用 MCP 再关一次。
- 通过 `tool_call` 单次只下发一个 TV MCP 工具（该类工具按 local 处理，不能批量；批量仅对 connector 命名空间生效）。

## 3. 测试运行器（本机无项目 venv 时的正确姿势）

```bash
HANGQING_NO_SEND=1 uv run --no-project --python 3.11 \
  --with "pytest==9.1.1" --with mcp --with massive \
  python -m pytest tests/ -q
```

- 缺 `mcp` / `massive` 时会有 12 项假失败（test_v16_screen_switch_dedup → pywintypes、
  test_massive_rolling_window → massive）；补齐后 1456 passed / 1 skipped（2026-09-17 实测）。
- 不要把这类 ModuleNotFoundError 当回归。
