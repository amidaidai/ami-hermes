#!/usr/bin/env python3
"""COT Bridge v1.0 — 解析 cot_collector.py 输出，为 auto_card 提供 COT 摘要注入。

核心函数：
    read_cot_gold()   → 执行 `python scripts/cot_collector.py --line` 并解析输出
    cot_summary_line()→ 返回一行 "COT摘要：黄金{net_position}·美元{net_position}·{verdict}"

注意：cot_collector 已存在，本模块只解析其输出，不重写采集逻辑。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 路径设置 ──
ROOT = Path("D:/Hermes agent")
SCRIPTS_DIR = ROOT / "scripts"
COT_COLLECTOR = SCRIPTS_DIR / "cot_collector.py"


# ── 解析 cot_collector.py --line 输出 ──

# 示例输出：
# COT(2026-06-24): 欧元+12345多 · 日元-6789空 · 英镑+2345多 · 黄金+45678多 · 标普迷你+8901多 · 纳指迷你-2345空
# COT(2026-06-24): pip install cot_reports
# COT(2026-06-24): 无匹配品种

# 品种信号正则：名称+数字+方向
_SIGNAL_PATTERN = re.compile(r"([\u4e00-\u9fff]+)([+-]\d+)(多|空)")

# 日期提取
_DATE_PATTERN = re.compile(r"COT\((\d{4}-\d{2}-\d{2})\)")


def read_cot_gold() -> dict:
    """执行 `python scripts/cot_collector.py --line` 并解析输出

    返回格式：
        {
            "date": "2026-06-24",
            "raw": "COT(2026-06-24): 黄金+45678多 · ...",
            "signals": {"黄金": {"net": 45678, "direction": "多"}, ...},
            "error": None  # 或错误信息
        }
    """
    result = {
        "date": "",
        "raw": "",
        "signals": {},
        "error": None,
    }

    try:
        proc = subprocess.run(
            [sys.executable, str(COT_COLLECTOR), "--line"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(ROOT),
            encoding="utf-8",
            errors="replace",
        )
        output = proc.stdout.strip()
        result["raw"] = output

        if proc.returncode != 0 and not output:
            result["error"] = f"cot_collector 退出码 {proc.returncode}: {proc.stderr.strip()[:200]}"
            return result

        # 提取日期
        date_match = _DATE_PATTERN.search(output)
        if date_match:
            result["date"] = date_match.group(1)

        # 解析品种信号
        for match in _SIGNAL_PATTERN.finditer(output):
            name = match.group(1)
            net_value = int(match.group(2) + match.group(3).replace("多", "").replace("空", ""))
            # 重新计算：符号在数字前
            direction = match.group(3)
            net_str = match.group(2)  # e.g. "+45678" or "-6789"
            net_num = int(net_str)
            result["signals"][name] = {
                "net": net_num,
                "direction": direction,
            }

        if not result["signals"] and "error" not in output.lower() and "pip install" not in output:
            # 有输出但没解析到信号
            if "无匹配" in output:
                result["error"] = "无匹配品种"

    except subprocess.TimeoutExpired:
        result["error"] = "cot_collector 执行超时(30s)"
    except FileNotFoundError:
        result["error"] = f"cot_collector.py 不存在: {COT_COLLECTOR}"
    except Exception as e:
        result["error"] = f"执行异常: {e}"

    return result


def _verdict_from_signals(signals: dict) -> str:
    """根据黄金和美元信号生成 verdict"""
    gold = signals.get("黄金", {})
    # 美元可能在 COT 中显示为"美元指数"或通过其他品种推断
    # COT legacy 中没有直接美元，但 TFF 中有欧元/日元等
    # 这里用黄金方向 + 外汇整体方向综合判断

    gold_net = gold.get("net", 0)
    gold_dir = gold.get("direction", "")

    # 综合 verdict
    if gold_net > 50000 and gold_dir == "多":
        return "强势看多·投机多头拥挤"
    elif gold_net > 20000 and gold_dir == "多":
        return "偏多·投机净多增加"
    elif gold_net < -10000 and gold_dir == "空":
        return "看空·投机净空"
    elif gold_net < 0 and gold_dir == "空":
        return "偏空·投机小幅净空"
    elif gold_net == 0:
        return "中性·方向不明"
    else:
        return f"黄金{gold_dir}·净{abs(gold_net):,}"


def cot_summary_line() -> str:
    """返回一行 COT 摘要

    格式：COT摘要：黄金{net_position}·美元{net_position}·{verdict}

    注意：COT 报告中没有直接的美元持仓数据（美元在 DX 期货），
    这里用黄金 + 主要外汇净方向综合推断美元方向。
    """
    data = read_cot_gold()

    if data.get("error") and not data.get("signals"):
        return f"COT摘要：数据不可用（{data['error']}）"

    signals = data.get("signals", {})

    # 黄金
    gold = signals.get("黄金", {})
    gold_net = gold.get("net", 0)
    gold_dir = gold.get("direction", "—")
    gold_str = f"{gold_dir}{abs(gold_net):,}" if gold_net != 0 else "—"

    # 美元方向推断：COT 没有直接美元数据
    # 方法：通过欧元/日元/英镑的净方向反推美元
    # 欧元净空 → 美元净多（EURUSD 跌 = 美元涨）
    eur = signals.get("欧元", {})
    jpy = signals.get("日元", {})
    gbp = signals.get("英镑", {})

    # 美元指数推断：主要看欧元（权重57.6%）
    eur_net = eur.get("net", 0)
    if eur_net < -30000:
        usd_str = "美元净多(欧元大空)"
        usd_infer = "多"
    elif eur_net < -10000:
        usd_str = "美元偏多(欧元偏空)"
        usd_infer = "多"
    elif eur_net > 30000:
        usd_str = "美元净空(欧元大多)"
        usd_infer = "空"
    elif eur_net > 10000:
        usd_str = "美元偏空(欧元偏多)"
        usd_infer = "空"
    else:
        usd_str = "美元中性"
        usd_infer = "中性"

    # Verdict
    verdict = _verdict_from_signals(signals)

    # 日期
    date_str = data.get("date", "")
    date_tag = f"[{date_str}] " if date_str else ""

    return f"COT摘要：{date_tag}黄金{gold_str}·{usd_str}·{verdict}"


# ── CLI 入口 ──

if __name__ == "__main__":
    print(cot_summary_line())
