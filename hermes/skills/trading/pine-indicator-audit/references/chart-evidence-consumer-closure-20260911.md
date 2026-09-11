# 图表证据消费闭环（2026-09-11）

## 适用范围
当SVP/AggVol源码已经包含ICT、价格栏和Data Window字段，但Hermes还不能稳定把整张图纳入分析卡/FinalVerdict时使用。此流程不修改Pine源码。

## 证据分层

1. 先跑源码哈希、plot标题、行动格行名/顺序对齐检查。
2. 现场核对TV身份：symbol、resolution、study列表；BTC主执行必须为`BINANCE:BTCUSDT.P / 15m`，5m只作触发。
3. 优先读取已有Data Window字段：StructPack、TriggerPack、EvidencePack、FVG/OB质量、Entry Valid。
4. 再读取lines/boxes/labels/tables；空返回只表示当前接口没有结构化读回，不能推断源码没有ICT。
5. 同现场截图做视觉核验，但截图不能单独升级执行授权。

## 标准对象

统一生成`chart_evidence`：

- `status`: `verified` / `partial` / `identity_mismatch` / `unavailable`
- `identity`: symbol、timeframe、study列表
- `price_context`: last、OHLC、日高/日低、complete
- `levels`: 价格线
- `ict`: FVG、OB/Breaker、BOS/MSS/CHoCH标签、流动性、StructPack存在性

## 安全闸门

- `identity_mismatch` → `NO-GO`。
- `partial`、`visual_only`或ICT结构化证据不完整 → 只能`WAIT`，不能升级`GO-A`。
- WAIT/NO-GO清空执行Entry/Stop/Target，只保留明确标注的人工观察候选。
- SVP是方向/执行授权源；AggVol只确认、降级或否决；图表证据不能越权。
- 不为消费层缺口新增并行ICT指标；先消费现有StructPack/Pack字段和图表对象。

## 验收

```text
python scripts/indicator_source_audit.py
python scripts/tv_indicator_alignment_check.py
python -m pytest tests/ -q
```

分析卡应展示图表证据状态、价格栏OHLC/现价、ICT对象摘要；缺失时明确“只观察，不升级GO-A”。

## 边界

源码合同通过且源码已有FVG/OB/BOS/MSS/流动性/StructPack，但TV对象接口空时，结论是消费适配或现场证据不完整，不是指标必须修改。标记`partial`，继续寻找已验证的消费路径；不要用视觉猜测填结构化字段，也不要把一次空返回写成永久工具故障。