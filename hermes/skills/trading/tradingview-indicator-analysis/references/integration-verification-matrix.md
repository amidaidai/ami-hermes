# GitHub 融合验证矩阵 · 五级标准 · 2026-06-18

## 五级标准

融合开源项目时，必须逐级验证，不可跳过：

| 级别 | 含义 | 验证方法 |
|------|------|----------|
| ① 代码存在 | 文件写入磁盘 | `os.path.exists()` |
| ② 逻辑正确 | 语法通过+逻辑合理 | `py_compile.compile(doraise=True)` |
| ③ 实弹跑通 | 真数据喂入输出合理 | 用 Binance K线/实时TV数据测试 |
| ④ 已接入管线 | 调用方代码已修改 | `grep` 确认 import + 调用 |
| ⑤ 产生信号 | 输出影响交易决策 | 全链路测试：数据→分析→操作 |

## 2026-06-18 融合结果

```
模块                  ①代码  ②逻辑  ③实弹  ④接入  ⑤信号  结论
smc_structure_detector  ✅    ✅     ❌     ❌     ❌   pandas 2.x bug·已删
scoring_engine          ✅    ✅     ✅     ✅     ✅   真正有用
risk_constitution       ✅    ✅     ✅     ✅     ✅   真正有用
five_model_matcher      ✅    ✅     ✅     ✅     ✅   真正有用
regime_classifier       ✅    ✅     ✅     ✅     ✅   真正有用
structure_detector      ✅    ✅     ✅     ❌     ❌   待接入
hard_stop               ✅    ✅     ✅     ❌     ❌   基础完成·实盘需MCP重启
freqtrade_integration   ✅    ✅     ❌     ❌     ❌   无Docker·已删
test_core               ✅    ✅     ✅     ✅     ✅   24/24通过
```

## 核心教训

- **逻辑正确 ≠ 已接入**：4个模块代码/逻辑/实弹全过，但全部未接入现有管线。必须改调用方代码 + 语法检查 + 全链路测试才算接入。
- **删除比保留好**：SMC库 1348行代码有 bug，Freqtrade 需要 Docker — 与其保留半成品，不如删了用简单方案替代。
- **测试先行**：写 test_core.py 后才敢放心改边界条件。没有测试的修改是盲改。
