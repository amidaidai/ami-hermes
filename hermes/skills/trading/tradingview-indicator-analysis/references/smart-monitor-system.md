# 智能价格监控系统

## 架构

```
smart_monitor.py (后台常驻，每30s)
  ↓ 检测突破/接近
  ├→ hermes send (实时推送，~1秒)
  └→ monitor_events.json (历史记录)
       ↓ 每10min (兜底)
      cron: check_monitor_events.py
```

## 监控脚本

- `D:/Hermes agent/scripts/smart_monitor.py` — 主监控 v5
- `D:/Hermes agent/scripts/check_monitor_events.py` — 事件检查+cron推送
- 数据文件目录: `D:/Hermes agent/data/`

## 数据文件

| 文件 | 用途 |
|------|------|
| `monitor_levels.json` | 当前监控的关键位 (自动更新) |
| `monitor_events.json` | 检测事件历史 (最近50条) |
| `monitor_state.json` | 推送冷却状态 |
| `monitor.log` | 运行日志 |

## 告警规则

### 三级告警

| 等级 | 条件 | 冷却 |
|------|------|------|
| 🔴 紧急 | 突破 2+ 位 或 突破DO/VWAP且CVD卖 | 2min |
| 🔴 突破 | 单次突破 | 5min |
| 🟡 接近 | 距关键位 < 0.3% | 15min |

### 防刷机制
- 同一关键位 30min 内不重复告警
- 各级别独立冷却
- 1小时推送预算：紧急最多8条、突破最多4条、接近最多2条、全局最多12条；紧急不受全局预算压制

### CVD 复合
- 突破 DO/VWAP + CVD 为"卖"方向 → 升级为紧急
- 单纯接近 → 始终为 🟡 接近

## 关键位自动更新

分析完成后，将新的 POC/VAH/DO/VWAP 写入 `monitor_levels.json`。
监控器自动读取，旧位被破后自动删除。

## 启动/停止

```bash
# 启动
python -u "D:/Hermes agent/scripts/smart_monitor.py" &

# 停止
kill <PID>
```

## 常见问题

- **监控无输出**: 检查代理，`proxies=None` 在 Windows Clash 下会超时
- **重复告警**: 清除 `monitor_state.json` 中的 `last_alerts`
- **脚本中推送失败**: 用 `hermes send -t "telegram:阿弥黛黛" -q "消息"` 而非直接调 Telegram API
