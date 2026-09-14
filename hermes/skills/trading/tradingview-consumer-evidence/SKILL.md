---
name: tradingview-consumer-evidence
description: Use when consuming TradingView evidence.
category: trading
---

> **同族导航** — TV证据组 5 个技能各司其职，别加载错 （本技能 = 入口）
> · **本技能 `tradingview-consumer-evidence`** = 入口 · 消费 TV 证据的总口径（什么算已验证）
> · 同族其余：`tradingview-state-integrity`（共享图表状态一致性（身份/周期/指标/同轮一致））、`tv-raw-plot-evidence`（packed 值丢精度时读原始 plot）、`tv-raw-study-evidence`（读原始 study 数值证据）、`pine-indicator-audit`（Pine 源码审计（正确性/配额/面板/合同/消费方核验））
> · 组内改动请同步其余成员的触发词，避免同名族抢触发。


# TradingView消费层证据

用于TradingView Desktop/CDP与后台采集器共用图表的加密分析消费层。目标是让“看完整张图”真正进入缓存、决策和分析卡，同时保持fail-closed：结构证据缺失时降级，不猜测、不伪造实时性。

## 核心原则

1. **实际状态优先于请求参数**：`chart_set_symbol`、`chart_set_timeframe`返回成功不等于生效。操作后必须读回`chart_get_state`，同时核对symbol、resolution和studies。
2. **报价身份必须验证**：TV CLI部分版本会忽略`quote --symbol`，返回当前图表报价。优先读取不带symbol的quote，并检查返回的symbol、exchange、type、description。BTC永续应匹配Binance、swap和Bitcoin描述；身份不符时整份报价丢弃。
3. **保留同一次响应的价格栏**：缓存O/H/L/C/last；日高、日低必须来自独立的Binance 24h ticker，不能用当前15m K线高低冒充。
4. **ICT对象不得凭价格猜类型**：box接口可能返回`boxes`或规范化的`zones`。兼容两种键；无label的区域只能叫通用zone，不能擅自标为FVG、OB、Breaker或流动性扫掠。
5. **空读是争用/重算信号**：`study_count=0`或行动格暂空时，只在图表身份仍正确的前提下有界重试；身份变化立即停止并标记stale。不得用别的周期或旧缓存冒充当前周期。实测切周期后指标常需 **8–12s** 才重算完（只等 2–3s 必然读到空表）；`pine_tables` 与 `study_values` 会同时空，两者都要重试；**读完仍空才写「继承高周」，不得把第一次空读直接当继承**。
6. **证据等级与执行权限分离**：`verified`表示身份、周期、研究、价格栏和结构化证据通过，不表示每种ICT子类型都有分类结果。`partial`、`visual_only`、`unavailable`最多支持WAIT；identity mismatch必须NO-GO。只有SVP、AggVol和FinalVerdict决定执行权限。
7. **独立源不可重复计数**：TV价格与Binance价格用于交叉校验；LSR等若是同源复制，不得写成两个独立确认。正常小价差不否决，品种错配、数量级异常、时间周期错配必须降级或硬阻断。

## 标准采集顺序

1. 获取TV health/state。
2. 必要时切换品种和主周期；再次读回实际symbol/resolution/studies。
3. 等指标重算；空表/空值按重试协议处理。
4. 读取主、副行动格、study values、lines、boxes、labels、TV报价。
5. 读取独立Binance 24h ticker、mark/index/funding等公开衍生品数据。
6. 建立`chart_evidence`与`binance_cross_validation`，记录各自来源、状态和时间。
7. 将证据传入FinalVerdict和卡片；不得绕过裁决层直接从证据生成Entry/Stop/Target。
8. 生成与最终身份一致的全屏截图；后台采集结束后核验用户图表归属。

## 推荐缓存形状

```json
{
  "chart_evidence": {
    "status": "verified",
    "identity": {"symbol": "BINANCE:BTCUSDT.P", "timeframe": "15"},
    "price_context": {"last_price": 0, "open": 0, "high": 0, "low": 0, "close": 0, "day_high": 0, "day_low": 0},
    "ict": {"fvg": [], "ob": [], "zones": [], "structure_labels": [], "liquidity": []}
  },
  "binance_cross_validation": {"status": "live", "cross_status": "aligned", "tv_price_delta_pct": 0.0}
}
```

`fresh=false`或`stale=true`不得作为实时交易授权。证据状态必须在卡片中可见，避免把读取失败伪装成指标没有信号。

## 参考资料

- `references/tv-consumer-evidence-and-binance-crosscheck.md`：CLI报价参数忽略、zones兼容、价格栏和独立Binance校验的现场规则与验收要点。
