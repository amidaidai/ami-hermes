# 双指标 → 分析卡 字段映射 v1.0

## 指标概览

| 指标 | 文件名 | 行数 | 核心功能 |
|------|--------|------|----------|
| 主指标 | `主指标.txt` (SVP+ICT+VWAP+EMA+CVD) | 3134 | SVP分布图·ICT关键位·VWAP/EMA·CVD·DMI决策·行动格 |
| 副指标 | `副指标.txt` (Volume Aggregated) | 425 | 聚合量·OI价仓·CVD流向·量能·爆仓·现货/永续占比·中文行动格 |

---

## 副指标 → 分析卡映射 (Volume中文行动格)

副指标的行动格位于源码 L286-420，在图表上以表格形式显示。

### 行动格字段 (table rows)

| 行动格行 | 源码变量 | 数据含义 | → 分析卡字段 | 推送卡 |
|----------|----------|----------|-------------|--------|
| 信号 | `signalA` | 🟢/🟡/🔴 + 偏多/偏空/无向 · X/4共振 | ①信号 | 首行方向+等级 |
| 结论 | `actText` | OI综合结论(实涨/衰竭/真跌/去杠杆/轧空顶/踩踏底) | ①结论 | ①行 |
| 高周 | `htfTxtA` | ▲偏多/▼偏空/·震荡 | ②高周 | — |
| 持仓 | `oiTxtA` | ▲新多进场/▼空头回补/▼新空进场/▲多头平仓 | ②OI | ②OI |
| 流向 | `cvdTxtA` | ▲买盘占优/▼卖盘占优/·均衡 | ②CVD | ②CVD |
| 量能 | `volTxtA` | ▲放量/▼缩量/·平量 + ⚠永续主导 | ②量能 | ②量能 |
| 占比 | `shareTxtA` | X%现 / Y%合 | ②占比 | — |
| 爆仓 | `liqTxtA` | 空头爆仓(轧空)/多头爆仓(踩踏)/无明显爆仓 | ②爆仓 | ⚠行 |
| 操作 | `comboTxt` | 配合主指标A多/空=可做 / 逆高周不追 / 等方向明朗 | ④操作 | ④行 |

### 核心判定逻辑 (源码 L309-373)

副指标的结论基于 OI + 价格 四象限判定：

| 价格方向 | OI变化 | 源码变量 | 结论 |
|----------|--------|----------|------|
| ↑涨 | OI↑ | `vGood` | 实涨可信 · 新钱+买盘 ✅ |
| ↑涨 | OI↓ | `vExh` | 上涨衰竭 · 空头回补 |
| ↑涨 | OI↑ CVD↓ | `vDiv` | 涨势存疑 · CVD不配 |
| ↓跌 | OI↑ | `vBad` | 真实下跌 · 新空进场 ✅ |
| ↓跌 | OI↓ | `vDelev` | 去杠杆 · 或超跌反弹 |
| ↓跌 | OI↓ OI↓ | `botExhaustA` | 踩踏杀跌 · 别追空 |

### 信号灯判定 (源码 L346-350)

4项确认: OI同向 + CVD同向 + 放量 + HTF同向 → 得分0-4
- ≥3且不缩量 → 🟢强信号
- =2或≥3但缩量 → 🟡中信号
- ≤1 → 🔴弱信号

---

## 主指标 → 分析卡映射 (DMI决策引擎+行动格)

### DMI 决策表数据

| TV表格字段 | 源码位置 | 数据含义 | → 分析卡字段 |
|-----------|----------|----------|-------------|
| 等级 | DMI引擎 | A多/A空/B多/B空/C反多/C反空/X/C等待 | 首行等级 |
| 处理 | DMI引擎 | 配合主指标A多/空=可做 | ④操作 |
| 背景 | DMI引擎 | 4h偏多/偏空/震荡 | ②高周 |
| 位置 | DMI引擎 | VWAP上方/下方/价值区内/外 | ③关键位 |
| 量能 | DMI引擎 | 放量/缩量 | ②量能 |
| CVD | DMI引擎 | 顺空/顺多/中性 | ②CVD |
| 执行 | DMI引擎 | 入场条件描述 | ④操作 |
| 风控 | DMI引擎 | 风险管理 | ⑤风控 |

### 行动格附加字段 (主指标图表右上角)

| 字段 | 含义 | → 分析卡 |
|------|------|----------|
| 方向 | 做多/做空/观望 | 首行 |
| 进场 | 入场价 | ④操作 |
| 止损 | 止损价 | ④操作 |
| 目标 | 磁吸上/磁吸下 | ④操作 |
| 磁吸上 | 上方磁吸目标 | ④止盈 |
| 磁吸下 | 下方磁吸目标 | ④止盈 |

### DMI 等级系统 (源码约L2450-2600)

| 等级 | 条件 | 含义 |
|------|------|------|
| A多 | trendLong≥8 + nearAKeyLevel + CVD顺多 | 强做多 |
| A空 | trendShort≥8 + nearAKeyLevel + CVD顺空 | 强做空 |
| B多 | trendLong≥6 + nearKeyLevel + CVD顺多 | 轻仓多 |
| B空 | trendShort≥6 + nearKeyLevel + CVD顺空 | 轻仓空 |
| C反多 | reversal≥7 + nearKeyLevel | 反转试探多 |
| C反空 | reversal≥7 + nearKeyLevel | 反转试探空 |
| C等待 | 不满足AB条件 | 等待 |
| X | 结构冲突/过热/ADR耗尽 | 禁做 |

---

## 技术指标数据 (study_values)

### 主指标 Data Window 输出

| TV Data Window字段 | 源码公式 | → 分析卡字段 |
|-------------------|----------|-------------|
| S VWAP | 会话VWAP计算 | ③VWAP |
| VAH | SVP价值区上沿 | ③VAH |
| VAL | SVP价值区下沿 | ③VAL |
| POC | 成交量最大价位 | ③POC |
| EMA 9 | EMA(close, 9) | ③EMA9 |
| EMA 21 | EMA(close, 21) | ③EMA21 |
| EMA 34 | EMA(close, 34) | ③EMA34 |
| EMA 55 | EMA(close, 55) | ③EMA55 |
| CVD Value | 会话CVD累值 | ②CVD值 |
| CVD Slope | CVD动能斜率 | ②CVD |
| Magnet+ICT+Score | Mag*1e6+DistA*1e3+Score/1e3+ICT/1e6 | 磁吸分析 |
| Scores | Loc*100+Cfm*10+Ext | 评分 |
| ICT Count | Swept*100+Active | ICT扫线 |
| Risk | R%*1e4+DailyStop%*1e2+WeeklyReduce% | 风控 |
| Replay Side+Grade | Side*10+Grade | 重放方向 |

### 编码字段解码公式

```python
# Magnet+ICT+Score
mag = int(val // 1e6)          # 磁吸价(整数部分)
dist_atr = int((val % 1e6) // 1e3) / 1000  # 距磁吸ATR
score_ict = val % 1e3                    # 小数部分(评分+ICT)

# Scores
loc = val // 100              # 位置评分 0-5
cfm = (val % 100) // 10       # 确认评分 0-5
ext = val % 10                 # 延展评分 0-5

# ICT Count
swept = val // 100            # 已扫线数
active = val % 100             # 活跃线数

# Replay Side+Grade
side = int(val // 10)          # 1多/-1空/9X/0无
grade = int(val % 10)           # 3A/2B/1C/-1X

# Risk
risk_pct = val // 10000        # 单笔风险%
daily_stop = (val % 10000) // 100  # 日止损%
weekly_reduce = val % 100       # 周减仓%
```

### 副指标 study_values

| 值 | 含义 |
|----|------|
| Spot (%) | 现货成交量占比 |
| Perp (%) | 永续成交量占比 |
| Delta | 主动买卖差 |
| MFI | 资金流量指数 |
| Liquidations | 爆仓量(过滤后) |
| OI (需单独加载) | 持仓量 |

---

## TV MCP 读取流程

```
1. chart_get_state → 确认品种和已加载研究
2. data_get_study_values → 获取所有指标数值
3. data_get_pine_tables → 获取主指标DMI表 + 副指标行动格
4. 解码Data Window编码字段
5. 传入 render_tv_card(main, sub) 渲染
```

---

## 简化卡格式速查

### Push推送卡 (6行)
```
↑做多 🔥A多 65,042 · VWAP 64,551 · 06-27 15:30
① 实涨可信 · 新钱+买盘
② ↑新多进场 · ↑买盘占优 · 放量
③ VAH 65,200 · VAL 63,800 · POC 64,550
④ 回调VWAP不破做多
```

### Full完整卡 (15行)
```
◷ 06-27 15:30 · BTCUSDT · 🔥A多

现价 `65,042` · VWAP `64,551`
↑ 做多 · 回调VWAP不破做多

① 信号
   偏多 · 3/4共振
   结论：实涨可信 · 新钱+买盘 ✅

② 证据
   OI  ↑新多进场
   CVD ↑买盘占优
   量  放量
   高周 ▲偏多

③ 关键位
   VAH `65,200` · VAL `63,800` · POC `64,550`

④ 操作
   回调VWAP不破做多 · 止损VAL下
   
⑤ 风控
   等级 A多 · 4h偏多 · 伦敦盘
```
