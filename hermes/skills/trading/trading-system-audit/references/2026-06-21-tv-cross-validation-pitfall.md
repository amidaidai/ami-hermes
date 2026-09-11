# TV Indicator vs auto_card Value Discrepancy (2026-06-21 实测)

## 症状

TV `data_get_study_values()` 返回的 SVP 指标值（VAH/VAL/POC/EMA）与 auto_card 从 K 线计算的值存在显著差异。

## 实测数据

| 字段 | TV SVP 值 | auto_card 值 | 差值 |
|------|----------|-------------|------|
| VAL   | 64,136   | 63,871      | 265点 |
| VAH   | 64,387   | 64,568      | 181点 |
| POC   | 64,213   | 64,215      | 2点（OK） |
| EMA9  | 64,079   | 64,217      | 138点 |

## 根因

- TV SVP 用 **session 内 tick 累计量** 计算价值区（精确到每次成交的价格-量分布）
- auto_card 用 **K 线 OHLC** （Yahoo/Binance K 线）做简化 TPO 近似
- 低流动性时（周末）K 线 OHLC 近似误差放大，偏差可达 200+ 点
- EMA 差异来自收盘价源不同（TV 用实时 tick，auto_card 用 K 线 close）

## 影响

- 若 auto_card 的 VAL 偏了 265 点：整个价值区判断（回收/突破/拒绝）全错
- 若 auto_card 的 EMA 偏了 138 点：排列判断（多头/空头）可能错
- TV 是棠溪价格主源 → TV 值为准

## 审计步骤

1. `mcp_tradingview_data_get_study_values()` 拉 SVP 当前值
2. `read_file("data/auto_card_BTCUSDT.md")` 读 auto_card 输出
3. 逐项对比 VAH/VAL/POC/EMA9/EMA21/EMA34/EMA55
4. 任何 >100 点差异 → P1 标记，写审计报告
5. 短期修法：出卡时在注释标注"TV VAL=`{tv_val}`·自动卡VAL=`{card_val}`"
6. 长期修法：auto_card 直接读 TV study_values 而非自己算价值区

## 辅助判断：CVD 恶化检测

两次读 TV CVD 值（间隔 10+ 分钟）：
- CVD 从 -2,062 → -3,795（50分钟内，+84%）→ 卖出加速
- 斜率从 -710 → -2,066（+191%）→ 急跌模式

此检测可写入极简卡作为辅助标注。

## XAU 特殊陷阱

自动卡 XAU 的 4h 失效线若显示 4,292（当前金价 4,157，差 135 点）:
→ 数据来自 Yahoo GC=F 期货的跨期异常价（非当前主力合约价）
→ 必须降权或跳过，不能直接用于风控
