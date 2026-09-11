# 模板权威链 & 管线文档审计（2026-08-29）✅ 全部修复完成

用户问「分析策略流程 + TradingView 模板有什么问题」时做的四 skill + 实码对照审计。
范围：tradingview-indicator-analysis / tradingview-execution-card / crypto-multisource-analysis / xau-analysis-format + `scripts/pipeline_router.py` 实码。

## 本次已修（2026-08-29 全部完成）

1. **P0-1 重复权威链 → 已删并修正**
   - 删掉 `tradingview-indicator-analysis` 里第一处混乱重复的「模板权威链」段落（35 行，含 3 次重复粘贴的表格行）
   - 保留的第二处权威链已修正：手动分析卡从「v8.0 叙事 5 段」改为「驾驶舱表格卡」，v8.0/V5.1/BTC精简卡统一降级为「存档」行
   - 现在全文件只有**一处**权威链声明，且与顶部 2026-07-02 警告完全一致

2. **P0-1 附带 v5.1 长卡模板 → 已移存档**
   - 139 行 v5.1 长卡模板从正文抽出，存到 `references/v5.1-legacy-longcard-template.md`（带「禁止作为当前输出格式」警告头）
   - 原位置只留一行指针

3. **P0-2 表数规格三方打架 → 三 skill 已统一**
   - `crypto-multisource-analysis` 的 11 项固定顺序前面加了「输出档位铁律」：默认三表速读，完整 8 表仅「完整/深度/出完整卡」时出
   - `xau-analysis-format` 的 v9.9 段落同步加了同一句话，并标注「三 skill 已统一」
   - `tradingview-indicator-analysis` 本身已有这句话，不动

4. **P1-3 周期写法 → 全局统一 `1D/4h/1h/15m/5m`**
   - 4 份 skill 主文件里所有裸 `D/4h`、`D→4h` 全部替换为 `1D` 前缀（perl 负向后行断言，不误伤已有 `1D`）
   - references/ 存档和其他 skill 不动

5. **P1-4 pipeline_router docstring → 已修**
   - `8步加密 / 5-6步其他` → `加密10步 / 黄金8步 / 外汇7步 / 股票8步 / 期货6步`
   - 实测验证：`route_pipeline()` 返回加密 10 步、黄金 8 步、外汇 7 步，与 docstring 一致

6. **P2-5 死步骤描述 → 已压缩**
   - `crypto-multisource-analysis` 里 Step 5b/5c/5d/5f（编号混乱、两个 Step 5b）共 102 行，压缩成一张「已并入 cron_read 数据源汇总表」（6 行表 + 注意事项），保留所有关键信息（替代方案、注意事项、参数陷阱）

## 改动量对照

| 文件 | 改前 | 改后 | 净变化 |
|------|------|------|--------|
| tradingview-indicator-analysis/SKILL.md | 1413 行 | 1246 行 | **-167 行** |
| crypto-multisource-analysis/SKILL.md | 1195 行 | 1108 行 | **-87 行** |
| xau-analysis-format/SKILL.md | ~596 行 | 600 行 | +4 行（加了统一声明） |
| pipeline_router.py | 312 行 | 312 行 | 仅 docstring 1 行 |

## 备份位置
四份原始文件都在各自目录下，后缀 `.bak-20260829`：
- `skills/trading/tradingview-indicator-analysis/SKILL.md.bak-20260829`
- `skills/trading/crypto-multisource-analysis/SKILL.md.bak-20260829`
- `skills/trading/xau-analysis-format/SKILL.md.bak-20260829`
- `scripts/pipeline_router.py.bak-20260829`

如果改后跑分析卡发现格式不对，直接 `cp .bak` 回去就行。

## 审计确认无问题（不要反向"修复"）

- 档位识别（分析=full / 看下=L1 / 现在呢=L2）skill 与 `resolve_analysis_mode` 实码一致。
- `route_pipeline` full ordered 列表是唯一干净真源。
- 追踪三层阈值（<0.2% / 0.2-0.5% / ≥0.5%）+ 每轮必拉 Binance 六件套（OI/费率/多空/Taker/depth），2026-08-29 规则本身写得清楚。