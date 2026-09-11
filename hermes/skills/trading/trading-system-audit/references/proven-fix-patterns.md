# 棠溪交易系统 · 已验证修复模式库

审计后实施阶段反复用到的、跨会话可复用的诊断与修复套路。每条都在真实系统上验证过。

## 1. 进程树诊断 — 区分「真重复」与「launcher+worker 父子对」
Windows 上看到「binance-mcp ×4 / finance-mcp ×4」先别 taskkill。多数是正常结构，不是 bug。

排查顺序（POSIX shell / wmic，PowerShell 内联 if 不可用）：
1. `wmic process where "name='python.exe'" get ProcessId,ParentProcessId,CommandLine` 取 PID 树。
2. 逐层向上追溯 ParentProcessId 到顶层 `Hermes Studio.exe`。
3. 判定规则：
   - 每个 MCP 通常是 **venv launcher → re-exec 成 uv worker** 的父子对（uv 运行 MCP 的标准模式），算 1 个实例不是 2 个。
   - 多个 Web UI runtime 宿主各自派生一套 MCP 属正常并发，不是泄漏。
   - 真正可疑的只有「父进程不在任何活宿主下」的孤儿树。
4. 结论：杀 MCP 子进程会让**当前会话的工具掉线**。要减进程应关掉多余的 Hermes Studio 窗口/runtime，而不是 taskkill。
- grep 中文匹配 wmic 输出会因 UTF-16/GBK 编码失败 → 改用 PID 父子结构数实例，别 grep 进程名。

## 2. 复盘闭环字段断点 — 自动标注写入字段必须与统计消费字段对齐
最隐蔽的闭环 bug：写入端和消费端字段名不一致，数据静默不被消费。
- 本系统实例：三重障碍自动标注写 `model_id` / `result_r`，但 `模型统计.py` 读 `model` / `r_multiple` → 自动标注的 review 全落「未标注模型」。
- 修复模式：在统计侧加**兼容取值函数**，不要去改写入侧。
  - `review_model_key(row)` = `model_id or model or setup_model or "未标注模型"`
  - `review_r(row)` = `result_r` 优先，回退 `r_multiple`
  - `group_reviews()` 统一用上面两个函数分组。
- 审计任何「写入→统计/训练」管线时，先 grep 两端字段名核对，再相信数字。

## 3. 三重障碍自动标注 — 根治复盘样本失衡（如 68:1）
计划数远大于复盘数 = 没有机制自动判定 setup 后续止盈/止损。
- 方案：`triple_barrier.py`（纯函数，止盈/止损/竖轨超时三障碍 + ATR 推导止损距离）+ 消费脚本拉历史 K 线批量标注 → 写 trade_reviews。
- 关键参数教训：
  - 周期别用 1m。BTC 用 ATR×1.5 在 1m 上止损距离仅 ~0.16%，一根就扫到 → `bars_held=1` 退化成噪音。**日内用 5m**。
  - 竖轨时间闸门必须按周期毫秒换算：`MAX_BARS * BAR_MS`，不能写死 `MAX_BARS * 60_000`（那是按分钟，5m K 线会提前 5 倍放行）。
  - events 的 `levels` 可能是 list（无显式止盈止损）→ 标注走 ATR 推导路径，`label_event` 不能假设 levels 是 dict。
- 接 cron 用 no-agent 桥接脚本：模块内部 `print` 要重定向掉，只在**有标注结果时**输出，否则每小时空推送。

## 4. CVD C级→A级升级 — 用 aggTrades 真实逐笔替代 K 线估算
- 旧 C 级：1m K 线 `taker_buy_volume`（列9）估算，粒度粗。
- A 级：`/api/v3/aggTrades`，字段 `m=isBuyerMaker`：`m=True`→主动卖出，`m=False`→主动买入。
- 单次拉 1000 笔耗时 ~0.5s，可接受，不拖慢主循环（不是预想的 6s）。
- 多周期一致性：5m/15m/1h 全同向才算 A 级强确认，分歧标 B 级 + ⚠ 仅作弱确认。
- 升级要改**两条路径**：`行情守望.get_cvd` 和 `system_data_bridge.cvd_dir`（后者是 `_HAS_BRIDGE` 主路径），都改 aggTrades 优先、失败回退旧估算。

## 5. 看门狗限速 — 真崩溃 vs 环境未就绪分桶
一刀切 3次/小时会在 cron 空/环境未就绪时也拉黑，导致进程真死了也救不活。
- 双桶：真崩溃（进程已死，`emergency=True`）走宽松预算（6次/小时，必须救活）；卡死强杀/心跳缺失走保守（3次/小时，防空转死循环）。
- guard 文件升级为 `{"restart_times": [], "restart_times_emergency": []}` 双键。

## 6. Telegram 推送直连 Bot API
- 解析 `telegram:-100xx:thread` → `chat_id` + `message_thread_id`，POST `https://api.telegram.org/bot<TOKEN>/sendMessage`。
- token 在 `.env` 的 `TELEGRAM_BOT_TOKEN`。
- 改 `_send_one` 为直连优先、subprocess 兜底，省掉每条消息一个子进程。
- 注意：Telegram API 受 GFW 影响，实测直连可达就用直连；不可达需走代理。

## 7. 自适应仓位
- `risk_constitution.adaptive_risk_usd()`：按 ATR% 波动率缩放 risk_usd，高波动减仓、低波动加仓。
- 硬上限是**绝对 10U**（账户铁律「单笔最大10 USD」），不是账户百分比 → 取 `min(百分比上限, 10.0)`。

## 通用纪律
- 全程 TDD：每个新模块先写 RED 测试（断言契约）→ 跑确认失败 → 实现 → GREEN。本系统测试基线随改动增长，收尾必跑全量 pytest 回归。
- 实弹验证不空说：拉真实 Binance/事件数据跑端到端，确认数字真实产生；临时测试数据用完即清理，避免污染 trade_reviews 统计。
