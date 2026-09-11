# 作战室融合报告（多源融合）参考

把 5 大源的「单源信号」融合成【单资产总评分】，解决 11 个 collector 各自推送、无跨源融合的缺口（参照 signalsGURU 三阶段融合置信引擎）。

实现见 `scripts/signal_confluence.py`（已上线，cron `721d5b6e1c66` 每小时 :17 跑，Deliver=local，脚本内自推 846）+ `scripts/btc_levels_read.py`（结构位只读）。

## 融合源与权重（满分 10）

| 源 | 取数函数（纯函数，不调 main） | 权重 | 说明 |
|:---|:---|:---:|:---|
| Orion雷达 | `orion_screener_radar.fetch_orion("binance")` → `detect_anomalies` → `compute_confidence` | 0–10 直接取 | 本就含 OI/费率/主动买卖/跨所确认，作主基底 |
| QLib因子 | `qlib_factors.fetch_klines("BTCUSDT","1h",200)` → `compute_factors` | SIGNAL(-5~+5)→0~5 映射 | 动量/趋势/量能 |
| Deribit期权 | `deribit_options.fetch_options()` → `BTC.cp_ratio` | >1.5:+2 / <0.7:-2 / 中性:0 | 看涨需求/看跌保护 |
| X情绪FOMO | `x_sentiment_context.fetch_fear_greed()` | >75过热:-2 / <25恐慌:+2 / 中性:0 | 过热反向减分防追高 |
| 稳定币流向 | 自写轻量读 `data/stablecoin_snapshot.json` 差值 | 增量:+1 / 减量:-1 / 持平:0 | 资金面 |

## 评分公式

```
base = orion_conf                      # 0–10
adjust = sum(其余源权重)               # 上限约 +3（2+2-... +1）
score = clamp(0, 10, base + clamp(-3, 3, adjust))
```

verdict 分级：`≥7.5 高置信·可做多🟢` / `≥5.5 中置信·逢低轻仓🟡` / `≥4.0 低置信·观望⚪` / `<4.0 偏空·规避🔴`。

## 关键集成技巧（复用 collectors 不触发其推送）

新建融合脚本时**只 import 各 collector 的纯数据函数，绝不调 `main()`**——`main()` 内含副作用（打印 + 自推 TG），会双重推送且污染 stdout。安全函数清单：
- `orion_screener_radar`: `fetch_orion`, `detect_anomalies`, `cross_verify`, `compute_confidence`, `build_report`
- `qlib_factors`: `fetch_klines`, `compute_factors`
- `deribit_options`: `fetch_options`（返回 `{"BTC":{cp_ratio,...},"ETH":{...}}`）
- `x_sentiment_context`: `fetch_fear_greed`, `fetch_trending`, `fetch_global`
- 稳定币：不要 import `stablecoin_collector.main`（强耦合 + 副作用）。自写轻量读数：读 `data/stablecoin_snapshot.json` 当前总量，与 `data/stablecoin_prev.json` 比对得 `total_delta`，再把当前快照写入 prev 供下次比。

## 两个必须避开的坑

1. **`orion_screener_radar.compute_confidence(c)` 接受单候选 dict，不是 list。**
   误传 list 会报 `list indices must be integers or slices, not str`。正确：
   ```python
   cands = o.detect_anomalies(bn, "Binance")
   cands = [o.compute_confidence(c) for c in cands]   # 逐个，不是 cands 整体
   cands.sort(key=lambda c: c.get("confidence", 0), reverse=True)
   ```

2. **主品种必须锚定 BTCUSDT，不能取 Orion 的 top 候选。**
   Orion 选出的是「异动最强」品种（如 KAITOUSDC），但 QLib/Deribit/X情绪/稳定币都是 BTC 维度。若把 headline symbol 设为 KAITO，融合报告会变成「拿 BTC 维度数据评 KAITO 品种」的错位。固定 `symbol="BTCUSDT"`，Orion 只作动量贡献（`orion_detail` 里展示其 top 品种即可）。

## 实测样例（2026-7-8 20:38）

```
🎯 作战室融合 · 2026年7月8日20：38
| 源 | 信号 | 权重 | 状态 |
| Orion雷达 | KAITOUSDC 信4.5 | +4.5 | 🔸 |
| QLib因子 | 偏空 | +0.0 | 🔴 |
| Deribit期权 | C/P=1.80 | +2.0 | 🟢 |
| X情绪FOMO | FNG=20恐慌 | +2.0 | 🟢 |
| 稳定币流向 | 持平 | +0.0 | ⚪ |
**融合总评分**: ⭐`7.5`/10 · 🟢**高置信·可做多**
**总体结论**: 🟢高置信·可做多；共振源[Orion雷达,Deribit期权,X情绪FOMO]。
```

## cron 创建命令（新 collector 必用）

`hermes cron add` **不存在** → 正确是 `hermes cron create`：
```bash
hermes cron create "17 * * * *" --name "作战室融合信号" \
  --script "signal_confluence.py" --workdir "D:/Hermes agent" \
  --deliver local --no-agent
```
- `--no-agent`：脚本 stdout 直接投递，空 stdout 静默（watchdog 模式）。
- `--script` 相对 workdir 即可（同 BTC关键位同步那种 `btc_ref_levels_sync.py` 写法）。
- 验证：`hermes cron list` 看是否 [active] + Next run 时间正确。

## 执行计划段（用户说「全面的来/给具体价位」时必加）

方向结论不够——棠溪要的是**可直接下单**的参数。在融合总评分后追加执行计划段（实现见 `scripts/signal_confluence.py` v1.1 + `scripts/btc_levels_read.py`）。

- **结构位来源**：读 TV 缓存 `data/tv_dmi_cache.json`（最新鲜，秒级），取 POC/VWAP/VAL/VAH/DO/W-VWAP。`btc_levels_read.read_levels()` 按新鲜度自动选 `tv_dmi_cache.json → tv_live.json → btc_ref_levels.json`，零副作用（不触发 TV 刷新/推送）。
- **映射规则**（评分→具体价位）：
  - 评分≥5.5 → 🟢做多：入场①=VWAP、入场②=VAL(加仓)、止损=**VWAP×0.995**、目标=VAH→DO→W-VWAP。
  - 评分<4.0 → 🔴做空：入场=VAH、入场②=VWAP、止损=**VAH×1.005**、目标=VAL→POC。
  - 中间 → ⚪观望，不进场。
- **风险%**：高置信(≥7.5)1.5% / 中1% / 偏空0.5%（快进快出小仓，固定分数×体制乘数）。
- **盈亏比**：自动算 `max(目标-入场)/|入场-止损|` 的 R 值，附在表末。

### ⚠️ 两条不可妥协硬规则（用户 2026-7-8 明确下达，写入 SKILL.md）

1. **盈亏比必须 ≥2R，否则不发执行计划段。**
   - 达标（R:R≥2）才输出「执行计划」真表（方向/入场①②/**止损**/目标/风险%/盈亏比/现价/结构位新鲜度）。
   - 未达标（中间区 4–5.5 方向不清 / 结构位窄导致 R<2）**只发一行 `**分析**: …` 说明原因，绝不发入场/止损/目标表**。R 不够就憋着，不硬发凑数方案。
   - 用户原话：「盈亏比大于等于2，不允许小于」「不达到的暂时不发后面那一段方案执行计划」。

2. **执行计划必须带分析，不能只列数字。**
   - 达标时也要有 `**分析**: 方向逻辑（融合分+共振源）· 入场逻辑（为何此位进）· 风控逻辑（止损依据+风险%+盈亏比）` 三段式。
   - 未达标时 `**分析**:` 说明「结构位不支持≥2R（当前测算X.XR），暂不发执行计划，等结构收敛/回踩确认后再评估」。

### 让盈亏比达 ≥2R 的关键技术（致命细节）

**止损必须紧贴入场（0.5% 夹层），不能设在 VAL/VAH 外。**
- 初版用 `止损 = VAL×0.995`（做多），结果 R = |VWAP−VAL×0.995| 被撑到 ~1195，而目标 VAH 距 VWAP 仅 843 → 盈亏比 0.7–1.2R，**被用户否决**。
- 改成 `止损 = VWAP×0.995`（入场本身下方 0.5%）后，R 缩小到 ~309，目标 VAH(距843)→2.7R、DO(距1418)→4.6R，**达标**。
- 做空镜像：`止损 = VAH×1.005`。

### DATA_DIR 路径坑（2026-7-8 实测）

`signal_confluence.py` 初版把 `DATA_DIR` 设成 `os.path.expanduser("~/AppData/Local/hermes/data")`，但 TV 缓存（tv_dmi_cache.json 等）实际在 **`D:/Hermes agent/data`**。两目录都有同名旧文件 → 读到 9 天前的结构位（BTC 在 59k）+ 新鲜度 12845min，价位全错。

**修复**：所有棠溪脚本读取 TV 缓存/数据 JSON 的 `DATA_DIR` 必须用 `REPO / "data"`（`REPO = Path("D:/Hermes agent")`），**不是** `~/AppData/Local/hermes/data`。两目录差异需在每次新建/改造脚本时核对。

### 实测样例（v1.1 含执行计划，2026-7-8 21:06，达标 4.6R）

```
| 执行计划 | 价位/参数 |
|:----|:----:|
| 方向 | 🟢做多 |
| 入场① | `61,917` (VWAP) |
| 入场② | `61,027` (VAL加仓) |
| **止损** | `61,608` |
| 目标 | `62,760` / `63,335` / `63,167` |
| 风险% | **1.5%** (1R) |
| 盈亏比 | **4.6R** |
| 现价 | `61,848` |
| 结构位新鲜度 | 11.5min |

**分析**: 方向逻辑：🟢做多（融合7.5/10，共振源[Orion雷达,Deribit期权,X情绪FOMO]）。入场逻辑：回踩VWAP接多，VAL加仓；现价在VAH上方属突破区，等回踩确认再进。风控逻辑：VWAP下方0.5%（夹层止损，破位即结构失效），风险1.5%/1R，盈亏比4.6R。
```

### 未达标样例（评分中间区，只发分析不发方案）

```
**分析**: 融合评分中间区(4-5.5)，方向不清，不发方案
```

## 后续演进（已规划未做）

- **P1 信号自验证回测**：cron 每日把昨日 Orion 候选与实际 4h 后价格比对，算各置信档 win rate 存 JSON，每月出「信号质量」表推 TG。
- **P2 交互命令 bot**：`/btc /orion /xau /status` 按需触发（执行计划已内嵌，命令 bot 是锦上添花，排最后）。

## 从重型引擎抽取轻量验证器（auto_card 融合案例，2026-7-8 已上线）

用户有独立分析引擎 `scripts/auto_card.py`（4200 行全量分析卡，依赖几十个采集器、单次运行分钟级）。**不要整吞 import**——会拖垮作战室 hourly cron。正确做法：**只抽取它的核心验证逻辑，做成独立轻量验证脚本**。

实现：`scripts/signal_validators.py`（已上线），从 auto_card 抽两类闸门：
- 🔍 **多空比反指** `long_short_contra()`：Binance `/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=5m&limit=1` → long/short 账户比。ratio≥2.0→散户拥挤多(反向警惕顶)；≤0.5→拥挤空(警惕底)；否则中性。轻量 API，秒级。
- 🔍 **周期一致性** `tf_alignment()`：Binance K线 4h/1h/15m 各自 `收盘 vs 开盘`（±0.05% 阈值判方向）→ 相邻周期 `d4×d1==-1` 或 `d1×d15==-1` 即**周期冲突硬门**（呼应 auto_card ④周期冲突）。不依赖 TV/SVP 重管线。

`validate_plan(symbol, side)` 综合两道闸门：任一否决 → 作战室 `compute_plan` 的 `qualified=False` → **不发执行计划**（与 auto_card 周期冲突硬门同效）。

### 抽取模式（可复用于其他重型引擎）

1. **识别要复用的"验证逻辑"而非"整个引擎"**：auto_card 要的是它的「多空比反指 + 周期冲突」判定，不是它 4200 行的采集/渲染。
2. **独立取数**：验证器自己调轻量 API（Binance 多空比 / K线），不 import 引擎的重采集环节。
3. **做双闸**：源表里加 🔍 维度**展示**（让用户看到验证状态），`compute_plan` 里加**硬门**（否决则不发方案）。
4. **触发时机**：用户说「有计划了就要用上能力多方面验证是不是支持」时，把已有分析/引擎的独立验证环节融进来当质检员。

### 实测样例（验证闸门通过，2026-7-8 21:19）

```
| 🔍多空比反指 | 正常(1.74) | +0.0 | 🟢 |
| 🔍周期一致性 | 4h空/1h空/15m空 · 同向 | +0.0 | 🟢 |
**分析**: ...独立验证：多空比1.74(正常)；4h空/1h空/15m空·同向。
```

否决路径（模拟周期冲突 4h多/1h空）：`qualified=False`，分析行「周期冲突→方向矛盾不交易」，执行计划段被抑制。
