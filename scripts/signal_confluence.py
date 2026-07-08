#!/usr/bin/env python3
"""
棠溪 · 作战室融合报告 signal_confluence.py v1.1

目标：把已有 5 大源的"单源信号"融合成【单资产总评分】，并给出具体执行计划
（方向/入场/止损/目标/风险%），解决"有方向无价位"的缺口。
参照 signalsGURU 三阶段融合置信引擎 + Turnkey「执行即头等」。

融合源 + 权重（满分 10）：
  - Orion      : 单品种置信(本就含 OI/费率/主动买卖/跨所确认) → 直接取 0-10 主权重
  - QLib 因子  : compute_factors SIGNAL(-5~+5) → 映射 0-5
  - Deribit    : C/P 比偏多空(+2 / -2 / 0)
  - X情绪FOMO   : 恐惧贪婪极端反向(+2 / -2 / 0)
  - 稳定币流向  : 边际增量(+1) / 减量(-1) / 持平(0)

执行计划：复用 BTC 结构位（tv_dmi_cache.json），给出具体价位+1R风险%。

输出：RichMarkdown 真表（每源一行 + 融合总评分 + 执行计划表）+ 总体结论。推 846。
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
DATA_DIR = REPO / "data"  # D:/Hermes agent/data，TV缓存在此目录
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
    try:
        prev_fp.write_text(json.dumps(cur, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return {"delta_b": delta_b, "total_delta": total_delta,
            "note": "增量=潜在买盘" if total_delta > 0 else "减量=撤资信号" if total_delta < 0 else "持平"}


def read_btc_levels() -> dict:
    """读 TV 缓存结构位（tv_dmi_cache.json 最新鲜），零副作用。"""
    candidates = [
        DATA_DIR / "tv_dmi_cache.json",
        DATA_DIR / "tv_live.json",
        DATA_DIR / "btc_ref_levels.json",
    ]
    best = None
    best_age = 1e9
    best_src = "?"
    for p in candidates:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not all(k in d for k in ("vwap", "val", "vah", "poc")):
            continue
        age = (time.time() - p.stat().st_mtime) / 60
        if age < best_age:
            best_age = age
            best = d
            best_src = p.name
    if not best:
        return {"error": "no valid TV cache"}
    spot = None
    try:
        req = urllib.request.Request(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
            headers={"User-Agent": "Hermes/1.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            spot = float(json.loads(r.read()).get("price", 0))
    except Exception:
        spot = None
    return {
        "poc": float(best.get("poc")),
        "vwap": float(best.get("vwap")),
        "val": float(best.get("val")),
        "vah": float(best.get("vah")),
        "do": float(best.get("do")) if best.get("do") else None,
        "w_vwap": float(best.get("w_vwap")) if best.get("w_vwap") else None,
        "spot": spot,
        "age_min": round(best_age, 1),
        "source": best_src,
    }


# ───────────────────────────── 融合引擎 ─────────────────────────────
def fuse() -> dict:
    sources = []

    # 1) Orion 主权重（最高置信候选作动量贡献，主品种锚定 BTC）
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
            qlib_w = max(0.0, min(5.0, (sig + 5) / 2))
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
        if fv > 75:
            x_w, x_sig = -2.0, f"FNG={fv}过热"
        elif fv < 25:
            x_w, x_sig = 2.0, f"FNG={fv}恐慌"
        else:
            x_w, x_sig = 0.0, f"FNG={fv}中性"
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

    # 6) 独立验证闸门（融合 auto_card 逻辑，仅作展示；硬门在 compute_plan）
    try:
        from signal_validators import long_short_contra, tf_alignment, tf_alignment_tv
        ls = long_short_contra("BTCUSDT")
        # 周期方向优先 TV MCP（等加载完再读），降级 REST；存快照供验证闸门同源使用
        tf = tf_alignment_tv("BTCUSDT")
        tf_src = "TV"
        if not tf.get("available"):
            tf = tf_alignment("BTCUSDT")
            tf_src = "REST"
        global _TF_CACHE
        _TF_CACHE = tf  # 同源快照：展示与 compute_plan 验证闸门用同一份
        ls_sig = ls.get("contra") or f"正常({ls.get('ratio')})" if ls.get("available") else "API不可用"
        tf_sig = (tf.get("note", "—") + f" [{tf_src}]") if tf.get("available") else f"数据不足[{tf_src}]"
        sources.append({"name": "🔍多空比反指", "sig": ls_sig, "w": 0.0,
                        "emoji": "🟢" if ls.get("signal") == "neutral" else "🔴",
                        "detail": "散户拥挤反向"})
        sources.append({"name": "🔍周期一致性", "sig": tf_sig, "w": 0.0,
                        "emoji": "🔴" if tf.get("conflict") else ("🟢" if tf.get("aligned") else "⚪"),
                        "detail": "4h/1h/15m/5m方向"})
    except Exception as e:  # noqa: BLE001
        sources.append({"name": "🔍验证闸门", "sig": f"异常:{e}", "w": 0.0,
                        "emoji": "⚪", "detail": "auto_card逻辑"})

    # 融合：Orion 作主基底(0-10) + 其余加权(限幅±3)
    base = orion_conf
    adjust = sum(s["w"] for s in sources[1:])
    score = max(0.0, min(10.0, base + max(-3.0, min(3.0, adjust))))
    score = round(score, 1)

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
    # 供 compute_plan 的 analysis 引用共振源名
    global _SUPPORTING_CACHE
    _SUPPORTING_CACHE = supporting
    plan = compute_plan(score)
    concl = (f"{v_emoji}{verdict}；共振源[{','.join(supporting) or '无'}]"
             + (f"；逆风[{','.join(contra)}]" if contra else ""))
    return {"symbol": "BTCUSDT", "score": score, "verdict": verdict,
            "v_emoji": v_emoji, "sources": sources, "concl": concl,
            "supporting": supporting, "contra": contra, "plan": plan}


# 模块级缓存：供 compute_plan 的 analysis 引用共振源名（避免循环依赖）
_SUPPORTING_CACHE: list = []
def _supporting_names() -> list:
    return _SUPPORTING_CACHE


# 模块级缓存：周期方向快照（fuse 算一次，展示+验证闸门同源，避免 Binance 数据漂移）
_TF_CACHE: dict = {}
def _tf_snapshot() -> dict:
    return _TF_CACHE


def compute_plan(score: float) -> dict:
    """根据融合评分给具体方向/入场/止损/目标/风险%。复用 BTC 结构位。
    规则：止损紧贴入场(0.5%夹层)，主目标取结构位上方，盈亏比必须≥2R才发方案。"""
    lv = read_btc_levels()
    if "error" in lv or lv.get("vwap") is None:
        return {"available": False, "reason": lv.get("error", "no levels")}

    vwap = lv["vwap"]; val = lv["val"]; vah = lv["vah"]; poc = lv["poc"]
    do = lv.get("do"); w_vwap = lv.get("w_vwap"); spot = lv.get("spot")

    if score >= 5.5:
        side = "🟢做多"
        entry = vwap
        entry2 = val
        stop = round(entry * 0.995)          # 入场下方0.5%紧贴止损
        targets = [vah] + ([do] if do else []) + ([w_vwap] if w_vwap else [])
        stop_logic = "VWAP下方0.5%（夹层止损，破位即结构失效）"
        entry_logic = "回踩VWAP接多，VAL加仓；现价在VAH上方属突破区，等回踩确认再进"
    elif score < 4.0:
        side = "🔴做空"
        entry = vah
        entry2 = vwap
        stop = round(entry * 1.005)          # 入场上方0.5%紧贴止损
        targets = [val] + ([poc] if poc else [])
        stop_logic = "VAH上方0.5%（夹层止损，突破即结构失效）"
        entry_logic = "反弹VAH承压做空，VWAP加仓"
    else:
        return {"available": True, "qualified": False, "side": "⚪观望",
                "spot": spot, "age": lv.get("age_min"),
                "reason": "融合评分中间区(4-5.5)，方向不清，不发方案"}

    risk_pct = 1.0
    if score >= 7.5:
        risk_pct = 1.5
    elif score < 4.0:
        risk_pct = 0.5

    r_ratio = None
    if entry and stop and targets:
        r = abs(entry - stop)
        if r > 0:
            best_t = max(targets, key=lambda t: abs(t - entry))
            r_ratio = round(abs(best_t - entry) / r, 1)

    # 盈亏比门槛：必须≥2R才发执行计划
    qualified = (r_ratio is not None and r_ratio >= 2.0)

    # ── 独立验证闸门（融合 auto_card 逻辑：多空比反指 + 周期一致性）──
    blockers = []
    val_notes = []
    if qualified:
        try:
            from signal_validators import validate_plan
            vres = validate_plan("BTCUSDT", side, tf_override=_tf_snapshot())
            val_notes = vres.get("notes", [])
            if not vres.get("pass"):
                blockers = vres.get("blockers", [])
                qualified = False
        except Exception as e:  # noqa: BLE001
            val_notes.append(f"验证器异常:{e}")

    if qualified:
        analysis = (f"方向逻辑：{side}（融合{score}/10，共振源[{','.join(_supporting_names()) or '无'}]）。"
                    f"入场逻辑：{entry_logic}。"
                    f"风控逻辑：{stop_logic}，风险{risk_pct}%/1R，盈亏比{r_ratio}R。"
                    f"独立验证：{'；'.join(val_notes) or '通过'}。")
    else:
        reason = (f"结构位不支持≥2R（当前测算{r_ratio}R）" if (r_ratio or 0) < 2.0
                  else "；".join(blockers) or "未达标")
        analysis = (f"暂不发执行计划：{reason}。"
                    f"{('独立验证：' + '；'.join(val_notes) + '。') if val_notes else ''}"
                    f"等结构收敛/回踩确认后再评估。")

    return {
        "available": True, "qualified": qualified, "side": side,
        "entry": entry, "entry2": entry2, "stop": stop, "targets": targets,
        "risk_pct": risk_pct, "r_ratio": r_ratio, "analysis": analysis,
        "stop_logic": stop_logic, "entry_logic": entry_logic,
        "validators": val_notes, "blockers": blockers,
        "spot": spot, "age": lv.get("age_min"),
    }


# ───────────────────────────── 渲染 ─────────────────────────────
def _fmt(v) -> str:
    if v is None:
        return "—"
    return f"`{v:,.0f}`"


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

    # 执行计划：仅当盈亏比≥2R才发具体价位方案；否则只给分析
    p = f.get("plan", {})
    if p.get("qualified"):
        lines.append("| 执行计划 | 价位/参数 |")
        lines.append("|:----|:----:|")
        lines.append(f"| 方向 | {p['side']} |")
        if p["entry"]:
            lines.append(f"| 入场① | {_fmt(p['entry'])} (VWAP) |")
            lines.append(f"| 入场② | {_fmt(p['entry2'])} (VAL加仓) |")
            lines.append(f"| **止损** | {_fmt(p['stop'])} |")
            tgt = " / ".join(_fmt(t) for t in p["targets"])
            lines.append(f"| 目标 | {tgt} |")
            lines.append(f"| 风险% | **{p['risk_pct']}%** (1R) |")
            lines.append(f"| 盈亏比 | **{p['r_ratio']}R** |")
        if p.get("spot"):
            lines.append(f"| 现价 | {_fmt(p['spot'])} |")
        if p.get("age") is not None:
            lines.append(f"| 结构位新鲜度 | {p['age']}min |")
        lines.append("")
        lines.append(f"**分析**: {p['analysis']}")
    else:
        # 未达标：不发方案段，只发分析说明
        reason = p.get("reason") or (p.get("analysis") or "结构位不支持≥2R")
        lines.append(f"**分析**: {reason}")
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
