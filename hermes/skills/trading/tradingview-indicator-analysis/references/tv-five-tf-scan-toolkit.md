# TV 五周期扫描工具包（一次终端调用取全五层）

用途：把「逐个发 MCP 调用读五个周期」压成**一次 `terminal` 调用**，并自带已验证的解析器，避免行动格被误解析成空表。三个脚本均在 `scripts/`，任何品种通用（`BINANCE:BTCUSDT.P`、`OANDA:XAUUSD`、股票代码同样传）。

## 三个脚本

| 脚本 | 作用 | 典型命令 |
|:---|:---|:---|
| `scripts/tv_full_scan.py` | 五层全量：1D/4h/1h/15m/5m × (study_values + 主格 pine_tables + 副格 pine_tables + OHLCV summary + labels + lines + boxes) | `python scripts/tv_full_scan.py BINANCE:BTCUSDT.P` |
| `scripts/binance_deriv_bundle.py` | 衍生品方向票一次取齐：24h / OI 现值与 15m 历史 / 费率 / 大户·全局多空比 / Taker / 现货前20档 Depth | `python scripts/binance_deriv_bundle.py BTCUSDT` |
| `scripts/tv_shot.py` | 切品种→切周期→等指标重算→`ui_fullscreen`→`capture_screenshot(region="full")`，返回 PNG 路径 | `python scripts/tv_shot.py BINANCE:BTCUSDT.P 15 --wait 22` |

- `tv_full_scan.py --tfs 5,15` 只扫指定周期（等待自动降到 8s），用于单周期复核（例如总线一致性复读）。
- 两个 TV 脚本通过 `fetch_tv_mcp.py` 的 stdio MCP 客户端直连（复用 `set_symbol` / `set_timeframe` / `call_tool` / `parse_result`），**不走 Hermes MCP 工具层**，因此不受「一次 `tool_call` 只能带一个本地工具条目」限制，也不消耗 MCP 往返轮次（5 层 × 5 类读取从 20+ 轮降为 1 轮）。
- 结果落盘 `outputs/tv_scan_<ticker>_<时间>.json` + 同名 `.txt` 摘要（输出过长时读文件，不重发非法请求）。
- 脚本内置切图去冗余（已是目标 symbol/周期则跳过重绘），末尾打印「图表切换 品种(实切n/跳过n) 周期(实切n/跳过n)」，可用于确认没有多余重绘。
- ⚠ 脚本只是采集器：它不替代「读图」。仍需 `tv_shot.py` 截 full 图并把 K 线形态/CVD 窗格当一级证据（图表优先读图铁律），行动格表格只做交叉。

## 标准用法（加密/黄金多周期分析的 TV 步骤）

1. `python scripts/tv_analysis_lease.py start --minutes 10 --symbol BINANCE:BTCUSDT.P` —— 先声明租约，防后台续航任务中途切走图表（否则行动格会读成空）。
2. `tv_health_check` 确认 `cdp_connected`、`api_available`。
3. `python scripts/tv_full_scan.py <SYMBOL>` 取五层；`python scripts/binance_deriv_bundle.py <SYMBOL>` 取衍生品。
4. `python scripts/tv_shot.py <SYMBOL> <主周期>` 复核主周期并截图（切周期后指标需 15-30s 重算，`--wait` 给足）。
5. `python scripts/tv_analysis_lease.py end`（忘了也会自然过期）。

## 解析契约（必须遵守，否则静默丢行动格）

`data_get_pine_tables` 返回结构：

```json
{"success": true, "study_count": 1,
 "studies": [{"name": "SVP+ICT+VWAP+CVD",
   "tables": [{"rows": ["位置 | 价在VA内·…", "结论 | 副S3冲突·不执行", "方向 | 观望 · 走弱·平衡", …]}]}]}
```

- **`rows` 是字符串数组**，每行形如 `"行名 | 值"`，**不是** `{cells:[…]}` / `{label,value}` 对象。按对象取值的解析器会**静默返回空表且不报错**，卡面于是出现「主格(空) 副格(空)」——行动格是唯一文字真理源，丢了等于整卡失去依据。
- 正确解析：遍历 `studies[].tables[]`，每行 `partition("|")` → 键去空格、值去空格。
- **自检**：主格必须能取到 13 行（位置/结论/方向/路径/风控/CVD/OI/协同/结构/磁吸↑/磁吸↓/前位/现位），副格必须能取到 信号/结论/流向/持仓/量能/操作。行数明显不足 = 解析错了，**不是**指标未渲染；`chart_get_state` 能看到指标在挂时更应如此判断。

## 主副总线一致性（S-code 校验）

- 主指标「协同」行的 S-code 必须等于副指标「信号」行的 S-code（如主 `副S3冲突·高周空` ↔ 副 `🔴 S3冲突·2/4·OI背离`）。
- **读到不一致时先复读一次再下结论**：未收线的那根柱会造成瞬时错位。实测同一轮扫描 5m 出现主格 `副S4降权` vs 副格 `S3冲突`，同周期复读即恢复一致——这是时序伪影，不是总线断。
- 只有 ①复读后仍不一致，或 ②主指标显示 `副S0未接` / `OI未接` 而副指标照常有值，才是真断（切品种会让主指标重新实例化、指向副指标的 `input.source` 引用回退成 `close`）。此时不得引用副指标的确认/否决结论、不得判 A 级，并在卡面写明。

## 数据面注意

- `binance_deriv_bundle.py` 用「代理 127.0.0.1:7897 → 直连」双策略，`_src` 字段逐项标 live/fail；卡面直接引用 `_src` 说明哪一路降级。
- OI 变化用 `futures/data/openInterestHist?period=15m&limit=17`：末两根算 15m 变化、首尾算 4h 变化；副指标给的 `OI Change %` 是归一化值，两者量级不同，不要混进同一句话。
- Depth 用现货 `api/v3/depth`（前 5 档名义额与买卖比）。
- 采集完成后如出现 `chart_get_state` 的周期与预期不符（auto_card / 其他任务会切图），截图前必须用 `tv_shot.py` 重新切回主周期并校验 `resolution`。
