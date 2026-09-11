# TV DMI 缓存桥接模式 (v6.9.15a · 2026-06-21)

## 问题

棠溪系统有两条并行告警管道，互不认识：

1. **行情守望.py** (10s轮询) — 实时价格告警推 Telegram，无 TV DMI 数据
2. **auto_card.py** (5m cron) — TV DMI 集成分析卡，写入文件，不推送

用户收到的"关键位触发"告警来自管道①，看不到 TV DMI 等级 (A/B/C/X)。

## 架构: tv_dmi_cache.json 桥接

```
cron agent (5m)                    行情守望.py (10s)
    │                                   │
    ├→ 读 TV MCP DMI 表                 │
    ├→ 生成 auto_card (如有A级)          │
    ├→ 写 tv_dmi_cache.json ──────────→ ├→ _load_tv_dmi_cache()
    └→ 推 Telegram (如有A级)            ├→ render_message 注入 TV 信号
                                        └→ 推 Telegram 告警 + "⑤ TV信号：⚠X·结构冲突"
```

## 缓存文件格式

`data/tv_dmi_cache.json`:
```json
{
  "grade": "X",
  "treatment": "结构冲突",
  "cvd_state": "顺多确认",
  "background": "空 4h",
  "position": "VAL下方｜下方控制",
  "execution": "等:等确认",
  "risk": "不进场",
  "updated": "2026-06-21T17:52:00+08:00"
}
```

## 消费者代码

```python
def _load_tv_dmi_cache():
    """读取 TV DMI 决策表缓存"""
    cache_file = DATA_DIR / "tv_dmi_cache.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    return {}
```

## 告警注入示例

`行情守望.py` 的 `render_message()` 在模型行后追加：
```python
⑤ TV信号：⚠X · 结构冲突
# 或
⑤ TV信号：🔥A多 · 回踩做多
```

## 关键约束

- **不要**让行情守望直接调 MCP（无 agent 上下文不行）
- **不要**让两个管道互斥——它们是互补的：一个10s告警，一个5m深度分析
- **缓存更新频率**：每5分钟（cron agent）
- **缓存读取频率**：每次告警（10秒轮询自动读最新缓存）

## 防重复

tv_signal_monitor.py 负责推送决策：
- A级：必推（30min内同等级不重推，日限6次）
- B+关键位：推送（日限3次）
- C/X：静默
- 状态持久化：`data/tv_signal_state.json`
