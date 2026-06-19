#!/usr/bin/env python3
"""交易日志系统 — SQLite 数据库 CRUD + 复盘报告"""

import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = os.environ.get("TRADING_JOURNAL_DB", "D:/Hermes agent/data/trading_journal.db")


# ─── 连接 ─────────────────────────────────────────────────────

def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT NOT NULL,
            side        TEXT NOT NULL CHECK(side IN ('BUY','SELL','LONG','SHORT')),
            entry_price REAL,
            exit_price  REAL,
            qty         REAL NOT NULL,
            pnl         REAL,
            market      TEXT DEFAULT 'spot' CHECK(market IN ('spot','futures')),
            opened_at   TIMESTAMP DEFAULT (datetime('now','localtime')),
            closed_at   TIMESTAMP,
            reason      TEXT,
            screenshot  TEXT,
            tags        TEXT,
            created_at  TIMESTAMP DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS analysis_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol        TEXT NOT NULL,
            timeframe     TEXT,
            analysis_type TEXT,
            result_summary TEXT,
            decision      TEXT,
            screenshot    TEXT,
            created_at    TIMESTAMP DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
        CREATE INDEX IF NOT EXISTS idx_trades_opened ON trades(opened_at);
        CREATE INDEX IF NOT EXISTS idx_analysis_symbol ON analysis_log(symbol);
    """)


# ─── 交易 CRUD ────────────────────────────────────────────────

def add_trade(symbol: str, side: str, entry_price: float, qty: float,
              market: str = "spot", reason: str = "", tags: str = "",
              screenshot: str = "") -> int:
    """记录一笔新交易（开仓）。返回 trade id"""
    conn = get_conn()
    conn.execute("""
        INSERT INTO trades (symbol, side, entry_price, qty, market, reason, tags, screenshot)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (symbol.upper(), side.upper(), entry_price, qty, market, reason, tags, screenshot))
    conn.commit()
    trade_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return trade_id


def close_trade(trade_id: int, exit_price: float, pnl: float = None,
                reason: str = "", screenshot: str = "") -> dict:
    """平仓。自动计算 pnl 如果未提供"""
    conn = get_conn()
    trade = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
    if not trade:
        conn.close()
        return {"error": f"Trade #{trade_id} not found"}
    if trade["closed_at"]:
        conn.close()
        return {"error": f"Trade #{trade_id} already closed"}

    if pnl is None:
        # 简易估算
        if trade["side"] in ("BUY", "LONG"):
            pnl = (exit_price - trade["entry_price"]) * trade["qty"]
        else:
            pnl = (trade["entry_price"] - exit_price) * trade["qty"]

    updates = ["exit_price=?", "pnl=?", "closed_at=datetime('now','localtime')"]
    params = [exit_price, pnl]
    if reason:
        updates.append("reason=CASE WHEN reason='' THEN ? ELSE reason || ' | ' || ? END")
        params.extend([reason, reason])
    if screenshot:
        updates.append("screenshot=?")
        params.append(screenshot)

    params.append(trade_id)
    conn.execute(f"UPDATE trades SET {', '.join(updates)} WHERE id=?", params)
    conn.commit()
    conn.close()
    return {"status": "closed", "trade_id": trade_id, "pnl": pnl}


def get_open_trades(symbol: str = "") -> list:
    """查看未平仓的交易"""
    conn = get_conn()
    if symbol:
        rows = conn.execute("""
            SELECT * FROM trades WHERE closed_at IS NULL AND symbol=?
            ORDER BY opened_at DESC
        """, (symbol.upper(),)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM trades WHERE closed_at IS NULL
            ORDER BY opened_at DESC
        """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trades(symbol: str = "", days: int = 30, limit: int = 50) -> list:
    """查询已平仓交易记录"""
    conn = get_conn()
    q = "SELECT * FROM trades WHERE closed_at IS NOT NULL"
    params = []
    if symbol:
        q += " AND symbol=?"
        params.append(symbol.upper())
    if days:
        q += " AND closed_at >= datetime('now', ? || ' days', 'localtime')"
        params.append(f"-{days}")
    q += " ORDER BY closed_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_trades(symbol: str = "", days: int = 30, limit: int = 50) -> list:
    """查看所有交易（含未平仓）"""
    conn = get_conn()
    q = "SELECT * FROM trades WHERE 1=1"
    params = []
    if symbol:
        q += " AND symbol=?"
        params.append(symbol.upper())
    if days:
        q += " AND (closed_at >= datetime('now', ? || ' days', 'localtime') OR closed_at IS NULL)"
        params.append(f"-{days}")
    q += " ORDER BY opened_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── 复盘报告 ────────────────────────────────────────────────

def generate_report(days: int = 1) -> dict:
    """生成复盘报告（统计指定天数内的交易）"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM trades
        WHERE closed_at >= datetime('now', ? || ' days', 'localtime')
        ORDER BY closed_at DESC
    """, (f"-{days}",)).fetchall()
    conn.close()

    closed = [r for r in rows if r["closed_at"] and r["pnl"] is not None]
    open_trades = [r for r in rows if r["closed_at"] is None]

    if not closed:
        return {
            "period": f"过去{days}天",
            "total_trades": 0,
            "message": "无已平仓交易",
            "open_trades": [dict(r) for r in open_trades],
        }

    pnls = [r["pnl"] for r in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    report = {
        "period": f"过去{days}天",
        "total_trades": len(closed),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "total_pnl": round(sum(pnls), 2),
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(abs(sum(losses) / len(losses)), 2) if losses else 0,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses else float("inf"),
        "max_win": round(max(pnls), 2) if pnls else 0,
        "max_loss": round(min(pnls), 2) if pnls else 0,
        "by_symbol": {},
        "open_trades": [dict(r) for r in open_trades],
    }

    # 按品种
    symbols = set(r["symbol"] for r in closed)
    for sym in symbols:
        sym_trades = [r for r in closed if r["symbol"] == sym]
        sym_pnls = [r["pnl"] for r in sym_trades]
        sym_wins = [p for p in sym_pnls if p > 0]
        report["by_symbol"][sym] = {
            "trades": len(sym_trades),
            "pnl": round(sum(sym_pnls), 2),
            "win_rate": round(len(sym_wins) / len(sym_trades) * 100, 1),
        }

    return report


def gen_report_text(report: dict) -> str:
    """生成人类可读的复盘报告文本"""
    if report.get("total_trades", 0) == 0:
        txt = f"📊 {report['period']}复盘"
        if report.get("open_trades"):
            txt += "\n\n🟡 当前持仓："
            for t in report["open_trades"]:
                txt += f"\n  {t['symbol']} | {t['side']} @ {t['entry_price']} | {t['qty']}"
        return txt

    txt = f"📊 {report['period']}交易复盘\n"
    txt += f"\n📌 总交易：{report['total_trades']} 笔"
    txt += f"\n✅ 盈利：{report['win_count']} 笔 | ❌ 亏损：{report['loss_count']} 笔"
    txt += f"\n📈 胜率：{report['win_rate']}%"
    txt += f"\n💰 总盈亏：{report['total_pnl']:+.2f}"
    txt += f"\n📊 盈亏比：{report['profit_factor']:.2f}" if report['profit_factor'] != float('inf') else "\n📊 盈亏比：∞"
    txt += f"\n🏆 最大盈利：{report['max_win']:+.2f}"
    txt += f"\n💥 最大亏损：{report['max_loss']:+.2f}"

    if report.get("by_symbol"):
        txt += "\n\n📋 品种明细："
        for sym, data in sorted(report["by_symbol"].items(), key=lambda x: x[1]["pnl"], reverse=True):
            txt += f"\n  {sym}: {data['trades']}笔 | PnL {data['pnl']:+.2f} | 胜率{data['win_rate']}%"

    if report.get("open_trades"):
        txt += "\n\n🟡 当前持仓："
        for t in report["open_trades"]:
            txt += f"\n  {t['symbol']} {t['side']} @ {t['entry_price']} | {t['qty']}"

    return txt


# ─── CLI 入口 ─────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"

    if cmd == "report":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        r = generate_report(days)
        print(gen_report_text(r))
        print(json.dumps(r, indent=2, ensure_ascii=False))

    elif cmd == "trades":
        symbol = sys.argv[2] if len(sys.argv) > 2 else ""
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        for t in get_all_trades(symbol=symbol, days=days):
            status = "🟢" if float(t.get("pnl") or 0) > 0 else ("🔴" if float(t.get("pnl") or 0) < 0 else "🟡")
            closed = t.get("closed_at") or "持仓中"
            print(f"{status} #{t['id']} {t['symbol']} {t['side']} @{t['entry_price']} → {t.get('exit_price','?')} PnL:{t.get('pnl','?')} {closed}")

    elif cmd == "open":
        symbol = sys.argv[2] if len(sys.argv) > 2 else ""
        trades = get_open_trades(symbol=symbol)
        if not trades:
            print("🟢 无持仓")
        for t in trades:
            print(f"🟡 #{t['id']} {t['symbol']} {t['side']} @{t['entry_price']} qty:{t['qty']} 开仓:{t['opened_at']}")

    elif cmd == "add":
        _, symbol, side, entry, qty = sys.argv[1:6]
        reason = sys.argv[6] if len(sys.argv) > 6 else ""
        tid = add_trade(symbol, side, float(entry), float(qty), reason=reason)
        print(f"✅ 开仓记录 #{tid}")

    elif cmd == "close":
        tid = int(sys.argv[2])
        exit_price = float(sys.argv[3])
        pnl = float(sys.argv[4]) if len(sys.argv) > 4 else None
        result = close_trade(tid, exit_price, pnl)
        print(json.dumps(result, ensure_ascii=False))
