---
name: xau-analysis-format
description: "Use when formatting BTC/XAU analysis cards. Follow the canonical verdict, timeframe labels and mobile-first layout."
---

> **同族导航** — 卡片组 4 个技能各司其职，别加载错 （同族入口：`tradingview-indicator-analysis`）
> · **本技能 `xau-analysis-format`** = 卡片格式细则（裁决措辞/周期标签/移动端布局）
> · 同族其余：`tradingview-indicator-analysis`（入口 · 分析卡主流程（多品种多周期、叙事驱动、5 段模板））、`tradingview-execution-card`（低周期执行卡（加密 15m / 黄金 5m，高周期限时继承））、`trading-card-generation`（卡片生成脚本（compact + full 双输出））
> · 组内改动请同步其余成员的触发词，避免同名族抢触发。


# 棠溪分析卡格式合同

## 权威入口

- 仓库：`D:/Hermes agent/docs/系统总览.md`。
- 字段/授权：`scripts/tv_indicator_contract.py`、`docs/指标驱动分析与策略合同.md`。
- 档位：`scripts/pipeline_router.py::ANALYSIS_TIERS`，不按对话次数私自降档。
- 渲染：`scripts/render_tv_card.py`、`scripts/render_v96.py`。

## 输出与档位

- 加密/黄金行情更新首行是本轮TV全屏截图，包含价格轴与CVD窗格，身份/周期/数据同轮核对。截图缺失写明未验证，不拿旧图、代码文件或其他品种代替。
- 中文日期与北京时间全角冒号；品种写 `BTCUSDT.P · BINANCE` / `XAUUSD · OANDA`。
- 首屏给品种·现价·方向·时段·唯一⭐主推或等待 ＋ 一行结构摘要。轻量档正文固定三节：**一、现在盯什么**（主观察位＋↑↓○三态应对表）／**二、关键位**／**三、多源**；标准/完整档把「多周期定位」插在「盯什么」之后；可复制骨架见 crypto-market-verification/templates/card-skeleton.md。触发/确认/失效/目标带并入「盯什么」与首屏，不再单独成段。
- 正文固定三张窄表、每表≤3列（盯什么/关键位/多源），数字列右对齐（`--:`），少长段落、同一事实只写一遍；完整卡正文 ≤40 行（v9.12，实测旧版 120 行）；详细来源矩阵与完整证据可另存报告，不压缩底层应采集数据。
- quick按路由只刷新执行层；standard显式标高周期继承及时间；full覆盖D/4h/1h/15m/5m；monitor仅事件。不把五周期强塞每次轻量刷新。
- 不用装饰分隔线；警报首行用↑↓○×直白结论，不用圈号开场。普通聊天不自动推TG。
- 卡末行固定为「**总结**」决策收束（等待/GO-A ＋ 触发 ＋ 作废线 ＋ 目标带）；源状态/TV-Binance 价差并入多源表，24h 与档位继承压成表下注脚一行，不占总结位。

## 裁决安全

- SVP是唯一结构授权来源，AggVol只能确认/降级/否决，FinalVerdict是唯一执行出口。
- 仅GO-A、executable=true、A等级方向一致、执行价格为有限正数且几何正确、R:R≥2，才显示执行三件套。
- 两条渲染路径复用 `render_tv_card.final_is_executable`；声明R:R及由三件套算出的R:R均须满足底线。非法/无穷/NaN不可放行。
- WAIT仅条件及获准的watch观察字段；NO-GO/X不显示候选价格。绝不能套用历史模板给C等待配两套可执行订单。
- 反向方案仅主推失效路径，不与主推平权。用户手动交易，不自动下单。
- 主侧R:R缺失/零/非法，不能借反侧或真值兜底变绿；单项R:R通过不等于最终裁决可执行。

## 结构位与数据语义

- 关键位表排序：上行位由近到远、下行位由近到远；每行标相对现价的 ±百分比（两位小数、工具计算不手算）。完整卡走 v9.12 角色制：先并簇（相邻 <0.15% 合成区间，如 `77,847–77,865`），再给 ≤4 行 `🔴上沿阻力簇 / 🟢近端转撑 / 🟢主观察 / 🟢失效·支撑带`，其余位与 24h 极值下沉「远端」注脚；现价落在簇内时该簇必须显示（`⚖ 现价所在带`），不得消失。
- 跨周期结构位保留来源周期，例如 `D·VAL`、`15m·VAH`、`15m·POC`，未知周期不猜造。
- VAH/VAL一致性仅在同品种、同周期、同来源快照/同价值区锚点比较。跨周期VAL高于VAH不构成价值区倒挂。
- 同组VAL>VAH降级为普通位并标数据不一致，不包装成有效价值区。
- 候选结构位与批准监控位分开；续期不是重新采集，更不是候选升格。
- 价格共识等级不是整体源健康度。卡片写“价格共识A（非全源健康度）”；来源状态看来源矩阵。
- 来源区分live/cache/stale_cache/unavailable/quota_cooldown以及not_run，不用默认中性数字假装采集成功。
- 路由步数、成功步骤、有效来源数是不同分母，禁止把11/15步骤写成11/15来源。
- 非加密禁套加密Funding/Taker/OI；XAU行情源身份与周期按当前代码元数据核验。

## 投递与验证

仅用户明确授权时走`telegram_reliable`的RichMarkdown真文本表，不能图片化表格或默认flush pending。投递须读回/回执验证，cron ok不等于送达。

验收至少覆盖：正常A、X+伪GO-A、WAIT、低R:R、缺主侧反侧高R:R、NaN/inf、反几何、跨周期价值区、同组倒挂、降级来源。源码测试不代表TV云编译或生产部署验收。

历史参考目录中的旧A/B对称订单、C等待给执行价、固定多表、自动外发等范例均不具备当前授权效力；发生冲突以本合同和仓库权威裁决合同为准。
