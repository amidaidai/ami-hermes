# DMI 引擎集成验证模式

2026-06-22 v4.0-v4.2 实战：Python DMI 决策引擎对标 Pine 指标

## 架构

```
Pine指标(SVP+ICT+VWAP+EMA+CVD, 2024行)
  ├─ data_window plots → fetch_tv_data.cjs → BTCUSDT.P_tv_data.json
  ├─ Pine labels/lines → fetch_tv_data.cjs → JSON
  └─ Pine tables(决策表) → fetch_tv_data.cjs → JSON(tv_grade)

btc_alert_watch_v3.py
  ├─ load_data() ← JSON
  ├─ compute_dmi/atr (OHLCV from Binance API fallback)
  └─ compute_scores() → grade A/B/C/X (only A pushes)
```

## 验证清单（审计时逐项检查）

### 1. TV 桥数据健康
```bash
python -c "
import json
d=json.load(open(r'$APPDATA/BTCUSDT.P_tv_data.json'))
print('vwap:', d.get('vwap'), '> 60000?', d.get('vwap',0) > 60000)
print('ema9:', d.get('ema9'), '> 60000?', d.get('ema9',0) > 60000)
print('cvd:', d.get('cvd'))
print('poc:', d.get('poc'))
print('tv_grade:', d.get('tv_grade'))
print('labels:', len(d.get('labels',[])))
"
```
- VWAP/EMA/POC ≥ 60000 → BTC 数据（非 XAU 4,xxx 污染）
- tv_grade 非 None → Pine tables 捕获成功

### 2. DMI 引擎健康
```bash
python scripts/btc_alert_watch_v3.py
cat $APPDATA/detector_state.json
```
- grade 在 A/B/C/X 之一
- trend_long + trend_short 有效
- dmi_adx 非默认 50.0

### 3. 推送门控
- 仅 A grade 写入 `btc_pending.txt`
- B/C/X 静默（exit 0, 无 pending 文件输出）
- push cron 读取 pending 后清空

### 4. 格式校验
- 首行方向标注（↑做多/↓做空/○等待/×禁做）
- 无 emoji/表格/粗体
- ①②③ 中文编号

## 常见问题

| 症状 | 根因 | 修复 |
|------|------|------|
| VWAP=4,xxx 而非 6x,xxx | Pine 指标切品种后未重编译 | Pine Editor → Ctrl+S |
| tv_grade=None | fetch_tv_data.cjs 表读取失败 | 检查 CDP 连接 + JS 语法 |
| grade 一直 X | ADX ≥ 40 或 VWAP 延展 > 1.5xATR | 等待回调，非 bug |
| cron last_status=error 但手动跑 ok | cron 使用不同 python 解释器（缺依赖） | 检查 cron 脚本路径 + 环境变量 |
