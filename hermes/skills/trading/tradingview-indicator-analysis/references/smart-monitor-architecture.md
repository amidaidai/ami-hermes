# 智能价格监控架构

## 组件

```
smart_monitor.py  ─→  monitor_levels.json  ─→  monitor_events.json  ─→  cron:check_events  ─→  Telegram
   (后台常驻)          (关键位存储)               (事件队列)               (每5min检查)           (推送)
```

## 数据流

1. `smart_monitor.py` 每 30s 轮询 Binance 价格
2. 对比 `monitor_levels.json` 中的关键位
3. 接近/突破 → 写入 `monitor_events.json`
4. Cron `price-alert` 每 5min 运行 `check_monitor_events.py`
5. 有新事件 → 标记 notified → stdout 输出 → Telegram 推送

## 关键位更新闭环

1. 用户说"分析 BTC" → 产出 32 条卡
2. 分析完成 → 自动覆写 `monitor_levels.json`（POC/DO/VAH/VWAP/纽高）
3. 监控器下次轮询自动读取新位
4. 循环继续

## 告警格式规范

- 中文上下文 + 标准英文术语（DO/VWAP/POC/CVD）
- 每行一个级别，带方向箭头和距离百分比
- 附带上次分析周期和操作建议
- 突破：🔴 · 接近：🟡
- 突破时自动删除已破位，等待分析重新补位

## 阈值

| 类型 | 阈值 | 最小间隔 |
|------|------|---------|
| 接近 | < 0.3% | 600s |
| 突破 | < 0.1% | 120s |

## 文件位置

- 监控脚本：`D:/Hermes agent/scripts/smart_monitor.py`
- 检查脚本：`~/.hermes/scripts/check_monitor_events.py`
- 关键位：`D:/Hermes agent/data/monitor_levels.json`
- 事件：`D:/Hermes agent/data/monitor_events.json`
- 日志：`D:/Hermes agent/data/monitor.log`
