# 完整档（L3）实跑与关键位证据

来源：2026-09-13 的 BTC「分析BTC」会话（仓库 `D:/Hermes agent`）。
记录当时可复现的调用序列、产物位置和两个实测坑，供后续完整卡复用。

## 1. 跑卡前：租约

```sh
python scripts/tv_analysis_lease.py start --minutes 12 --symbol BINANCE:BTCUSDT.P
python scripts/tv_analysis_lease.py status   # 看 remaining_seconds / holder_pid
python scripts/tv_analysis_lease.py end      # 出卡后释放（忘了也会自然过期）
```

不声明租约时后台续航（`btc_tv_refresh` / `xau_tv_sync`）会在读图中途切图，行动格读成空表。

## 2. 跑卡：用系统自带入口

```sh
HANGQING_NO_SEND=1 TANGXI_ENABLE_AUTOMATED_TG=0 \
  python scripts/auto_card.py BTCUSDT --mode-auto --message "分析 BTCUSDT"
```

- 回执第 3 行确认 `档位=full`；下一行是 `管线路由：15步 → tv→binance→cg_pro→macro→x_sent→cron_read→cvd→depth→corr→engine→regime→dual→advanced→risk→card`。
- 耗时约 2-3 分钟 → 后台跑（`background=true, notify=true`）+ `process wait`，别前台占着。
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

## 4. 截图：两个来源 + 内容复核

| 来源 | 路径形态 |
|:---|:---|
| 跑卡链自动截图 | `tools/tradingview-mcp/screenshots/<SYM>_15m_<BJT 时间戳>.png` |
| MCP 手工截图 | `tools/tradingview-mcp/screenshots/tv_full_<UTC ISO>.png`（`capture_screenshot` + `region="full"`） |

复核顺序：截图前后各读一次 `chart_get_state` 核 `symbol` / `resolution`（实测得到 `BINANCE:BTCUSDT.P` + `resolution: 15`），
再对图片做一次看图复核，确认：左上角品种/周期、右侧价格轴、底部副窗格。

**写文案时注意副窗格的真名**：本机布局底部是 `Volume Aggregated`（图例写作 `AggVol`）+ 成交量直方图，
没有单独标为 CVD 的窗格 —— 不要笼统声称「有独立 CVD 窗格」。

## 5. 完成度审计的典型形状

15 步路由、**完成 11/15**：TV 五层 / Binance 衍生品 / CVD / 深度 / 相关性 / 引擎 / 体制 / 双指标 / 高级订单流 / 风控 / 出卡 = ✅；
`CoinGecko Pro`、`宏观背景`、`X情绪`、`Cron缓存` = ⚠「本轮未采到有效字段」。

- 这四项多为「仅展示/辅助」源，不进裁决；如实写降级、不要把它们写成 15/15。
- `Cron缓存` 那行会逐源列出 `stale_cache` / `unavailable`（对应六个无采集调度的可选源），保留原样。
- 来源矩阵里应能看到 `风险快照` 一行显示 `stale_cache·<旧日期>·stale`，这是有意保留的可见降级，不是故障。
