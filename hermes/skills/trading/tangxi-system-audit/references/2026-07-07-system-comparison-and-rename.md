# 2026-07-07 系统对比方法论 + 命名漂移修复（audit 补充）

本文件沉淀 2026-07-07「全方位优化+对比社区」会话的两类可复用模式：
①「全面检查我们的系统 vs 内置tangxi skill vs 社区标杆」的对比方法论
② 版本命名漂移（render_v8→render_v96）的修复模式

---

## 一、系统全面对比方法论（用户说「全面检查/对比社区/我们的系统」时产出）

**核心认知（2026-07-07 实测）**：棠溪系统 = Hermes 内置 `tangxi-*` skill 规格的**落地实现**。
- `tangxi-system-audit` / `trading-system-v95-plus-evolution` / `crypto-multisource-analysis` / `xau-analysis-format` / `skill-curation-tangxi` 是规格说明书
- 用户的 100+ 自研脚本（scripts/）是这些规格的工程落地
- 所以「系统对比」= ①规格(skill)与实现(脚本)一致性 + ②实现 vs 社区标杆差距

**对比四步法**：
1. **自研 vs 内置 tangxi skill**：`hermes skills list` 找 trading 类，核对每个规格是否有脚本落地。一致性高=健康。
2. **自研 vs 社区标杆**：
   - TraderMonty(667⭐)：股票/期权 Black-Scholes/Greeks → 我们已装 options-strategy-advisor 对齐
   - kukapay/crypto-skills：DeFi/Yield/土狗 → 定位不符不采用
   - Binance官方Skills Hub(13个)：期权/COIN-M/组合保证金/Algo → 需开户+API key
   - Hermes内置trading套件(35个)：我们即其落地
   - 能力矩阵：多源(10源)≥标杆；期权Greeks平；链上/回测/实时管道平；官方期权执行/美股FMP缺(主动边界)
3. **六市场能力完整度地图**：BTC/XAU=A，外汇/股/期=B(样本少)，期权=B(理论层新装)
4. **真实差距(非定位边界)**：①零真实成交校准(宪法P0-6自知，参数未校准) ②策略治理库空(rules:{}) ③外汇/股/期实战样本少

**评级输出**：架构完整性/数据链贯通/社区对标/实战校准/可维护性 五维评分，总评 A-。
**铁律**：对比结论必须区分「主动定位边界」(不开户/不碰美股/不碰DeFi)与「真实短板」(零成交校准)，不把边界当短板。

**XAU TV cron 接入（2026-07-07 用户批准）**：`hermes cron create "*/15 * * * *" --name "XAU TV现场同步" --script xau_tv_sync.py --no-agent --workdir "D:/Hermes agent" --deliver local` → 每15min刷真实五层，手动分析始终有 TV 现场数据。cron 总数 17→18（合并省3 + XAU同步+1）。

---

## 二、命名漂移修复模式（render_v8 → render_v96）

**问题**：`scripts/render_v8.py` 文件名/函数 `render_v8_card` 带 v8 残留，但内容已是 v9.6 渲染器（误导）。

**修复模式**：
1. `git mv scripts/render_v8.py scripts/render_v96.py`（保留 git 历史）
2. 函数 `render_v8_card → render_v96_card`
3. 全局搜调用方改：auto_card.py（from+call 两处）、regression_system_audit.py（from+call 两处）
4. docstring 误导说明清除
5. 验证：`grep -rn "render_v8" scripts/ --include="*.py"` 无残留 + `ast.parse` 三文件 + import 验证

**审计新增检查项**：`grep -rn "render_v8\|v8.0" scripts/ references/` → 发现旧版本名即标 P2 命名漂移。

**Pyright 误报处理**：动态 import（如 fetch_tv_mcp 的 set_symbol/set_timeframe）Pyright 可能报 unknown import symbol，但运行时正常——以实跑验证为准，不盲信静态检查。
