# QLib 因子库接入 (2026-06-29)

## 概述

从微软 QLib alpha360 提取 30 个经典技术因子，纯 Python 实现（零 numpy 依赖），
注入 pipeline_integration.py 的分析卡输出。

## 脚本

`scripts/qlib_factors.py` (12KB)
Cron: `fd78e36de132` 每30min，no_agent，投递 TG:846

## 30 因子分类

| 类别 | 因子 | 说明 |
|------|------|------|
| 动量 | KMID, KLEN, RSV, KDJK, KDJD, ROC6, ROC20, RSI, MACD, DIF | 价格位置·变化率·趋势强度 |
| 波动率 | ATR, BBW | 真实波幅·布林带宽 |
| 成交量 | VEMA5, VEMA20, VRATIO, VSTD | 量能均线·量比·量波动 |
| 趋势 | MA5_DEV, MA60_DEV, MOM5, MOM20 | 均线偏离·价格动量 |
| 相关性 | CORR_VP | 量价20期相关性 |
| 流动性 | ILLIQ, TURN | Amihud非流动性·换手率 |
| 形态 | SHADOW | K线影线比 |
| 综合 | SIGNAL_SCORE, SIGNAL_BIAS | -5到+5多空评分·方向 |

## 注入 pipeline_integration.py

`generate_analysis_card()` 末尾追加：
```
因子 ↓ neutral(-1/5) | RSI50 MACD+99.8
DMI ADX13.0 | 震荡
```

因子数据从 `~/AppData/Local/hermes/data/qlib_factors.json` 读取。
若文件不存在或读取失败，静默跳过（不阻塞卡片生成）。

## 评分逻辑

多空评分（SIGNAL_SCORE）：
- KMID > 0.7 → +1, < 0.3 → -1
- RSI > 60 → +1, < 40 → -1
- MACD > 0 → +1, else → -1
- ROC6 > 0 → +1, else → -1
- MA5_DEV > 0 → +1, else → -1
- ≥3 → bullish, ≤-3 → bearish, else → neutral
