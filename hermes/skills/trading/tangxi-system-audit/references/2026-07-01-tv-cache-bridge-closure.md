# 2026-07-01 TV缓存桥闭环修复模式

## 适用场景
- 全方位系统审计后发现 `tv_live.json` / `tv_dmi_cache.json` 过期、错品种、或 BTC/XAU 关键位串数据。
- TradingView MCP `mcp test tradingview` 可用但 `tv_data_bridge.py` 无法刷新、POC/VAH/VAL 为空。
- `auto_card.py` 明明有新 `tv_dmi_cache.json`，却仍因旧 `tv_live.json` 降级或跳过。

## 核心经验
1. **先修CDP，再修解析**
   - `node tools/tradingview-mcp/src/cli/index.js status` 若返回 `CDP connection failed`，先用 `mcp_tradingview_tv_launch(port=9222, kill_existing=true)` 启动 TradingView Desktop。
   - 再用 `mcp_tradingview_tv_health_check` 验证 `cdp_connected=true`、`chart_symbol` 和 `chart_resolution`。

2. **TradingView CLI现在返回JSON，不要按旧文本格式解析**
   - `tv values` 返回 JSON，其中 `studies[].values` 含 `POC Price`、`VAH Price`、`VAL Price`。
   - `tv data tables --study-filter SVP` 返回 JSON，其中 `studies[].tables[].rows` 为行动格行，如 `结论 | 等多 回踩`。
   - `tv data lines --study-filter SVP` 返回 JSON，其中 `horizontal_levels` 只有水平价位，通常没有 POC/VAH/VAL 标签；POC/VAH/VAL 应优先从 `values` 取。

3. **缓存候选必须逐个校验并继续fallback**
   - `auto_card.py` 不能遇到第一个 `fresh+poc` 的旧 `tv_live.json` 就停止。
   - 对每个候选缓存执行 `_tv_cache_status(cache, symbol)`；若过期/品种不匹配，记录原因并继续试下一个候选（如 `tv_dmi_cache.json`）。
   - 只有 `usable=true` 才允许注入 `klines` 和 `merged`。

4. **禁用硬编码TV dump**
   - `tv_live_dump.py` 不得写静态BTC POC/VAH/VAL。历史硬编码59k会污染未来审计。
   - 正确做法：让 `tv_live_dump.py` 作为兼容wrapper调用 `tv_data_bridge.collect_and_cache()`，CDP不可用时明确失败退出。

5. **BTC/XAU双品种回归不可省**
   - BTC：应输出 `TV实时注入: POC... VAH... VAL...`，且价格来自当前TV缓存。
   - XAU：若缓存 symbol 为 `BINANCE:BTCUSDT.P`，必须输出品种不匹配并拒绝注入；grep XAU输出不得出现 59k/60k BTC级别关键位。

## 最小验证命令
```bash
cd "D:/Hermes agent"
python -m py_compile scripts/auto_card.py scripts/tv_data_bridge.py scripts/tv_live_dump.py scripts/regression_system_audit.py
python scripts/regression_system_audit.py
python scripts/tv_live_dump.py
python scripts/auto_card.py BTCUSDT
python scripts/auto_card.py XAUUSD
```

## 预期信号
- `data/tv_dmi_cache.json` age < 5分钟，`symbol=BINANCE:BTCUSDT.P`，`poc/vah/val` 不为 null。
- BTC卡出现真实TV注入。
- XAU卡出现 `品种不匹配 BINANCE:BTCUSDT.P`，不出现BTC 59k/60k价位。

## 提交纪律
- 若存在会前已有的大diff（如 Orion格式改造），不要混入TV缓存修复提交。
- stage只包含本轮修复文件和回归脚本；提交后 `git status` 可保留明确标注的既有diff。