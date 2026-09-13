# v9.6 表格驾驶舱渲染落地记录

适用：棠溪交易分析卡/auto_card 渲染、模板同步、六市场流程说明。

## 背景

本轮用户要求“按照建议全面优化，驾驶舱一定要最新”，随后要求继续下一步并梳理各市场分析流程、用了什么 skill/能力/搜索、还能怎么优化。

核心发现：文档模板已升级到 v9.6 表格驾驶舱，但 `auto_card.py` 实际仍可能输出旧 v8.0 叙事/极简卡，造成“模板最新但渲染层没吃到”。

## 已落地模式

1. `references/master-template-v68.md` 是 v9.6 权威模板。
2. `references/tangxi-trading-cockpit.md` 是 v9.6 流程总控。
3. `scripts/render_v96.py`（2026-07-07 由 render_v8.py 更名）导出 `render_v96_card()`，输出 v9.6 表格驾驶舱。
4. `hermes/scripts/auto_card.py` 手动标准出卡不再被旧极简卡覆盖；默认返回完整 v9.6 表格卡。
5. `tests/test_card_render_locked.py` 的 marker 从 v8.0 叙事段落更新为 v9.6 五大区块。

## v9.6 必须包含的五大区块

- `### 多周期定位`
- `### 关键位矩阵`
- `### 多源交叉验证`
- `### 执行预案`
- `### 风控闸门`

回归测试和 smoke test 都必须检查这些 marker。

## 验证 bundle

```bash
cd "D:/Hermes agent"
python -m py_compile scripts/render_v96.py hermes/scripts/auto_card.py scripts/pipeline_router.py
python -m pytest tests/ -q --tb=short --disable-warnings
python hermes/scripts/auto_card.py BTCUSDT
python hermes/scripts/auto_card.py XAUUSD
python - <<'PY'
from pathlib import Path
markers=['### 多周期定位','### 关键位矩阵','### 多源交叉验证','### 执行预案','### 风控闸门']
for sym in ['BTCUSDT','XAUUSD']:
    txt=Path(f'data/auto_card_{sym}.md').read_text(encoding='utf-8', errors='ignore')
    print(sym, len(txt.splitlines()), all(m in txt for m in markers), txt.count('|---'))
PY
```

健康结果样例：`116 passed`；BTC/XAU 卡片约 54 行，五大 marker 全 True，表格分隔线数量约 22。

## 六市场 full 流程

| 市场 | full 流程 | 主周期 |
|---|---|---|
| 加密 | tv → binance → cg_pro → macro → x_sent → cron_read → cvd → depth → corr → card | 15m |
| 贵金属 | tv → macro → x_sent → cron_read → cvd → corr → gold_macro → card | 5m |
| 外汇 | tv → macro → x_sent → cron_read → corr → forex_rate → card | 15m |
| 股票 | tv → macro → x_sent → cron_read → corr → fmp → options_chain → card | 1h |
| 期货 | tv → macro → x_sent → cron_read → corr → card | 15m |
| 期权 | tv → options_chain → card | 跟底层 |

## 社区对照后新增优化方向

- TradingView 2026 footprint/order-flow：评估 Pine `request.footprint` / `volume_row` 是否可替代近似 CVD。
- Freqtrade Protections：实时检查不够，回测/日评也要启用 protections 报告。
- NautilusTrader：下单前 GO/NO-GO pre-trade risk check 必须成为硬闸门。
- Bookmap：多源验证表要拆出 CVD背离、吸收/派发、扫荡、冰山，而不是只写粗略 CVD。
- Reddit/WFO：样本不足或无 walk-forward/OOS 时，不允许 A 级升级。
- 期权：options_chain 不应只声明，应输出 IV Rank、Delta/Gamma/Vega/Theta、OI、Volume、到期、MaxPain。

## 关键坑

- 改模板不等于改渲染层；必须跑 `auto_card.py BTCUSDT/XAUUSD` 验证真实输出。
- 保留旧函数名、换内部输出格式是低风险迁移方式。
- XAU 当前若没有 TV MCP 现场多周期关键位，表格会用占位 K 线，价位全等于现价；正式可执行 XAU 卡必须先现场读 TV 5m/15m/1h/4h。