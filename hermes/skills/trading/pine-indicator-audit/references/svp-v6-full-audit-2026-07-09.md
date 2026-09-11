# SVP v6_ready 全量审计 — 2026年7月9日

## 文件
- `SVP_v6_ready.pine` · SHA `e0c2e8b89ddd4d10` → `38e889f5a7eb8582`（修复 f_htf_fvg return）
- 2,860行 · 79,957 tokens · 186,300 chars

## 资源配额

| 资源 | 使用 | 上限 | 状态 |
|------|------|------|------|
| Token | 79,957 | 80,000 | ⚠️ 余量49 |
| request.security | 12 | 40 | ✅ |
| plot() | 24 | 64 | ✅ |
| alertcondition | 16 | 16 | ✅ 已满 |
| Data Window | 12 | — | ✅ |
| input | 252 | — | 分27组 |
| var | 70 | — | 可控 |
| for/while | 48 | — | 需实测性能 |

## 架构概览

7个type: NakedPOC / VolumeProfileEngine / VwapAccumulator / ICTLevel / SessionState / FVG / OBZone
51个函数, 10个array（全有cap+shift清理）

## Token 模块分布

| 模块 | Token | 占比 |
|------|-------|------|
| 头部+input(252个) | 14,412 | 18.0% |
| ICT函数 | 8,909 | 11.1% |
| 关键位/文本函数 | 9,047 | 11.3% |
| 评分/行动格 | 12,822 | 16.0% |
| VolumeProfileEngine | 5,788 | 7.2% |
| CVD delta+计算 | 5,111 | 6.4% |
| OB/BOS/CHoCH | 3,571 | 4.5% |
| FVG | 2,611 | 3.3% |
| LV | 1,190 | 1.5% |
| 行动格表格+MCP | 2,165 | 2.7% |

## FVG/OB 逻辑审计结论

FVG: 检测✅ HTF确认✅ 标签✅ MCP✅ 评分✅ 缓解✅
OB: 检测✅ HTF确认✅(仿FVG) 标签✅ MCP✅ 评分✅ 缓解✅
LV: 检测✅ 标签✅ MCP✅(StructPack位) 默认关✅

## 评分体系

```
setupTotalScore = clamp(0~10)
= locationScore(0~3) + confirmScore(0~8) + rrScore(0~2) - extensionRiskScore(0~3)
```

confirmScore 五路: CVD确认(2) + 扫线(2) + 接受(1) + OB(1) + OB-HTF(1) + FVG-HTF(1)
bcDirectRaw 含: inBullFvgHtf / inBullFvg / inBullOB / inBullBreaker / inBullObHtf

## 重绘审计

| req.security | lookahead | [1]偏移 | barstate.isconfirmed | 风险 |
|---|---|---|---|---|
| ADR | ✅ | ✅ | — | ✅ |
| HTF趋势确认 | ✅ | ✅ | — | ✅ |
| FVG HTF | ✅ | ✅(low[1]>high[3]) | ✅ | ✅ |
| OB HTF | ✅ | ⚠️(close>lsh无[1]) | ✅ | ⚠️P2加固 |

## 死代码（5个函数, 352 tokens）

| 函数 | 行 | Token | 调用数 |
|------|----|-------|--------|
| f_dist_text | L367 | 192 | 0 |
| f_score_text | L1922 | 42 | 0 |
| f_price_text | L1924 | 48 | 0 |
| f_strength_text | L1928 | 40 | 0 |
| f_level_short | L1677 | 30 | 0 |

注意: f_near 有9处调用, 不是死代码

## 可删项分级矩阵

| 级别 | 删什么 | 释放 | 删后余量 |
|------|--------|------|---------|
| 保守 | 死代码(352)+银弹(346)+Band2(314)+小项(430) | ~1,442 | ~1,491 |
| 中等 | +EMA单线input(565) | ~2,007 | ~2,056 |
| 激进 | +LV(1,152) | ~3,159 | ~3,208 |

推荐: 中等方案

## 社区对标

FVG 3K检测+位移过滤 = 社区标准
OB BOS触发回溯 = 社区标准
HTF确认 lookahead_on+barstate.isconfirmed = 官方推荐
Volume Profile+minBuckets = 超越社区多数
CVD三级星评+低位TF = 比社区更完善
MCP 12plot打包编码 = 社区无对标

## 本轮修复历史

1. Token超限 80485→79957 (tooltip截25+精简函数+内联循环)
2. type OBZone 移到 htfObList 之前 (编译错误)
3. f_htf_fvg return 回到函数末尾 (孤儿行修复)
4. LV OBZone.new 补第8参false (类型不匹配)
5. CW10002 × 4处 全局提取
6. OB HTF完整链路新增
7. BOS/CHoCH alerts删除4个(逻辑保留)