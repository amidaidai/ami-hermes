#!/usr/bin/env python3
"""
X情绪采集器 v1.1 — 表格化输出
"""
import json, sys, os
from datetime import datetime, timezone, timedelta
import urllib.request

TZ = timezone(timedelta(hours=8))
UA = "Hermes/1.0"


def fetch_trending():
    try:
        url = "https://api.coingecko.com/api/v3/search/trending"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        coins = data.get("coins", [])
        top = []
        for c in coins[:10]:
            item = c.get("item", {})
            top.append({
                "symbol": item.get("symbol", "?"),
                "name": item.get("name", "?"),
                "rank": item.get("market_cap_rank", 9999),
                "score": item.get("score", 0),
            })
        low_cap_trending = sum(1 for c in top if c["rank"] and c["rank"] > 100)
        return {"top_coins": top[:5], "fomo_score": min(low_cap_trending, 5)}
    except Exception as e:
        return {"error": str(e), "fomo_score": 0, "top_coins": []}


def fetch_fear_greed():
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        item = data.get("data", [{}])[0]
        return {"value": int(item.get("value", 50)), "classification": item.get("value_classification", "Neutral")}
    except Exception:
        return {"value": 50, "classification": "Error"}


def main():
    now = datetime.now(TZ)
    ts = now.strftime("%Y-%m-%d %H:%M BJT")
    
    trending = fetch_trending()
    fg = fetch_fear_greed()
    fg_val = fg.get("value", 50)
    
    mood_map = {range(75, 101): "极度贪婪", range(55, 75): "贪婪", range(45, 55): "中性", range(25, 45): "恐惧", range(0, 25): "极度恐惧"}
    mood = "中性"
    for r, m in mood_map.items():
        if fg_val in r:
            mood = m
            break
    
    fomo = trending.get("fomo_score", 0)
    fomo_text = "FOMO高热" if fomo >= 4 else "温和关注" if fomo >= 2 else "冷清"
    
    # 表格化输出
    lines = [f"市场情绪 {ts}"]
    lines.append("")
    lines.append("| 指标 | 数值 | 解读 |")
    lines.append("|------|------|------|")
    lines.append(f"| 恐惧贪婪 | {fg_val} | {mood} |")
    lines.append(f"| 搜索热度 | {fomo}/5 | {fomo_text} |")
    
    top = trending.get("top_coins", [])
    if top:
        lines.append("")
        lines.append("| 热门币种 | 市值排名 | 热度评分 |")
        lines.append("|----------|----------|----------|")
        for c in top:
            rank = f"#{c['rank']}" if c['rank'] and c['rank'] < 9999 else "未入榜"
            lines.append(f"| {c['symbol']} | {rank} | {c['score']} |")
    
    output = "\n".join(lines)
    try:
        from alert_dedup import dedup_wrapper
        dedup_wrapper("x_sentiment", output, force_seconds=1800)
    except ImportError:
        print(output)
    
    # 保存 — 两处落盘
    result = {"ts": now.isoformat(), "fear_greed": fg_val, "fear_greed_label": mood, "fomo_score": fomo, "trending": top}
    
    # 落盘1: hermes data目录（现有路径）
    data_dir1 = os.path.expanduser("~/AppData/Local/hermes/data")
    os.makedirs(data_dir1, exist_ok=True)
    with open(os.path.join(data_dir1, "sentiment.json"), "w") as f:
        json.dump(result, f, ensure_ascii=False)
    
    # 落盘2: 项目data目录（cron_read 读取）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir2 = os.path.join(script_dir, "..", "data")
    os.makedirs(data_dir2, exist_ok=True)
    with open(os.path.join(data_dir2, "x_sentiment.json"), "w") as f:
        json.dump(result, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
