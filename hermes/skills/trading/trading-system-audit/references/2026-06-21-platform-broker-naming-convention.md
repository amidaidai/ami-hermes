# 棠溪交易系统 · 平台/经纪商名显示约定（2026-06-21）

## 核心规则
- **监控警报（行情守望 + Feishu sidecar）** 和 **完整分析卡** 必须使用干净“平台”名，**禁止“交易所”三字**。
- 品种行格式：`品种：{SYMBOL} · {平台}`
  - XAUUSD / GOLD：`OANDA`（用户明确“经常使用oanda的”，TradingView 常用数据源）
  - BTCUSDT / ETH：`BINANCE`（带 .P 后缀）
  - 外汇：`OANDA`
  - 股票：`NASDAQ`
  - 期权：`OPRA`

## 必须同步的文件（变更时全量 patch）
1. `scripts/行情守望.py:display_symbol()`
2. `hermes/scripts/auto_card.py:_display_symbol()` + `_leverage_text()` （杠杆文本极易残留旧名如 Exness 1000x）
3. `references/master-template-v68.md`（头部规则示例 + 资产专属操作规则）
4. `scripts/multi_symbol_templates.py`（"exchange" 字段）

## 验证 bundle（必须执行）
```bash
python -c "
from scripts.行情守望 import display_symbol
from hermes.scripts.auto_card import _display_symbol
print('短卡 XAU:', display_symbol('XAUUSD'))
print('卡片 XAU:', _display_symbol('XAUUSD'))
"
python scripts/auto_card.py XAUUSD
grep -E '品种：|风控：' data/auto_card_XAUUSD.md
grep -iE 'exness|交易所' data/auto_card_*.md references/master-template-v68.md || echo '0 残留 OK'
```

## 用户偏好
- “EXNESS换成tradingview的交易所，我经常使用oanda的”
- “交易所那几个字删掉，就是监控警报发到飞书那个”
- 响应：立即全路径批量 + “其他的一起全部修复了” 模式 + git 锁定。

## 常见陷阱
- 只改 header display_symbol，遗漏 _leverage_text() 中的 “Exness 1000x”。
- 只更新模板示例，代码渲染仍输出旧名。
- 历史 card_excerpt / 推送记录中残留旧格式（不影响新输出，但审计时需区分）。

此约定属于模板合规 P0 项，任何审计必须显式验证。
