# 警报阈值梯度 · 最终锁定值 (2026-06-19)

## 社区共识

多渠道联网验证（TradingView Pine Script 社区、r/algotrading Confirmation Gate 帖、ROT 开源监控系统、知乎量化社区）：

- **突破信号**：价格已跨过关键位，有天然确认 → SNR 高 → 门槛可放低
- **接近信号**：价格尚未跨越，噪音大 → SNR 低 → 门槛应更高
- 因此 `MIN_WARNING_LEVEL_SCORE > MIN_CRITICAL_LEVEL_SCORE` 是合理的（看似"倒挂"，实为信号本质决定）

## 最终锁定值

```
MIN_WARNING_LEVEL_SCORE = 75   # 接近/未确认 → 严格过滤
MIN_CRITICAL_LEVEL_SCORE = 70  # 突破/已确认 → 优先推送
MIN_INFO_LEVEL_SCORE = 60      # 失效/过期 → 保持提醒
```

## push_allowed 完整映射

| tier | 门槛常量 | 值 | 逻辑 |
|------|----------|----|------|
| critical | MIN_CRITICAL_LEVEL_SCORE | 70 | 突破/多触发 → 优先 |
| warning | MIN_WARNING_LEVEL_SCORE | 75 | 单触发 → 严格过滤 |
| info | MIN_INFO_LEVEL_SCORE | 60 | 接近/观察 → 宽松 |
| invalidated | MIN_INFO_LEVEL_SCORE | 60 | 计划失效 → 提醒即可 |
| expired | MIN_INFO_LEVEL_SCORE | 60 | 过期 → 提醒即可 |

## 修复记录

- 2026-06-19: warning 从 65→75, critical=70, 新增 info=60
- 初次设 warning=68，棠溪要求提到 75
- invalidated 原借用 MIN_WARNING_LEVEL_SCORE(75) → 改为 MIN_INFO_LEVEL_SCORE(60)
- expired 原硬编码 65 → 改为 MIN_INFO_LEVEL_SCORE(60)
- 注释更新为社区共识声明
