# 多资产模板样式烟测与 Telegram 预览

适用场景：用户要求“看模板样式”“各种跑一下”“加密/贵金属/外汇/股票/期权模拟发 Telegram”。

## 推荐流程

① 先读取 `references/master-template-v68.md` 锁定当前权威格式。

② 不要直接跑 `auto_card(symbol, push=True)` 做样式烟测：真实一键出卡会采集实时数据、写 `data/auto_card_*.md`、追加 trade plan、更新 monitor metadata，可能污染实盘 BTC/XAU 监控位。

③ 用 `hermes/scripts/auto_card.py::render_card_locked()` 构造模拟 `merged/results/meta/engine_data` 渲染五类卡：
- 加密：`BTCUSDT` → `BTCUSDT.P · 交易所：BINANCE`
- 贵金属：`XAUUSD` → `XAUUSD · 交易所：EXNESS`
- 外汇：`EURUSD` → `EURUSD · 交易所：OANDA`
- 股票：`AAPL` → `AAPL · 交易所：NASDAQ`
- 期权：`AAPL250117C` → `AAPL250117C · 交易所：OPRA`

④ 导入真实渲染器时必须绕开 `scripts/auto_card.py` 兼容 wrapper。该 wrapper 顶层执行 `runpy.run_path(..., run_name="__main__")`，被 `import auto_card` 导入会误触发真实 BTC 出卡。安全方式：

```python
import importlib.util
spec = importlib.util.spec_from_file_location('real_auto_card', ROOT / 'hermes' / 'scripts' / 'auto_card.py')
auto_card = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(auto_card)
```

⑤ Telegram 预览默认发任务报告话题 `telegram:-1003733144325:846`，不要占用 BTC/XAU 实盘警报话题。每条开头标明“模板样式模拟 · 非实盘建议”。

⑥ 发送前后做格式烟测：
- `validate_card_rules(card, meta)` 必须空列表。
- 扫描输出，禁止 `setup_id|model_id|entry_tag|exit_tag|critical|warning|info|｜|\|`。
- 确认头部为“◷ 时间 → ① 品种 → ② 周期”，且操作段 A/B 都有 ①-⑦。

## 已知适配坑

① 当前渲染器对黄金有专属环境分支，但外汇/股票/期权仍可能继承加密衍生字段或尝试 `depth_wall`，导致 `depth_wall fetch failed: HTTP 400`。这不一定影响发送，但说明非加密模板适配仍需继续精修。

② 期权卡必须重点看权利金、到期日、行权价、Delta/Gamma/Theta/Vega、IV分位、最大亏损；不要套 Funding/OI/Taker。

③ 外汇卡必须看美元腿/交叉盘/点数/手数/隔夜利息/新闻闸门；不要套加密 Funding/OI。

④ 股票卡必须看股数、指数/板块、财报窗口、盘前盘后、流动性；低杠杆优先。
