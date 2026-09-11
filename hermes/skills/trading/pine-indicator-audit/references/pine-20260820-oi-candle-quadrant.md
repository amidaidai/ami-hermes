# 20260820 OI K线(四象限蜡烛) + 行动格直白含义词

来源：20260820 会话。用户需求：①副指标加 OI K 线（官方数据、四象限配色）帮助判断"真买 vs 逼空"；②行动格表格加直白说明（用户不懂看 OI 线）；③主副指标联动同口径。

## 一、功能设计（已落地）

1. **副指标 OI K线**：`SHOW_OI_CANDLE` 开关（默认关，gp_act 组）。BINANCE 官方 `_OI` 的 OHLC 元组 → plotcandle 四象限蜡烛：
   - 色=价格窗口方向（priceUpA/priceDnA，与持仓行状态词同口径）：红=价涨段、绿=价跌段
   - 实体=本根 OI 增减（close>=open 实心=新仓、空心=平仓）
   - 红实=新多·真买、红空=空回补·逼空、绿实=新空·加空、绿空=多平仓·离场
   - 图例 label 挂在最后一根蜡烛上方："实心=新仓 空心=平仓 红=价涨 绿=价跌"
2. **持仓行含义词**：四象限词后直白翻译——新多·真买/空回补·逼空/新空·加空/多平仓·离场；开 OI K 线后行尾加"·实N/·空N"（连续新仓/平仓根数，N>=2，与 K 线实心/空心视觉同口径）。
3. **主指标 OI 行同款含义词**（f_panel_oi 的 oiRowText 四象限词），与副指标 K 线四象限同口径；压缩 f_panel_oi 注释块对冲 token（CE10117）。

## 二、Pine 技术坑（本次踩到，复用）

1. **三元不能返回元组**："Ternary operations cannot return tuples"（CE 编译错误）。修法：if/else 分支返回元组的函数包装（f_oi_ohlc_safe）。裸元组解构也不要在 if 块内对已有变量做（会触发 shadowing 警告×N）。
2. **plotcandle 的 display 参数三元只能是 input/simple 条件**：`display=SHOW_OI_CANDLE ? display.pane : display.none` ✓；`SHOW_OI_CANDLE and isCryptoA ? ...` ✗（isCryptoA 是 series → "Cannot call ... argument type" 编译错误）。非加密门控放数据层（f_oi_ohlc_safe 返回全 na 元组，蜡烛自然不画）。
3. **var int streak 的 [1] 历史引用**：bar0 上为 na，累加必须 nz()：`nz(oiKhSolidStreakA[1]) + 1`，否则首根永久 na。
4. plotcandle 计 4 个 plot 配额（TV 编译器口径）；静态扫描器不把 plotcandle 计入 plot 计数，人工 +4 核算。

## 三、配额影响（副指标）

- request：31/40（f_oi_ohlc_safe 顶层 1 次展开；开关关=函数内 if 走 else 分支、f_oi_ohlc 不调用 → 运行时 0 请求，20260814 request 语义实证的"函数未调用才真省"）
- plot：41+4(plotcandle)=45/64
- label：+1（默认 max_labels 50 内）
- 编译：translate_light 0 错 0 警（61,871 字符）

## 四、主指标 token 对冲

加含义词 ~110 字符，删 f_panel_oi 注释块 ~400 字符，净 -466 字节（241,774 < 基线 242,240），token 安全。

## 五、交付

桌面/hermes下载文件/OI K线四象限_20260820/：AggVol副指标_OIK线增强_20260820.txt、SVP主指标_OI含义词_20260820.txt（LF 行尾，旧版保留在各自历史目录）。
