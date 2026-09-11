# 2026-06-21 模板监控策略 & 监控警报格式审计修复

## 触发
用户要求“全面检查系统，检查我的模板监控策略，全方位审计” + “修复，全部修复。还有啊，交易所那几个字删掉，就是监控警报发到飞书那个。”

## 核心铁律更新（监控警报路径）
- 监控短卡（行情守望.py 构建 + display_symbol）品种行必须干净：`品种：XAUUSD · EXNESS`、`品种：BTCUSDT.P · BINANCE`（禁止出现“交易所”字样）。
- Feishu sidecar / gateway 警报直接复用短卡文本 → 必须同步更新模板 + 代码显示函数。
- 完整分析卡（auto_card.py）与短监控卡渲染必须双路径对齐。

## 具体修复（批量一次完成）
1. `references/master-template-v68.md`：①品种行模板及规则示例从“交易所”改为“平台”。
2. `references/monitor-template.md`：推送目标描述更新，删除 Discord，强调 Feishu sidecar。
3. `scripts/行情守望.py`：display_symbol + 短卡构建逻辑；get_close() 增加 XAU 守卫（与 get_price 一致，早期返回 None 阻断 Binance 调用）。
4. `hermes/scripts/auto_card.py`：渲染器强制周期逐行（5m/15m/1h/4h 各一行）、头部禁用 ** 加粗。
5. `scripts/multi_symbol_templates.py` + cron 注释：清理残留“交易所”和 Discord。
6. watchdog 参数放宽 + `data/watchdog_guard.json` 重置；`data/prediction_log.jsonl` 清空。
7. 验证 bundle 必须全跑：
   - read_file references/master-template-v68.md
   - 再生 BTC/XAU 卡
   - 模拟短警报文本检查（grep “交易所” == 0）
   - python -c 测试 get_close('XAUUSD') / get_price('XAUUSD') → None
   - 0 machine leaks + 周期逐行 + 无 **
   - git status --short → clean → commit + push

## 工作流偏好嵌入
- “全部修复” / “全部一起” = 识别所有受影响路径后**全量批量 patch**（不分步等待确认），立即执行验证 bundle + git 锁定。
- 涉及具体字词删除（如“交易所”）时，视为 P0：模板 + 所有显示/渲染/推送路径 + 注释全部更新。
- 验证必须用真实输出（短卡模拟 + 卡片 regen + 函数直调 + grep），不能只描述。

## 持久教训
- 监控警报格式是独立于完整分析卡的短纵向格式，必须单独检查（行情守望.py 路径）。
- 任何格式/字词变更后，旧 references/ 示例文档容易滞后 → 同步 patch 它们。
- XAU 守卫必须覆盖 price + close + kline 所有入口，否则主循环仍会被 400 拖垮。
- Feishu 警报格式与 Telegram 一致，统一走短卡文本管道。

## 验证证据（本次会话）
- 短警报示例输出：
  ① 品种：XAUUSD · EXNESS
  ① 品种：BTCUSDT.P · BINANCE
  （0 “交易所”）
- 周期逐行、无 ** 头部。
- Git clean，commit 进入历史。
- 守卫测试通过。

此文件记录模板监控策略专项审计模式，供后续全面审计复用。
