# BTC 关键位同步 · 正确架构（MCP stdio 路径）— 2026-07-08 根治

## 三种「看似正确但实测失败」的修法（必须避免）

1. **`tv_data_bridge.collect_and_cache(expect_symbol=...)` 拒绝写入+回退旧缓存**
   回退的旧缓存本身可能已是错误品种（图表停在 XAU 时手动跑过 bridge 把 XAU 写进了 tv_dmi_cache）。回退→写 tv_live.json=XAU→`btc_ref_levels_sync.pick_cache()` 找不到 BTC 缓存→每日4次的 BTC关键位同步全部 `script failed`。
2. **`tv values/data tables/data lines --symbol BTC` 直读**
   SVP **主指标**（POC/VAH/VAL/决策表）绑定图表品种，`--symbol` 直读只对 **HALDRO 副指标**（聚合、仅加密有效）生效，SVP 主驾驶数据仍读全局图表。实测 `values --symbol BTC` 返回的是 HALDRO 的 EMA/Composite，不是 SVP 决策表。
3. **CLI `node .../index.js symbol set "BINANCE:BTCUSDT.P"`**
   CDP 模式下极不稳定，反复切换会卡死在诡异品种 `CBOE_DLY:SET` 且读不到 SVP。本会话实测切到 BTC 后 30s 仍停在 CBOE_DLY:SET。

## 正确修法（已落地验证 · `scripts/btc_ref_levels_sync.py`）

`refresh_tv_cache()` 改用 **MCP stdio 路径**（与 XAU 同步同源 `fetch_tv_mcp.py`），独立切 BTC 读 SVP，写完回切原图表：

```python
from fetch_tv_mcp import (get_ohlcv, get_study_values, get_pine_lines, set_symbol, get_chart_state)
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession

async def _run():
    sp = StdioServerParameters(command="node", args=[str(server_script)])
    for attempt in range(2):  # 偶发空，重试1次
        async with stdio_client(sp) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                prev = await get_chart_state(s)          # 记录原品种
                prev_sym = <从 prev 解析 symbol>
                await set_symbol(s, "BINANCE:BTCUSDT.P")
                await asyncio.sleep(4)
                dmi = await get_study_values(s)          # SVP 主指标
                lines = await get_pine_lines(s)         # horizontal_levels
                ov = await get_ohlcv(s)                 # high/low/close
                if prev_sym:
                    await set_symbol(s, prev_sym)       # 回切，保住看盘
                parsed = _parse_btc(dmi, lines, ov)
                if parsed: return parsed
    raise RuntimeError(...)
```

### `_parse_btc` 关键坑（必看）

MCP 工具返回的是 `CallToolResult`，**必须先 `parse_result(raw)` 取 `.content[0].text` 再 `json.loads`**。直接 `json.loads(str(raw))` 会因含 `meta=None content=[TextContent(...)]` 包装而失败返回 `{}` → `_parse_btc` 返回 None → 降级。

```python
from fetch_tv_mcp import parse_result
def _j(raw):
    try: return json.loads(parse_result(raw))   # ← 不是 str(raw)
    except Exception: return {}
```

- `get_study_values` → `studies[].values` 取 `S VWAP`/`POC`/`POC_PRICE`/`VAH_PRICE`/`VAL_PRICE`/`DO Price`
- `get_pine_lines` → `studies[].horizontal_levels`（按价排序，VWAP 上下取最近边界推算 VAH/VAL）
- 写出 `tv_live.json` + `tv_dmi_cache.json` 时**顶层放裸字段** `poc/vwap/val/vah/do/w_vwap`（兼容 `main()`/`pick_cache` 既有取法 `ind.get("s_vwap") or ind.get("S VWAP")`），`symbol` 标 `BINANCE:BTCUSDT.P`
- **失败兜底**：MCP 失败 → `recent_hilo()` Binance K线直取，保证 cron 不 `script failed`（无内容可推时 `silent`，非失败）

### 验证

- `hermes cron run ada5d94913fd` → `Ran now: succeeded`，输出 `Status: silent (empty output)`
- `data/btc_ref_levels.json`：`poc~62638 vwap~62639 vah~62766 val~62434 tv_symbol=BINANCE:BTCUSDT.P`
- 图表切到 XAU 跑同步后仍停在 XAU（回切生效）
- XAU 卡不受影响（独立走 `data/xau_tv_state.json`）
