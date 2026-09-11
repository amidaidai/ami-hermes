# 数据管线健康审计方法 v1.0

◷ 2026-06-21 · 从全面审计实战中提炼

## 问题

渲染的卡片看起来像完整分析，但内容大量是占位符（N/A、数据待采、无数据、CVD ?、裸POC ?）。

根因不是模板渲染，而是**数据管线喂入渲染器的内容**。

## 审计三步法

### Step 1: 出卡 + 逐行读卡

```bash
python hermes/scripts/auto_card.py BTCUSDT
python hermes/scripts/auto_card.py XAUUSD
read_file data/auto_card_BTCUSDT.md
read_file data/auto_card_XAUUSD.md
```

### Step 2: 占位符扫描

```bash
grep -E "(N/A|数据待采|无数据|CVD \?|裸POC \?|方向不明/震荡|——|待采集)" data/auto_card_*.md
```

**P0 占位符（必须为 0）：**
- `4h背景：数据待采` / `4h背景：无数据` → 4h K线管线断裂
- `VAH \`—\` · POC \`—\` · VAL \`—\`` → 价值区计算失败
- `5m 当前无数据` / `1h 当前无数据` → K线采集失败
- `Taker N/A` → Taker API管线断裂

**P1 占位符（允许周末/低频出现）：**
- `CVD ?` → CVD采集降级
- `裸POC ?` → POC计算缺数据

### Step 3: 管线断点诊断

| 占位符 | 数据来源 | 诊断命令 |
|--------|---------|---------|
| 4h=无数据 | Binance K线 / Yahoo GC=F | 检查 `_collect_binance_data` 或 XAU kline采集 |
| VAH/POC/VAL=空 | K线数据无vah/poc/val键 | 检查 `_collect_binance_data` 的kline dict构造 |
| Taker=N/A | Binance futures/data API | 检查HMAC签名+端点路径 |
| XAU周期=无数据 | gold-api/Yahoo GC=F | 检查金十API被墙→Yahoo回退 |

## 已修复的常见断点

1. **Taker API路径错误**: `/fapi/v1/takerlongshortRatio` → `/futures/data/takerlongshortRatio`（需HMAC签名）
2. **4h direction缺失**: `_kl_bias` 期望 `k.get("direction")` 但kline dict只有 `description` → 从description提取
3. **VAH/POC/VAL缺失**: kline dict构造不包含这些键 → `_collect_binance_data` 中追加poc/vah/val计算
4. **XAU K线被覆盖**: `_collect_binance_data` 无资产判断 → 覆盖Yahoo已采集的XAU K线 → 加 `if "XAU" in symbol: return`
5. **数据等级通胀**: Taker C级但总体标A → `_effective_grade()` 木桶原理降级
