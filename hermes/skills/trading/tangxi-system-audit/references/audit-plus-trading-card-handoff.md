# 审计后补交易卡交接流程

触发：用户说"分析我的系统""审计"，完成系统健康审计后，又追问"有没有使用我们的分析流程""用上我们的能力了吗"等。

## 动作清单

1. 判断当前系统健康是否有未修复 P0
   - 有 P0 未修：先修复再出卡（`crypto-multisource-analysis` 铁律：TV MCP 不可用时不能跳过）
   - 无 P0 或已修：立即补交易卡

2. 切 TV 到目标品种主执行周期
   - BTC：BINANCE:BTCUSDT.P · 15m
   - XAU：OANDA:XAUUSD · 5m
   - 外汇/期货：15m；股票：1h

3. `capture_screenshot(region="full")` 截图
   - 必须含右侧价格轴 + 底部 CVD 窗格
   - 保存到 `tools/tradingview-mcp/screenshots/`

4. 采集多源数据（cron_read + 实时 snapshot）
   - `data/source_snapshot_{SYMBOL}.json`
   - `data/tv_dmi_cache.json` / `data/tv_live.json` / `data/xau_tv_state.json`
   - `data/orion_radar.json`
   - `data/deribit_options.json`（加密）
   - `data/x_sentiment.json`

5. 按 6 段式出卡
   - ① 当前结构
   - ② 多周期定位（1D/4h/1h/15m/5m）
   - ③ 关键位矩阵
   - ④ 多源交叉验证
   - ⑤ 执行方案（⭐主推 + 🔁备选 + ⚠️禁止）
   - ⑥ 最终裁决

6. 推送
   - BTC → telegram:-1003733144325:386
   - XAU → telegram:-1003733144325:385
   - 必须走 `telegram_reliable.push_tg_rich` RichMarkdown 真表格

## 格式雷区

- 不要把系统审计报告再发一遍
- 不要等用户说"继续"才出卡
- 不要只给文字段落，必须用真 Markdown 管道表
- 不要给用户 A/B 同权菜单，主推只给一个

## 参考

- `crypto-multisource-analysis` skill：完整 10 步管线
- `tradingview-execution-card` skill：低周期执行卡
- `xau-analysis-format` skill：10 段头部 + 五段正文格式
