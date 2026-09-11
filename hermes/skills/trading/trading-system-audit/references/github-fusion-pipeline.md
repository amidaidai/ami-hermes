# GitHub 融合管线 · 已验证模块（2026-06-18）

## 融合方法论

```
五级验证：代码存在 → 逻辑正确 → 实弹跑通 → 已接入管线 → 产生信号
   L1 ✅      L2 ✅       L3 ✅       L4 ✅          L5 ✅  ← 真正有用
   L1 ✅      L2 ✅       L3 ❌       —             —      ← 花架子·删
```

## 已验证的4个真有用模块

### 1. 评分引擎 → `auto_card.py`
- **文件**: `scripts/scoring_engine.py`
- **接入点**: `auto_card.py` L163 Step 6b
- **输出**: 14分加权评分 + 等级 + 逐项明细 + 风控违规
- **验证**: 实弹跑通 7.5/14 🥈A · 自动检测 R:R 违规 + 仓位超标

### 2. 风险宪法 → `行情守望.py`
- **文件**: `scripts/risk_constitution.py`
- **接入点**: `行情守望.py` L824 · `risk_gate()` 覆盖率
- **输出**: Kelly仓位建议 + 日回撤5%熔断 + 连亏3暂停 + 新闻黑窗
- **验证**: Kelly $2.03 · 当前仓位超标→降级轻仓 $1.01

### 3. 五模型匹配 → `智能更新结构.py`
- **文件**: `scripts/five_model_matcher.py`
- **接入点**: `智能更新结构.py` L92 · `build_levels_v2()`
- **输出**: VWAP反抽/VAH回收/VAL回收/POC拒绝/扫流动性回收/突破接受
- **验证**: VWAP反抽做空 @64283 · R:R 3.3 · 位信78
- **退化**: TV数据不可用时降级到原 `build_levels()` 硬编码

### 4. 市场体制 → `auto_card.py`
- **文件**: `scripts/regime_classifier.py`
- **接入点**: `auto_card.py` L163 Step 6b 博弈段
- **输出**: 6种体制分类 + VIX + F&G极端修正
- **验证**: LOW_VOL_BEAR · F&G=15极恐 ⚠底部博弈

### 5. 结构检测（独立可用）
- **文件**: `scripts/structure_detector.py`
- **输出**: 摆动高/低点 · 支撑/阻力聚类 · 位信评分
- **限制**: 需≥200根K线才有效（<50根= C/50）
- **替代**: 替换不可用的 SMC 库

## 已删除的2个花架子

### ❌ smart-money-concept (Prasad1612)
- **原因**: pandas 2.x `assignment destination is read-only`
- **处理**: 删除库+适配层，替换为 `structure_detector.py`

### ❌ freqtrade_integration
- **原因**: 需Docker，当前环境无
- **处理**: 删除集成脚本，保留5模型策略模板 `hermes/strategies/*.py`

## 接入禁区

- **不要未验证就宣称"已接入"** — 必须改管线代码 + 语法检查 + 全链路测试
- **不要修不兼容的库** — 删掉自己写纯Python替代更快更稳
- **GitHub有星≠可运行** — 先跑5行最小验证再写适配层
