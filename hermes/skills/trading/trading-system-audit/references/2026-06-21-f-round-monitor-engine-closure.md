# F轮 监控+引擎闭环强化（2026-06-21）

## 背景
E轮完成 asset_macro_enrich + enrich 到渲染卡片 + 宏观加分。
F轮目标（用户“F” + “全部一起批量执行 + 推送”）：把宏观推送到监控短警报正文；让 asset_weight_adapter 自动对所有 run_all_models 调用生效；把 has_min_liquidity 门槛集成到行情守望 process_block 决策点。延续“你的建议推送一次，优化一次 + 全部一起”模式。

## 核心变更模式（可复用）

### 1. 监控警报正文注入宏观（render_message + process_block）
- `scripts/行情守望.py` render_message 增加参数 `macro_text=None`
- 在 extras 区（接续圈号）追加：
  ```
  ⑤ 宏观：DXY `100.85` · US10Y `4.45` · 美债/实际收益率
  ```
- process_block 主循环：
  - `macro = asset_macro_enrich(symbol)`
  - 构造 `macro_text`
  - 传给所有 render_message 调用（expired / invalidated / breach / near）
- 同时在 process_block 集成流动性守卫：
  ```python
  if not has_min_liquidity(symbol, snapshot):
      return  # 或降优先级
  ```

### 2. 引擎权重适配器全路径打通（run_all_models）
- `hermes/scripts/multi_model_engine.py`:
  ```python
  def run_all_models(data, symbol="BTCUSDT"):
      ...
      for model_name, ...:
          base = ...
          adjusted = asset_weight_adapter(symbol, base, model_name)
  ```
- 所有调用方同步更新传 symbol：
  - hermes/scripts/auto_card.py（~1469 行）
  - scripts/system_data_bridge.py（dir_flip 路径）
  - multi_model_engine __main__
- 默认值 "BTCUSDT" 保持向后兼容。

### 3. session_filter 流动性门槛
- 新增 `has_min_liquidity(symbol, snapshot=None)`
  - gold: 复用 require_liquidity_for_gold()（Kill Zone）
  - crypto: 检查 snapshot quality（A/B+）
  - 其他: return True
- 由 process_block 在时段过滤后立即调用。

## 验证 Bundle（F轮必须全跑，不可跳过）
```bash
python -m py_compile scripts/行情守望.py hermes/scripts/multi_model_engine.py scripts/session_filter.py hermes/scripts/auto_card.py scripts/system_data_bridge.py

python -c '
from system_data_bridge import asset_macro_enrich
from session_filter import has_min_liquidity
print("XAU macro:", asset_macro_enrich("XAUUSD"))
print("has_liquidity XAU weekend:", has_min_liquidity("XAUUSD"))
print("has_liquidity BTC:", has_min_liquidity("BTCUSDT"))
'

# 模拟监控警报
python -c '
from 行情守望 import render_message
print(render_message(..., macro_text="DXY `100.85` · US10Y `4.45`"))
'

# 权重适配验证
python -c '
from hermes.scripts.multi_model_engine import asset_weight_adapter
print("XAU sweep:", asset_weight_adapter("XAUUSD", 0.7, "sweep"))
print("BTC CVD:", asset_weight_adapter("BTCUSDT", 0.7, "cvd"))
print("AAPL:", asset_weight_adapter("AAPL", 0.7, "some"))
'

python scripts/auto_card.py XAUUSD && python scripts/auto_card.py BTCUSDT
grep -E "setup_id|model_id|entry_tag|exit_tag" data/auto_card_*.md || echo "0 leaks OK"

git status --short
```

## 观察证据（本轮真实输出）
- 模拟警报正文出现：⑤ 宏观：DXY `100.85` · US10Y `4.45`
- 权重：XAU 0.7 → 0.7（不变），BTC 0.7 → 0.77（×1.1），AAPL 0.7 → 0.595（×0.85）
- 卡片再生：0 machine leaks（主卡片）
- XAU snapshot quality A- 保持
- commit: db3993c
- push 成功

## 提交消息示例
optimize: F轮 监控+引擎闭环强化 (render_message 注入宏观 DXY/US10Y/财报到警报正文, run_all_models+所有调用方接 asset_weight_adapter, session_filter has_min_liquidity 门槛, 行情守望 process_block 集成流动性检查, 模拟警报验证 macro 显示, 0泄漏卡片+编译+功能测试全通过)

## 工作流铁律（“全部一起” + F 延续）
- 用户说 “F” / “继续” / “全部一起批量执行 + 推送” → **立即** 识别 monitor + engine + filter + callers 全路径，批量 patch，不分步。
- 每轮结束：完整验证 bundle + git commit + push 作为“锁定”。
- 连续轮次从干净 git 状态开始。
- macro 现在同时服务分析卡 + 监控短警报。
- 权重 adapter 必须接在 run_all_models 内部（而非只在调用方），避免遗漏。

## 坑点
- 遗漏任何 run_all_models 调用方 → 权重静默失效（必须 grep 所有调用点）。
- macro_text 只追加到 extras 区，不要覆盖主警报内容。
- 周末 XAU has_min_liquidity=False 是预期（闭市），不要误判为 bug。
- 模拟 render_message 要覆盖多种触发路径（expired/breach/near）。
- py_compile + 实测函数 + 卡片 0 leaks 三重验证缺一不可。
- 历史 _full.md 可能残留，验证只看主 auto_card_*.md。

## 可复用模式
- “监控闭环” = render_message 支持额外 text 参数 + 主循环实时构造 + 所有调用点传入。
- “引擎自动适配” = 在核心 run_all_models 内部做 per-symbol 调整 + 强制更新所有上游调用方。
- “轻量门槛” = session_filter 提供 has_min_liquidity，monitor 决策点立即调用。
- 验证 bundle 必须包含：编译 + python -c 关键函数 + 模拟短卡 + 卡片再生 + 0 leaks + 权重实测 + git clean。

此模式将“建议一次 → 优化一次”从卡片/数据桥扩展到监控警报 + 模型执行层。

下一步可扩展：真实成交量/深度数据到 liquidity gate、完整 earnings calendar（finance MCP）、更多资产监控支持。
