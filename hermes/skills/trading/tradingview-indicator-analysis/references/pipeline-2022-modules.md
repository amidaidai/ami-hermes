# 2022模型管线模块 — FVG/OB/评分/日历/复盘

2026-06-22 会话产出。6个独立模块 + 1个集成器 + 1个管线守护，串联为全自动高胜率入场流程。

## 架构总览

```
btc_vwap_daemon.py (v12守护,10s轮询)
    │ 实时价/CVD/扫荡/多空比/Taker
    │
    └── btc_pipeline_daemon.py (每3分钟)
            │
            ├── fvg_detector.py ─── 三烛不重叠FVG
            ├── order_block.py ──── 机构OB识别
            ├── pipeline_2022.py ── Sweep→Displacement→FVG→Retest→Entry
            ├── scoring_engine_v2.py ── 14因子汇聚评分(3+信号=高概率)
            ├── event_calendar.py ──── Jin10日历+30min阻塞
            ├── auto_review.py ─────── 信号→结果→胜率统计
            │
            └── pipeline_integration.py ─ 全流程串联→btc_pending.txt
                      │
                      └── tv_screenshot.py ─ 高概率时截图
```

## 模块详情

### fvg_detector.py
**三烛不重叠FVG检测。** 输入: kline[OHLCV]列表

- **牛市FVG**: candle1.high < candle3.low (跳空向上)
- **熊市FVG**: candle1.low > candle3.high (跳空向下)
- 返回: [{type, top, bottom, midpoint, gap_size, confirmed, status}]
- `update_fvg_status()`: 回测/扩散/填充状态
- `best_fvg()`: 取最大间隙的活跃FVG

### order_block.py
**机构Order Block识别。** 输入: kline[OHLCV]列表

- **牛市OB**: 前一根(小实体)最低价区，紧跟强阳线(实体>0.3%, 放量>1.5x)
- **熊市OB**: 前一根(小实体)最高价区，紧跟强阴线(实体>0.3%, 放量>1.5x)
- 强度: 1-5(基于位移百分比)
- 去重: $10内取最强
- `nearest_ob()`: 最近OB(可指定方向)

### pipeline_2022.py
**2022 ICT/SMC 模型管线核心。** 社区验证的高胜率流程:

```
Step 1  detect_sweep()      — 价格突破关键位(VAH/VAL/VWAP/POC)后回收
Step 2  detect_displacement() — 扫荡后5根内强势移动(实体>0.3% + 放量>1.3x)
Step 3  FVG形成              — 位移后自动检测是否形成FVG
Step 4  check_retest()       — 价格回测FVG 50%线
Step 5  Entry                — 回测确认=入场就绪
```

确认数=3+得分≥5=高概率信号。`run_pipeline(klines, levels, price)` 返回全状态。

### scoring_engine_v2.py
**14因子多信号汇聚评分(0-22分)。** 读取btc_signals.json+latest+tv_data。

| 因子 | 权重 | 触发条件 |
|------|------|----------|
| CVD背离 | 2 | 价格vsCVD方向相反 |
| VWAP测试 | 2 | ≤$60(1分)·≤$20(2分) |
| 流动性扫荡 | 2 | 破位+30s回收 |
| FVG缺口 | 1 | 存在活跃FVG |
| 银弹窗口 | 1 | 23:00-00:00 NY AM |
| KillZone | 1 | 亚洲/伦敦/纽约时段 |
| 折溢价区 | 1 | 方向匹配(溢价空/折价多) |
| 多空比极端 | 2 | LS>1.8或<0.55 |
| Taker翻转 | 2 | Taker偏极+价格同向 |
| CVD吸收 | 2 | CVD波动>150+价波动<$30 |
| 量能爆发 | 2 | 量变>50%(1分)·>100%(2分) |
| OB支撑/阻力 | 1 | 最近OB在$20内 |
| EMA交叉 | 1 | 9/21死叉/金叉 |
| 三源一致 | 2 | TV+价格+量方向同 |

- 总分≥8 + ≥3活跃信号 = `high_probability`
- 所有dict字段用 `_safe_dict()` 防bool/None崩溃

### event_calendar.py
**事件日历阻塞。** 使用Jin10公开API获取财经日历。

- `fetch_calendar()`: CDN免费接口
- `is_blocked()`: 检测重大事件(FOMC/NFP/CPI/PPI/利率决议)前30min
- `next_event()`: 最近事件信息
- `get_block_status()`: 完整状态(blocked/reason/next_event)

### auto_review.py
**自动复盘闭环。** 读取trade_journal.csv/json。

- `analyze_trades()`: 总计/胜率/总R/期望值，按信号类型、按日统计
- `review_today()`: 今日复盘
- `review_week()`: 本周复盘
- `recommend_improvements()`: 基于数据建议调整权重(需≥5笔样本)
- `report_full()`: 完整报告

### pipeline_integration.py
**全流程串联器。** `run_full_pipeline(klines)` 串接全部模块。

1. 读取 Binance 15m K线
2. 构建关键位字典(VAH/VAL/POC/VWAP)
3. 运行 pipeline_2022 (扫荡→位移→FVG)
4. 运行 fvg_detector (额外FVG检测)
5. 运行 order_block (OB检测)
6. 运行 scoring_engine_v2 (14因子评分)
7. 运行 event_calendar (事件阻塞)
8. 生成分析卡 → 写入 pending + signals 文件
9. 自动触发 TV 截图(仅高概率时)

### btc_pipeline_daemon.py
**管线守护(每3分钟)。** 独立于10s vwap_daemon运行。

- PIPELINE_INTERVAL=180s
- SCREENSHOT_INTERVAL=300s(仅活跃信号)
- 首轮立即触发(ONESHOT_TRIGGER=True)
- 写入 `btc_pipeline_state.json` 状态文件
- 高概率信号 → ⭐ 推送 + 自动截图

## 集成方式

```python
# 调用全流程
from pipeline_integration import run_full_pipeline
klines = fetch_binance_klines()
result = run_full_pipeline(klines)
print(result["analysis_card"])

# 调用单个模块
from fvg_detector import detect_fvg
fvgs = detect_fvg(klines)
```

## 注意事项

- fvg_detector/order_block 作为 `pipeline_2022` 的内部依赖导入，`FVG_AVAILABLE` 标志控制降级
- scoring_engine_v2 需要读 btc_signals.json / btc_latest.json / btc_tv_data.json 的数据桥输出
- event_calendar 的 Jin10 MCP 调用可能超时，回退到 HTTP 公开API
- 所有模块有 `if __name__ == "__main__"` 独立测试入口
