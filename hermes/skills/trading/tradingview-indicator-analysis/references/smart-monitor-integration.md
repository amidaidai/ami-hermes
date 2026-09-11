# 智能监控集成

## 架构

```
smart_monitor.py (后台进程)
    ↓ 30s轮询 Binance API (免费)
    ↓ 对比 monitor_levels.json
    ↓ 突破 → 写 monitor_events.json + 删除已破位
    ↓ 接近 → 写 monitor_events.json (10分钟间隔)
    
cron: price-alert (每5分钟)
    ↓ 运行 check_monitor_events.py
    ↓ 读 monitor_events.json 中未通知事件
    ↓ --deliver telegram → 中文推送
    
用户/Agent: "分析 BTC"
    ↓ 全量分析 + 出卡
    ↓ 自动覆写 monitor_levels.json (新关键位)
    ↓ 监控器下次轮询自动读取新位
    ↓ 闭环循环
```

## 为什么不用直接 Telegram API

1. Token 管理复杂 — Hermes 凭证存储无法直接读取
2. cron `--deliver telegram` 已内置推送能力
3. 监控只负责检测，通知由 cron 负责 — 职责分离

## 关键文件

| 文件 | 用途 |
|------|------|
| `scripts/smart_monitor.py` | 后台监控进程 |
| `scripts/check_monitor_events.py` | cron 事件检查 |
| `data/monitor_levels.json` | 监控关键位(每次分析后更新) |
| `data/monitor_events.json` | 事件日志(最近50条) |
| `data/monitor.log` | 监控运行日志 |

## 启动命令

```bash
# 启动监控
python -u "D:/Hermes agent/scripts/smart_monitor.py" &

# 创建 cron (一次性)
hermes cron create --name "price-alert" \
  --script "check_monitor_events.py" \
  --no-agent --deliver telegram "every 5m"

# 查看日志
cat "D:/Hermes agent/data/monitor.log"
```

## 阈值

| 类型 | 阈值 | 间隔 |
|------|------|------|
| 突破 | <0.1% | ≥2分钟 |
| 大破(2+位) | <0.1% ×2 | ≥2分钟 |
| 接近 | <0.3% | ≥10分钟 |
