# CLI 品种识别与预检闭环（2026-09-03）

## 已验证的问题

`auto_card.py --mode-auto --message "看下XAUUSD" --no-push` 原先会因为 `_parse_cli_symbol()` 只扫描位置参数、跳过 `--message`，在没有有效位置品种时静默回退到 `BTCUSDT`。表现为消息档位判定为 quick，但实际生成 BTC 卡，属于跨资产入口的高风险错配。

## 修复模式

- 先解析 `--message` 的值，再扫描位置参数。
- 保留 `BTC`→`BTCUSDT`、`XAU`→`XAUUSD` 的别名。
- 当消息包含 `XAU`/`GOLD` 时解析为 `XAUUSD`，包含 `BTC` 时解析为 `BTCUSDT`；未知消息仍使用安全默认值。
- 用 BTC 与 XAU 各执行一次 `--mode-auto --message ... --no-push`，确认标题、管线路由、TV主周期和截图品种均一致。

## 运行态验收顺序

1. 刷新资产专属现场数据（XAU 用 `xau_tv_sync.py`，BTC 用现役关键位/TV采集器）。
2. 运行 `python scripts/audit_preflight.py`。
3. 只有退出码为 0 才可把运行态标记为闭环；单项缓存新鲜不能替代严格契约。
4. 预检失败时修复根因后重新采集并复跑，不以旧缓存或“进程有心跳”包装为健康。
5. 最后运行目标测试、`compileall` 和全量回归。

## 本次实测证据

- XAU 五周期 + 5m 行动格：通过。
- BTC 五周期：刷新后通过，覆盖 5/5。
- `--mode-auto --message "看下XAUUSD"`：正确生成 XAUUSD quick 卡。
- 全量测试：407 passed。
- 自动推送未启用；本流程只做本地、人工辅助验证。
