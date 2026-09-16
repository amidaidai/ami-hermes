#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出 Hermes 三个记忆存储的完整状态。

只读、零三方依赖。用于回答「读取记忆」类请求时避免只读两个 .md 就交差。

输出：
  1. USER.md / MEMORY.md —— 逐条原文、条目数、字符预算、mtime、sha256、lock 状态
  2. memory_store.db   —— 表清单、条目数、时间线、分类计数、最后写入时间
  3. 注入判定           —— plugins.enabled 是否含 holographic、memory.provider 取值

用法:
  python memory_inventory.py            # 全部导出
  python memory_inventory.py --summary  # 只看计数与判定，不打印条目全文
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        pass

SUMMARY_ONLY = "--summary" in sys.argv
BJT = timezone(timedelta(hours=8))


def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "hermes"
    return Path.home() / ".hermes"


HOME = hermes_home()
MEM = HOME / "memories"

# 与 config.yaml 的 memory_char_limit / user_char_limit 对应；改了配置就同步这里
BUDGET = {"MEMORY.md": 2200, "USER.md": 1375}


def fmt_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, BJT).strftime("%Y年%m月%d日 %H:%M:%S")


def read_md(name: str) -> dict:
    p = MEM / name
    if not p.exists():
        return {"name": name, "exists": False}
    raw = p.read_bytes()
    txt = raw.decode("utf-8", "replace")
    # 字符预算口径：去掉 § 分隔符后的正文
    entries = [e.strip() for e in txt.split("§") if e.strip()]
    body = "".join(entries)
    lock = MEM / (name + ".lock")
    return {
        "name": name,
        "exists": True,
        "bytes": len(raw),
        "raw_chars": len(txt),
        "body_chars": len(body),
        "budget": BUDGET.get(name),
        "pct": round(len(body) / BUDGET[name] * 100, 1) if BUDGET.get(name) else None,
        "entries": entries,
        "mtime": fmt_ts(p.stat().st_mtime),
        "sha256_16": hashlib.sha256(raw).hexdigest()[:16],
        "lock_bytes": lock.stat().st_size if lock.exists() else None,
    }


def dump_db() -> dict:
    db = HOME / "memory_store.db"
    if not db.exists():
        return {"exists": False}
    out: dict = {"exists": True, "path": str(db), "bytes": db.stat().st_size, "tables": {}}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cur = con.cursor()
    names = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for t in names:
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        out["tables"][t] = {"rows": n, "cols": cols}
    if "facts" in names:
        rows = list(cur.execute(
            "SELECT fact_id, content, category, created_at, updated_at FROM facts ORDER BY fact_id"
        ))
        out["facts"] = [
            {"id": r[0], "category": r[2], "created_at": r[3], "updated_at": r[4],
             "chars": len(r[1] or ""), "preview": (r[1] or "")[:110]}
            for r in rows
        ]
        out["facts_by_day"] = dict(cur.execute(
            "SELECT substr(created_at,1,10), COUNT(*) FROM facts GROUP BY 1 ORDER BY 1"
        ))
        out["facts_by_category"] = dict(cur.execute(
            "SELECT category, COUNT(*) FROM facts GROUP BY 1"
        ))
        out["facts_latest_write"] = cur.execute("SELECT MAX(created_at) FROM facts").fetchone()[0]
        seq = cur.execute("SELECT seq FROM sqlite_sequence WHERE name='facts'").fetchone()
        out["facts_seq"] = seq[0] if seq else None
    if "memory_banks" in names:
        out["memory_banks_rows"] = cur.execute("SELECT COUNT(*) FROM memory_banks").fetchone()[0]
    con.close()
    return out


def injection_verdict() -> dict:
    cfg = HOME / "config.yaml"
    v = {"config": str(cfg), "exists": cfg.exists()}
    if not cfg.exists():
        return v
    txt = cfg.read_text(encoding="utf-8", errors="replace")
    v["holographic_enabled"] = bool(re.search(r"^\s*-\s*holographic\s*$", txt, re.M))
    m = re.search(r"^memory:\s*$(.*?)(^\S|\Z)", txt, re.M | re.S)
    v["memory_provider"] = None
    v["char_limits"] = {}
    if m:
        block = m.group(1)
        pm = re.search(r"^\s*provider:\s*['\"]?([^'\"\n]*)", block, re.M)
        if pm:
            v["memory_provider"] = pm.group(1).strip()
        for key in ("memory_char_limit", "user_char_limit"):
            km = re.search(rf"^\s*{key}:\s*(\d+)", block, re.M)
            if km:
                v["char_limits"][key] = int(km.group(1))
    v["db_injected"] = bool(v["holographic_enabled"])
    return v


USD = "=" * 72


def main() -> int:
    print(f"Hermes home : {HOME}")
    print(f"导出时间     : {datetime.now(BJT).strftime('%Y年%m月%d日 %H:%M:%S')} (BJT)")
    print(f"memories/ 存在: {MEM.exists()}")

    mds = [read_md("USER.md"), read_md("MEMORY.md")]
    for d in mds:
        print(f"\n{USD}\n# {d['name']}\n{USD}")
        if not d["exists"]:
            print("  不存在")
            continue
        lock = d["lock_bytes"]
        print(f"字节 {d['bytes']} | 原始字符 {d['raw_chars']} | 正文 {d['body_chars']}/{d['budget']}"
              f" ({d['pct']}%) | 条目 {len(d['entries'])}")
        print(f"最后修改 {d['mtime']} | sha256 {d['sha256_16']}"
              f" | lock {lock} 字节" + ("（未锁定）" if lock == 0 else ""))
        if not SUMMARY_ONLY:
            print("-" * 72)
            for i, e in enumerate(d["entries"], 1):
                print(f"【{i:02d}】{e}")

    db = dump_db()
    print(f"\n{USD}\n# memory_store.db\n{USD}")
    if not db["exists"]:
        print("  不存在")
    else:
        print(f"{db['path']} | {db['bytes']} 字节")
        for t, info in db["tables"].items():
            print(f"  表 {t:18s} {info['rows']:>6d} 行  {info['cols']}")
        if "facts" in db:
            print(f"  最新写入 {db['facts_latest_write']} | seq={db.get('facts_seq')}"
                  f" -> 已删 {max(0, (db.get('facts_seq') or 0) - len(db['facts']))} 条")
            print(f"  时间线 {db['facts_by_day']}")
            print(f"  分类   {db['facts_by_category']}")
            if "memory_banks_rows" in db:
                nb = db["memory_banks_rows"]
                print(f"  memory_banks {nb} 行" + ("（向量检索未建；hrr_vector 若全 NULL 即确认）" if nb == 0 else ""))
            if not SUMMARY_ONLY:
                print("-" * 72)
                for f in db["facts"]:
                    print(f"  [{f['id']:>3}] {f['created_at']} {f['category']:<10} {f['chars']:>5}字  {f['preview']}")

    v = injection_verdict()
    print(f"\n{USD}\n# 注入判定\n{USD}")
    print(f"  USER.md          -> 已注入（built-in，每轮全文）")
    print(f"  MEMORY.md        -> 已注入（built-in，每轮全文）")
    print(f"  config.yaml      -> {v['config']} (存在={v['exists']})")
    if v["exists"]:
        print(f"  plugins.enabled 含 holographic : {v['holographic_enabled']}")
        print(f"  memory.provider                : {v['memory_provider']!r}")
        print(f"  memory 字符上限                : {v['char_limits']}")
        print(f"  => memory_store.db 注入上下文   : {'是' if v['db_injected'] else '否（休眠库，token 贡献 0）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
