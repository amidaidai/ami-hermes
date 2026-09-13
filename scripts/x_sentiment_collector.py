#!/usr/bin/env python3
"""
X情绪采集器 v1.1 — 表格化输出

⚠️ 已停用（2026-09-13 审计确认）——**不要重新接进 cron**
--------------------------------------------------------------------------
证据：① 无 cron 任务（原任务 `X情绪数据刷新` 已于 2026-09-10 归档进
`data/cron_paused_archive_20260910.json`）；② 无任何消费者——其输出
`data/x_sentiment.json` 在全仓只有本文件第 133 行的写入方，零读取方，
该文件已归档到 `data/_archive/`；③ 现行替代 = `scripts/x_sentiment_refresh.py`
（写 `data/x_sentiment_context.json`，即 `auto_card.py` X情绪步骤实际读的那份）。

⚠️ 停用理由（真实事故模式）：本脚本的输出一旦被误当实时值使用，会让卡面
用 ✅ 打印过期的恐贪/市占（2026-07-15 那份曾打印恐贪 25 / 市占 56.3%），
比没有数据更容易误导。要恢复 X 情绪，请用 refresh 脚本，不要复活本脚本。
"""
import json, sys, os
from datetime import datetime, timezone, timedelta
import urllib.request
from pathlib import Path
from atomic_json import atomic_write_json
from source_contract import attach_source_contract

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
    ts = f"{now.year}年{now.month}月{now.day}日{now.hour:02d}：{now.minute:02d}"
    
    trending = fetch_trending()
    fg = fetch_fear_greed()
    fg_val = fg.get("value", 50)
    
    mood_map = {range(75, 101): "极度贪婪", range(55, 75): "贪婪", range(45, 55): "中性", range(25, 45): "恐惧", range(0, 25): "极度恐惧"}
    mood = "中性"
    for r, m in mood_map.items():
        if fg_val in r:
            mood = m
            break
    # 恐惧贪婪分层决策
    fg_note = "潜在抄底区" if fg_val <= 25 else "偏谨慎" if fg_val <= 45 else "观望" if fg_val <= 55 else "防回调" if fg_val <= 75 else "高风区"
    
    fomo = trending.get("fomo_score", 0)
    fomo_text = "FOMO高热" if fomo >= 4 else "温和关注" if fomo >= 2 else "冷清"
    
    # 表格化输出
    direction = "×高风险" if fg_val > 75 else "↑反弹观察" if fg_val <= 25 else "○中性"
    lines = [f"{direction} · 市场情绪 · {ts}"]
    lines.append("")
    lines.append("| 指标 | 数值 | 解读 |")
    lines.append("|:----|:----:|:----|")
    lines.append(f"| 恐惧贪婪 | {fg_val} | {mood}（{fg_note}） |")
    lines.append(f"| 搜索热度 | {fomo}/5 | {fomo_text} |")
    
    top = trending.get("top_coins", [])
    if top:
        lines.append("")
        lines.append("| 热门币种 | 市值排名 | 热度评分 |")
        lines.append("|:----|:----:|:----:|")
        for c in top:
            rank = f"#{c['rank']}" if c['rank'] and c['rank'] < 9999 else "未入榜"
            lines.append(f"| {c['symbol']} | {rank} | {c['score']} |")
    lines.append("")
    if fg_val > 75 or fomo >= 4:
        verdict = "×情绪过热，禁止追涨，防回调"
    elif fg_val <= 25:
        verdict = "↑极度恐惧区，仅等结构确认后小仓试多"
    else:
        verdict = "○情绪未给出单边优势，按结构交易"
    lines.append(f"**总体结论**: **{verdict}**。")
    
    output = "\n".join(lines)
    # 降噪：去重时不要把时间戳纳入 hash；同一情绪结构最多 2 小时强制推一次。
    dedup_key = json.dumps({"fear_greed": fg_val, "mood": mood, "fomo_score": fomo, "trending": top}, ensure_ascii=False, sort_keys=True)
    try:
        should_send = __import__("alert_dedup").should_send
        if should_send("x_sentiment", dedup_key, force_every_seconds=7200):
            print(output)
            # v9.8: 同步推 TG 真表格（原本只落盘静默）
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from telegram_reliable import push_tg_rich
                push_tg_rich("telegram:-1003733144325:846", output)
            except Exception as _te:
                print(f"⚠ X情绪RichMarkdown推送失败: {_te}", file=sys.stderr)
    except ImportError:
        print(output)
    
    # 保存 — 两处落盘
    source_error = "upstream_error" if trending.get("error") or fg.get("classification") == "Error" else None
    result = attach_source_contract(
        {"ts": now.isoformat(), "fear_greed": fg_val, "fear_greed_label": mood, "fomo_score": fomo, "trending": top},
        "x_sentiment",
        status="live" if source_error is None else "unavailable",
        captured_at=now,
        symbol="BTCUSDT",
        error=source_error,
    )
    
    # 落盘1: hermes data目录（现有路径）
    data_dir1 = os.path.expanduser("~/AppData/Local/hermes/data")
    os.makedirs(data_dir1, exist_ok=True)
    atomic_write_json(Path(os.path.join(data_dir1, "sentiment.json")), result)
    
    # 落盘2: 项目data目录（cron_read 读取）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir2 = os.path.join(script_dir, "..", "data")
    os.makedirs(data_dir2, exist_ok=True)
    atomic_write_json(Path(os.path.join(data_dir2, "x_sentiment.json")), result)


if __name__ == "__main__":
    main()
