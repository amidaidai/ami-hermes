#!/usr/bin/env python3
"""
棠溪 · 对抗式分析桥 v1.0
借鉴 TradingAgents: Bullish/Bearish Researcher 辩论 → Judge 裁决模式。

不做 LLM 调用的多层 agent（成本过高），而是基于现有 engine 输出
做**结构化 Bull/Bear 评分**：

输入: engine_data (multi_model_engine 的全量模型结果)
输出:
  1. Bull Case Score (0-10)
  2. Bear Case Score (0-10)
  3. Bull 压力测试: 做多面临的最大反证
  4. Bear 压力测试: 做空面临的最大反证
  5. 分歧度: abs(Bull - Bear) / max(Bull, Bear) → 低/中/高

核心设计:
  - 从多模型结果中自动拆分为 Bull-favoring 和 Bear-favoring 两组
  - 按 confidence 加权评分
  - 提取最高 confidence 的反向信号作为压力测试
  - 分歧度低 = 市场方向清晰 · 分歧度高 = 震荡/不确定
"""

from typing import Optional


def adversarial_scoring(engine_data: dict, symbol: str = "", results: list[dict] = None) -> dict:
    """基于引擎输出做 Bull/Bear 对抗评分

    Args:
        engine_data: multi_model_engine 的 engine_data 输出
        symbol: BTCUSDT / XAUUSD
        results: 模型结果列表 (可选，从 engine_data 提取)

    Returns:
        {
            "bull_score": 6,        # 0-10 做多理由评分
            "bear_score": 3,        # 0-10 做空理由评分
            "bull_case": "VWAP反抽(5)+POC拒绝(4): 多头结构完整",
            "bear_case": "CVD卖背离(4): 主动卖压",
            "bull_stress": "CVD卖背离未修复·假突破风险",
            "bear_stress": "结构多头排列·EMA多头阵营",
            "divergence": 0.45,     # 分歧度 0-1
            "div_label": "中分歧",  # 低/中/高
            "net": 3,               # bull_score - bear_score
        }
    """
    if results is None:
        results = []
        if engine_data:
            raw = engine_data.get("results", [])
            if hasattr(raw, "items"):
                raw = list(raw.items())
            for item in raw:
                if isinstance(item, tuple) and len(item) >= 2:
                    name, data = item
                    if isinstance(data, dict):
                        data["name"] = name
                        results.append(data)
                elif isinstance(item, dict):
                    results.append(item)

    if not results:
        return _empty_adversarial()

    bull_items = []
    bear_items = []
    neutral_items = []

    for r in results:
        name = str(r.get("name") or "")
        bias = str(r.get("bias") or r.get("direction") or "").lower()
        conf = float(r.get("confidence") or r.get("conf") or 0)
        action = str(r.get("action") or "")

        score = min(conf * 10, 10)  # 0-10 scale

        if any(x in bias for x in ("多", "long", "bull")) or any(x in action for x in ("做多",)):
            bull_items.append({"name": name, "score": round(score, 1), "conf": conf})
        elif any(x in bias for x in ("空", "short", "bear")) or any(x in action for x in ("做空",)):
            bear_items.append({"name": name, "score": round(score, 1), "conf": conf})
        elif conf > 0.01:
            # 中性但高 conf → 可视为一种方向信号
            neutral_items.append({"name": name, "score": round(score, 1), "conf": conf})

    # 加权计算 Bull/Bear Score
    bull_total = sum(m["score"] * m["conf"] for m in bull_items)
    bear_total = sum(m["score"] * m["conf"] for m in bear_items)

    bull_count = len(bull_items)
    bear_count = len(bear_items)

    # 防止除零
    if bull_total > 0:
        bull_score_raw = bull_total / sum(m["conf"] for m in bull_items)
    else:
        bull_score_raw = 0

    if bear_total > 0:
        bear_score_raw = bear_total / sum(m["conf"] for m in bear_items)
    else:
        bear_score_raw = 0

    # 缩放到 0-10
    bull_score = round(min(bull_score_raw, 10), 1)
    bear_score = round(min(bear_score_raw, 10), 1)

    # 压力测试: 找最高 confidence 反向信号
    bull_stress = _stress_text(bear_items, "做多", symbol)
    bear_stress = _stress_text(bull_items, "做空", symbol)

    # Bull/Bear Case 文本
    bull_case = _case_text(bull_items, "bull")
    bear_case = _case_text(bear_items, "bear")

    # 分歧度
    max_score = max(bull_score, bear_score, 1)
    divergence = round(abs(bull_score - bear_score) / max_score, 2)

    if divergence < 0.3:
        div_label = "低分歧 · 方向清晰"
    elif divergence < 0.6:
        div_label = "中分歧 · 需催化剂确认"
    else:
        div_label = "高分歧 · 震荡格局"

    net = round(bull_score - bear_score, 1)

    return {
        "bull_score": bull_score,
        "bear_score": bear_score,
        "bull_case": bull_case or "暂无做多模型触发",
        "bear_case": bear_case or "暂无做空模型触发",
        "bull_stress": bull_stress or "多头方向无显著反向信号",
        "bear_stress": bear_stress or "空头方向无显著反向信号",
        "divergence": divergence,
        "div_label": div_label,
        "net": net,
        "bull_models": bull_count,
        "bear_models": bear_count,
        "neutral_models": len(neutral_items),
    }


def _stress_text(items: list, target_direction: str, symbol: str) -> str:
    """从反向模型列表中提取压力测试文本"""
    if not items:
        return ""

    # 取最高 confidence 的 1-2 个反向信号
    items_sorted = sorted(items, key=lambda x: x["conf"], reverse=True)
    top = items_sorted[:2]

    parts = []
    for item in top:
        parts.append(f"{item['name']}({item['score']})")
    return f"{target_direction}最大反证 — " + " · ".join(parts)


def _case_text(items: list, direction: str) -> str:
    """构建 Bull/Bear Case 文本"""
    if not items:
        return ""
    items_sorted = sorted(items, key=lambda x: x["conf"], reverse=True)
    top = items_sorted[:3]
    parts = []
    for item in top:
        parts.append(f"{item['name']}({item['score']})")
    return " · ".join(parts)


def _empty_adversarial() -> dict:
    return {
        "bull_score": 0, "bear_score": 0,
        "bull_case": "暂无模型结果", "bear_case": "暂无模型结果",
        "bull_stress": "", "bear_stress": "",
        "divergence": 1.0, "div_label": "无数据",
        "net": 0,
        "bull_models": 0, "bear_models": 0, "neutral_models": 0,
    }


def adversarial_text_for_card(adv: dict) -> str:
    """生成可直接嵌入分析卡 博弈段 的文本

    格式:
      对抗分歧: Bull 6.0 vs Bear 3.0 — 低分歧 · 方向清晰
      Bull压力: CVD卖背离(4)未修复
      Bear压力: EMA多头排列完整
    """
    lines = []
    lines.append(f"Bull {adv['bull_score']} vs Bear {adv['bear_score']} — {adv['div_label']}")
    if adv.get("bull_stress"):
        lines.append(f"Bull压力 — {adv['bull_stress']}")
    if adv.get("bear_stress"):
        lines.append(f"Bear压力 — {adv['bear_stress']}")
    return "\n".join(lines)


# CLI 测试
if __name__ == "__main__":
    # 模拟测试数据
    mock_results = [
        {"name": "VWAP反抽", "bias": "多", "confidence": 0.8},
        {"name": "POC拒绝", "bias": "多", "confidence": 0.6},
        {"name": "EMA趋势", "bias": "多", "confidence": 0.55},
        {"name": "CVD背离", "bias": "空", "confidence": 0.70},
        {"name": "扫流动性回收", "bias": "空", "confidence": 0.45},
        {"name": "突破接受", "bias": "多", "confidence": 0.35},
        {"name": "费率反转", "bias": "空", "confidence": 0.25},
    ]
    engine_data = {"results": mock_results}

    adv = adversarial_scoring(engine_data, "BTCUSDT")
    print("  Bull/Bear 对抗评分")
    print(f"  ├─ Bull: {adv['bull_score']}/10 · {adv['bull_models']}模型 — {adv['bull_case']}")
    print(f"  ├─ Bear: {adv['bear_score']}/10 · {adv['bear_models']}模型 — {adv['bear_case']}")
    print(f"  ├─ Net: {adv['net']} · {adv['div_label']}")
    print(f"  ├─ Bull压力: {adv['bull_stress']}")
    print(f"  └─ Bear压力: {adv['bear_stress']}")
    print()
    print("  Cards嵌入文本:")
    print(f"  {adversarial_text_for_card(adv)}")
