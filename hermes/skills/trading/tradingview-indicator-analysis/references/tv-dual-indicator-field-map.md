# 双指标字段映射 —— 已改为指针（不要再在本文件维护字段清单）

> 本文件旧版为 v1.2（2026-07-02），记的是**主 v5 / 副 v6、3163+469 行、旧 10 行行动格**的指标。
> 那份内容自 v13 起全部作废，且与权威源冲突——已清空，只留指针。
> 历史事故：字段清单曾在**三个地方**各存一份（本文件、`auto_card` 两处硬编码、`tv_data_bridge`），
> 互相对不上，导致主指标 13 行行动格只有 4 行能被卡片吃到。**不要重演。**

## 唯一权威（三处，不要另抄一份）

| 用途 | 位置 |
|---|---|
| 人读的字段映射 / 授权四态 / 分析流程 | `D:\Hermes agent\docs\tv-indicator-field-map.md`（v3.0+） |
| 代码唯一契约（改字段先改这里） | `D:\Hermes agent\scripts\tv_indicator_contract.py` |
| 对齐守卫 + 回归测试 | `scripts/tv_indicator_alignment_check.py`、`tests/test_indicator_alignment_20260911.py` |

## 定版指标（2026-09-11）

| 指标 | 上传名 | sha256[:24] | 行数 |
|---|---|---|---:|
| 主指标 | `SVP_主指标_空格修正_20260911.pine` | `68a34fc32da035880a0b332c` | 3557 |
| 副指标 | `AggVol_副指标_最终版_20260911.pine` | `c4c563ef4a08b77cb0ceb73f` | 966 |

仓内对应：`outputs/pine_20260905/SVP_audit_fixed17_20260910.pine`、
`outputs/pine_20260905/AggVol_audit_fixed14_20260910.pine`。

## 变更纪律

1. 指标改字段 → **先改 `tv_indicator_contract.py`**，再改消费方；禁止在消费方另写白名单。
2. 改完跑 `python scripts/tv_indicator_alignment_check.py`，退出码 0 才算对齐。
3. 本文件不再维护字段清单；需要细则看上面三处权威。
