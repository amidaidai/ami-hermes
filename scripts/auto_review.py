#!/usr/bin/env python3
"""自动复盘闭环 — 信号→结果→胜率统计管线"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json, os, csv
from datetime import datetime, timezone, timedelta
from collections import defaultdict

TZ = timezone(timedelta(hours=8))
DIR = os.path.expanduser("~/AppData/Local/hermes/data")
SCRIPTS = os.path.expanduser("~/AppData/Local/hermes/scripts")
SIGNALS_FILE = os.path.join(DIR, "btc_signals.json")
JOURNAL_DIR = os.path.join(SCRIPTS, "trading-journal")

# ===== 信号分类 =====
SIGNAL_CATEGORIES = {
    "fvg_retest_bullish": "FVG回测·多",
    "fvg_retest_bearish": "FVG回测·空",
    "vwap_bounce": "VWAP反弹",
    "vwap_break": "VWAP突破",
    "val_bounce": "VAL反弹",
    "val_break": "VAL跌破",
    "vah_break": "VAH突破",
    "sweep_recovery": "扫荡回收",
    "cvd_divergence_bullish": "CVD看多背离",
    "cvd_divergence_bearish": "CVD看空背离",
    "silver_bullet_long": "银弹窗口·多",
    "silver_bullet_short": "银弹窗口·空",
    "killzone_breakout": "KZ突破",
    "pipeline_2022": "2022模型管线",
    "other": "其他",
}


def read_signals():
    """读取历史信号。"""
    try:
        with open(SIGNALS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def read_journal():
    """读取交易日记。"""
    records = []
    journal_file = os.path.join(JOURNAL_DIR, "trade_journal.csv")
    if os.path.exists(journal_file):
        with open(journal_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)
    
    # 也读JSON格式
    journal_json = os.path.join(JOURNAL_DIR, "trade_journal.json")
    if os.path.exists(journal_json):
        try:
            with open(journal_json) as f:
                data = json.load(f)
                if isinstance(data, list):
                    records.extend(data)
                elif isinstance(data, dict):
                    records.extend(data.get("trades", []))
        except (json.JSONDecodeError, AttributeError):
            pass
    
    return records


def analyze_trades(trades):
    """分析交易记录。"""
    if not trades:
        return {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "total_r": 0,
            "avg_r": 0,
            "expected_value": 0,
            "by_signal": {},
            "by_day": {},
        }
    
    wins = 0
    losses = 0
    total_r = 0.0
    
    by_signal = defaultdict(lambda: {"wins": 0, "losses": 0, "count": 0, "total_r": 0.0})
    by_day = defaultdict(lambda: {"wins": 0, "losses": 0, "count": 0, "total_r": 0.0})
    
    for t in trades:
        result = t.get("result", t.get("outcome", "")).lower()
        r_multiple = float(t.get("r_multiple", t.get("rr", 0)))
        signal = t.get("signal_type", t.get("signal", "other"))
        date = t.get("date", t.get("time", "unknown"))[:10]
        
        is_win = result in ("win", "profit", "tp", "take_profit", "赢")
        
        if is_win:
            wins += 1
        else:
            losses += 1
        
        total_r += r_multiple if is_win else -1
        
        sig = SIGNAL_CATEGORIES.get(signal, signal)
        by_signal[sig]["wins"] += 1 if is_win else 0
        by_signal[sig]["losses"] += 0 if is_win else 1
        by_signal[sig]["count"] += 1
        by_signal[sig]["total_r"] += r_multiple if is_win else -1
        
        by_day[date]["wins"] += 1 if is_win else 0
        by_day[date]["losses"] += 0 if is_win else 1
        by_day[date]["count"] += 1
        by_day[date]["total_r"] += r_multiple if is_win else -1
    
    total = wins + losses
    win_rate = round(wins / total * 100, 1) if total > 0 else 0
    
    # 按类型统计胜率
    signal_stats = {}
    for sig, stats in sorted(by_signal.items()):
        c = stats["count"]
        wr = round(stats["wins"] / c * 100, 1) if c > 0 else 0
        avg_r = round(stats["total_r"] / c, 2) if c > 0 else 0
        signal_stats[sig] = {
            "count": c,
            "wins": stats["wins"],
            "losses": stats["losses"],
            "win_rate": wr,
            "avg_r": avg_r,
        }
    
    # 日统计
    day_stats = {}
    for d, stats in sorted(by_day.items()):
        c = stats["count"]
        wr = round(stats["wins"] / c * 100, 1) if c > 0 else 0
        day_stats[d] = {
            "count": c,
            "win_rate": wr,
            "total_r": round(stats["total_r"], 2),
        }
    
    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_r": round(total_r, 2),
        "avg_r": round(total_r / total, 2) if total > 0 else 0,
        "expected_value": round(win_rate / 100 * round(total_r / total, 2) - (1 - win_rate / 100), 2) if total > 0 else 0,
        "by_signal": signal_stats,
        "by_day": day_stats,
    }


def review_today():
    """今日交易复盘。"""
    trades = read_journal()
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    today_trades = [t for t in trades if t.get("date", "")[:10] == today]
    
    if not today_trades:
        return {"date": today, "count": 0, "summary": "今日无交易"}
    
    analysis = analyze_trades(today_trades)
    analysis["date"] = today
    return analysis


def review_week():
    """本周复盘。"""
    trades = read_journal()
    now = datetime.now(TZ)
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    
    week_trades = [t for t in trades if t.get("date", "")[:10] >= week_ago]
    if not week_trades:
        return {"period": f"{week_ago}~{now.strftime('%Y-%m-%d')}", "count": 0}
    
    analysis = analyze_trades(week_trades)
    analysis["period"] = f"{week_ago}~{now.strftime('%Y-%m-%d')}"
    return analysis


def recommend_improvements(review_data):
    """根据复盘数据推荐调整。"""
    if review_data.get("count", 0) < 5:
        return "数据不足(需≥5笔), 暂不能给出可靠建议"
    
    recommendations = []
    best_signal = None
    worst_signal = None
    
    by_sig = review_data.get("by_signal", {})
    for sig, stats in by_sig.items():
        if stats["count"] < 2:
            continue
        if stats["win_rate"] >= 60 and stats["avg_r"] > 0.5:
            best_signal = (sig, stats)
        if stats["win_rate"] < 40 and stats["avg_r"] < -0.3:
            worst_signal = (sig, stats)
    
    if best_signal:
        sig, stats = best_signal
        r = stats.get("avg_r", 0)
        recommendations.append(f"✅ 信号[{sig}]胜率{stats['win_rate']}%·R{r:.1f} — 加大关注")
    
    if worst_signal:
        sig, stats = worst_signal
        r = stats.get("avg_r", 0)
        recommendations.append(f"⚠ 信号[{sig}]胜率{stats['win_rate']}%·R{r:.1f} — 降低权重或过滤")
    
    if review_data.get("win_rate", 0) > 55:
        recommendations.append("整体胜率健康，可考虑适当增加仓位")
    elif review_data.get("win_rate", 0) < 40:
        recommendations.append("整体胜率偏低，建议减仓+提高入场标准")
    
    if not recommendations:
        recommendations.append("无显著偏离，维持当前策略")
    
    return "\n".join(recommendations)


def report_full():
    """完整复盘报告。"""
    trades = read_journal()
    analysis = analyze_trades(trades)
    
    lines = [
        "📊 自动复盘报告",
        f"总计 {analysis['total']} 笔 · 胜率 {analysis['win_rate']}% · 总R {analysis['total_r']} · 期望值 {analysis['expected_value']}",
    ]
    
    if analysis.get("by_signal"):
        lines.append("\n-- 按信号类型 --")
        for sig, stats in sorted(analysis["by_signal"].items(), key=lambda x: x[1]["count"], reverse=True):
            lines.append(f"  {sig}: {stats['count']}笔 · {stats['win_rate']}% · R{stats['avg_r']}")
    
    if analysis.get("by_day"):
        lines.append("\n-- 按日 --")
        for d, stats in sorted(analysis["by_day"].items()):
            lines.append(f"  {d}: {stats['count']}笔 · {stats['win_rate']}% · R{stats['total_r']}")
    
    recs = recommend_improvements(analysis)
    lines.append(f"\n-- 建议 --\n{recs}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    print(report_full())
    print("\n--- 今日复盘 ---")
    today = review_today()
    if isinstance(today, dict):
        print(f"今日: {today.get('summary', str(today.get('count', 0))+'笔')}")
        if today.get("count", 0) > 0:
            print(f"胜率 {today['win_rate']}% · R{today['total_r']}")
