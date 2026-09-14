# 完整档（L3）实跑与关键位证据

来源：2026-09-14 的 BTC「分析BTC」会话（仓库 `D:/Hermes agent`）。
记录当时可复现的调用序列、产物位置和实测坑，供后续完整卡复用。

## 1. 跑卡前：租约

```sh
python scripts/tv_analysis_lease.py start --minutes 12 --symbol BINANCE:BTCUSDT.P
python scripts/tv_analysis_lease.py status   # 看 remaining_seconds / holder_pid
python scripts/tv_analysis_lease.py end      # 出卡后释放（忘了也会自然过期）
```

不声明租约时后台续航（`btc_tv_refresh` / `xau_tv_sync`）会在读图中途切图，行动格读成空表。

**`status` 顶层 `active` 不是租约有效性**：`start` 是 fire-and-forget，持有进程随即退出，
所以紧接着 `status` 会打印 `"active": false, "reason": "租约持有进程已退出"`，而同一响应里的
`lease.active: true` / `remaining_seconds` 才是真状态。判据看 `lease.remaining_seconds > 0`；
`end` 之后才是 `{"active": false, "reason": "无分析租约"}`。

## 2. 跑卡：用系统自带入口

```sh
HANGQING_NO_SEND=1 TANGXI_ENABLE_AUTOMATED_TG=0 \
  python scripts/auto_card.py BTCUSDT --mode-auto --message "分析 BTCUSDT"
```

- 回执第 3 行确认 `档位=full`；下一行是 `管线路由：15步 → tv→binance→cg_pro→macro→x_sent→cron_read→cvd→depth→corr→engine→regime→dual→advanced→risk→card`。
- 实测 44-52s 就跑完 15 步 → 后台跑（`background=true, notify=true`）+ `process wait`，别前台阻塞；慢时仍会到分钟级，所以也别改成前台。
- 产物：`data/auto_card_<SYM>_full.md`（卡体 + 尾部完成度审计）、截图进 `tools/tradingview-mcp/screenshots/`。

### 坑 1：`--help` 不是 help

`python scripts/auto_card.py --help` **不打印用法，会直接跑一张 quick 卡**
（实测输出「一键分析卡 · BTCUSDT · quick / 3步路由」）并顺带去刷新 TV 图表。
想看用法请读源码；调完整档只走上一节的显式命令，不带 `--mode-auto --message` 就是静默 quick。

## 3. 关键位：卡面给不够，必须补读

实测那张完整卡的 `②关键位` 六行全部落在现价 0.1% 以内：

| 显示位 | 价格 | 距现价 |
|:---|:---:|:---:|
| 4h·POC | 77,213 | +0.05% |
| 15m·VAL | 77,216 | +0.05% |
| 1h·POC | 77,231 | +0.07% |
| 15m·VWAP | 77,239 | +0.08% |
| 5m·VWAP | 77,241 | +0.08% |
| 15m·POC | 77,252 | +0.10% |

原因是渲染层只取最近的 6 个（`levels_prepared[:6]`），各周期 VWAP/POC 又天然扎堆。
读者从这六行看不出结构在哪 —— 完整卡必须补读：

```python
tool_call(name="mcp_tradingview__data_get_pine_lines",  arguments={"study_filter": "SVP"})
tool_call(name="mcp_tradingview__data_get_pine_labels", arguments={"study_filter": "SVP"})
tool_call(name="mcp_tradingview__data_get_pine_tables", arguments={"study_filter": "SVP+ICT+VWAP+CVD"})
tool_call(name="mcp_tradingview__data_get_pine_tables", arguments={"study_filter": "Volume Aggregated"})
```

labels 才会告诉你哪根线叫什么：`VAH/VAL/POC`（分周期多套）、`周六高/周六低`、`上周低`、
`周六 伦/纽 高·低`；lines 给完整价位堆。补完才写得出「上方第一阻力 / 下方磁吸」这类可决策的具名位。

余下可直接引用的指标字段（比卡面浓缩版更全）：

- 主指标「现位」行已给单一观察位口径，如 `待·反抽VWAP77237.1·等MSS↓`；
- 「磁吸↑/↓」行带 ATR 距离与命中率，如 `周六高 77477.4·5.1A·分52·46%`；
- 「前位」行给刚失效但仍当阻力的位，如 `+B1 77268.8·被替代·仍阻·↑4.1A`；
- 副指标「信号/结论/操作」三行给冲突与可否执行（如 `S3冲突·共振2/4·OI背离 → 不执行`）。
- `data_get_study_values`（主指标）给整套可直接写进关键位段的量：`S VWAP` / `S VWAP ±Band1`（判「1σ 内/外」）、
  `EMA 9/21/34/55`（判多空排列）、`POC/VAH/VAL Price`、`W VWAP` 与 `M VWAP`（价在其下方=周月偏空）、`DO Price`（当日开盘）。
- 「现位」行带**待定时间戳**（如 `待·回踩VWAP76983.9·等MSS↑·03:30定`）—— 直接引用它的方向词，
  不要自己把「回踩均价」改写成入场价；Entry Valid Code=0 时它只是观察口径。

### 出卡时的关键位收敛（用户格式要求）

补读 lines/labels 是为了**挑**位，不是把读到的位全列 —— 十几行的位表用户已明确嫌多。
出卡时收敛成 **≤4-5 行角色制**：

| 角色 | 说明 |
|:--|:--|
| ↑ 上沿阻力簇 | 最近的上方结构位；相邻 <0.15% 并成区间（`77,847–77,865`） |
| 近端转撑 | 刚破转撑的 B1／枢轴，给「中间分水岭」 |
| ↓ 主观察位 | 指标「现位」行给的 POC／VWAP —— 必须与「盯什么」是同一根 |
| ↓ 下方失效带 | 下沿支撑簇（`77,344–77,174`） |

- 24h 高低、FVG 带、日开 DO、高周期 VAH 等远端位 → 表下一行「远端 …」注脚，不占行。
- 每行只写「角色｜价位（可区间）｜距现价 ±%」，不写内部 ID、不写用法长句。
- 理由：卡面要 5 秒可读；结构位在截图上本来就看得见 —— **截图负责结构，文字负责决策**。
- 多周期同样压成一行体温条；多源表固定 ≤4 行（主指标／副指标／衍生品／宏观事件），源状态并进表下注脚。

## 4. 截图：两个来源 + 内容复核

| 来源 | 路径形态 |
|:---|:---|
| 跑卡链自动截图 | `tools/tradingview-mcp/screenshots/<SYM>_15m_<BJT 时间戳>.png` |
| MCP 手工截图 | `tools/tradingview-mcp/screenshots/tv_full_<UTC ISO>.png`（`capture_screenshot` + `region="full"`） |

复核顺序：截图前后各读一次 `chart_get_state` 核 `symbol` / `resolution`（实测得到 `BINANCE:BTCUSDT.P` + `resolution: 15`），
再对图片做一次看图复核，确认：左上角品种/周期、右侧价格轴、底部副窗格。

**看图复核的边界**：图像读数会把十字线所在那根 K 线的 OHLC、以及**可见区间内**的历史极值
描述成「最右一根 K 线 / 最新价」（实测把两天前的十字线柱和一个历史尖峰当成当前价，与 live 价差数百美元）。
所以看图只用来确认身份元素（品种/周期/价格轴/副窗格是否在画面内），
**价格一律以 `quote_get` + Binance 端点为准**，图里读出的数字不要写进卡面。

**写文案时注意副窗格的真名**：本机布局底部是 `Volume Aggregated`（图例写作 `AggVol`）+ 成交量直方图，
没有单独标为 CVD 的窗格 —— 不要笼统声称「有独立 CVD 窗格」。

### 坑 2：截图前图表身份可能已被后台切走 —— 复位 + 重读

租约只能防「读图中途被切」，不修复「已经切走」。实测 `lease start` 成功的那一刻 `chart_get_state` 返回
`OANDA:XAUUSD / 5`（后台 `xau_tv_sync` 刚切过去），此时直接截图会拍回一张黄金图，首行截图身份违规。
`chart_set_symbol` 返回 `chart_ready: false` 是正常中间态，接着设周期即可。

复位序列（每一步一次 `tool_call` 单条调用；TV 工具按 deferred 方式提供，先 `tool_search` 找回再调）：

```python
tool_call('mcp__tradingview__chart_set_symbol',    {'symbol': 'BINANCE:BTCUSDT.P'})
tool_call('mcp__tradingview__chart_set_timeframe', {'timeframe': '15'})   # 字段名是 timeframe，不是 resolution
tool_call('mcp__tradingview__chart_get_state',     {})                    # 核 symbol+resolution 后再截图
tool_call('mcp__tradingview__capture_screenshot',  {'region': 'full'})
```

复位之后**必须重读主/副指标表**（`data_get_pine_tables` ×2、`data_get_study_values`）：换过品种的 study
会对复位后的品种重算，行动格与量值都是新的，不能沿用复位前的读数写卡。

**改周期后第一次读表可能是空的**：`chart_set_timeframe` 之后首次 `data_get_pine_tables` 实测返回 `study_count: 0`
（study 尚在重算），不是指标故障 —— 等约 5-6 秒重读一次即恢复；不要用空表出卡。

### 坑 3：行动格随每根新 K 线改写，重排版/补卡也要重读

「现位」「磁吸↑/↓」「前位」在每根新 bar 上改写（实测「现位」从 `回踩VWAP` 变成 `回踩POC`，
磁吸↑ 从周六高换成新的时段高点）。任何再次出卡（哪怕用户只是要求重排版）前重读行动格，
用当前 bar 的口径写方案，并在尾注说明读数时间；读数跨过 bar 边界时以读数为准。

## 5. 完成度审计的典型形状

15 步路由、完成度实测落在 **11-14/15**（同一命令不同时段跑出 11、13、14 三种计数），差额全在「仅展示/辅助」源上：
TV 五层 / Binance 衍生品 / CVD / 深度 / 相关性 / 引擎 / 体制 / 双指标 / 高级订单流 / 风控 / 出卡 = ✅；
`CoinGecko Pro`、`宏观背景`、`X情绪`、`Cron缓存` 视本轮采集结果各自 ✅ 或 ⚠「本轮未采到有效字段」。

- 卡面写 `X情绪 ⚠ 本轮未采到有效字段` **不等于本轮没有情绪源**：完整档里 agent 自己调一次 `x_search`
  （`degraded: false` 且 `inline_citations` 非空即采用），审计里写「卡面未采到，已用 x_search 现场补齐」，不要照抄 ⚠ 认缺。

- 这四项多为「仅展示/辅助」源，不进裁决；如实写降级、不要把它们写成 15/15。
- `Cron缓存` 那行会逐源列出 `stale_cache` / `unavailable`（对应六个无采集调度的可选源），保留原样。
- 来源矩阵里应能看到 `风险快照` 一行显示 `stale_cache·<旧日期>·stale`，这是有意保留的可见降级，不是故障。

## 6. 2026-09-14 新增实战补丁

| 问题 | 修正 | 验证 |
|------|------|------|
| Grok token 读取路径错误 | `_read_grok_token()` 改为 `providers.xai-oauth.tokens.access_token`（原 flat `access_token`） | `call_grok_validation` 返回 `agree`/`divergence` 而非 `skipped=无token` |
| X情绪文件部分刷新 | `x_sentiment_context.json` 逐段校验语义时间戳，任一段过期 → 整段 `stale_cache` | `source_health.inspect_json_file` 按字段检查 |
| 关停 cron 源免责 | `dune_cache`/`deribit_options`/`qlib_factors`/`liquidation_pressure` 属 `PAUSED_SOURCES`（有意停用），审计出现 `stale_cache` 属正常降级 | `data_freshness_watchdog.PAUSED_SOURCES` 列表 |
| 相关性卡面 0.0 | `correlation_matrix.py` 改用 Binance fapi 日线（XAUUSDT 可用） | `python scripts/correlation_matrix.py` 返回 `status=ok` |
| 输出顺序固化 | 证据在前、方案在后：截图 → 裁决 → 多周期 → 关键位 → 多源冲突 → 主方案 → 失效路径 | 实跑卡面目测 |
| 仅一个主推 | 对侧仅写失效路径，不写独立触发/目标的平行方案 | 卡面只出现 ⭐主推 + 失效后看什么 |