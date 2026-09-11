# 智能价格监控系统

事件驱动，非定时轮询。监控关键位，突破时触发分析。

## 架构

```
Binance API (免费) → 每 30s 查价 → 对比关键位 → 突破 → 写事件文件
                                                              ↓
                    monitor_levels.json ← 分析后更新 ← Hermes 分析卡
```

## 文件

| 文件 | 用途 |
|------|------|
| `D:/Hermes agent/scripts/smart_monitor.py` | 监控主脚本 |
| `D:/Hermes agent/data/monitor_levels.json` | 当前关键位 |
| `D:/Hermes agent/data/monitor_events.json` | 触发事件队列 |

## 触发规则

| 级别 | 条件 | 动作 |
|------|------|------|
| 🟡 接近 | 距关键位 < 0.3% | 写事件 |
| 🔴 突破 | 突破 1 个关键位 | 写事件，移除该位 |
| 🔴🔴 大破 | 突破 2+ 关键位 | 写事件，触发全量分析 |

## 启动

```bash
python -u "D:/Hermes agent/scripts/smart_monitor.py"
```

后台常驻，0 token 消耗。

## 分析联动

每次分析后自动更新 `monitor_levels.json`，写入新的 POC/VAH/DO/VWAP/纽高。
分析前检查 `monitor_events.json`，有事件时在环境段附加触发上下文。
