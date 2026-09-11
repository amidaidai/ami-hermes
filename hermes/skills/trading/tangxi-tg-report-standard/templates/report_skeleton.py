#!/usr/bin/env python3
# 棠溪推 TG 报告脚本骨架 — 复制后改 main 的数据获取与表格构造即可。
# 铁律：RichMarkdown 真表格 + 末尾总体结论 + 置信降序 + 表情侧重点 + 决策厚度。
import sys, os, json
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
TG_TARGET = "telegram:-1003733144325:846"

def push(text):
    """统一推 TG 真表格。失败落盘 pending，不外抛。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from telegram_reliable import push_tg_rich
        push_tg_rich(TG_TARGET, text)
    except Exception as e:
        print(f"⚠ 推送失败: {e}", file=sys.stderr)

def main():
    now = datetime.now(TZ)
    ts = now.strftime("%Y年%m月%d日%H：%M")

    # 1) 取数（这里用占位，替换为真实数据源）
    rows = []  # 每行: dict(symbol, confidence, price, chg, note)

    # 2) 排序：置信降序（高置信/有机会排前）
    rows.sort(key=lambda r: r.get("confidence", 0), reverse=True)

    # 3) 构造表格（带等级符号 + 表情侧重点）
    lines = [f"📡 示例报告 · {ts}", ""]
    lines.append("| 品种 | 置信 | 数据 | 信号 |")
    lines.append("|:----|:----:|:----|:----|")
    for r in rows:
        conf = r.get("confidence", 0)
        lvl = "⭐" if conf >= 6 else "🔸" if conf >= 4 else "⚪"
        chg = r.get("chg", 0)
        arrow = "🟢" if chg > 0 else "🔴" if chg < 0 else "⚪"
        lines.append(f"| {r['symbol']} | {lvl}`{conf}` | 价`{r['price']}` | {arrow}{chg:+.1f}% |")

    # 4) 末尾总体结论（一句话决策）
    lines.append("")
    lines.append(f"**总体结论**: 共{len(rows)}项，{'偏多为主' if rows else '无信号'}。")

    output = "\n".join(lines)
    print(output)
    push(output)
    return 0

if __name__ == "__main__":
    sys.exit(main())
