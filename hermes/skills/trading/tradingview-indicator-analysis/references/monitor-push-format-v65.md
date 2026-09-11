# 监控推送格式 v7.0

> 2026-06-17：与分析卡 v5.1 风格统一——冒号对齐·子项缩进无号·无分段标题

## 推送卡片模板

```
{head}

① 品种：{symbol}
② 价格：`{price}`
③ 状态：{situation_text}
④ 计划：{plan_display}
⑤ 周期：{cycle}
⑥ CVD：{direction} · {quality}
⑦ Taker：{dir} {ratio} · {quality}
⑧ 多空：{long_pct}%多 · {dir}
⑨ 衍生：{derivatives_text}
⑩ 模型：引擎判{偏多/偏空} · 位信{一致✓/矛盾⚠}
⑪ 冲突：{conflict_text}
⑫ 风控：{risk_text}

   价位：{display_name} `{level}`
   动作：{action}

动作：{urgency}
提示：说「分析 {symbol_short}」刷新完整卡
```

## 格式规则

- 无 `—— 触发细节 ——` / `—— 执行结论 ——` 分段标题
- 子项（价位/动作）缩进3空格，无序号
- 底部「动作」「提示」各一行

Telegram 推送卡片标准格式（行情守望.py v6.5 生成）。

## 关键位触发推送

```
🔴 BTCUSDT 关键位触发
① 品种 BTCUSDT
② 价格 `64960`
③ 置信 B级 · 74% · 近端结构
④ 计划 比特币日内计划·6月17日22:08
⑤ 现状 价格触发关键位
⑥ CVD 卖 · B级
⑦ Taker sell 0.72·B级
⑧ 多空 62.6%多·long
⑨ 衍生 费率+0.0020%·大户62%多
⑩ 冲突 多头拥挤vsTaker卖
⑪ 风控 允许·轻仓·最大风险3U

—— 触发细节 ——
⑫ 价位：支1·VAL防线 `64957`
   动作：跌破不收回=空头延续·快速收回=假跌VAL回收

—— 执行结论 ——
⑬ 周期 4h空头→1hVAL回收→15m站EMA→5m等Fed
   动作 尽快看5m确认
   提示 说「分析 BTC」刷新完整卡
```

## 方向翻转推送

```
🔄 BTCUSDT 多模型方向翻转
旧方向：方向不明/震荡
新方向：偏多
请检查是否需要更新分析卡
```

## 字段说明

| 序号 | 字段 | 数据源 | 何时显示 |
|------|------|--------|---------|
| ① | 品种 | 固定 | 始终 |
| ② | 价格 | Binance API | 始终 |
| ③ | 置信 | level_confidence | 始终 |
| ④ | 计划 | monitor_levels plan_id | 始终 |
| ⑤ | 现状 | 触发等级 | 始终 |
| ⑥ | CVD | system_data_bridge.cvd_dir() | 始终(B级) |
| ⑦ | Taker | bridge_snap().taker | 始终 |
| ⑧ | 多空 | bridge_snap().ls | 始终 |
| ⑨ | 衍生 | bridge_deriv() | 始终 |
| ⑩ | 冲突 | 自动检测(多头拥挤vsTaker卖/空头拥挤vsTaker买/费率翻转) | 有冲突时 |
| ⑪ | 风控 | risk_gate | 始终 |

## 推送通道

- 主场：Telegram `telegram:阿弥黛黛`
- 方式：`sys.executable -m hermes_cli.main send -t "telegram:阿弥黛黛" -q "{msg}"`
- 重试：3次，每次间隔2秒
- 备用：Discord bot "安禾"（仅在Telegram不可用时手动切换）
