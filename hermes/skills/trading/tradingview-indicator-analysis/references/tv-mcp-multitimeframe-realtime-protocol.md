# TV MCP 多周期实时分析协议（2026-06-26）

## 触发场景

用户上传或指定自己的 TradingView Pine 指标（例如 `指标svp_v10_优化版.txt` / `SVP+ICT+VWAP+EMA+CVD`），并要求“我说分析哪一个就多周期分析，然后截图发我，高周期可以继承，低周期要实时分析”。

## 必做流程

1. **读取当前上传源码**
   - 用用户上传路径读取 Pine 源码；不要假设桌面旧文件、patched 文件或记忆里的旧版本就是当前生产版本。
   - 识别：右上角行动格、Data Window plots、VWAP/EMA/CVD、SVP、ICT 扫线、DMI/执行评分字段。

2. **连接 TV MCP**
   - 先 `tv_health_check` / `chart_get_state` 确认 CDP、当前 symbol、timeframe、studies。
   - 若 CDP 失败且提示可启动，允许 `tv_launch(kill_existing=false)` 后复查。
   - 不要把一次连接失败写成“TV MCP不可用”的长期结论。

3. **默认品种映射**
   - BTC → `BINANCE:BTCUSDT.P`
   - ETH → `BINANCE:ETHUSDT.P`
   - XAU/黄金 → 用户布局常用品种优先；若不确定再查当前图表或询问。
   - 用户只说“分析 BTC/XAU/ETH”时，直接切图执行，不反问周期。

4. **多周期链**
   - 高周期：默认 `4h → 1h`，用于背景方向和结构继承。
   - 低周期：BTC 默认 `15m → 5m` 实时执行；XAU 默认 `15m → 5m` 或用户当前布局主执行周期。
   - 高周期可以继承最近有效背景，但必须说明继承依据和失效条件；低周期必须实时读取 TV 数据。

5. **等待和重试**
   - `chart_set_timeframe` 后不要立刻信任数据。
   - 读取 `study_values` 后检查是否包含当前指标的 `S VWAP` / EMA / CVD 等字段。
   - 若缺 SVP 指标值或只返回 Volume/OI：等待 3s 后重读，最多 3 次。
   - 若周期切换后 study 仍存在但无 plot 值，继续用 OHLCV + 已读高周期表格做降级判断，并在结论中标注“该周期指标值未返回”。

6. **每个周期读取集合**
   - `data_get_ohlcv(summary=true)`：确认真实价格、最近波动和最后K线。
   - `data_get_study_values()`：VWAP/EMA/CVD/Data Window 编码。
   - **必须解码 Data Window 编码字段**：SVP 指标将多个数值打包进单个 plot（如 `Scores (Loc*100+Cfm*10+Ext)`、`Magnet+ICT+Score (Mag*1e6+DistA*1e3+Score/1e3+ICT/1e6)`、`ICT Count (Swept*100+Active)`、`Risk (R*1e4+D*1e2+W)`、`CVD Session (A*1e6+L*1e3+N)`、`Replay Side+Grade (Side*10+Grade)`、`SMT Div (2=多背离 -2=空背离)`）。用 Pine 源码公式逆向拆解。详见 `references/svp-indicator-data-window-encoding.md`。
   - `data_get_pine_tables(study_filter="SVP")`：右上角行动格，优先作为执行结论。
   - `data_get_pine_labels(study_filter="SVP")`：ICT/日周池/POC/VAH/VAL 标签。
   - `data_get_pine_lines(study_filter="SVP")`：水平关键位。

7. **数量级/旧数据校验**
   - 用 OHLCV close 对比 `S VWAP`/EMA：如果数量级明显不匹配或差距极端异常，视为旧品种/旧周期残留。
   - 修复方式：再次 `chart_set_symbol` + `chart_set_timeframe`，然后重读；必要时截图佐证当前图表。

8. **截图时机**
   - 完成低周期实时读取后立即 `capture_screenshot(region="full")`。
   - full 截图必须包含右侧价格轴、主图指标、右上角行动格、底部 CVD/OI/Volume 窗格。
   - 截图是分析证据，不是可选附件；输出中必须给用户 Markdown 图片路径。

9. **输出原则**
   - 首行先给明确方向：偏多/偏空/观望，不要把两个方向丢给用户选。
   - 手动分析用 5 段：结构 → 关键位 → 量价/CVD → 方案 → 评分。
   - **BTC 默认用紧凑决策卡优先**：用户只说“分析BTC / [Tang Xi] 分析BTC”时，除非明确要求完整版，先输出一屏内可执行卡（方向、关键位、量价、操作、结论），不要展开80行研究报告。
   - 结合行动格原文，如 `B空 轻仓`、`等空 反抽`、`HTF✓ EMA✓ CVD-`。
   - 高周期给背景继承，低周期给实时触发价。
   - 不要写“你自己看TV确认”；必须替用户读完图。

## 本次 BTC 示例要点

- 当前图表 `BINANCE:BTCUSDT.P`，指标 `SVP+ICT+VWAP+EMA+CVD` 已加载。
- 4h 可读行动格：`等空 反抽`，方向 `15m→ 1h↓ 4h↓ 1D↓ 顺空`。
- 1h 出现 study_values 只返回 Volume/OI 的情况；不能假装有 SVP 值，需标注该周期指标 plot 未返回或重试。
- 15m/5m 行动格均给 `B空 轻仓`，执行点是反抽 VWAP，目标 `58030.0`。
- 截图路径示例：`D:/Hermes agent/tools/tradingview-mcp/screenshots/BTCUSDT_5m_SVP_v10_analysis.png`。
