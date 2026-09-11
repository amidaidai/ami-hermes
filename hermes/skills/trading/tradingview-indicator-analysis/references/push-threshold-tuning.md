# 推送阈值调优方法论 · 2026-06-18

## 问题
旧阈值 `MIN_WARNING_LEVEL_SCORE=70` 导致推送率仅 22%，大部分 warning/info/invalidated 事件被静默。

## 调优方法（数据驱动）

1. 导出 trade_events.jsonl 全量事件
2. 对每条被抑制的事件，用新阈值重新判断
3. 统计新推送率，调整阈值直到目标范围
4. 不应拍脑袋改数字 — 用历史数据验证

## v2.2 → v2.3 阈值（2026-06-18 生效）

```
MIN_WARNING_LEVEL_SCORE = 65  (was 70)
breached_like 增加 "near_or_breach" + "触发" in condition_reason
info:     high+score≥60 或 score≥68  (was 70)
expired:  high 或 score≥65           (was only high)
invalidated: high+score≥60 或 score≥65 (was 70)

# v2.3 新增（2026-06-18 14:40）：
# warning tier 第三条件: medium优先级 breach + 位信≥68 + 数据A/B → 推送
# 解决"位信69% · 数据B级"被无差别降噪的问题
```

## 效果

| 指标 | 旧 | v2.2(历史回测) | v2.3(实测) |
|------|-----|-------------|-----------|
| 推送率 | 22% | ~80% | ~50%正常日 |
| info | 0条 | +20条 | ~5条 |
| invalidated | 0条 | +21条 | ~3条 |
| expired | 1条 | +8条 | ~2条 |
| warning medium breach | ❌全部拦截 | ❌仍拦截 | ✅位信≥68+B级推送 |

## 陷阱
- 历史事件多集中在波动日（BTC 65800→63600），正常日事件稀少
- 阈值改完后必须重启 `行情守望.py` 进程才生效（`taskkill` + 重启）
- `breached_like` 之前只匹配 `breach/close_confirm`，漏掉了 `near_or_breach` — 这是大部分warning被吞的根因
