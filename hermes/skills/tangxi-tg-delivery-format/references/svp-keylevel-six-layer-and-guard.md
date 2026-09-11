# SVP 完整关键位六层系统 + 通用化监测守卫（2026-08-28 实测）

> 用户纠正：**"还有图表上面的那些关键位呢，它不显示在磁吸位的。"** 磁吸↑/磁吸↓ 只是
> 指标加权筛出的最优 2 个，不是完整关键位集。推荐监测位必须读全套图表关键位。
> 本文档是 `svp-haldro-indicator-keylevel-recommendation.md` 的**补充/纠正版**，并记录
> 已落地的通用化监测守卫演进（从单品种硬编码 → 配置驱动多品种多顶点）。

## 一、SVP 关键位是七层系统（每层独立画在图上）

| 层 | 数据源 | 内容 |
|:--|:--|:--|
| ① SVP 价值区 | `data_get_study_values` + 轴标 | POC / nPOC / VAH / VAL / 日开盘DO / 周W-VWAP / 月M-VWAP |
| ② ICT 会话位 | `data_get_pine_labels` | 上周高/低、周四/周五/当日、亚/纽高低、前高前低 |
| ③ 结构位 BOS/CHoCH | `data_get_pine_tables` 行动格「结构」行 | `转空·CHoCH↓·等BOS·平衡·看VA边` |
| ④ FVG 缺口 | `data_get_pine_boxes`（`type FVG`） | top/bot/isBull/htfConf/qualityScore/touchCount |
| ⑤ OB/Breaker | `data_get_pine_boxes`（`type OBZone`） | top/bot/isBull/isBreaker/mitigated/htfConf |
| ⑥ HTF 共振位 | `htfFvgList`/`htfObList`（各 ≤4） | 顺高周期方向的 FVG/OB |
| ⑦ 磁吸位 | 行动格「磁吸↑/磁吸↓」 | ①②③ 加权筛出的最优 2 个 |

**五源齐读才是完整集**：`pine_lines`(全部水平线) + `pine_labels`(带名标注) + `pine_boxes`(FVG/OB) + `study_values`(价值区) + `pine_tables`(行动格磁吸/现位/路径)。只读磁吸会漏 FVG/OB/HTF 共振位/会话位。

### 核心类型定义（`SVP_ICT_VWAP_CVD_optimized.pine`）
- `type FVG` L2163：`box bx / line ce / label lb / float top / float bot / bool isBull / bool htfConf / int bornBar / float baseScore / float qualityScore / int touchCount / bool wasInside`
- `type OBZone` L2221：`box bx / label lb / float top / float bot / bool isBull / bool isBreaker / bool mitigated / bool htfConf / int breakerBar / int bornBar / float baseScore / float qualityScore / int touchCount / bool wasInside`
- ICT level 结构体（会话位）L1101-1119：`prevDayHigh/Low / prevWeekHigh/Low` 等。

### 磁吸位评分公式（`type FVG`/磁吸 段 L2460-2475）
```
distScore    = max(0, 100 - (距离/ATR)×20)
freshnessScore = max(0, 100 - 年龄/(30min))
prioScore    = priority×20
totalScore   = distScore×0.4 + freshnessScore×0.3 + prioScore×0.3 + 20(落HTF FVG内)
score        = min(round(totalScore), 100)
```

## 二、当前版指标源码位置（最新 · 现位路径压缩版）

- 主指标现位路径压缩版：`C:/Users/Administrator/AppData/Local/hermes/cache/documents/doc_bda776dc5b75_SVP主指标_现位路径压缩版_20260827.txt`（3442行，含「现位」「路径」行动格行 + `type FVG`/`type OBZone`）
- 副指标六行决策收敛版：`...doc_cb4621b34898_AggVol副指标_六行决策收敛版_20260827.txt`（529行，固定 6 行：信号/结论/流向/持仓/量能/操作；`S1支持多/S2支持空/S3冲突/S4降权/S0无效`）
- 旧生产版：`outputs/indicator-audit-20260710/{SVP_ICT_VWAP_CVD_optimized.pine, HALDRO_AggVol_optimized.pine}`

## 三、关键位六层分级采集器 `keylevels_collect.py`

一次读齐全套关键位并按角色分级，输出 `data/keylevels_candidates.json` + 打印候选表。

**读法**（`fetch_tv_mcp` stdio，与 btc_ref_levels_sync 同源）：
```python
from fetch_tv_mcp import (set_symbol, set_timeframe, get_ohlcv, get_study_values,
                          get_pine_lines, get_pine_labels, get_pine_boxes, get_pine_tables)
```
> ⚠ `fetch_tv_mcp.py` 原本**缺 `get_pine_boxes` 和 `get_pine_tables`**——需按 `get_pine_labels`
> 的写法补这两个 async 函数（`data_get_pine_boxes` / `data_get_pine_tables`，带 `study_filter`）。2026-08-28 已补。

**六层分级 → 候选表**：价值区(study_values) / 会话位(labels) / 结构位(boxes) / 磁吸位(action grid) / HTF磁吸(4h grid) / 现位+路径(action grid)。

**磁吸正则要匹配真实行动格文本**（这版不匹配会漏掉磁吸）：
```
磁吸↑ | ↑周五 伦 高 79864·2.1A·分56·66%
磁吸↓ | ↓nPOC 78390.1·2.1A·分47
# 正则（鲁棒版）
MAGNET_RE = re.compile(r"([↑↓]?)\s*([^\s·]+)\s*([0-9][0-9,]*\.?\d*)\s*(?:·|,)?\s*(\d+\.?\d*)?A?\s*分?(\d+)?\s*(?:·|,)?\s*(★HTF)?\s*(\d+)?%?")
```

**去重陷阱**：按 `round(price/100)` 去重会**吞掉与会话位同价的磁吸位**（磁吸81500 vs 会话·周五亚高81500）。必须**按层去重** `(layer, round(price/100))`，跨层保留——磁吸位自带评分价值，不能因同价被吞。

## 四、通用化监测守卫 `keylevel_guard.py`（取代单品种硬编码）

单品种 `btc_keylevel_rest_guard.py`（LEVELS 硬编码）已演进为 **配置驱动多品种多顶点**：

```python
# data/keylevels_config.json（唯一配置源，守护热读）
{
  "symbols": {
    "BTCUSDT": {
      "ws_price": "https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT",
      "levels": [
        {"name": "磁吸↑·周五伦高", "price": 79864, "note": "反抽短空位"},
        {"name": "磁吸↓·周五伦低", "price": 78400, "note": "企稳试多位"}
      ]
    }
  }
}
```
- `keylevel_guard.py`：`while True` 0.5s 轮询**所有品种所有顶点**，crossing 检测，穿越→写 `data/trigger_{symbol}.json`（含 level/price/dir/ts/cooldown_until），每 level 独立 30min 冷却。配置热读（加位/删位/加品种 **零重启**）。
- `keylevel_read_trigger.py`：cron 前置，读各品种 trigger 文件 → `TRIGGER symbol=... level=...` / `WAIT no-trigger`。
- `btc_keylevel_guard_watchdog.py`：心跳 >90s 自动杀旧+重启（需把脚本内 `btc_keylevel_rest_guard.py` 字符串改成 `keylevel_guard.py`，心跳文件改 `.keylevel_guard_heartbeat.json`）。

**「用户确认→写配置」是正确用法**：用户不报价格，安禾从六层候选分级推荐 → 用户勾选 → 写 `keylevels_config.json` → 守护实时盯。加位/删位/加品种 = 改配置即生效。

## 五、WS 不可用 → 本机用 REST 亚秒轮询（正面顺延，非"WS坏了"）

本机 `websockets`/`websocket-client` 连 `fstream.binance.com`：域名解析到不可达 IPv6（`2001::...`），Python 库代理隧道与 curl 不一致连不上，curl 能返回 101 但流式读帧不可靠。**结论：本机关键位提醒用方案 A（REST 0.5s 轮询，实测每次 ~0.35s 稳），别硬试 WS**。其它机器若 WS 通畅则优先 WS。WebSocket/streaming 是工具能力，环境不支持时选 REST 兜底，不是永久禁用 WS。
