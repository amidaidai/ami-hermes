"""叙事断言闸门·看门狗（no-agent cron 用）

每轮扫描 Hermes state.db 里**最近的 assistant 文本回复**，对「外部引用类数字」做溯源检查：
- 有违规 → 打印告警（cron deliver=local 直接留档）+ 追加 data/claim_lint_alerts.jsonl
- 只有单一来源（未交叉）→ 不报警、不阻断，追加 data/claim_lint_weak.jsonl（趋势可查）
- 无违规 → 静默（遵循零 token 看门狗约定：只在触发时输出）

设计要点：
- 幂等：用 data/claim_watchdog_state.json 记 last_id，重跑不重复报警
- 只检查「归因型」消息（含 因为/由于/受…影响/归因/原因/推动/压制/降权/流出 等标记），
  避免把纯行情卡里的正常数字刷成告警
- 本机可核数据 = outputs/ 与 data/ 下最近 30 个 JSON

用法：
  python scripts/claim_watchdog.py                 # cron 默认：近 3h，写状态
  python scripts/claim_watchdog.py --hours 8 --dry # 试跑：不写状态
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from claim_lint import (lint, load_local_numbers, numbers_in_text,  # noqa: E402
                        build_token_set)
import claim_lint as lintmod  # noqa: E402

DB = Path.home() / "AppData/Local/hermes/state.db"
STATE = ROOT / "data/claim_watchdog_state.json"
ALERTS = ROOT / "data/claim_lint_alerts.jsonl"
WEAK = ROOT / "data/claim_lint_weak.jsonl"       # 单一来源（未交叉）：只落档，不报警
HEARTBEAT = ROOT / "data/claim_watchdog_heartbeat.json"

# 哪些工具的产出算“本会话已实拉”（数字可核）：结构化行情/指标工具。
# 关键排除：web_search / web_extract / browser / terminal —— 它们返回的是外部来源或任意文本，
# 必须走“带出处”通道（terminal 尤其不能算：curl 出来的新闻数字会被当成“已实拉”）。
LOCAL_TOOL_RE = re.compile(
    r"(binance|tradingview|financekit|jin10|stock_api|stock-api|fmp|yfinance|finnhub|alphavantage|akshare)",
    re.I)

# 本地脚本缓存也要进“已实拉”语料：非加密品种（外汇利率、黄金快照）不走 MCP 工具，
# 只落 JSON 缓存——不纳进来，非加密卡手拉的数字会被误判成“外部无源”。
CACHE_GLOBS = ("scripts/.cache/*.json", "data/cache/*.json")

# 归因型标记：出现其一才纳入检查（避免对纯数字卡刷告警）
ATTRIB = ("因为", "由于", "受", "影响", "原因", "归因", "推动", "压制", "驱动", "降权", "流出", "爆仓",
          "加息", "ETF", "据", "来源", "推升", "拖累", "利空", "利多")
# 必须是「行情/市场」类内容才检查——否则会把 config 审计、代码评审里的行号/版本号刷成告警
MARKET = ("BTC", "比特币", "BTCUSDT", "ETH", "以太", "XAU", "黄金", "现价", "关键位", "行情",
          "美债", "美股", "爆仓", "资金费", "ETF", "美元", "止损", "仓位", "结构", "CVD", "加息")
SKIP = ("config.yaml", "model.default", "auxiliary.", "provider=", "pytest", "def ", "import ",
        "tests/", "行号")
MIN_LEN = 300
# 真行情文本必带千分位价格（77,742 / 78,116）。用它区分「顺口提了脚本名的行情回复」
# 与「纯代码/配置讨论」——老实现只要命中 SKIP 词就整条跳过，会把行情回复漏检（实测）。
PRICE_RE = re.compile(r"\d{2},\d{3}")


def relevant(txt: str) -> bool:
    if not (any(k in txt for k in MARKET) and any(k in txt for k in ATTRIB)):
        return False
    code_hits = sum(1 for k in SKIP if k in txt)
    if code_hits and not PRICE_RE.search(txt):
        return False          # 纯代码/配置讨论：无价格 → 跳过
    return True


def _state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_id": 0}


def _recent_assistant(hours: float, after_id: int) -> list[tuple]:
    if not DB.exists():
        return []
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    cut = time.time() - hours * 3600
    return con.execute(
        "select id, session_id, content, timestamp from messages "
        "where role='assistant' and id > ? and timestamp >= ? and length(coalesce(content,'')) >= ? "
        "order by id asc", (after_id, cut, MIN_LEN)).fetchall()


def _tool_corpus(hours: float) -> tuple[list[float], list[str]]:
    """本会话“已实拉”的证据：结构化行情/指标工具产出 + 本地卡片 md。

    精度关键：卡片里的百分比/价位来自 TV 面板现场读数，不在任何 JSON 里，
    若不纳入，闸门会把“我实拉的”误判成“外部无源”（实测误报率 90%）。
    但 web_search/web_extract/browser 的文本一律排除——它们返回外部来源，必须走带出处通道。
    """
    texts, vals = [], []
    if DB.exists():
        con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
        cut = time.time() - hours * 3600
        for (name, content) in con.execute(
                "select coalesce(tool_name,''), coalesce(content,'') from messages "
                "where role='tool' and timestamp >= ? and length(coalesce(content,'')) > 0", (cut,)):
            if LOCAL_TOOL_RE.search(name):
                texts.append(content)
                vals += numbers_in_text(content)
    for p in sorted(ROOT.glob("data/auto_card_*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:8]:
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
            texts.append(t)
            vals += numbers_in_text(t)
        except Exception:
            pass
    return vals, texts


def _db_status() -> tuple[bool, str]:
    """DB 可用性检查（封住“静默失败”：读不到 DB 时必须可见，而不是看起来干净）。"""
    if not DB.exists():
        return False, f"state.db 不存在：{DB}"
    try:
        con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
        con.execute("select 1 from messages limit 1").fetchone()
        return True, "ok"
    except Exception as e:
        return False, f"state.db 不可读：{e}"


def _write_heartbeat(**extra) -> None:
    payload = {"updated_epoch": time.time(),
               "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
               **extra}
    HEARTBEAT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def _local_files(limit: int = 30) -> list[str]:
    """本机“已实拉”证据文件：最近的 outputs/ 与 data/ JSON + 脚本缓存（外汇/黄金等非加密源）。

    排除自己的叙述稿/审计存档（`audit_*`/`probe_*`/`draft_*`…）：那些文件里的错数字
    不能反过来成为“本地可核”证据，否则幻觉会自我合法化。
    """
    jf = list((ROOT / "outputs").glob("*.json")) + list((ROOT / "data").glob("*.json"))
    cand = sorted([p for p in jf if not lintmod.is_narrative_artifact(p)],
                  key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    for g in CACHE_GLOBS:
        cand += [p for p in ROOT.glob(g) if not lintmod.is_narrative_artifact(p)]
    return [str(f) for f in cand]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=3.0)
    ap.add_argument("--dry", action="store_true", help="不写状态、不落告警文件、不写心跳")
    ap.add_argument("--all", action="store_true", help="不过滤归因型标记")
    ap.add_argument("--strict", action="store_true",
                    help="单一来源也判违规（默认只落 weak 档，不报警）")
    a = ap.parse_args()
    t0 = time.time()

    db_ok, db_detail = _db_status()
    if not db_ok:
        # 非静默：让 cron 的 local 投递留下证据（否则“读不到”和“跑干净”长得一样）
        print(f"⚠️ 叙事断言闸门无法运行：{db_detail}")
        print("   这不是‘本轮无违规’，是闸门本身没跑起来 —— 请检查 state.db 路径/权限。")
        if not a.dry:
            _write_heartbeat(db_ok=False, error=db_detail, checked=0, hits=0)
        return 2

    st = _state()
    rows = _recent_assistant(a.hours, int(st.get("last_id", 0)))
    files = _local_files()
    tool_vals, tool_texts = _tool_corpus(a.hours)
    local = load_local_numbers(files) + tool_vals
    local_tokens = build_token_set(tool_texts, files)

    hits, weak, checked, max_id = [], [], 0, int(st.get("last_id", 0))
    for mid, sid, content, ts in rows:
        max_id = max(max_id, mid)
        txt = content or ""
        if not a.all and not relevant(txt):
            continue
        checked += 1
        res = lint(txt, local, date.today(), fin_only=not a.all, local_tokens=local_tokens,
                   scope_only=not a.all, min_sources=2, strict=bool(a.strict))
        if res["violations"]:
            hits.append({"msg_id": mid, "session": sid,
                         "when": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)),
                         "violations": res["violations"]})
        elif res.get("warnings"):
            # 单一来源：不报警、不阻断，只落档（趋势可查），避免把正常引用刷成告警
            weak.append({"msg_id": mid,
                         "when": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)),
                         "count": len(res["warnings"]),
                         "sources": sorted({s for w in res["warnings"] for s in (w.get("sources") or [])}),
                         "sample": res["warnings"][0]["sentence"][:90]})
    if not a.dry:
        STATE.write_text(json.dumps({"last_id": max_id, "at": time.strftime("%Y-%m-%d %H:%M:%S")},
                                    ensure_ascii=False), encoding="utf-8")
        _write_heartbeat(db_ok=True, checked=checked, hits=len(hits), weak=len(weak),
                         local_vals=len(local), tokens=len(local_tokens), local_files=len(files),
                         hours=a.hours, took_ms=int((time.time() - t0) * 1000))
        if hits:
            with ALERTS.open("a", encoding="utf-8") as f:
                for h in hits:
                    f.write(json.dumps(h, ensure_ascii=False) + "\n")
        if weak:
            with WEAK.open("a", encoding="utf-8") as f:
                for w in weak:
                    f.write(json.dumps(w, ensure_ascii=False) + "\n")

    if not hits:
        return 0                      # 静默：不产生 cron 输出
    print(f"⚠️ 叙事断言闸门：{len(hits)} 条回复存在「外部数字缺出处/时间窗错配」（已查 {checked} 条）")
    print(f"  明细落档：{ALERTS.as_posix()}")
    for h in hits:
        print(f"\n- {h['when']}  session={h['session']}  msg#{h['msg_id']}  {len(h['violations'])} 处")
        for v in h["violations"][:6]:
            print(f"    ✗ {v['num']:<12} {v['verdict']} | {v['sentence'][:70]}")
            if v.get("evidence"):
                print(f"      {v['evidence']}")
    print("\n修法：补「来源 URL + 发布/事件日期 + 时间窗」，或把该句降级为『疑似/未验证』。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
