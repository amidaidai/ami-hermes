# 2026-06-19 审计精简 + Cron合并 + 警报修复实战

## 过度审计教训

初次审计产出 14 条 P0/P1/P2。棠溪反问"有必要吗"后复查：
- 11 条是文档整洁度（模板占位符 vs 渲染剥离、CVD等级描述过时、话题路由文档滞后等）
- 仅 2 条真问题：gold_monitor 硬编码价格 + auto_label_bridge.py 脚本不存在

**铁律**：审计报告产出前过三问法，砍掉所有文档洁癖项。

## Cron 合并：7→3

合并步骤：
1. 列出所有 cron → 逐个读脚本 → 找职责重叠
2. 创建 wrapper 脚本（subprocess.run 串行调用原脚本）
3. 注册新 cron → 验证能跑 → 逐个删除旧 cron
4. 清理 paused 状态的废弃 cron（jobs.json 残留）

### 合并案例分析
- 信号巡检(3m) + 持仓监测(5m) → 持仓与信号(5m) — 每天轮询 800→300 次
- 凌晨三连(3:20+3:50+4:10) → 日间维护(8:30) — 一条日报
- 清理守护 6h → 每天 12:00 一次

### Windows 目录联接消除双路径
```python
import ctypes, os
appdata = os.path.join(os.environ['LOCALAPPDATA'], 'hermes', 'scripts')
target = r'D:\Hermes agent\scripts'
kernel32 = ctypes.windll.kernel32
CreateSymbolicLinkW = kernel32.CreateSymbolicLinkW
CreateSymbolicLinkW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
CreateSymbolicLinkW.restype = ctypes.c_bool
CreateSymbolicLinkW(appdata, target, 0x1)
```

### 时段门控原则
✅ `*/5 8-23 * * *` — cron 管时段，简洁
❌ 脚本内写复杂时间窗口判断 — 难读、难调

## 警报系统修复（3项）

### ① 预测回验偏向
- 根因：`prediction_tracker.py` 把"方向不明"永远标为正确
- 修复：排除"方向不明"、阈值 0.1%→0.3%
- 日志降频：30min→60min

### ③ 推送合并
- 根因：突破触发时先推 alerts 再推 "结构已更新"
- 修复：结构重算移到 render_message 前，通知追加到警报末尾

### ④ warning 门槛
- 65→68→75（棠溪最终要求）
- 但 75 > critical(70) 导致层级反了 → 同步提 critical 到 78
