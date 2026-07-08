#!/usr/bin/env python3
"""
棠溪 · 作战室融合报告 signal_confluence.py v1.0

目标：把已有 5 大源的"单源信号"融合成【单资产总评分】，解决 11 个 collector
各自推送、无跨源融合的缺口（参照 signalsGURU 三阶段融合置信引擎）。

融合源 + 权重（满分 10）：
  - Orion      : 单品种置信(本就含 OI/费率/主动买卖/跨所确认) → 直接取 0-10 主权重
  - QLib 因子  : compute_factors SIGNAL(-5~+5) → 映射 0-5
  - Deribit    : C/P 比偏多空(+2 / -2 / 0)
  - X情绪FOMO   : fomo_score(0-5) 过热反向减分(+2 / -2 / 0)
  - 稳定币流向  : 边际增量(+1) / 减量(-1) / 持平(0)
  - 恐惧贪婪    : 极端值(<25>75) 反向权重(+1 / -1 / 0)

输出：RichMarkdown 真表（每源一行：信号·权重·符号）+ 融合总评分 + verdict +
      supporting_sources 列表 + 简洁总体结论。推 846 情报群。

不触发任何子 collector 的 TG 推送（只 import 纯数据函数）。
"""
from __future__ import annotations
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import os
import json
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
REPO = Path("D:/Hermes agent")
SCRIPTS = REPO / "scripts"
DATA_DIR = Path(os.path.expanduser("~/AppData/Local/hermes/data"))
sys.path.insert(0, str(SCRIPTS))

# ───────────────────────────── 轻量取数 ─────────────────────────────
def _get(url, timeout=10, retries=2):
    last = None
    for ph in [None, {}]:
        for _ in range(retries):
            try:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler(ph)) if ph is not None else urllib.request.build_opener()
                req = urllib.request.Request(url, headers={"User-Agent": "Hermes/1.0"})
                with opener.open(req, timeout=timeout) as r:
                    return json.loads(r.read().decode("utf-8", "replace"))
            except Exception as e:  # noqa: BLE001
                last = e
                continue
    return None


def fetch_stablecoin_flow() -> dict:
    """读 stablecoin_snapshot.json 计算边际流向（自写，不触发 stablecoin_collector.main）。"""
    fp = DATA_DIR / "stablecoin_snapshot.json"
    try:
        cur = json.loads(fp.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"delta_b": 0.0, "total_delta": 0, "note": "无历史快照"}
    prev_fp = DATA_DIR / "stablecoin_prev.json"
    try:
        prev = json.loads(prev_fp.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        prev = {}
    cur_total = sum(c.get("now", 0) for c in cur.values() if isinstance(c, dict)) if isinstance(cur, dict) else 0
    prev_total = sum(c.get("now", 0) for c in prev.values() if isinstance(c, dict)) if isinstance(prev, dict) else 0
    total_delta = cur_total - prev_total
    delta_b = total_delta / 1e9
    # 落盘当次为下次 prev
    try:
        prev_fp.write_text(json.dumps(cur, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return {"delta_b": delta_b, "total_delta": total_delta,
            "note": "增量=潜在买盘" if total_delta > 0 else "减量=撤资信号" if total_delta < 0 else "持平"}


# ───────────────────────────── 融合引擎 ─────────────────────────────
def fuse() -> dict:
    """返回 {symbol, score, verdict, sources:[{name,sig,w,emoji}], concl}。"""
    sources = []  # {name, sig, w, emoji, detail}

    # Orion 主权重（取最高置信候选作动量贡献，主品种锚定 BTC）
    orion_sym = "BTCUSDT"
    orion_conf = 0.0
    orion_detail = "未扫描"
    try:
        import orion_screener_radar as o
        bn = o.fetch_orion("binance")
        if bn:
            cands = o.detect_anomalies(bn, "Binance")
            if cands:
                cands = [o.compute_confidence(c) for c in cands]
                cands.sort(key=lambda c: c.get("confidence", 0), reverse=True)
                top = cands[0]
                orion_top_sym = top.get("symbol")
                orion_conf = float(top.get("confidence", 0))
                orion_detail = f"{orion_top_sym} 信{orion_conf:.1f}"
    except Exception as e:  # noqa: BLE001
        orion_detail = f"扫描异常:{e}"
    # Orion 已是 0-10 量级，直接作主评分基底
    sources.append({"name": "Orion雷达", "sig": orion_detail, "w": round(orion_conf, 1),
                    "emoji": "🟢" if orion_conf >= 6 else "🔸" if orion_conf >= 4 else "⚪",
                    "detail": "量价异动+跨所确认" if orion_conf >= 4 else "无异动"})

    # 2) QLib 因子（BTC 1h）
    qlib_bias = "观望"
    qlib_w = 0.0
    try:
        import qlib_factors as q
        kl = q.fetch_klines("BTCUSDT", "1h", 200)
        f = q.compute_factors(kl)
        if "error" not in f:
            sig = f.get("SIGNAL", 0)
            qlib_bias = f.get("BIAS", "观望")
            qlib_w = max(0.0, min(5.0, (sig + 5) / 2))  # -5~+5 → 0~5
    except Exception as e:  # noqa: BLE001
        qlib_bias = f"异常:{e}"
    sources.append({"name": "QLib因子", "sig": qlib_bias, "w": round(qlib_w, 1),
                    "emoji": "🟢" if qlib_w >= 3 else "🔴" if qlib_w <= 1.5 else "⚪",
                    "detail": "动量/趋势/量能综合"})

    # 3) Deribit C/P 偏多空
    deribit_w = 0.0
    deribit_sig = "数据不足"
    try:
        import deribit_options as d
        data = d.fetch_options()
        btc = data.get("BTC", {})
        cp = btc.get("cp_ratio")
        if cp:
            deribit_w = 2.0 if cp > 1.5 else -2.0 if cp < 0.7 else 0.0
            deribit_sig = f"C/P={cp:.2f}"
    except Exception as e:  # noqa: BLE001
        deribit_sig = f"异常:{e}"
    sources.append({"name": "Deribit期权", "sig": deribit_sig, "w": round(deribit_w, 1),
                    "emoji": "🟢" if deribit_w > 0 else "🔴" if deribit_w < 0 else "⚪",
                    "detail": "看涨需求/看跌保护"})

    # 4) X情绪 FOMO（过热反向减分）
    x_w = 0.0
    x_sig = "无"
    try:
        import x_sentiment_context as x
        fg = x.fetch_fear_greed()
        fv = int(fg.get("value", 50))
        tr = x.fetch_trending()
        fomo = sum(1 for c in tr.get("coins", []) if c.get("symbol") == "BTC")  # 简化：BTC在热搜则偏热
        # fomo_score 近似：恐惧贪婪>75过热 / <25恐慌反向机会
        if fv > 75:
            x_w = -2.0
            x_sig = f"FNG={fv}过热"
        elif fv < 25:
            x_w = 2.0
            x_sig = f"FNG={fv}恐慌"
        else:
            x_w = 0.0
            x_sig = f"FNG={fv}中性"
    except Exception as e:  # noqa: BLE001
        x_sig = f"异常:{e}"
    sources.append({"name": "X情绪FOMO", "sig": x_sig, "w": round(x_w, 1),
                    "emoji": "🟢" if x_w > 0 else "🔴" if x_w < 0 else "⚪",
                    "detail": "恐惧贪婪温度"})

    # 5) 稳定币边际流向
    sc = fetch_stablecoin_flow()
    sc_w = 1.0 if sc["total_delta"] > 0 else -1.0 if sc["total_delta"] < 0 else 0.0
    sources.append({"name": "稳定币流向", "sig": sc["note"], "w": round(sc_w, 1),
                    "emoji": "🟢" if sc_w > 0 else "🔴" if sc_w < 0 else "⚪",
                    "detail": f"Δ{sc['delta_b']:+.1f}B"})

    # 融合：Orion 作主基底(0-10) + 其余归一化加总(各 -2~+2 量级 → 上限 +5)
    base = orion_conf
    adjust = sum(s["w"] for s in sources[1:])  # 上限约 +2+2-2+1=+3 左右
    score = max(0.0, min(10.0, base + max(-3.0, min(3.0, adjust))))
    score = round(score, 1)

    # verdict + 符号
    if score >= 7.5:
        verdict, v_emoji = "高置信·可做多", "🟢"
    elif score >= 5.5:
        verdict, v_emoji = "中置信·逢低轻仓", "🟡"
    elif score >= 4.0:
        verdict, v_emoji = "低置信·观望", "⚪"
    else:
        verdict, v_emoji = "偏空·规避", "🔴"

    supporting = [s["name"] for s in sources if s["w"] > 0]
    contra = [s["name"] for s in sources if s["w"] < 0]

    concl = (f"{v_emoji}{verdict}；共振源[{','.join(supporting) or '无'}]"
             + (f"；逆风[{','.join(contra)}]" if contra else ""))
    return {"symbol": orion_sym or "BTCUSDT", "score": score, "verdict": verdict,
            "v_emoji": v_emoji, "sources": sources, "concl": concl,
            "supporting": supporting, "contra": contra}


# ───────────────────────────── 渲染 ─────────────────────────────
def build_report(f: dict, ts: str) -> str:
    lines = [f"🎯 作战室融合 · {ts}", ""]
    lines.append("| 源 | 信号 | 权重 | 状态 |")
    lines.append("|:----|:----|:----:|:----|")
    for s in f["sources"]:
        lines.append(f"| {s['name']} | {s['sig']} | {s['w']:+} | {s['emoji']} |")
    lines.append("")
    lvl = "⭐" if f["score"] >= 7.5 else "🔸" if f["score"] >= 5.5 else "⚪"
    lines.append(f"**融合总评分**: {lvl}`{f['score']}`/10 · {f['v_emoji']}**{f['verdict']}**")
    lines.append("")
    lines.append(f"**总体结论**: {f['concl']}。")
    return "\n".join(lines)


def main() -> int:
    now = datetime.now(TZ)
    ts = f"{now.year}年{now.month}月{now.day}日{now.hour:02d}：{now.minute:02d}"
    try:
        f = fuse()
        report = build_report(f, ts)
        print(report)
        sys.path.insert(0, str(SCRIPTS))
        from telegram_reliable import push_tg_rich
        ok, reason = push_tg_rich("telegram:-1003733144325:846", report)
        print(f"[TG] ok={ok} reason={reason}", file=sys.stderr)
        return 0 if ok else 1
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
