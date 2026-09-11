# 2026-07-08 TV 缓存 XAU/BTC 交叉污染复发 · 根因与两段式修复

## 复发现象
- `auto_card.py BTCUSDT` 实跑输出 `📡 TV实时注入: POC4122 VAH4132 VAL4107`，多周期定位 D 行显示 `POC 4122`，但 BTC 现价 62,854。
- 引擎饿死信号却正常（`✅ VWAP/EMA引擎：快线62736`），说明只有 TV 缓存价位被污染，K线路径正常 → 污染集中在 `tv_live.json` / `tv_dmi_cache.json` 的 POC/VAH/VAL 字段。

## 根因定位（写入端）
`scripts/tv_data_bridge.py` 第183行（修复前）:
```python
"symbol": "BINANCE:BTCUSDT.P",   # 硬编码，未读真实图表
"fresh": True,                    # 自标，非实时计算
```
`collect_and_cache()` 调 `read_indicators()` / `read_dmi_table()` 读的是 **TV 当前图表** 的 POC/VAH/VAL。审计当时图表停在 `OANDA:XAUUSD`（价位 4122），但 symbol 字段硬标 BTC → XAU 的 4122 被写成 `tv_dmi_cache.json` 且谎称 BTCUSDT。`tv_live_dump.py` 包 `collect_and_cache()` 同病。`行情守望.py` 的 `_check_tv_grade_change` 也读此缓存 → 等级告警误报风险。

auto_card 旧 `_tv_cache_status` 只校验：symbol 字符串匹配（谎称 BTCUSDT 通过）+ 年龄新鲜（self-marked `fresh:True` 通过）→ 误判 usable。

## 两段式修复（已落地 + 双品种实跑验证）

### ① 写入端根治 — tv_data_bridge.py
- 新增 `read_state_symbol()`：调 `_tv_json("state", timeout=10)` 读真实图表 symbol（**CLI 命令是 `state`，不是 MCP 的 `chart_get_state`**）。
- 新增模块内 `_norm_symbol_for_cache()`（与 auto_card 同逻辑归一化）。
- `collect_and_cache(alert_mode=False, expect_symbol=None)`：传 `expect_symbol` 时，真实 symbol 归一化不匹配则**拒绝写入并回退旧缓存**（return old / None）。
- 缓存 `symbol` 字段改为 `real_symbol or "UNKNOWN"`，删除硬编码。
- `tv_live_dump.py` 调 `collect_and_cache(expect_symbol="BINANCE:BTCUSDT.P")`。

### ② 读取端第二道防线 — auto_card._tv_cache_status
价位区间合理性校验（即使 symbol 字符串被错标也能拦）：
```python
poc = safe_float(cache.get("poc"))
if poc:
    if want.startswith("BTC") and poc < 10000: price_ok=False; reason="价位污染 POC=.. 疑似XAU数据"
    elif want.startswith("XAU") and poc > 10000: price_ok=False; reason="价位污染 POC=.. 疑似BTC数据"
usable = bool(symbol_ok and fresh and price_ok)
```

### ③ 旧污染缓存清理
`tv_live.json` 当时 `symbol=BINANCE:BTCUSDT.P` 但 `poc=4122` → 标 `stale=True` 防误用（不要直接删，保留证据）。

## 验证结果
- 修复前：`tv_dmi_cache.json` symbol=BTCUSDT.P poc=4122
- 修复后 `tv_data_bridge.py` 实跑：图表停 XAU → symbol 如实标 `OANDA:XAUUSD` poc=4122（正确归属）
- BTC 卡：`tv_live.json: 价位污染 POC=4122.132 疑似XAU数据` + `tv_dmi_cache.json: 品种不匹配 OANDA:XAUUSD` 双拒 → 现62831 POC62669（干净）
- XAU 卡：4132 正确，无反向污染
- GO/NO-GO 均正常拦截（rr_ratio / data_freshness 红灯）

## 回归断言（补 regression_system_audit.py）
- `XAU拒绝BTC TV缓存`：构造 symbol=BTCUSDT.P 但 poc=4122 的缓存 → `_tv_cache_status` 必须 usable=False
- `BTC接受BTC TV缓存`：symbol=BTCUSDT.P 且 poc=62669 → usable=True
- 反向同理：XAU 缓存 poc>10000 必须拒绝

## 铁律（写入本条后长期有效）
- 任何写 TV 缓存的脚本**禁止硬编码 symbol**，必须读 `chart_get_state`/`state` 真实 symbol。
- 任何读 TV 缓存的注入点必须做**双校验**（symbol 匹配 + 价位区间合理性）。
- 单一 TV 图表多品种切换场景下，缓存 symbol 与当前图表不一致即视为污染，宁可降级不可用也绝不采信。
