#!/usr/bin/env python3
"""五周期TV全量扫描（1D/4h/1h/15m/5m）—— 主指标+副指标行动格、study_values、OHLCV、labels/lines/boxes。

用法: python scripts/tv_full_scan.py [SYMBOL] [--out FILE]
输出: JSON 落盘 outputs/ + stdout 紧凑摘要（供 agent 直接读取）。
"""
import sys, os, json, asyncio, argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(r"D:/Hermes agent")
sys.path.insert(0, str(ROOT / "scripts"))

from fetch_tv_mcp import (  # noqa
    stdio_client, StdioServerParameters, call_tool, parse_result,
    set_symbol, set_timeframe, switch_stats_line, _tf_alias,
)

TFS = [("1D", "1D"), ("240", "4h"), ("60", "1h"), ("15", "15m"), ("5", "5m")]
WAIT = {"1D": 18, "240": 16, "60": 14, "15": 16, "5": 14}


async def _jt(session, tool, args=None):
    """调用 MCP 工具并把文本结果解析成 JSON（失败返回原始文本）。"""
    try:
        r = await call_tool(session, tool, args or {})
        t = parse_result(r)
        try:
            return json.loads(t)
        except Exception:
            return t
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}


def _rows_to_dict(rows):
    """rows 可能是 [\"键 | 值\", ...] 字符串数组，或 [{cells:[...]}]，统一成 {键: 值}。"""
    d = {}
    for r in rows or []:
        if isinstance(r, dict):
            k = str(r.get("label") or r.get("key") or r.get("name") or "").strip()
            v = r.get("value")
            if v is None:
                cells = r.get("cells") or []
                v = " | ".join(str(x) for x in cells[1:]) if len(cells) > 1 else ""
            d[k] = v
        elif isinstance(r, str):
            if "|" in r:
                k, _, v = r.partition("|")
                d[k.strip()] = v.strip()
            else:
                d[r.strip()] = ""
        elif isinstance(r, (list, tuple)) and len(r) >= 2:
            d[str(r[0]).strip()] = r[1]
    return d


def _tbl_rows(tbl):
    """把 pine_tables 返回压成 {table_title: {row: value}} 紧凑结构。"""
    out = {}
    if not isinstance(tbl, dict):
        return out
    studies = tbl.get("studies")
    if isinstance(studies, list):
        for s in studies:
            if not isinstance(s, dict):
                continue
            title = str(s.get("name") or "table")
            tables = s.get("tables") or []
            merged = {}
            for t in tables:
                if isinstance(t, dict):
                    merged.update(_rows_to_dict(t.get("rows") or t.get("data")))
                elif isinstance(t, list):
                    merged.update(_rows_to_dict(t))
            if merged:
                out[title] = merged
        if out:
            return out
    tables = tbl.get("tables") or tbl.get("result") or []
    if isinstance(tables, str):
        try:
            tables = json.loads(tables)
        except Exception:
            return out
    if isinstance(tables, dict):
        tables = tables.get("tables", [])
    for i, t in enumerate(tables if isinstance(tables, list) else []):
        if isinstance(t, dict):
            title = t.get("title") or t.get("study") or f"table{i}"
            out[str(title)] = _rows_to_dict(t.get("rows") or t.get("data"))
        elif isinstance(t, list):
            out[f"table{i}"] = _rows_to_dict(t)
    return out


async def scan(symbol, out_path, quiet=False):
    server = ROOT / "tools/tradingview-mcp/src/server.js"
    params = StdioServerParameters(command="node", args=[str(server)])
    result = {"symbol": symbol, "bjt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "tf": {}}
    async with stdio_client(params) as (read, write):
        from mcp import ClientSession
        async with ClientSession(read, write) as session:
            await session.initialize()
            await set_symbol(session, symbol)
            await asyncio.sleep(2)
            for tf, label in TFS:
                await set_timeframe(session, tf)
                await asyncio.sleep(WAIT.get(tf, 15))
                state = await _jt(session, "chart_get_state")
                cur_res = str(state.get("resolution") or "") if isinstance(state, dict) else ""
                entry = {"label": label, "resolution_seen": cur_res,
                         "chart_symbol_seen": state.get("symbol") if isinstance(state, dict) else None}
                entry["sv"] = await _jt(session, "data_get_study_values")
                entry["ohlcv"] = await _jt(session, "data_get_ohlcv", {"summary": True})
                entry["t_main"] = _tbl_rows(await _jt(session, "data_get_pine_tables", {"study_filter": "SVP"}))
                entry["t_sub"] = _tbl_rows(await _jt(session, "data_get_pine_tables", {"study_filter": "Volume Aggregated"}))
                entry["lines"] = await _jt(session, "data_get_pine_lines")
                entry["labels"] = await _jt(session, "data_get_pine_labels")
                entry["boxes"] = await _jt(session, "data_get_pine_boxes", {"study_filter": "SVP"})
                result["tf"][label] = entry
                if not quiet:
                    print(f"[ok] {label} res={cur_res} bars_tables={len(entry['t_main'])}/{len(entry['t_sub'])}", flush=True)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result, out


def fmt(result, out):
    L = []
    L.append(f"# TV五周期扫描 {result['symbol']} @ {result['bjt']} BJT")
    for label in ["1D", "4h", "1h", "15m", "5m"]:
        e = result["tf"].get(label) or {}
        L.append(f"\n=== {label} (res_seen={e.get('resolution_seen')}, sym={e.get('chart_symbol_seen')}) ===")
        oh = e.get("ohlcv")
        if isinstance(oh, dict):
            L.append("OHLCV: " + json.dumps({k: v for k, v in oh.items() if k != "bars"}, ensure_ascii=False))
        sv = e.get("sv")
        if isinstance(sv, dict):
            keep = {}
            for s in (sv.get("studies") or []):
                nm = s.get("name", "")
                vv = s.get("values") or {}
                if "SVP" in nm or "Volume Agg" in nm or "Anchored" in nm:
                    keep[nm] = {k: v for k, v in vv.items() if v not in (None, "", 0)}
            if keep:
                L.append("SV: " + json.dumps(keep, ensure_ascii=False)[:2600])
            else:
                L.append("SV: (无SVP/AggVol键)" + json.dumps(sv, ensure_ascii=False)[:600])
        for tag, key in (("主格", "t_main"), ("副格", "t_sub")):
            d = e.get(key) or {}
            if d:
                for title, rows in d.items():
                    L.append(f"{tag}[{title}]: " + json.dumps(rows, ensure_ascii=False))
            else:
                L.append(f"{tag}: (空)")
        for k in ("lines", "labels", "boxes"):
            v = e.get(k)
            L.append(f"{k}: " + json.dumps(v, ensure_ascii=False)[:1400])
    txt = "\n".join(L)
    print("\n" + txt)
    side = out.with_suffix(".txt")
    side.write_text(txt, encoding="utf-8")
    print(f"\n[saved] {out}  |  {side}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", nargs="?", default="BINANCE:BTCUSDT.P")
    ap.add_argument("--out", default="")
    ap.add_argument("--tfs", default="", help="逗号分隔子集，如 5 或 15,5")
    args = ap.parse_args()
    if args.tfs:
        want = [x.strip() for x in args.tfs.split(",") if x.strip()]
        TFS = [t for t in TFS if _tf_alias(t[0]) in [_tf_alias(w) for w in want]]
        for t in TFS:
            WAIT[t[0]] = 8
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    tick = args.symbol.split(":")[-1]
    outp = args.out or str(ROOT / "outputs" / f"tv_scan_{tick}_{ts}.json")
    res, o = asyncio.run(scan(args.symbol, outp))
    fmt(res, o)
    print(switch_stats_line())
