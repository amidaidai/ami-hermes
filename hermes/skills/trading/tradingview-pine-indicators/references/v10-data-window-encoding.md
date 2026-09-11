# v10 指标 Data Window 编码解码参考

> 历史记录（2026-08-31）：旧版编码参考；当前编码以 `tv_indicator_contract.py` 为准。

指标名称: `SVP+ICT+VWAP+EMA+CVD`  (v10 优化版, 2957行)
文件: `指标svp_v10_优化版.txt`
来源: Pine Script 源码 plot() 输出到 Data Window

## 编码字段速查

| Data Window 标题 | 解码公式 | 示例值 | 含义 |
|-----------------|----------|--------|------|
| `CVD Value` | 直接值 | −572.1 | 当前K线CVD值(负=卖压) |
| `CVD Slope` | 直接值 | −169.3 | CVD斜率(负=卖压加速) |
| `CVD Session (A*1e6+L*1e3+N)` | A=floor(V/1e6), L=floor(V%1e6/1e3), N=V%1e3 | 4,994,000 → A=4, L=994, N=0 | 亚/伦/纽三会话累积CVD(千位) |
| `SMT Div (2=多背离 -2=空背离)` | 2=多背离, -2=空背离, 0=无 | 0 | SMT跨品种背离 |
| `Magnet+ICT+Score (Mag*1e6+DistA*1e3+Score/1e3+ICT/1e6)` | Mag=floor(V/1e6), DistA=round(V%1e6/1e3×10)/10, Score=round(V%1e3×1e3), ICT=round((V-floor(V))×1e6-V%1e3/1e3×1e3) | 60,734,004,974.0 → Mag价=60,734, Dist=4.97ATR, Score=4, ICT=974 | 磁吸位价格×1e6+距离(ATR×1e3)+磁吸分/1e3+ICT编码/1e6 |
| `Magnet Score 0-100` | 直接值 | 47 | 磁吸评分(距离40%+新鲜度30%+优先级30%) |
| `ICT Count (Swept*100+Active)` | Swept=floor(V/100), Active=V%100 | 106 → 1扫+6活跃 | ICT扫线计数 |
| `Risk (R*1e4+D*1e2+W)` | R=floor(V/1e4), D=floor(V%1e4/1e2), W=V%1e2 | 10,306 → R=1%, D=3%, W=6% | 单笔风控/日止/周减 |
| `Eff Params (ATR*1e3+VWAP*1e2+CVD)` | ATR=floor(V/1e3), VWAP=floor(V%1e3/1e2), CVD=V%1e2 | 2,001.5 → ATR=2.0x, VWAP=0.0x, CVD=1.5wt | 有效止损倍数/延展阈值/CVD权重 |
| `Replay Side+Grade (Side*10+Grade)` | Side=floor(V/10) (1=多,-1=空,9=X,0=无), Grade=V%10 (3=A,2=B,1=C,-1=X,0=无) | 0 → Side=0无, Grade=0无 | 回放模式方向+等级编码 |
| `Replay Plan Price` | 直接值 | na | 回放入场计划价 |
| `Replay Invalid Price` | 直接值 | na | 回放失效价 |
| `Replay Stop(Dist*100+ATR)` | Dist=floor(V/100), ATR=V%100/10 | na | 回放止损距离+ATR倍数 |
| `Scores (Loc*100+Cfm*10+Ext)` | Loc=floor(V/100) [0-3], Cfm=floor(V%100/10) [0-6], Ext=V%10 [0-3] | 310 → Loc=3, Cfm=1, Ext=0 | 位置评分(关键位/VA内)+确认评分+延展风险 |
| `POC Price` | 直接值 | 59,773.1 | 分布图控制点 |
| `VAH Price` | 直接值 | 60,524.3 | 价值区上沿 |
| `VAL Price` | 直接值 | 59,126.6 | 价值区下沿 |
| `W VWAP Price` | 直接值 | 61,327.8 | 周VWAP |
| `M VWAP Price` | 直接值 | 63,636.6 | 月VWAP |
| `DO Price` | 直接值 | 59,772.0 | 日线开盘价 |

## Scores 解码详解

`Scores (Loc*100+Cfm*10+Ext)` = `locationScore * 100 + confirmScore * 10 + extensionRiskScore`

- **locationScore** (0-3):
  - 3 = 近关键位 (距 ATR*0.6 内 POC/VAH/VAL/VWAP/-B1/+B1/nPOC)
  - 2 = 近CVD关键位 (距 ATR*0.45)
  - 1 = VA内
  - 0 = VA外

- **confirmScore** (0-6):
  - CVD确认(合格) +2
  - 扫线/接受 +2
  - 接受(稳定收位) +1

- **extensionRiskScore** (0-3):
  - 3 = VWAP延展
  - 2 = DMI过热 或 结构冲突
  - 0 = 常态

## 行动格 v2 结构 (精简模式 9行)

右上角2列表格，左列字段名右列值：

| 行 | 字段 | 颜色规则 |
|---|------|---------|
| 0 | 结论 | 结论行: 风险=黄,多=绿,空=红,中性=白 |
| 1 | 方向 | 同上(含DMI验证词) |
| 2 | 进场 | 空=红,多=绿 |
| 3 | 止损 | 红 |
| 4 | 目标 | 绿 |
| 5 | 观察 | 灰 |
| 6 | 核对 | 全通过=绿,含✗=黄,其它=灰 |
| 7 | 今日 | 多=绿,空=红,中性=灰 |
| 8 | 磁吸上 | 绿 |
| 9 | 磁吸下 | 红 |

**方向行格式**: `{偏多/偏空/观望}  {HTF偏}{TF-dir}  {DMI验证词}`
DMI验证词: "顺多" / "顺空" / "走弱" / "过热" / "待定"

**结论行值映射** (源码 lines 2642-2671):
- "A多 回踩" / "A空 反抽" — A级信号
- "B多 轻仓" / "B空 轻仓" — B级等待
- "C多 等站回" / "C空 等跌回" — 反转等待
- "等空 反抽" / "等多 回踩" — C等待但倾向
- "观望" / 各种禁追 — X级

## 等级系统 (源码 lines 2404-2439)

| 等级 | 条件 | 含义 |
|-----|------|------|
| A多 | trendLongScore ≥ 8 + CVD确认 + 价在SWAP上 + VA接受 + HTF允许 + 非过热 + 位移确认 + PD非深溢价 + ADR空间足 | **强烈做多** |
| A空 | trendShortScore ≥ 8 + 对应空条件 | **强烈做空** |
| B多 | trendLongScore ≥ 6 + CVD允许 + HTF允许 + (近关键位或已扫线接受) | 轻仓等多 |
| B空 | trendShortScore ≥ 6 + 对应空条件 | 轻仓等空 |
| C反多 | reversalLongScore ≥ 6 + 扫低收回/CVD吸收/VAL回收 | 反转试探多 |
| C反空 | reversalShortScore ≥ 6 + 对应空条件 | 反转试探空 |
| C等待 | 以上均不满足 | 默认观望 |
| X | 过热+远离 / 结构冲突 / 高周冲突 / 低流动性 | 禁做 |

**等级稳定机制**: A级需连续 `GRADE_STABLE_BARS` 根K线保持同方向才激活。X级即时生效。

## 市场自适应引擎

源码 `var MARKET_ADAPTIVE_ENGINE = input.bool(true)` 自动调整:

| 市场 | 焦点 | 特殊处理 |
|-----|------|---------|
| 加密永续 | CVD+资金费率 | 硬CVD闸门(cvdHardGateMarket), 优先cvdConfirmQualified |
| 加密现货 | CVD+扫点 | 同上 |
| 贵金属 | DXY+ICT | 扫线反转加分更大 |
| 外汇 | VWAP+会话 | 同上 |
| 股票/指数 | SVP+VWAP | 量能权重更高 |

来源: 指标源码 line 2580 `focusHint` + lines 2384-2386 `cvdHardGateMarket`
