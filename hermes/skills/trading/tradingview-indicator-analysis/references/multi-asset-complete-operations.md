# Multi-Asset Complete Operations Rule (v6.9.2+)

## Core Iron Law (用户明确要求)
- **操作段必须完整**：无论资产类型，所有预案A/B 的操作段必须完整展开 **①-⑦**（方向、入场、风控、仓位、退出、轨迹）。
  - ① 方向
  - ② 入场 + 确认（至少2-3个触发条件）
  - ③ 风控（杠杆 + 止损 + 止盈1 + 止盈2，R:R ≥1:2 硬底线）
  - ④ 仓位（按资产单位：BTC/币、XAU/oz、 forex/手、stock/股、option/合约）
  - ⑤ 退出（失效条件 + 备用预案）
  - ⑥ 轨迹（前态 → 现态闭环）
- **其他段可精炼**：环境/结构/博弈/风控段允许简洁（一行一信号、`—` 破折号），但必须保留核心铁律（Sweep灵魂、CVD背离/吸收、Displacement、Kill Zone、Confluence 8/8、50-65%真实回测心态）。
- 禁止因简洁而压缩操作段。用户已多次纠正：操作要完整。

## Asset Classification & Adaptations

Use `_asset_class(symbol)` logic (see auto_card.py):
- **crypto** (BTCUSDT, ETHUSDT, etc.): Binance 100x (BTC/ETH) or 20x. Unit: 币种。止损距离参考400点(BTC)。
- **gold** (XAUUSD): Exness 1000x. Unit: oz。止损距离参考15点。
- **forex** (EURUSD, GBPUSD...): 按账户规则(通常50-100x)。Unit: 标准手/迷你手。止损距离参考0.0015。
- **stock** (AAPL, TSLA...): 按账户规则(1-5x或无杠杆)。Unit: 股。止损距离参考3点。
- **option**: 高杠杆注意时间价值衰减(Theta) + IV Crush。Unit: 合约。止损距离参考150点。**特别强调时间衰减和波动率骤降**。

杠杆/单位/仓位计算必须通过 asset_class 统一分支。

## Template Pointers
- 主模板：`references/master-template-v68.md`
- 通用完整操作示例：`references/universal_asset_card_v692_complete.md` (本会话产出，覆盖加密/贵金属/外汇/股票/期权)
- 每次出卡前必须 `read_file` 锁定当前模板。

## Verification
每次多资产模板变更后：
1. 重新生成代表卡片 (BTCUSDT + XAUUSD + EURUSD + AAPL 测试)
2. 确认操作段 ①-⑦ 全量、无机器字段
3. R:R ≥1:2
4. 价格反引号、纯序号、冒号对齐

## Pitfalls
- 不要把操作段简化成"B计划：等确认" — 用户明确要完整。
- 期权特别容易漏时间价值说明。
- 外汇需强调新闻闸门（非农、利率决议）。
- 股票需注意财报催化 + 成交量异常。
- 仓位计算必须传入 symbol 使用正确 _qty_unit / _leverage_text。

This rule was established during the 2026-06-20 multi-asset card completeness audit.