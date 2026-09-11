# 2026 六社区下单辅助优化清单

## 社区源与核心提取

| 源 | 搜索方向 | 核心提取 |
|---|---|---|
| ICT/SMC Medium (2026 30策略) | Displacement #1 过滤 · PD铁律 · KillZone · OTE 70.5% | Displacement 是质量闸门、溢价区不做多、折价区不做空 |
| Reddit r/Daytrading SMC/orderflow | Session CVD · VP · VWAP 三联核心 | 分会话CVD最受推崇、界面整洁不堆砌 |
| ATAS SMC 模板 (28K+订阅) | Delta + vPOC + 吸收 + 流动性 | 5m/15m执行TF、四件套缺一不可 |
| Bookmap CVD+冰山 | CVD背离 · 吸筹/派发 · stop-run | CVD背离是最可靠反转先导、关键位CVD平坦+价不动=吸收 |
| TradingView Session CVD脚本 | 亚/伦/纽三通道 · 四类背离 | 牛背离(price LL + CVD HL)、熊背离(price HH + CVD LH) |
| Freqtrade/X 2026 | ATR夹层止损 · 连亏缩仓 | 仓位管理向，非下单辅助核心 |

## 下单辅助优化优先级

### P0 — 下单前必须确认
1. **方向** (多/空) — actionBiasWord
2. **溢价/折价** — pdShort: 深溢价/溢价/折价/深折价。深溢价不做多、深折价不做空
3. **位移质量** — 核对行 `位移✓/✗`。无位移=假突破不追
4. **CVD背离** — 副指标流向行 `⚠卖背离/⚠买背离`。背离时追多/追空降级

### P1 — 情境感知
5. **KillZone活跃** — `⚡亚/⚡伦/⚡纽`
6. **待扫/已扫位** — `扫3/5`

### P2 — 深度验证
7. Session CVD 主导
8. 吸筹/派发检测
9. 时间紧迫度

## 行动格缩写规范

- KillZone: `⚡亚` `⚡伦` `⚡纽`（完整标保留在联动行）
- PD区: `深溢价` `溢价` `深折价` `折价`（均衡不显示）
- 扫位: `扫3/5`（已扫/剩余）
- DMI: 仅冲突状态（`过热`/`走弱`/`待定`），`顺多/顺空` 与方向重叠省略

## 方向行优化模式

```
原始:  偏多  EMA多头  · 溢价偏上  ⚡伦敦开盘  · 已扫3/剩5
冗余1: 偏多 + EMA多头(顺多) → 两个"多"重叠 → DMI同向省略
冗余2: panelDirVal含pdShort + f_pnl_row再追pdZone → 深溢价·深溢价
优化:  偏多  · 溢价  ⚡伦  扫3/5
```

## CVD背离检测公式（副指标）

```pine
// 价HH + CVD LH = 卖背离⚠
cvdBearDivA = high >= ta.highest(high, LB*3)*0.999 and sessCvdA < ta.highest(sessCvdA, LB*3)*0.95
// 价LL + CVD HL = 买背离⚠
cvdBullDivA = low <= ta.lowest(low, LB*3)*1.001 and sessCvdA > ta.lowest(sessCvdA, LB*3)*1.05
```

背离时用 cWarn 着色替代正常多/空颜色。

## 双指标协作铁律

- CVD背离时 → 以主指标为准（真Delta），副指标流向仅佐证
- 非加密品种 → 副指标自动隐藏，只看主指标
- CVD锚定周期 → 副指标与主指标对齐（日/周/月可选）
