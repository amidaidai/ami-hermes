# 监控脚本中文命名

## 标准脚本名

- 主监控：`scripts/行情守望.py`
- 兜底巡检：`scripts/信号巡检.py`
- 停止监控：`scripts/停止行情守望.ps1`

## 命名含义

- `行情守望`：持续看盘、守关键位、等触发，不乱动。
- `信号巡检`：每 1 分钟检查事件、主监控心跳、重复进程、结构刷新队列和关键位健康，防止主推送遗漏或旧结构继续响。
- `停止行情守望`：统一停止所有旧/新监控进程。

## 兼容脚本

以下旧文件只作为兼容包装，内部转发到新名字：

- `scripts/smart_monitor.py` → `scripts/行情守望.py`
- `scripts/价格监控.py` → `scripts/行情守望.py`
- `scripts/check_monitor_events.py` → `scripts/信号巡检.py`
- `scripts/监控事件检查.py` → `scripts/信号巡检.py`
- `scripts/stop_smart_monitor.ps1` → `scripts/停止行情守望.ps1`
- `scripts/停止价格监控.ps1` → `scripts/停止行情守望.ps1`

## Cron

运行时 cron 使用：

```text
Name: 信号巡检
Script: 信号巡检.py
```

## 重启命令

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'D:/Hermes agent/scripts/停止行情守望.ps1'
python -u 'D:/Hermes agent/scripts/行情守望.py'
```

## 原则

- 用户可见、日志、cron、文档优先使用更自然的中文名字。
- 旧英文/直白中文文件名保留兼容，避免历史任务断掉。
