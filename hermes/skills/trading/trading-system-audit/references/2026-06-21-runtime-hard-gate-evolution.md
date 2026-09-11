# 2026-06-21 运行态硬闸进化教训

## 新增审计发现

① CLI 参数污染交易品种
- 症状：`trade_plans.jsonl` 出现 `symbol=-q`，心跳也可能显示 `symbol=-q`。
- 根因：`auto_card.py` 直接使用 `sys.argv[1]` 作为 symbol；pytest/CLI 静默参数 `-q` 被当作交易品种落盘。
- 修法：新增 `_parse_cli_symbol(argv)`，跳过所有 `-` 开头参数，只接受真实品种白名单/后缀。
- 回归：`_parse_cli_symbol(["-q"]) == "BTCUSDT"`。

② Crypto B级快照误杀
- 症状：BTCUSDT 实时快照为 `quality=B confidence=75 spread≈0.22%`，但 `has_min_liquidity()` 只允许 `A/A-/B+`，导致 24/7 主品种静默。
- 判别：社区风险闸应阻断执行风险，不应因为价格源一致但等级为 B 而完全静默主流 crypto。
- 修法：crypto 若 `quality=B` 且 `confidence>=70` 且 `price_spread_pct<=0.5`，允许进入监控；低于该门槛仍静默。
- 回归：B/75/0.22 通过，B/65/0.22 拒绝。

③ 监控非法 symbol 防线
- 症状：即使清理日志污染，脏数据仍可能通过 `monitor_levels.json` 或单体 raw 进入监控循环。
- 修法：`行情守望.py::_valid_symbol()` + `iter_symbol_blocks()` 入口过滤 `-q` 等非法品种；单体 raw 非法时回退 `BTCUSDT`。
- 回归：`{"symbols":{"-q":{},"BTCUSDT":{}}}` 只产出 `BTCUSDT`。

④ Watchdog blocked 状态语义
- 症状：重启限速拒绝后，状态/日志可能让人误以为“已启动”；审计运行态容易误判。
- 修法：限速触发时 `watchdog_state.status="blocked"`，`last_restart_reason` 写完整限速原因，`notify_watchdog_block()` 不再覆盖成另一套状态名。
- 回归：限速 `start_monitor()` 返回 False，状态为 `blocked`，并外发告警钩子。

## 验证 bundle
- `HANGQING_NO_SEND=1 python -m pytest -q --tb=short` → 104 passed
- `python -m py_compile hermes/scripts/auto_card.py scripts/行情守望.py scripts/session_filter.py scripts/watchdog.py`
- 再生 BTC/XAU 卡 + grep 机器字段泄漏 → 0 leaks
- 函数级实测 BTC B/75 放行、非法 symbol 过滤、CLI `-q` 回退 BTCUSDT
- commit: `3c04582 进化交易系统运行态硬闸`
