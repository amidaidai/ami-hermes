# 完整档运行时验收（2026-09-12）

## 现场现象

用户说「分析BTC」时，`pipeline_router` 正确识别为 L3/full，返回完整路由；但直接运行：

```bash
python scripts/auto_card.py BTCUSDT
```

实测输出仍为 `quick`，审计只有 `tv → binance → card`。因此不能把 auto_card 默认入口的输出当成完整档已完成。

## 验收流程

1. 运行 `pipeline_router.tier_table()` 与 `route_pipeline("BTCUSDT", "full")`。
2. 读取TV健康、确认 `BINANCE:BTCUSDT.P`，按 `1D → 4h → 1h → 15m → 5m` 独立读取。
3. 切回15m，开启全屏并截取含价格轴与CVD/副指标窗格的新图。
4. 取Binance现价、15m K线、OI、资金费率、大户/全局多空比、主动买卖。
5. 取FinanceKit的BTC价格、Top10、Trending；宏观和相关性失败要显式降级。
6. 取x_search实时情绪、金十日历/快讯、Binance深度。
7. cron_read先检查文件mtime：>60分钟只能标 stale_cache/过期跳过，不得当实时证据。
8. 最终报告区分「现场完整采集」和「auto_card实际渲染档位」，完整性审计不得沿用quick的3步结果。

## 可靠性规则

- SVP主行动格是方向真源；副指标只能确认、降级或否决。
- 主指标冲突、C等待、未收线、等解除时只给等待，不渲染Entry/Stop/Target。
- 相关性返回数据不足时写明不可用，禁止编造相关系数。
- 本地旧Dune/QLib/X情绪缓存只能作历史参考，不能覆盖现场数据。
