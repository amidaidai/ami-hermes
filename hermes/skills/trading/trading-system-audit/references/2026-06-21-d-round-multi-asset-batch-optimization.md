# D轮 “全部一起再来一轮” 多资产批量优化模式（2026-06-21）

## 触发与铁律
用户说 “D” 或 “全部一起再来一轮” 或 “按照你的建议来全方面的帮我优化，全部优化吧。你的建议推送一次，优化一次” 时：
- 识别剩余高/中优先项（本轮：scoring_engine 资产加权、should_trade/session_filter 全资产、model_engine per-asset adapters）。
- **立即全量批量**：不分步等待确认。
- 每条改动后必须跑验证 bundle。
- 结束时必须 git commit + push 作为锁定。

## 本轮具体实现（可复用）
1. **session_filter.py 升级**
   - 新增 `get_asset_class(symbol)` → gold/forex/crypto/stock/option
   - `get_active_sessions` 按资产分支：
     - crypto: ["24/7"]
     - gold: GOLD_SESSIONS + Kill Zone
     - forex: FOREX_SESSIONS (London+NY overlap 优先)
     - stock: US market hours
     - option: 跟随底层
   - 强化 `should_trade` + `is_weekend_closed`（crypto 例外）
   - 新增 `require_liquidity_for_gold` 等辅助

2. **scripts/行情守望.py 集成**
   - 移除 XAU 硬编码 if
   - 总是调用 `from session_filter import should_trade, get_asset_class`
   - 非 crypto 资产走时段过滤，失败则静默
   - 引入 `asset_macro_enrich` 写入 `raw["_macro"]`，财报窗口记录

3. **hermes/scripts/multi_model_engine.py**
   - 新增 `get_asset_class`（冗余但自包含）
   - `asset_weight_adapter(symbol, base_conf, model_name)`：
     - gold: Kill/Sweep/DXY ×1.25
     - forex: SMT/Silver/DXY ×1.15
     - crypto: CVD/Funding ×1.1
     - stock: ×0.85

4. **references/master-template-v68.md**
   - 资产规则标题 → “社区2026全面多资产优化版”
   - 新增时段门控铁律段落

## 验证 bundle（必须全跑）
```bash
python -m py_compile scripts/session_filter.py scripts/行情守望.py hermes/scripts/multi_model_engine.py
python -c "
from session_filter import get_asset_class, should_trade
for s in ['XAUUSD','BTCUSDT','EURUSD','AAPL','AAPL250117C']:
    print(s, get_asset_class(s), should_trade(s))
"
python -c "
from system_data_bridge import asset_macro_enrich
print(asset_macro_enrich('XAUUSD'))
print(asset_macro_enrich('EURUSD'))
print(asset_macro_enrich('AAPL'))
"
python scripts/auto_card.py XAUUSD && python scripts/auto_card.py BTCUSDT
python -c "
import re, glob
for f in glob.glob('data/auto_card_*.md'):
    leaks = re.findall(r'setup_id|model_id|entry_tag|exit_tag', open(f).read())
    print(f, 'leaks:', len(leaks))
"
git status --short
```

## 提交模式
git add ... ; git commit -m "optimize: D轮 全面多资产优化 (session_filter全资产时段+... )"; git push

## 坑
- session_filter 曾因 patch 导致函数嵌套 → 必须读完整文件后 targeted replace
- 资产分类必须在 session_filter 和 model_engine 保持一致（或抽共享）
- 周末测试时非 crypto 会返回 closed（正常）
- 必须同时更新 monitor + renderer + engine + template

此模式可直接用于下一次“E轮”或用户说“全部一起”时复用。
