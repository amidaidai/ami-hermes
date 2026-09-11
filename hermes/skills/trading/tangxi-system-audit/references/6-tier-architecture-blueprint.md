# 棠溪 6层实时分析架构 · 社区对标蓝图

> 历史记录（2026-08-31）：旧版架构蓝图；当前运行入口以仓库实际代码和 cron 为准。

对标 `realtime-trading-pipeline` 技能标称的 6 层架构。每层必须全部存活。

## 架构图

```
T1: Data Collection (1m, no_agent)
├── btc_collector.py → Binance REST → btc_latest.json
│   字段: price·vwap·vol24·oi·funding·ls_ratio·taker_ratio
│   自愈: price缺失→ fapi markPrice fallback→ None标记
└── Cron: * * * * * · deliver=local

T1.5: TV Data Bridge (2m, no_agent)
├── tv_fetch_bridge.py → Node CDP → fetch_tv_data.cjs
│   → btc_tv_data.json + XAUUSD_tv_data.json
│   字段: vwap·vah·val·poc·ema9/21/34/55·cvd·cvd_slope
│   守卫: 抓前强制切 BINANCE:BTCUSDT.P · 校验active symbol
└── Cron: */2 8-23 * * * · deliver=local

T2: Fast Sub-Minute Daemon (10s, bg process) ★新增v3.2
├── btc_fast_daemon.py → 10s轮询 · 轻量· sub-minute
│   检测: CVD背离(24周期HH/LH)·扫荡(30s VA/VAH回收)·吸收(18周期)
│   输出→ btc_pending.txt (共享push管道)
│   冷却: 5min同事件·启动前8轮预热抑制
└── Process: terminal(background=true) · PID检查

T2.5: Multi-Factor Alert (1m, no_agent)
├── btc_alert_watch_v3.py → 14维检测+Confluence评级
│   新增v3.2: CVD趋势线破(LEADING信号)
│   输出→ btc_pending.txt (方向标注↑↓○·★A+标记)
└── Cron: * * * * * · deliver=local

T3: Alert Push (1m, no_agent)
├── btc_push_cron.py → 读pending·方向标注·分段发送
│   目标→ Telegram:386 · 格式: ↑↓○+模型+理由(conf:XX%)
│   成功后清空pending · 失败仅ASCII stderr
└── Cron: * * * * * · deliver=telegram:-1003733144325:386

T4: MTF Analysis (15m, LLM)
├── BTC MTF分析 cron → 读数据文件+TV MCP
│   输出: 多时间框架分析+TV截图 → Telegram origin
└── Cron: */15 8-23 * * * · toolsets: terminal+file+vision+web+search

T4.5: Event Analysis (2m, LLM)
├── BTC高胜率事件 cron → 读priority文件
│   输出: 深度分析卡 ★事件驱动
└── Cron: */2 8-23 * * * · toolsets: terminal+file+vision+search+web

T5: Risk Management (passive + active)
├── Protections: protections_state.json (StoplossGuard·Cooldown·MaxDrawdown)
├── 风控宪法: risk_constitution.py (1% max·Kelly 0.20·ATR夹层)
├── 余额守卫: data_gatherer.py → signed_futures(/fapi/v2/account)
└── 连亏追踪: auto_card.py → _consecutive_losses() → ≥3半仓·≥5暂停
```

## 审计验证命令

```bash
# T1: 数据采集
cat ~/AppData/Local/hermes/data/btc_latest.json | python -c "import json,sys; d=json.load(sys.stdin); print('price' in d, d.get('price'))"

# T1.5: TV桥
cat ~/AppData/Local/hermes/data/btc_tv_data.json | python -c "import json,sys; d=json.load(sys.stdin); print('vwap' in d, d.get('vwap'))"

# T2: 守护进程
tasklist //FI "IMAGENAME eq python.exe" //V | findstr "fast_daemon"

# T2.5: 告警器
python D:/Hermes\ agent/scripts/btc_alert_watch_v3.py 2>&1

# T3: 推送
cat ~/AppData/Local/hermes/data/btc_pending.txt | wc -l

# T4/4.5: LLM cron
hermes cron list | grep -E "BTC MTF|BTC高胜率"

# T5: 风控
cat ~/AppData/Local/hermes/data/protections_state.json
```

## 常见恢复步骤

### T2 守护挂了
```bash
taskkill //F //IM python.exe //FI "WINDOWTITLE eq fast_daemon*"
python D:/Hermes\ agent/scripts/btc_fast_daemon.py &
```

### Protections 未初始化
```bash
python -c "
import json; from pathlib import Path
state = {'last_reset':'','stoploss_guard':{'count':0,'last_trigger':None},
         'cooldown':{'count':0,'last_loss':None},'max_drawdown':{'daily':0,'weekly':0},
         'loss_streak':0,'risk_multiplier':1.0}
Path.home().joinpath('AppData/Local/hermes/data/protections_state.json').parent.mkdir(parents=True,exist_ok=True)
Path.home().joinpath('AppData/Local/hermes/data/protections_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2))
"
```
