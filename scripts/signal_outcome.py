#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""信号 → 结果 闭环（P0）：验证「副指标确认」到底有没有提高结果。

数据来源：data/tv_dmi_cache.json（两个行动格合并表，已由既有采集链写好）
结果回看：Binance 公开 K 线（只对 Binance 可解析的品种；XAU/外汇标记 unresolved）

三个动作：
  init            建表
  record          读缓存 → 凡是主表处于 A 级可执行态，落一条信号（按 symbol+bar_ts 去重）
  eval            对未结算信号回看后续 K 线，判定先到目标还是先到止损
  report          分组统计：副确认放行 / 副未确认 / 副缺数据 / 副不参与

用法：
  python scripts/signal_outcome.py init
  python scripts/signal_outcome.py record
  python scripts/signal_outcome.py eval --max-bars 96
  python scripts/signal_outcome.py report
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "trading_journal.db"
CACHE = ROOT / "data" / "tv_dmi_cache.json"
BJT = timezone(timedelta(hours=8))
MAX_BARS_DEFAULT = 96          # 15m × 96 = 1 天
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"

DDL = """
CREATE TABLE IF NOT EXISTS signals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    bar_ts       INTEGER,               -- 信号所在 K 线起点(秒)
    entry        REAL, stop REAL, target REAL, rr REAL,
    direction    INTEGER,               -- 1=多 -1=空（由 入/止 几何反推，避免文本解析）
    main_concl   TEXT, main_path TEXT, main_risk TEXT, main_sync TEXT,
    sub_op       TEXT, sub_signal TEXT, sub_sync_state TEXT,
    sub_group    TEXT,                  -- confirmed / unconfirmed / missing / na
    price        REAL,
    UNIQUE(symbol, bar_ts)
);
CREATE TABLE IF NOT EXISTS outcomes (
    signal_id    INTEGER PRIMARY KEY REFERENCES signals(id),
    resolved_at  TEXT,
    status       TEXT,                  -- win / loss / timeout / unresolved
    bars_held    INTEGER,
    mfe_atr      REAL, mae_atr REAL,
    exit_price   REAL,
    r_mult       REAL,                  -- win=+R / loss=-1R / timeout=按到期收盘 mark-to-market
    note         TEXT
);
CREATE INDEX IF NOT EXISTS idx_sig_sym ON signals(symbol, bar_ts);
"""


def conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


# ---------------------------------------------------------------- 解析
def _num(s: str, key: str):
    m = re.search(key + r"\s*([0-9]+(?:\.[0-9]+)?)", s or "")
    return float(m.group(1)) if m else None


def parse_signal(row: dict) -> dict | None:
    """从合并行动格解析一条 A 级信号；不是 A 级返回 None。"""
    path = str(row.get("路径", ""))
    risk = str(row.get("风控", ""))
    if "A执行" not in path:
        return None
    entry, stop = _num(risk, "入"), _num(risk, "止")
    target, rr = _num(risk, "标"), _num(risk, r"·([0-9.]+)R")
    if not (entry and stop and target):
        return None
    direction = 1 if entry > stop else -1
    if (direction == 1 and target <= entry) or (direction == -1 and target >= entry):
        return None

    sub_op = str(row.get("操作", ""))
    sub_sig = str(row.get("信号", ""))
    sync = str(row.get("协同", ""))
    if "不计A级票" in sub_sig or "副不参与" in sync or "副关闭" in sync:
        group = "na"
    elif "S0未接" in sync or "合同不匹配" in sync or "S0无效" in sync:
        group = "missing"
    elif sub_op.startswith("确认"):
        group = "confirmed"
    elif re.search(r"副S\d", sync):
        group = "unconfirmed"
    else:
        group = "missing"
    m = re.search(r"副S(\d)", sync)
    return dict(entry=entry, stop=stop, target=target, rr=rr, direction=direction,
                main_concl=str(row.get("结论", "")), main_path=path, main_risk=risk,
                main_sync=sync, sub_op=sub_op, sub_signal=sub_sig,
                sub_sync_state=("S" + m.group(1)) if m else "", sub_group=group)


# ---------------------------------------------------------------- record
def record(cache_path: Path = CACHE, dry: bool = False, quiet: bool = False) -> int:
    if not cache_path.exists():
        if not quiet:
            print(f"[record] 缓存不存在：{cache_path}")
        return 0
    d = json.loads(cache_path.read_text(encoding="utf-8"))
    table = d.get("decision_table") or {}
    ts = d.get("timestamp", "")
    sym = d.get("symbol", "?")
    price = d.get("last_price")
    sig = parse_signal(table)
    if not sig:
        if not quiet:
            print(f"[record] {sym} 当前非 A 级可执行态（路径={table.get('路径','')!r}），不记录")
        return 0
    try:
        dt = datetime.fromisoformat(ts)
    except Exception:
        dt = datetime.now(BJT)
    # 用 15 分钟对齐的 bar_ts 作为去重键
    bar_ts = int(dt.timestamp()) // 900 * 900
    if dry:
        print("[record][dry] 将记录：", json.dumps({**sig, "symbol": sym, "bar_ts": bar_ts}, ensure_ascii=False))
        return 1
    with conn() as c:
        c.execute("""INSERT OR IGNORE INTO signals
            (created_at,symbol,bar_ts,entry,stop,target,rr,direction,
             main_concl,main_path,main_risk,main_sync,sub_op,sub_signal,sub_sync_state,sub_group,price)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (datetime.now(BJT).isoformat(timespec="seconds"), sym, bar_ts,
                   sig["entry"], sig["stop"], sig["target"], sig["rr"], sig["direction"],
                   sig["main_concl"], sig["main_path"], sig["main_risk"], sig["main_sync"],
                   sig["sub_op"], sig["sub_signal"], sig["sub_sync_state"], sig["sub_group"], price))
        n = c.total_changes
    if n or not quiet:
        print(f"[record] {sym} bar_ts={bar_ts} 新增 {n} 条（副组={sig['sub_group']} 动作={sig['sub_op']}）")
    return n


# ---------------------------------------------------------------- eval
def _binance_symbol(sym: str) -> str | None:
    s = sym.split(":")[-1].upper().replace(".P", "").replace("-", "")
    return s if re.fullmatch(r"[A-Z0-9]{5,20}", s) else None


def _klines(bsym: str, start_ms: int, limit: int = 200):
    url = f"{BINANCE_KLINES}?symbol={bsym}&interval=15m&startTime={start_ms}&limit={limit}"
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


def evaluate(max_bars: int = MAX_BARS_DEFAULT, dry: bool = False, quiet: bool = False) -> int:
    resolved = 0
    with conn() as c:
        rows = c.execute("""SELECT s.* FROM signals s LEFT JOIN outcomes o ON o.signal_id=s.id
                            WHERE o.signal_id IS NULL ORDER BY s.bar_ts""").fetchall()
    for r in rows:
        bsym = _binance_symbol(r["symbol"])
        if not bsym or not r["bar_ts"]:
            _save_outcome(r["id"], "unresolved", None, None, None, None, "非 Binance 可解析品种")
            continue
        try:
            ks = _klines(bsym, int(r["bar_ts"]) * 1000, max_bars + 5)
        except Exception as e:
            _save_outcome(r["id"], "unresolved", None, None, None, None, f"取K线失败: {e}")
            continue
        entry, stop, tgt, d = r["entry"], r["stop"], r["target"], r["direction"]
        risk = max(abs(entry - stop), 1e-9)
        mfe = mae = 0.0
        status, exit_px, bars, hit = None, None, 0, False
        for i, k in enumerate(ks[:max_bars]):
            hi, lo, cl = float(k[2]), float(k[3]), float(k[4])
            mfe, mae = max(mfe, (hi - entry) * d / risk), max(mae, (entry - lo) * d / risk)
            # 同一根内先到谁未知：保守判先到止损（不给自己虚高胜率）
            hit_stop = lo <= stop if d == 1 else hi >= stop
            hit_tgt = hi >= tgt if d == 1 else lo <= tgt
            bars = i + 1
            if hit_stop:
                status, exit_px, hit = "loss", stop, True
                break
            if hit_tgt:
                status, exit_px, hit = "win", tgt, True
                break
        if status == "win":
            r_mult = (tgt - entry) * d / risk
        elif status == "loss":
            r_mult = -1.0
        else:
            # 关键：观察窗还没走满就不能结算，否则新信号下一根就被误判成"超时"
            if len(ks) < max_bars:
                continue
            last = float(ks[max_bars - 1][4])
            status, exit_px, bars = "timeout", last, max_bars
            r_mult = (last - entry) * d / risk
        _save_outcome(r["id"], status, bars, mfe, mae, exit_px, "", r_mult)
        resolved += 1
    if not dry and (resolved or not quiet):
        print(f"[eval] 结算 {resolved} 条")
    return resolved


def _save_outcome(sid, status, bars, mfe, mae, px, note, r_mult=None):
    with conn() as c:
        c.execute("""INSERT OR REPLACE INTO outcomes
            (signal_id,resolved_at,status,bars_held,mfe_atr,mae_atr,exit_price,r_mult,note)
            VALUES (?,?,?,?,?,?,?,?,?)""",
                  (sid, datetime.now(BJT).isoformat(timespec="seconds"), status, bars, mfe, mae, px, r_mult, note))


# ---------------------------------------------------------------- report
GROUP_LABEL = {"confirmed": "副确认放行", "unconfirmed": "副未确认(降权/不升级)",
               "missing": "副缺数据/未接", "na": "副不参与(非加密)"}


def report() -> None:
    with conn() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(outcomes)")]
        if "r_mult" not in cols:
            c.execute("ALTER TABLE outcomes ADD COLUMN r_mult REAL")
        rows = c.execute("""SELECT s.sub_group, o.status, o.r_mult, o.bars_held, o.mfe_atr, o.mae_atr
                            FROM signals s JOIN outcomes o ON o.signal_id=s.id""").fetchall()
        total = c.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    print(f"信号总数 {total}，已结算 {len(rows)}")
    if not rows:
        print("暂无数据。先让 record / eval 跑起来。")
        return
    agg: dict[str, dict] = {}
    for r in rows:
        g = agg.setdefault(r["sub_group"], {"win": 0, "loss": 0, "timeout": 0, "unresolved": 0,
                                            "rs": [], "bh": 0, "mfe": [], "mae": []})
        g[r["status"]] = g.get(r["status"], 0) + 1
        if r["r_mult"] is not None:
            g["rs"].append(r["r_mult"])
        if r["bars_held"]:
            g["bh"] = max(g["bh"], r["bars_held"])
        if r["mfe_atr"] is not None:
            g["mfe"].append(r["mfe_atr"])
            g["mae"].append(r["mae_atr"])

    def m(v):
        return (sum(v) / len(v)) if v else float("nan")

    print(f"\n{'分组':<20}{'胜':>4}{'负':>4}{'超':>4}{'未':>4}{'胜率':>8}{'期望R':>9}{'MFE':>7}{'MAE':>7}")
    for k, v in agg.items():
        w, l, t, u = v.get("win", 0), v.get("loss", 0), v.get("timeout", 0), v.get("unresolved", 0)
        n = w + l + t
        wr = f"{w/n*100:.0f}%" if n else "—"
        print(f"{GROUP_LABEL.get(k, k):<20}{w:>4}{l:>4}{t:>4}{u:>4}{wr:>8}"
              f"{m(v['rs']):>9.2f}{m(v['mfe']):>7.2f}{m(v['mae']):>7.2f}")
    print("\n期望R = 全部结算单的平均 R 倍数（胜=实际R，负=−1R，超时=按到期收盘折算，不丢样本）。")
    print("只有『副确认放行』组的期望R 显著高于『副未确认』组，副指标那票否决权才有数据支撑。")


def _migrate(c: sqlite3.Connection) -> None:
    """老库补列：CREATE TABLE IF NOT EXISTS 不会给已存在的表加列。"""
    cols = [r[1] for r in c.execute("PRAGMA table_info(outcomes)")]
    if "r_mult" not in cols:
        c.execute("ALTER TABLE outcomes ADD COLUMN r_mult REAL")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["init", "record", "eval", "report", "tick"])
    ap.add_argument("--max-bars", type=int, default=MAX_BARS_DEFAULT)
    ap.add_argument("--cache", default=str(CACHE))
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    with conn() as c:
        c.executescript(DDL)
        _migrate(c)
    if a.action == "init":
        print(f"[init] 表已就绪：{DB}")
    elif a.action == "record":
        record(Path(a.cache), a.dry)
    elif a.action == "eval":
        evaluate(a.max_bars, a.dry)
    elif a.action == "tick":
        # 静默：只有真发生事（新增信号/结算）才输出，适配 no_agent cron
        n_rec = record(Path(a.cache), quiet=True)
        n_ev = evaluate(a.max_bars, quiet=True)
        if n_rec or n_ev:
            print(f"[tick] 新增信号 {n_rec}，结算 {n_ev}")
    else:
        report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
