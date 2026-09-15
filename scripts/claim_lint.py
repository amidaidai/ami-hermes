"""叙事断言闸门（claim lint）：检查「外部引用类数字」有没有出处 + 时间窗。

设计目标（对治 2026-09-15 实际发生的幻觉）：
- 幻觉不是"判断错"，而是**引用不带出处和窗口**：把某周的数字挂到"昨日"、把两周前的文章拼进本次因果链。
- 本工具只判「可溯源完整性」，不判真伪（真伪靠打开原文）。

规则：
  R1 本地可核：数字能在本轮实拉数据文件里找到（±0.5%）→ PASS(local)
  R2 外部引用：句子必须同时含 ①http(s) 链接或具名来源（据/来源/Reuters/SoSoValue/CoinGlass/金十…）
                ②日期（YYYY-MM-DD / YYYY年M月D日 / M月D日）→ 否则 VIOLATION(no_source)
  R3 时间窗：句子含"昨日/昨天/今日/刚刚/本日/本周"等相对时间词，但同句链接 URL 里的日期
             距今 > 2 天 → VIOLATION(window_mismatch)
  R4 URL 日期可解析：/a/202608313859... 或 /2026/07/03/ 等形态自动提取

用法：
  python scripts/claim_lint.py --text "…"                  # 直接检查一段文字
  python scripts/claim_lint.py --file reply.md --asof 2026-09-15
  python scripts/claim_lint.py --file reply.md --data outputs/binance_BTCUSDT_20260915_0814.json
退出码：0 = 通过；1 = 有违规（可当发布前闸门）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# ---------- 抽取 ----------
NUM_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(\s*)(亿|万|美元|USD|美元|%|点|人|张)?")
TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
URL_RE = re.compile(r"https?://[^\s)>\]]+")
ISO_RE = re.compile(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})")
MD_RE = re.compile(r"(?<!\d)(\d{1,2})月(\d{1,2})日")
URLDATE_RE = re.compile(r"/(20\d{2})(\d{2})(\d{2})|/(20\d{2})/(\d{1,2})/(\d{1,2})/")
REL_WORDS = ("昨日", "昨天", "今日", "今天", "刚刚", "本日", "本周", "昨夜", "隔夜", "最新")
SRC_WORDS = ("据", "来源", "引自", "原文", "Reuters", "路透", "SoSoValue", "CoinGlass",
             "金十", "财联社", "Derive", "CoinMetrics", "Bloomb", "彭博")
# 只有“外部事件类”句子才进闸门：宏观/资金流/政策/地缘。
# 卡面里的价位与百分比（我自己实拉/推算）不属于外部断言，不该被要求出处。
EXTERNAL_SCOPE = ("ETF", "爆仓", "清算", "净流出", "净流入", "资金流入", "资金流出", "加息", "降息",
                  "CPI", "PPI", "非农", "失业率", "美联储", "FOMC", "美债", "收益率", "美元指数",
                  "DXY", "VIX", "标普", "纳斯达克", "道指", "黄金", "原油", "油价", "机构", "鲸鱼",
                  "链上", "稳定币", "资金费", "持仓量", "法案", "参议院", "众议院", "关税", "制裁",
                  "中东", "监管", "政策", "美联储主席", "会议纪要", "央行")
SHORT_DATE_RE = re.compile(r"(?<!\d)\d{1,2}/\d{1,2}(?!\d)")

SKIP_NUM = {"24", "15", "5", "1", "2", "3", "4", "6", "100"}  # 纯周期/倍率噪声
FIN_UNITS = ("亿", "万", "美元", "USD", "usd", "%", "％", "点", "张", "人")
UNIT_MULT = {"亿": 1e8, "万": 1e4}
LINE_REF_RE = re.compile(r"(第\s*\d+(?:[-–~]\d+)?\s*行|L\d+|行\s*\d+|v\d+\.\d+|\d+\.\d+\s*(?:flash|pro|turbo|token))")

# ---- 来源身份归一（多源交叉用）----
# 幻觉的典型形态是「一条二手摘要支撑整条因果链」。所以关键因果断言要求 ≥2 个**独立**来源；
# 同一家的不同写法（Reuters / 路透 / reuters.com）只能算 1 个。
SOURCE_ALIASES = {
    "reuters": "reuters", "路透": "reuters",
    "bloomberg": "bloomberg", "bloomb": "bloomberg", "彭博": "bloomberg",
    "coinglass": "coinglass", "sosovalue": "sosovalue", "farside": "farside",
    "jin10": "jin10", "金十": "jin10", "财联社": "cls", "cls": "cls",
    "wu blockchain": "wublock", "wublockchain": "wublock",
    "derive": "derive", "coinmetrics": "coinmetrics", "glassnode": "glassnode",
    "coindesk": "coindesk", "cointelegraph": "cointelegraph", "the block": "theblock",
    "alternative.me": "fng", "cftc": "cftc", "fred": "fred", "tradingview": "tradingview",
    "binance": "binance", "binance_deriv_bundle": "binance",
    "okx": "okx", "bybit": "bybit", "coinbase": "coinbase",
    "yahoo": "yahoo", "finance.yahoo": "yahoo", "wsj": "wsj", "cnbc": "cnbc",
    "macro_probe": "macro_probe", "xau_ohlcv_source": "xau_ohlcv",
}
DOMAIN_RE = re.compile(r"https?://(?:www\.)?([^/\s:)\]>'\"，。]+)")
_DOMAIN_ALIAS = {"finance.yahoo.com": "yahoo", "www.reuters.com": "reuters"}


def _domain_id(netloc: str) -> str:
    host = netloc.lower().strip(".")
    if host in _DOMAIN_ALIAS:
        return _DOMAIN_ALIAS[host]
    if host in SOURCE_ALIASES:
        return SOURCE_ALIASES[host]
    parts = host.split(".")
    head = parts[-2] if len(parts) >= 2 else host        # reuters.com → reuters
    return SOURCE_ALIASES.get(head, head)


def sources_in(text: str) -> set[str]:
    """抽出这段文字里出现的**独立来源身份**（具名媒体 + 链接域名，归一后去重）。"""
    low = (text or "").lower()
    ids = {canon for alias, canon in SOURCE_ALIASES.items() if alias in low}
    for m in DOMAIN_RE.finditer(text or ""):
        ids.add(_domain_id(m.group(1)))
    return ids


def norm_token(raw: str, unit: str | None) -> str:
    """把「数字+单位」归一成可精确比对的 token（单位必须参与，防 1.668亿 撞上本地 1.668）。"""
    mant = raw.replace(",", "")
    try:
        f = float(mant)
    except ValueError:
        return raw
    if unit in ("%", "％"):
        return f"{round(f, 4):g}%"
    if unit in UNIT_MULT:
        return f"{round(f, 6):g}{'万' if unit == '万' else '亿'}"
    # 无单位/元类：按绝对数值归一（>10 去掉小数尾）
    return f"{round(f, 4):g}"


def token_values(raw: str, unit: str | None) -> list[float]:
    """给出该 token 的候选数值集合（含单位换算），供与本地数值做单位感知比对。"""
    mant = raw.replace(",", "")
    try:
        f = float(mant)
    except ValueError:
        return []
    if unit in UNIT_MULT:
        return [f * UNIT_MULT[unit]]
    return [f]


def is_financial(num_str: str, unit: str | None, value: float) -> bool:
    """只放行“金额/比例/量级”型数字：带金融单位，或绝对值 ≥ 10,000（价格/资金量级）。"""
    if unit and unit in FIN_UNITS:
        return True
    return abs(value) >= 10_000


def claim_decimals(raw: str) -> int:
    """断言里写了几个小数位（0.13% → 2）。写作常会把 0.134% 舍入成 0.13%，这不算编造。"""
    return len(raw.split(".")[1]) if "." in raw else 0


def rounds_match(claim: float, local_val: float, raw: str) -> bool:
    """本地值按断言的精度四舍五入后相等即算命中（0.134 → 0.13）。"""
    dec = claim_decimals(raw)
    if dec > 4:
        return False
    try:
        return round(local_val, dec) == claim
    except Exception:
        return False


def _val(raw: str) -> float:
    return float(raw.replace(",", ""))


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；!?;\n])", text)
    return [p.strip() for p in parts if p.strip()]


def numbers_in_text(text: str) -> list[float]:
    """从任意文本里抽数值（含千分位），用于给“本会话已实拉”的数字建可核集合。"""
    out = []
    for m in re.finditer(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)", text or ""):
        try:
            out.append(_val(m.group(1)))
        except ValueError:
            pass
    return out


def load_local_numbers(paths: list[str]) -> list[float]:
    vals: list[float] = []

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            vals.append(float(o))
        elif isinstance(o, str):
            for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", o):
                try:
                    vals.append(_val(m.group(0)))
                except ValueError:
                    pass
    for p in paths:
        fp = Path(p)
        if fp.exists():
            try:
                walk(json.loads(fp.read_text(encoding="utf-8")))
            except Exception:
                pass
    return vals


def url_date(url: str) -> date | None:
    m = URLDATE_RE.search(url)
    if not m:
        return None
    try:
        if m.group(1):
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return date(int(m.group(4)), int(m.group(5)), int(m.group(6)))
    except ValueError:
        return None


def build_token_set(texts: list[str], json_paths: list[str] | None = None) -> set[str]:
    """构建“已实拉”token 集合：文本（工具产出/卡片）+ JSON 数值，单位参与归一。"""
    toks: set[str] = set()
    for t in texts:
        for m in NUM_RE.finditer(t or ""):
            toks.add(norm_token(m.group(1), m.group(3)))
    for path in (json_paths or []):
        p = Path(path)
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue

        def walk(o):
            if isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
            elif isinstance(o, (int, float)) and not isinstance(o, bool):
                toks.add(norm_token(f"{o:.6f}".rstrip("0").rstrip("."), None))
            elif isinstance(o, str):
                for m in re.finditer(r"\d[\d,]*(?:\.\d+)?\s*(%|亿|万)?", o):
                    s = m.group(0)
                    unit = m.group(1)
                    if unit:
                        s = s[: s.rindex(unit)]
                    toks.add(norm_token(s.strip(), unit))
        walk(data)
    return toks


# 本地可核语料**只能来自实拉数据产物**，不能包含我自己的叙述稿/审计存档：
# 否则我写进 audit/probe 里的错数字会反过来把幻觉"合法化"（自我背书）。
NARRATIVE_ARTIFACT_PREFIXES = ("audit_", "probe_", "diag_", "draft_", "verify_", "remeasure_",
                               "hallucination_", "github_", "claim_lint_", "chatty_", "reply_")
NARRATIVE_ARTIFACT_MARKERS = ("_card_v", "card_v6", "card_v7")


def is_narrative_artifact(path) -> bool:
    name = Path(path).name.lower()
    return name.startswith(NARRATIVE_ARTIFACT_PREFIXES) or any(m in name for m in NARRATIVE_ARTIFACT_MARKERS)


def lint(text: str, local: list[float], asof: date, tol: float = 0.0005,
         fin_only: bool = False, local_tokens: set[str] | None = None,
         scope_only: bool = False, min_sources: int = 2, strict: bool = False) -> dict:
    findings, violations, warnings = [], [], []
    prev_src = prev_date = None          # 同一段落内的来源/日期可继承（写作常态：据 X（日期）A；B；C）
    prev_row = False
    for para in text.split("\n\n"):
        prev_src = prev_date = None
        prev_row = False
        para_sources: set[str] = set()   # 该段已出现的独立来源（多源交叉判据）
        for sent in split_sentences(para):
            urls = URL_RE.findall(sent)
            # 抽数字前先抠掉 URL 与日期（否则链接 ID、年月日会被当成数字）
            bare = URL_RE.sub(" ", sent)
            bare = ISO_RE.sub(" ", bare)
            bare = MD_RE.sub(" ", bare)
            nums = [(m.group(1), m.group(3)) for m in NUM_RE.finditer(bare)]
            # 过滤时间/纯周期噪声
            keep = []
            for raw, unit in nums:
                if TIME_RE.match(sent.strip()) or (raw in SKIP_NUM and not unit):
                    continue
                if LINE_REF_RE.search(bare):        # 整句是行号/版本引用 → 跳过
                    continue
                if fin_only and not is_financial(raw, unit, _val(raw)):
                    continue
                keep.append((raw, unit))
            if not keep:
                continue
            has_src = bool(urls) or any(w in sent for w in SRC_WORDS)
            d_iso = ISO_RE.search(sent)
            d_md = MD_RE.search(sent)
            # 具名来源 + M/D 简写日期也认（如“Reuters 9/14”）
            has_date = bool(d_iso or d_md or (SHORT_DATE_RE.search(sent) and has_src))
            rel = [w for w in REL_WORDS if w in sent]
            in_scope = any(k in sent for k in EXTERNAL_SCOPE) if scope_only else True
            inherited = False
            cur_row = sent.lstrip().startswith("|")
            # 出处继承只在“正文句”之间成立；表格行必须自带出处，
            # 否则一行里的 Reuters/9-14 会让整张表的数字都“看起来有源”（实测漏检 1.668 亿）。
            if (not (has_src and has_date)) and prev_src and prev_date and not prev_row and not cur_row:
                has_src, has_date, inherited = True, True, True
            prev_row = cur_row
            if has_src and has_date:
                prev_src, prev_date = True, True
                para_sources |= sources_in(sent)
            for raw, unit in keep:
                v = _val(raw)
                is_local = bool(local_tokens and norm_token(raw, unit) in local_tokens)
                # 亿/万 量级必须 token 精确命中：数值容差在这两个量级上最容易撞车
                # （实测 1.668亿 曾被本地 1.668 放行 → 真幻觉漏检）
                if not is_local and unit not in UNIT_MULT:
                    for tv in token_values(raw, unit):
                        if any(abs(abs(tv) - abs(lv)) <= max(abs(lv) * tol, 1e-9)
                               or rounds_match(abs(tv), abs(lv), raw)
                               for lv in local):
                            is_local = True
                            break
                rec = {"num": raw + (unit or ""), "value": v, "sentence": sent[:120],
                       "grade": "local" if is_local else "external",
                       "src": has_src, "date": has_date, "rel": rel, "urls": urls,
                       "inherited": inherited}
                if is_local:
                    rec["verdict"] = "local"
                    findings.append(rec)
                    continue
                if not in_scope:
                    rec["verdict"] = "out_of_scope"
                    findings.append(rec)
                    continue
                if not has_src or not has_date:
                    rec["verdict"] = "VIOLATION:no_source"
                    violations.append(rec)
                else:
                    rec["verdict"] = "ok"
                    # 多源交叉：一条二手摘要撑不起整条因果链（这正是本次幻觉的形态）
                    if len(para_sources) < min_sources:
                        rec["sources"] = sorted(para_sources)
                        rec["evidence"] = (f"该段仅 {len(para_sources)} 个独立来源"
                                           f"（{', '.join(sorted(para_sources)) or '未识别'}）"
                                           f"，因果链断言建议 ≥{min_sources} 个独立来源交叉")
                        if strict:
                            rec["verdict"] = "VIOLATION:single_source"
                            violations.append(rec)
                        else:
                            rec["verdict"] = "weak_source"
                            warnings.append(rec)
                # R3 时间窗：相对时间词 + URL 日期过旧
                for u in urls:
                    ud = url_date(u)
                    if ud and rel and (asof - ud) > timedelta(days=2):
                        rec["verdict"] = "VIOLATION:window_mismatch"
                        rec["evidence"] = f"URL日期 {ud} 距 {asof} 已 {(asof - ud).days} 天，却配了相对时间词 {rel}"
                        violations.append(rec)
                        break
                findings.append(rec)
    # 去重（同一数字/同一结论只留一条），保持出现顺序
    seen, uniq = set(), []
    for v in violations:
        key = (v["num"], v["verdict"], v["sentence"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(v)
    seen_w, uniq_w = set(), []
    for w in warnings:
        key = (w["num"], w["verdict"], w["sentence"])
        if key in seen_w:
            continue
        seen_w.add(key)
        uniq_w.append(w)
    return {"findings": findings, "violations": uniq, "warnings": uniq_w}


def default_corpus(data_args: list[str] | None = None) -> tuple[list[str], set[str]]:
    """CLI 的默认「本机已实拉」语料。

    老实现把 `--data` 默认值写成目录名，`load_local_numbers()` 读目录会静默跳过 →
    **CLI 的本地可核集合实际是空的**，同一份文本在 CLI 与看门狗下结论不同（2026-09-15 审计发现）。
    这里改成：目录 → 展开成 JSON 文件列表，并同步构建 token 集合（与看门狗同源）。
    """
    if data_args:
        return list(data_args), build_token_set([], list(data_args))
    files: list[str] = []
    for d in ("outputs", "data"):
        p = Path(d)
        if p.is_dir():
            files += [str(f) for f in sorted(p.glob("*.json")) if not is_narrative_artifact(f)]
    files += [str(f) for f in sorted(Path(".").glob("scripts/.cache/*.json"))
              if not is_narrative_artifact(f)]
    files = sorted(set(files))
    return files, build_token_set([], files)


def tool_corpus(hours: float = 8.0) -> tuple[list[float], list[str]]:
    """可选：把本会话结构化行情工具产出也纳入（与看门狗完全一致的口径）。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import claim_watchdog as cw
        return cw._tool_corpus(hours)
    except Exception:
        return [], []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text")
    ap.add_argument("--file")
    ap.add_argument("--asof", default=date.today().isoformat())
    ap.add_argument("--data", action="append", default=[])
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--all-numbers", action="store_true",
                    help="不限制为金融量级数字（默认只查带单位或 ≥10,000 的）")
    ap.add_argument("--no-scope", action="store_true",
                    help="不限制为外部事件类句子（默认只查 ETF/爆仓/加息/CPI/美债/VIX/政策… 的句子）")
    ap.add_argument("--strict", action="store_true",
                    help="单一来源也判违规（默认只作弱提示）：发重要因果结论前用它")
    ap.add_argument("--min-sources", type=int, default=2,
                    help="因果链断言要求的独立来源数（默认 2）")
    ap.add_argument("--with-tools", action="store_true",
                    help="把本会话结构化行情工具产出也纳入可核语料（与看门狗完全同口径）")
    a = ap.parse_args()
    text = a.text or (Path(a.file).read_text(encoding="utf-8") if a.file else "")
    if not text:
        print("no input", file=sys.stderr)
        return 2
    asof = date.fromisoformat(a.asof)
    files, local_tokens = default_corpus(a.data)
    local = load_local_numbers(files)
    if a.with_tools:
        tvals, ttexts = tool_corpus()
        local += tvals
        local_tokens |= build_token_set(ttexts, [])
    # 默认口径必须与看门狗一致，否则同一份文本会得到两种结论（2026-09-15 审计发现）
    res = lint(text, local, asof, fin_only=not a.all_numbers, scope_only=not a.no_scope,
               local_tokens=local_tokens, min_sources=a.min_sources, strict=a.strict)
    if not a.quiet:
        print(f"[claim_lint] 可核语料 {len(files)} 文件 / {len(local)} 数值 / {len(local_tokens)} token")
    ext = [f for f in res["findings"] if f["grade"] == "external"]
    if not a.quiet:
        print(f"[claim_lint] 数字 {len(res['findings'])} 条 | 本地可核 {len(res['findings']) - len(ext)} | 外部引用 {len(ext)}")
        for f in res["findings"]:
            tag = {"local": "OK-local", "ok": ("OK-sourced*" if f.get("inherited") else "OK-sourced"),
                   "weak_source": "WEAK-source"}.get(f["verdict"], f["verdict"])
            print(f"  [{tag:<22}] {f['num']:<14} {f['sentence'][:64]}")
    if res["violations"]:
        print(f"\n拦截：{len(res['violations'])} 条外部数字缺出处/日期或时间窗错配")
        for v in res["violations"]:
            print(f"  ✗ {v['num']} ← {v['verdict']} | {v.get('evidence', '缺 URL/具名来源 或 缺日期')}")
            print(f"    句：{v['sentence']}")
        print("\n修法：给该句补「来源 URL + 发布/事件日期 + 时间窗」，或把它降级为『疑似/未验证』。")
        return 1
    if res["warnings"]:
        srcs: dict[tuple, int] = {}
        for w in res["warnings"]:
            srcs[tuple(w.get("sources") or ["未识别"])] = srcs.get(tuple(w.get("sources") or ["未识别"]), 0) + 1
        print(f"\n弱提示：{len(res['warnings'])} 条外部数字只有单一来源（未交叉）——默认不拦，"
              f"重要因果结论请跑 --strict")
        for k, n in sorted(srcs.items(), key=lambda kv: -kv[1])[:5]:
            print(f"  · {n} 条 仅 [{', '.join(k)}]")
        print("通过（但有单一来源提示）：出处与日期齐备，未做交叉验证。")
        return 0
    print("\n通过：所有外部引用数字都带出处与日期，且无时间窗错配。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
