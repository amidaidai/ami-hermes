# 核心测试指南 · 2026-06-18

## 运行

```bash
cd "D:/Hermes agent"
python -m pytest scripts/test_core.py -v --tb=short
# 24 passed in 0.03s
```

## 覆盖范围

| 测试类 | 数量 | 覆盖模块 |
|--------|------|----------|
| TestScoringEngine | 5 | 评分·CVD折扣·R:R违规·黑窗·极端恐慌 |
| TestRiskConstitution | 6 | 正常·超大·连亏·回撤·Kelly·无数据 |
| TestFiveModelMatcher | 5 | VWAP·VAL·突破·全量·R:R |
| TestHardStop | 5 | 仓位·多空·最小值·模拟·止盈 |
| TestRegimeClassifier | 3 | 低波·极恐·高波 |

## 添加新测试

1. 在对应 TestClass 中添加 `test_xxx` 方法
2. 用 `assert` 验证输出
3. 运行 `pytest scripts/test_core.py -v`

## 注意事项

- 所有测试依赖纯Python逻辑，不调用外部API
- 测试数据用 demo 值（不用实时市场数据）
- 边界条件必须覆盖（如 3.006% 仓位在 3% 上限的判定）
- R:R 检查、Kelly零数据、连续亏损熔断 必须写进测试 — 这些是生产中最容易出 bug 的地方
