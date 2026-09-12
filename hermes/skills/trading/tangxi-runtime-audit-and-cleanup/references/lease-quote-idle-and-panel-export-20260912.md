# 2026-09-12 现场：死进程租约 / 让路假绿 / idle 与 DEGRADED / 报价身份 / 风控文字

与 SKILL.md 「死进程分析租约 + 让路退出码0」那节配对。本文只存取证与验收句。

## 1. 死 pid 租约

`data/tv_analysis_lease.json` `active=true`、TTL 未到，但 `pid=16700` 已不存在。XAU cron 每 15 分 `return 0`，缓存停 17h，调度器 `last_status=ok`。

验收：`analysis_lease_status()` 对死 pid 返 `active=false, reason 含「进程」`。

## 2. 让路退出码

已发布缓存仍 usable → `return 0`。已过期 → `return 1`。不能把 17h stale 记成成功。

## 3. idle ≠ DEGRADED

用户 `enabled=false` 静默全部批准位。`config_health.status=idle`，看门狗 exit 0。不要自动 `enabled=true`，不要续期静默位。

## 4. 报价身份

`_collect_and_cache_locked` 不能写死 BTC swap。XAU 报价要 OANDA/cfd，禁止 Binance 合约交叉。XAU 只写 `tv_live_XAUUSD.json`。

## 5. 主格没有「操作」行

那是副指标。XAU 配对契约：结论/方向/路径 + 风控标签。周末 `X·等开市` 也能发布。

## 6. 归属棘轮补丁

`pending_restore` 清掉后图停在采集品种：用记住的 `user_symbol` 修回，不能当「用户真在看 XAU」。

## 7. 风控行文字 ≠ 执行导出

面板 `入/止/标` 是给人看的。可执行三件套只认 MCP Entry/Stop/Target，且 `risk_label==风控`。渲染器禁止 `entry or position`。

## 8. 历史哨兵 `__main__`

`btc_keylevel_sentinel` / `rest_guard` / `ws_guard` / `btc_price_arrival_sentinel` 仍在 `scripts/`（态②）。`__main__` 应打「已退役·权威 keylevel_guard」并 exit 0，不要写「已删除」。

## 9. 用户上传指标审计第一步

上传 pine 与 `outputs/pine_20260905/` 定版逐字比 + `tv_indicator_alignment_check` + 图上 `data_get_pine_tables` 13+6 行。本轮三者一致：sha `68a34fc32da0` / `c4c563ef4a08`。
