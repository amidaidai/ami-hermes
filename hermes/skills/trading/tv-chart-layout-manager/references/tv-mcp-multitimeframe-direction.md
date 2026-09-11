# TV MCP 多周期方向一致性验证（真路径 · 2026-07-08 落地 · 2026-07-08 末次纠正补回1D）

棠溪周期一致性验证标准链 = **1D / 4h / 1h / 15m / 5m**（五周期，2026-07-08 末次纠正：原四周期漏 1D，已补回）。
加密主周期截图 15m、贵金属主周期截图 5m；验证链统一五周期。周期字符串：TV 用 "1D"（也接受 "D"），Binance REST 用 "1d"。

## 铁律
1. **每周期独立 MCP 会话**（开→set_symbol→sleep→set_timeframe→sleep→读→关）。单会话连续切周期会 `Connection closed`。
2. `set_timeframe` 后必须 `sleep(3)` 等指标完全加载再读 OHLCV summary。
3. `data_get_ohlcv(summary=True)` 返回的是 **JSON 字符串**，含 `change_pct` 字段，不是纯文本 —— 必须 `json.loads` 后读 `change_pct`。旧正则匹配纯文本会恒返回 0（表现为「TV多周期方向全空」）。
4. 端口探测：TV Desktop CDP(9222) 未开 → 直接降级 REST，不卡死。

## 方向判定（_dir_from_ohlcv_summary 正确实现）
```python
import json
def _dir(txt: str) -> int:
    s = txt.strip()
    try:
        obj = json.loads(s) if s.startswith("{") else None
    except Exception:
        obj = None
    if obj and "change_pct" in obj:
        ch = float(str(obj["change_pct"]).replace("%", "").strip())
        return 1 if ch > 0.05 else -1 if ch < -0.05 else 0
    return 0
```
真实 OHLCV summary 结构示例：
`{"success":true,"bar_count":100,"open":63309.2,"close":61984,"high":64234.1,"low":61615,"change":-1325.2,"change_pct":"-2.09%","last_5_bars":[...]}`

## 独立会话模板（async）
```python
async def _one_tf(res: str) -> int:
    sp = StdioServerParameters(command="node", args=[str(server_script)])
    async with stdio_client(sp) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            await tv.set_symbol(s, symbol)      # "BINANCE:BTCUSDT.P" 或 "OANDA:XAUUSD"
            await asyncio.sleep(3)              # 等品种加载
            await tv.set_timeframe(s, res)      # "240"/"60"/"15"/"5"
            await asyncio.sleep(3)              # 等指标完全加载
            raw = await tv.get_ohlcv(s, summary=True)
            return _dir(tv.parse_result(raw))
# 五周期元组（1D/4h/1h/15m/5m）
for res in ("1D", "240", "60", "15", "5"):
    dirs[res] = await _one_tf(res)
```

## 冲突规则（相邻反向 = 否决交易）
`1D≠4h` 或 `4h≠1h` 或 `1h≠15m` 或 `15m≠5m` → `conflict=True` → 验证闸门拦截，不发执行计划。
全部同向 → `aligned=True`。

## 实测结果（2026-07-08 · TV 真实路径）
| 品种 | 1D | 4h | 1h | 15m | 5m | 结论 |
|------|----|----|----|-----|----|------|
| BTCUSDT | 空 | 空 | 空 | 空 | 空 | 同向·无冲突 |
| XAUUSD  | 空 | 空 | 多 | 空 | 空 | 冲突（4h 与 1h 反向）|

## 启动 TV Desktop（CDP 端口 9222）
```bash
# 先杀残留实例，否则 CDP 端口冲突
taskkill /F /IM TradingView.exe
cd "D:/Hermes agent/tools/tradingview-mcp"
node --input-type=module -e "import { launch } from './src/core/health.js'; launch({port:9222, kill_existing:true})"
# 探测
python -c "import socket; s=socket.socket(); print('OPEN' if s.connect_ex(('127.0.0.1',9222))==0 else 'CLOSED')"
```
`launch()` 内部已 `delete childEnv.ELECTRON_RUN_AS_NODE`（否则 TV 报 `bad option: --remote-debugging-port` 后退出）。
