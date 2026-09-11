# G轮: TradingAgents 社区融合 — 完整代码模式

> 2026-06-21 · 棠溪交易系统 · `0cdaf8d`

## 借鉴来源

**TauricResearch/TradingAgents** — 87.7k stars · v0.2.5 · Apache-2.0
- 12-agent LangGraph 辩论网络 (Analyst→Researcher→Trader→Risk→PM)
- 结构化 Bull/Bear 辩论 + Judge 裁决
- Polymarket 预测市场 zero-key vendor
- 共享 Instrument Context + Persistent Memory Log

## 融入策略

只取**零 LLM 开销**部分:
1. 结构化 Bull/Bear 评分 (纯规则引擎，不调 LLM)
2. Polymarket 宏观桥 (免费公开 API)
3. 管线注入模式 (复用现有 enrich_engine_data + render_card_locked)

## 代码文件

### 1. `scripts/adversarial_analyst.py` (8KB · 对抗式分析)

```
adversarial_scoring(engine_data, symbol, results)
  → {
      bull_score: 6.2, bear_score: 5.4,
      bull_case: "VWAP反抽(8.0) · POC拒绝(6.0)",
      bear_case: "CVD背离(7.0) · 扫流动性回收(4.5)",
      bull_stress: "做多最大反证 — CVD背离(7.0)",
      bear_stress: "做空最大反证 — VWAP反抽(8.0)",
      divergence: 0.08, div_label: "低分歧 · 方向清晰",
      net: 0.8
    }

adversarial_text_for_card(adv) → "Bull 6.2 vs Bear 5.4 — 低分歧 · 方向清晰\n..."
```

核心规则:
- 按 bias ("多"/"空") 或 direction 拆分模型
- confidence × 10 缩放到 0-10 分
- 加权平均 (weight = confidence)
- 压力测试: 取最高 confidence 反向信号
- 分歧度 = abs(bull - bear) / max(bull, bear, 1)
  - <0.3 = 低分歧 (方向清晰)
  - <0.6 = 中分歧 (需催化剂)
  - ≥0.6 = 高分歧 (震荡格局)

### 2. `scripts/polymarket_bridge.py` (9KB · 预测市场桥)

```
get_polymarket_signal() → {
  _cached_at: ISO时间,
  markets: [10条过滤后市场],
  sentiment: {
    fed_cut_prob: 概率,
    recession_risk: 概率,
    crypto_signal: "乐观"/"悲观"/"中性",
    geo_signal: "紧张"/"缓和",
    summary: "一句话总结"
  }
}

polymarket_context_text() → "Polymarket — 地缘紧张 · 加密乐观"
```

数据源: `https://gamma-api.polymarket.com/events?closed=false&limit=30`
过滤: RELEVANT_TAGS (fed/衰退/通胀/地缘/加密/黄金/贸易/选举/原油/就业)
缓存: `data/polymarket_cache.json` · TTL 1h

### 3. 管线注入 (三步串联)

**Step 1**: `system_data_bridge.enrich_engine_data()` 调用 Polymarket:
```python
# 新增代码
from polymarket_bridge import polymarket_context_text
pm_text = polymarket_context_text()
ed.setdefault("polymarket", pm_text)
ed["_polymarket"] = pm_text
```

**Step 2**: `auto_card.render_card_locked()` 调用对抗分析:
```python
# 新增代码 (在 TV DMI 之后、渲染之前)
from adversarial_analyst import adversarial_scoring
adversarial = adversarial_scoring(engine_data, symbol, results)
engine_data["_adversarial"] = adversarial
```

**Step 3**: 渲染消费:
```python
# 环境段
f"⑦ 预测市场：{pm_text or '数据待采集'}"

# 博弈段
f"⑦ 对抗分歧：Bull {adversarial.get('bull_score', '?')} vs Bear {adversarial.get('bear_score', '?')} — {adversarial.get('div_label', '无数据')}"
```

## 模板变更

`references/master-template-v68.md` v6.9.14 → v6.9.15:
```
环境段:
   +⑦ 预测市场：{Polymarket宏观信号} — 衰退概率/降息概率/地缘/加密情绪
   +⑧ 对抗视角：Bull {n} vs Bear {n} — {低/中/高}分歧 · {方向}占优

博弈段:
   +⑦ 对抗分歧：Bull {n} vs Bear {n} — {低/中/高分歧} · {模型分组评分对抗}
```

## 验证 Bundle

```bash
# 模块语法 + 逻辑
python -c "from scripts.adversarial_analyst import adversarial_scoring; print('OK')"
python -c "from scripts.polymarket_bridge import polymarket_context_text; print('PM:', polymarket_context_text())"

# 卡片再生
python hermes/scripts/auto_card.py BTCUSDT
python hermes/scripts/auto_card.py XAUUSD

# 0 机器字段泄漏
grep -E "(setup_id|model_id|entry_tag|exit_tag)" data/auto_card_*.md || echo "0 leaks"

# 新字段存在
grep "预测市场" data/auto_card_BTCUSDT_full.md data/auto_card_XAUUSD_full.md
grep "对抗分歧" data/auto_card_BTCUSDT_full.md data/auto_card_XAUUSD_full.md

# pytest 全量
python -m pytest tests/ -q

# git 锁定
git status --short
git add -A
git commit -m "G轮: TradingAgents社区融合"
git push origin main
```

## 坑点

### 测试预期漂移
- `test_card_render_locked.py` 期望 `⑤ 模型`/`⑥ 评分`/`⑦ 决策`
- 渲染器实际产出 `⑤ 识别信号`/`⑥ 数据`/`⑦ 风险`
- 本会话修复: `⑤ 识别信号→⑤ 模型`（对齐模板）、测试期望更新为实际字段
- 教训: 每次改模板后必须跑全套 pytest，模板-渲染器-测试三方对齐

### 对抗评分在无模型结果时
- `adversarial_scoring()` 返回 `_empty_adversarial()`: bull=0, bear=0, div_label="无数据"
- 卡片渲染用 `.get()` 安全取值，不崩

### Polymarket API 不稳定
- 所有 `urllib.request.urlopen` 包在 try/except 中
- 失败时 `polymarket_context_text()` 返回 "获取失败"
- 缓存 1h 减少请求频率
- 不阻塞卡片生成主流程

## 未融入设计 (待定)

以下 TradingAgents 设计需要全 LLM agent 调用 (高 token 成本)，暂不融入:
- **12-agent LangGraph 辩论网络**: 全 LLM Bullish/Bearish Researcher → Judge → Trader
- **双模型分派** (deep_think vs quick_think): 我们已有 multi_model_engine 覆盖
- **Portfolio Manager + Simulated Exchange**: 我们是"人控驾驶舱"，不需要自动下单
- **Persistent Memory Log**: 我们已有 成交记录+成交复盘+策略治理 闭环

如未来做 LLM 辩论，可作为 cron agent:
```
cron agent "对抗辩论" (30m · 只在出卡前):
  prompt: "基于 engine_data，生成 Bull Case 和 Bear Case 各一段，给出裁决和置信度"
  context_from: [数据收集 job]
  model: deep_think_llm
保存 → 注入 auto_card 博弈段
```

## 通用社区融合模式

本会话摸索出的"借鉴开源 → 融入棠溪"三步法:

1. **学习**: 读 README + 源码 + docs (web_extract / GitHub)
2. **提取**: 只取**零成本可复用**的设计模式 (结构化评分 / 免费数据源 / 抽象概念)
3. **融入**: 三步串联 — bridge 增强 → renderer 新增 section → template 版本 bump

**铁律**: 
- 不融入需要全 LLM 调用的部分 (除非明确说要做)
- 不改变核心风控/决策逻辑
- 融入后必须验证: 卡片再生 + 0 leaks + pytest + commit