# 双cron联动触发模式

## 场景

需要监控价格到某个条件后，自动出完整分析卡。但不想每次检查都花token。

## 架构

```
no_agent 价格监控 (5m)           agent 分析出卡 (1m)
┌────────────────────┐          ┌──────────────────────┐
│ Python脚本          │          │ agent会话             │
│ urllib→免费API     │ 触发时   │ 检查gold_trigger_    │
│ 价格条件判断        │ ──────→ │ request.json         │
│ 匹配→写标记文件+推  │  写文件  │ 读trigger信息         │
└────────────────────┘          │ 拉MCP数据             │
                                │ 出分析卡              │
                                │ 改标记status=completed│
                                └──────────────────────┘
```

## 文件约定

```
data/gold_trigger_request.json
{
  "triggered_at": "2026-06-18T10:20:00+08:00",
  "price": 4320.5,
  "phase": 1,
  "phase_name": "回踩确认等待",
  "triggers": [{"id": "A", "label": "回踩POC做多区间"}],
  "quality": "A",
  "source": "gold-api+GC=F",
  "status": "pending"    // no_agent写为pending，agent读完改为completed
}
```

## 创建步骤

### 1. no_agent 监控脚本 (python)

- 放在 `~/.hermes/scripts/` 下
- 用 `urllib.request` 从免费API获取数据（不依赖MCP）
- 条件匹配时：`print(消息)` + 写 `data/gold_trigger_request.json`
- 不匹配时：不输出任何内容（静默）

### 2. 创建no_agent cron

```python
cronjob(
    action='create',
    no_agent=True,
    script='gold_monitor.py',
    schedule='5m',
    deliver='origin'
)
```

### 3. 创建agent分析cron

```python
cronjob(
    action='create',
    schedule='1m',
    skills=['tradingview-indicator-analysis'],
    prompt='检查 D:/Hermes agent/data/gold_trigger_request.json。'
           '如果status!=pending → 什么都不做直接结束。'
           '如果status==pending → 读取trigger信息，'
           '拉MCP数据（金十quote/TV study_values/OHLCV/截图），'
           '出完整分析卡（含MEDIA），然后将status改为completed。',
    deliver='origin'
)
```

## 注意事项

1. **no_agent cron 不要设 enabled_toolsets**: MCP工具默认可用
2. **agent cron 不要设 enabled_toolsets**: 需要MCP工具拉数据
3. **文件路径**：agent session中绝对路径 `D:/Hermes agent/data/gold_trigger_request.json` 或 `~/Hermes agent/data/gold_trigger_request.json` 都行
4. **防重复**：no_agent脚本自带冷却（同条件10min内不重复写标记），agent cron检查status不是pending就跳过
5. **避免路径硬编码**：no_agent脚本用 `os.path.abspath(__file__)` 定位项目根目录
6. **MQCP tools不属于toolsets分类**: 不要用 `enabled_toolsets` 过滤工具，否则MCP工具不出现
