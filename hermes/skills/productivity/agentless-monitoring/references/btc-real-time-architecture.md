# BTC 实时分析系统架构

> 来自棠溪 BTC 交易系统的实战实现，适用于 VWAP/CVD/VA 框架的实时监控。

## 系统总图

```
┌────────────── 零 Token 采集层 ──────────────┐
│                                              │
│  btc_collector.py (1m cron, no_agent)        │
│  ├─ Binance: 价·OI·资金费率·多空比·Taker量   │
│  └─ 输出: data/btc_latest.json              │
│                                              │
│  btc_vwap_daemon.py (10s daemon, background) │
│  ├─ Binance 实时价 + 自算 15m VWAP           │
│  ├─ 检测: VWAP站回/破·VAL破/站回·VWAP反抽    │
│  ├─ 去重: 按 5min block 防重复               │
│  └─ 输出: data/btc_pending.txt              │
│                                              │
│  TV 截图 (5m cron, no_agent)                 │
│  └─ 输出: screenshots/btc_15m.png            │
│                                              │
└──────────────────┬───────────────────────────┘
                   │
┌────────────── LLM 分析层 (cron) ─────────────┐
│                                              │
│  [每1m] btc_push_cron.py → pending 有内容    │
│    就推 386 话题 (no_agent, 0 token)          │
│                                              │
│  [每15m KillZone] 完整 MTF 分析 → 压缩卡     │
│    + TV 截图 → 386 话题                       │
│                                              │
│  [8:30] 日间计划 → 416 话题                   │
│  [22:00] 复盘 → 416 话题                      │
│                                              │
└──────────────────────────────────────────────┘
```

## 关键价 - 指标映射

基于 SVP+ICT+VWAP+EMA+CVD 指标，数据源可靠，按 TD 线分层解读。

### 15m 执行层 (当前)

| 指标 | 公式/来源 | 用途 |
|:--|:--|:--|
| VWAP | 15m 量加权均价 | 多空分水岭 |
| ±1σ Band | VWAP ± 1stddev (`~$260`) | 超价执行区 |
| ±2σ Band | VWAP ± 2stddev (`~$520`) | 极限反转区 |
| EMA9/21/34/55 | 快/中/慢均线 | 多头排列=顺多, 空头排列=顺空 |
| CVD Value | Cumulative Delta | +值=买主控, -值=卖主控 |
| CVD Slope | Delta 变化速率 | 正加速=买盘增强, 负加速=卖盘增强 |
| POC | 15m 成交量最大价位 | 价格磁吸/阻力支撑转换 |
| VAH | 价值区域上沿 (70%) | 突破=多头强势 |
| VAL | 价值区域下沿 (70%) | 跌破=空头强势 |
| DO | 当日开盘 | 多空初始平衡位 |

### 4h 方向层

同样的指标但值完全不同：
- VWAP ±1σ 宽度 ~`$2,800`
- POC/VAH/VAL 覆盖更大价格区间
- CVD 值负 = 长期卖压仍存

### 1h 结构层

- 连接 4h（方向）和 15m（执行）
- 判断反弹通道/震荡区间/BOS 信号

## 事件分类规则

| 符号 | 条件 | 含义 |
|:--|:--|:--|
| 📊 VWAP反抽 | `0 < VWAP-价 ≤ $60` | 价回测 VWAP，看承压/突破 |
| 🟢 站回VWAP | 价 > VWAP | 空单失效信号 |
| 🔴 VWAP破位 | 价 < VWAP + CVD跟空 | 多单失效信号 |
| 🔴 破VAL | 价 < VA下沿 | 空头加速 |
| 🟡 站回VAL | 价 > VA下沿 (之前跌破) | 多头防守成功 |
| 🔴 破VAH | 价 > VA上沿 | 多头突破 |
| 📈 CVD背离 | 价新低 + CVD新高 | 买背离 = 反转信号 |
| 📉 CVD背离 | 价新高 + CVD新低 | 卖背离 = 反转信号 |
| 🔥 量能爆发 | 5m量 > 3倍均量 | 大资金进场 |

## 推送格式

### 预警推送 (pending→cron)

```
📊 BTC VWAP反抽测试 · 16:15
现价`64,268` · 距VWAP`64,235`上`$33`
看VWAP反应：承压空 / 突破多
---
🟢 BTC站回VWAP · 16:16
现价`64,314` · VWAP上`$79`
空单失效 · 结构转多可能
```

### 压缩分析卡 (LLM cron)

```
方向→关键位→现价数据→入场条件→核对清单→预案A/B
(6段 + 操作段完整①-⑦ + 截图)
```

### CCTV 卡 (完整)

```
10段头 + 5段正文 + 操作段①-⑦ + 截图
(走 xau-analysis-format 模板)
```

## 守护守护注意事项

- **daemon 不跨 Hermes 会话** — 重启后需手动检查并重启
- **pending 文件 daemon + cron 路径一致** — 都用 `os.path.expanduser("~/AppData/Local/hermes/data/")`
- **Windows taskkill** — `taskkill //PID <pid>` (双斜杠)
- **带时间的 block 去重** — `now.minute // 5` 做 5 分钟块防重复
- **VWAP 每分刷新** — daemon 每分钟重新从 Binance API 算一次 VWAP
- **多源数据** — 纯价格监控用公网 API，TV 指标用 TV MCP 截图采集
