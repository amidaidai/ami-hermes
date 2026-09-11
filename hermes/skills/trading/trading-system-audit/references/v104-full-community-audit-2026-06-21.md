# v10.4 全面联网社区审计（2026-06-21 · 本会话）

◷ 2026-06-21 21:36 · `d8798ba` → `ca0a417` pushed

## 六大社区联网扫描

| 源 | 搜索 | 新发现 |
|---|------|--------|
| **X/Twitter ICT/SMC** | `x_search` | CVD趋势线突破是LEADING信号（早于价格2-5根K线）· SMT背离确认 · 动态回撤降级是2026机构共识 |
| **Reddit r/algotrading** | `web_search` | 回撤控制 > 胜率优化 · 固定分数1% + 动态降级 = 机构标准 |
| **Freqtrade** | `web_search` | Protections三层 ✅ 已对齐 |
| **NautilusTrader** | `web_search` | Pre-trade风险闸门 ✅ 宪法覆盖 |
| **Bookmap** | `web_extract` | 冰山水吸收→Stop Run → 框架已有·缺MBO数据 |
| **TradingView Pine v6** | `web_extract` | Footprint API → 需Premium/Ultimate |

## P0 系统发现

### Watchdog 重启风暴
- **根因链**: Discord推送100%超时（hermes_cli timeout 6s×2=14s）→ 阻塞worker线程 → 主循环累积超时 → 心跳停滞 >90s → watchdog误判卡死强杀 → 速率限制触顶 → 全停
- **修复**: 清冷却 `watchdog_guard.json` · Discord已从系统完全清除
- **状态**: 当前稳定（周末XAU闭市静默）

### Discord清除
- 系统零残留：config/skills/cron/scripts/全部扫描
- `send_message` 列表仅剩 Telegram + 飞书

### TradingView
- 路径: `C:\Program Files\WindowsApps\TradingView.Desktop_3.2.0.7916_x64`
- MCP服务器离线 → CDP无法连接

## P1 核心修复

### CVD趋势线突破检测（`orderflow_absorption.py` +123行）
- `detect_cvd_trendline_break(cvd_series, window=20)` — 线性回归拟合趋势线
- 跌破/突破方向 + 信号 + 置信0-90
- 社区共识：CVD趋势转变早于价格结构转变（LEADING信号）

### 动态回撤降级（`risk_constitution.py` +122行）
- `dynamic_drawdown_scaling()` — 5级渐进降险
- `combined_risk_check()` — 三层组合：回撤降级 × 波动率自适应 × 硬上限(10U)
- 社区共识值：
  ```
  DD<5%  → full   (1.0×)
  DD≥5%  → reduced(0.75×)
  DD≥8%  → half   (0.50×)
  DD≥12% → quarter(0.25×)
  DD≥15% → micro  (0.10×)
  DD≥20% → paused (0×)
  ```

### Cron优化
- 4个cron话题统一 → `telegram:-1003733144325:416`
- `持仓与信号.py` v1.3: 有变化才输出·静默零刷屏
- `tv_signal_monitor_wrapper.py` v1.1: 零输出·内部已推Telegram

## 社区共识对照（更新后）

**🟢 已对齐 15项**: CVD背离 · Liquidity Sweep · ATR夹层 · 日/周硬限 · 时间止损 · 分批止盈 · Protections · CVD+Taker+Funding · Kill Zone · 1%仓位 · 相关性矩阵 · 48h就绪 · 三层架构 · CVD趋势线突破 · 动态回撤降级

**🟡 差距 3项**: Walk-Forward产出 · 蒙特卡洛模拟 · 冰山水吸收实装

**🔴 缺失 2项**: TV Footprint数据 · MBO数据源

## 现存问题

| 优先级 | 问题 | 状态 |
|--------|------|------|
| P0 | 296 plans · 277 B等待 · 0 executed | 驾驶舱空置 |
| P1 | monitor_events 48,606行 1.3MB | 需提速清理 |
| P1 | Walk-Forward框架未产出 | 待跑 |
| P0 | TV Desktop MCP离线 | 待启动 |

## 测试状态
- 103/104 passed（99%）
- 1失败 = watchdog速率限制正常生效（重启风暴后）
