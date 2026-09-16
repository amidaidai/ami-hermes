# 完整档手工跑管线（四步以上采集一次跑通）

适用于用户说了「分析 / 深度 / 完整卡」= **L3 完整档** 的加密与黄金请求。TV 与衍生品的具体脚本参数见 `references/tv-five-tf-scan-toolkit.md`；本文件只管「整条管线怎么按顺序跑完、哪些结论不能信」。

## 0. 定档与选品种（先定这两件，再动工具）

- **关键词优先于无上下文降级**：「分析 / 深度 / 完整卡」是硬开关。哪怕会话刚开头、上下文为空，只要话里带这些词就走完整档——不要因为「没有上下文」把它降成轻量档。
- **没给品种时默认 BTC**（主战场）直接开跑，出卡后在卡尾问一句要不要接着出 XAU。**不要先反问品种再停下等回复**——那等于让用户把同一条指令说两遍。
- 档位与步数的唯一权威仍是 `scripts/pipeline_router.py`；跑前先复算：
  ```
  python -c "import sys;sys.path.insert(0,'scripts');import pipeline_router as r;print(r.route_pipeline('BTCUSDT','full'));print(r.tier_table())"
  ```

## 1. 执行序列（整轮 4-6 分钟）

1. `python scripts/tv_analysis_lease.py start --minutes 12 --symbol <SYMBOL>` —— 防后台续航中途切图（漏了这步行动格会读成空表）。
2. `tool_call('mcp__tradingview__tv_health_check')` —— 确认 `cdp_connected` / `api_available`，顺手看 `chart_symbol` 是否已是目标品种。
3. `python scripts/binance_deriv_bundle.py <TICKER>` —— 方向票一次取齐，`_src` 逐项标 live/fail。
4. `python scripts/tv_full_scan.py <SYMBOL>` —— 五层 study_values + 主/副行动格 + OHLCV + labels/lines/boxes。
5. `python scripts/macro_filter.py`（DXY/VIX/SPX + risk_on/off）· `python scripts/correlation_matrix.py`（首行给黄金腿来源与偏差）。
6. 引擎步：**直接调单个引擎**，不要用 `engine_orchestrator.py` —— 它的适配器已陈旧（报 `scoring_engine has no attribute score_all` / `risk_constitution has no attribute evaluate`），只当健康检查打印，不当数据源。
7. 闸门步：`timeout 420 python scripts/auto_card.py <SYMBOL> > outputs/autocard_<sym>.txt`，只取它的 **GO/NO-GO、Protections、risk_constitution 违规项、①周期体温行**（这几项手工拼不出来），**不要把它当完整卡直接输出**。
8. `python scripts/tv_shot.py <SYMBOL> <主周期> --wait 20` —— 上一步 `tv_full_scan` 会把图表停在最后一个周期上，**截图前必须切回主周期**。
9. `python scripts/tv_analysis_lease.py end`。

每步失败都写进卡尾完整性备注，不静默跳过。

## 2. `auto_card.py` 的档位陷阱

**`auto_card.py` 不带模式参数时默认走轻量 3 步**（`tv → binance → card`），它没有 full 开关。所以：完整档**不能**指望 auto_card 一把出全管线 —— 它是「闸门 + 体检」，不是完整卡执行器。用它的输出做这几件事：

| 可用的 | 不可用的 |
|:---|:---|
| GO/NO-GO 红绿灯与硬闸门名 | 完整五周期定位（它只跑 3 步） |
| Protections 是否拦截 + 快照新鲜度 | 宏观/事件/x_sent/相关性（轻量档直接跳过） |
| `risk_constitution` 违规明细（如「R:R 0.8:1 不合格」「仓位 4.4% > 3% 上限」） | 当作用户可见的最终卡 |
| 「①周期体温」五行方向串（可补单周期主格缺失，见 toolkit） | — |

## 3. 数据面保真铁律（照抄会出错的地方）

| 陷阱 | 机制 | 处理 |
|:---|:---|:---|
| cron 落盘文件新、内层数值旧 | `data/x_sentiment_context.json` 的 mtime 是当轮，但其中 `market_snapshot[].price` 可能是早前缓存（与现价差上万刀） | **价格只认 Binance / TV**，永不引用该字段；`cron_read` 标 ⚠「内层快照陈旧」 |
| 引擎自带陈旧情绪 | `scoring_engine.py` 的结论与 recommendation 会引用过期恐慌贪婪（报「极度恐惧 15」而实时 F&G=51） | 引擎结论只作交叉参考，必须与实时 F&G / x_search 对照；矛盾时该步标 ⚠，**不引用它的 grade 与推荐语** |
| 清算/逐笔流停更 | 逐笔规模源可能已数十分钟无新事件（卡面标注「疑似停更」），但缓存文件本身仍新鲜 | 该源标 ⚠ 并写明「最新事件 N 分钟前」；**清算只作人工观察，不参与执行授权** |
| 风险快照陈旧 | Protections 读到的快照可能是数周前 | 标 `stale_cache` 可见降级，**不硬拦截**，也不当成「实时风控」引用 |

## 4. 窗口内高星事件 = 硬闸门

完整档必查金十日历（`mcp__jin10__list_calendar`）里**未来数小时**的高星事件：

- 5 星事件（FOMC 利率决定 / CPI / NFP 等）落在交易窗口内 → 裁决只能写「**等待/不宜**」，触发行**点名事件与北京时间**，**不给执行三件套**（B 等待卡本来就严禁给入场/止损/止盈价）。
- 这类情况同时满足用户定的 MoA 复核条件（critical 级宏观事件），可在卡尾提示可 `/moa` 深度复核；MoA 只给反方视角，无执行权。
- 事件前不改主线程结论：现价卡在 VWAP/POC 上、主副不共振时，事件只是把「观察」钉死为「不入场」，不是新方向的理由。

## 5. 卡面落点

- MEDIA 截图首行；截图路径尽量拷到无空格路径再引（仓库根目录名带空格，MEDIA 行容易断）。
- 只有 `GO-A + executable + R:R ≥ 2` 才给执行三件套；其余等级清空候选价。
- 五周期表里任何一层都不许因为主格没渲染而删除 —— 用体温行补位并标 ⚠。
