# Cron任务管理最佳实践（2026-06-29）

## 频率合理性检查

| 频率 | 合理上限 | 原则 |
|------|:--:|------|
| 每5分钟 | ≤2 | 仅看门狗+关键价格触发 |
| 每15分钟 | ≤3 | Deribit/新鲜度等高时效数据 |
| 每30分钟 | ≤6 | 大多数市场扫描任务 |
| 每2小时 | ≤3 | 链上/稳定币等较慢数据 |
| 每4小时 | ≤2 | 关键位同步(LLM)+低时效数据 |
| 每天 | ≤6 | 维护+复盘+COT(周) |

**反模式**: XAUUSD每5分钟推TG → 刷屏，应删或降频到15m+
**反模式**: BTC深度分析每3分钟 → 烧token，已停

## 僵尸任务清理

已禁用但输出目录残留的cron，用以下命令检查：

```bash
# 列出cron output目录中存在但不在活跃cron列表的job_id
ls ~/AppData/Local/hermes/cron/output/

# 删除残留目录
rm -rf ~/AppData/Local/hermes/cron/output/<job_id>
```

## ETF Flow教训

SoSoValue（2026-06-29确认）：被Cloudflare完全封禁，curl和Python requests均失败。
Farside Investors：同样Cloudflare保护。
**没有免费的BTC ETF API可用**。Dune链上净流 + DeFiLlama稳定币作替代覆盖机构资金面。

## 删除cron

```bash
hermes cron remove <job_id>
```

删除后手动清理输出目录。
