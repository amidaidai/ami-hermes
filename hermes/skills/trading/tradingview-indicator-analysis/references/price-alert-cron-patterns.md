# 价格提醒 cron 模式（自 SKILL.md 移出，2026-09-15 为技能瘦身）

- **到价通知分两种模式：LLM cron vs no_agent脚本。优先用no_agent**：
  - **LLM模式**（默认）：`cronjob(action='create', schedule='5m', prompt='...', deliver='origin')`。prompt内写明用哪些MCP工具和触发条件。**切勿设置 `enabled_toolsets`** — MCP工具不属于toolsets分类。每次跑都耗token。
  - **no_agent模式（推荐·零token）**：写一个Python脚本用 `urllib.request` 或 `curl` 从免费API拉价格做条件判断，用 `cronjob(action='create', no_agent=True, script='myscript.py', schedule='5m', deliver='origin')`。脚本输出=推送内容，空输出=静默。黄金现货价走 `api.gold-api.com/price/XAU`（免费无Key），期货价+成交量走 `query1.finance.yahoo.com/v8/finance/chart/GC=F`。零token消耗，更可靠。
  - 适用场景：价位监控、条件触发、简单价格检查 → no_agent。需推理判断、多源分析、情绪解读 → LLM模式。
  - **gold_monitor.py v2 设计要点**（双源+阶段自升级）：
    - 数据源：`api.gold-api.com/price/XAU`（现货主源）+ `query1.finance.yahoo.com/v8/finance/chart/GC=F`（期货校验，减$20溢价估算现货）。双源差价<$5取均值（A级），差价大信托主源（B级），单源运作标C级。
    - 阶段定义：8个阶段（0初始→1回踩确认→2突破确认→3空头确认→4持仓做多→5目标区→6持仓做空→7空头目标区），触发后自动跳转下一阶段不重复。
    - 冷却防刷：同阶段同条件10分钟冷却（时间戳记录，重启不丢失）。
    - 日志记录：每次触发写入 `data/gold_monitor_events.jsonl`。
    - 状态自清理：超过7天的冷却记录和警报自动清除。
    - 推送条件宽（价到位即推）+ 防重复严（冷却内不推）= 用户不丢失信号也不被刷屏。

- **双cron联动模式（no_agent触发 → agent出卡）**：当需要\"触发时自动出分析卡\"时，用两个cron配合：
  ① **no_agent价格监控**（5m间隔，零token）：`cronjob(action='create', no_agent=True, script='gold_monitor.py', schedule='5m')`。脚本检测到触发条件后，除了print推送消息，还写一个trigger request JSON文件到 `data/gold_trigger_request.json`，格式：`{'status':'pending', 'price':N, 'phase':N, 'triggers':[...], 'triggered_at':'...'}`。
  ② **agent分析cron**（1m间隔，只触发时耗token）：`cronjob(action='create', schedule='1m', skills=['tradingview-indicator-analysis'], prompt='检查 D:/Hermes agent/data/gold_trigger_request.json，如果status=pending则拉MCP数据出完整分析卡，然后改status为completed')`。
  — 没触发时：no_agent静默，agent cron检查完立即退出（几乎零token）。
  — 触发时：no_agent推消息+写标记，agent cron读到标记后自动拉MCP数据出分析卡。
  — 避免两cron打架：no_agent写完标记才走，agent读完改标记为completed，没有竞态。
  — 详见 `references/dual-cron-trigger-pattern.md`。
