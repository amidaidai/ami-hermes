#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""闸门饥饿审计 — GO-A 授权可达性探针（只读，零写入）。

用法:
    python scripts/gate_starvation_audit.py [仓库根目录]

回答一个问题：裁决系统在长窗口里真的给得出可执行授权吗，还是只有一个输出值？
判据：可执行授权出现 0 次（窗口 >=1 个月 / >=200 条）=> 结构缺陷，不是行情判断。

节次:
  1 档位 / 等级分布            从没出现过的档位 = 被结构封死
  2 有方向 vs 无方向            必看：neutral 扫描 tick 会把「本来没方向」算成「被否决」
  3 有方向信号拦因频次
  4 「只差一个条件」子集         离放行最近，修复杠杆最大
  5 拦因数量 + 等待家族共现     同一件「不做」被记成几条
  6 结果首触分布                判断结果数据能否为闸门背书

详见 references/go-a-reachability-audit.md。
"""
from __future__ import annotations

import collections
import datetime
import json
import os
import statistics
import sys

WAIT_FAMILY = (
    "no_direction", "b_wait", "svp_wait_language", "svp_no_trade_reason",
    "bar_closed", "location", "trigger", "dual_alignment",
)
EXECUTABLE_STATES = ("GO-A",)
DIRECTIONS = ("long", "short")


# ---------------------------------------------------------------- 基础

def load_jsonl(path):
    recs = []
    if not os.path.exists(path):
        return recs
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except Exception:
                continue
    return recs


def pct(n, d):
    return f"{(n / d * 100) if d else 0:5.1f}%"


def ts_str(ms):
    try:
        return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"


def r_of(rec, horizon):
    oc = (rec.get("outcome") or {}).get(horizon) or {}
    hit = oc.get("first_hit")
    if hit == "target":
        return abs(oc.get("mfe_r") or 0.0)
    if hit == "stop":
        return -abs(oc.get("mae_r") or 1.0)
    return 0.0


def sec(title):
    print("\n" + "=" * 62)
    print(title)
    print("=" * 62)


# ---------------------------------------------------------------- 主流程

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    sig_p = os.path.join(root, "data", "shadow", "decision_signals.jsonl")
    out_p = os.path.join(root, "data", "shadow", "decision_outcomes.jsonl")

    sigs = load_jsonl(sig_p)
    outs = load_jsonl(out_p)
    if not sigs:
        print(f"[unavailable] 读不到 {sig_p}")
        print("影子账本路径可能已变——先用 search_files 找 decision_signals.jsonl 再重跑。")
        return 2

    ts = [s.get("ts") for s in sigs if s.get("ts")]
    sec(f"影子账本窗口　{len(sigs)} 条信号 / {len(outs)} 条已标注")
    if ts:
        print(f"  {ts_str(min(ts))} → {ts_str(max(ts))}")
    print(f"  账本: {sig_p}")

    # 1 档位 / 等级
    sec("1. 档位与等级分布　（出现 0 次的档位 = 被结构封死）")
    st = collections.Counter(s.get("final_state") for s in sigs)
    gr = collections.Counter(s.get("grade") for s in sigs)
    for k, v in st.most_common():
        print(f"  final_state {str(k):<12s} {v:5d}  {pct(v, len(sigs))}")
    print()
    for k, v in gr.most_common():
        print(f"  grade       {str(k):<12s} {v:5d}  {pct(v, len(sigs))}")
    n_exec = sum(v for k, v in st.items() if k in EXECUTABLE_STATES)
    print(f"\n  → 可执行授权 {EXECUTABLE_STATES} 次数: {n_exec}")
    print("    0 次 = 结构缺陷；不要解释成「行情不好」。")

    # 2 有方向 vs 无方向
    sec("2. 有方向 vs 无方向　（不能把 neutral 扫描 tick 算成「被否决」）")
    for k, v in collections.Counter(s.get("side") for s in sigs).most_common():
        print(f"  side={str(k):<8s} {v:5d}  {pct(v, len(sigs))}")
    dirs = [s for s in sigs if s.get("side") in DIRECTIONS]
    print(f"\n  有方向候选 {len(dirs)}/{len(sigs)} = {pct(len(dirs), len(sigs))}")
    print(f"  其中有方向的裁决: {dict(collections.Counter(s.get('final_state') for s in dirs))}")
    print(f"  其中有方向的等级: {dict(collections.Counter(s.get('grade') for s in dirs))}")
    if not dirs:
        print("  [warn] 没有有方向候选——先查上游方向判定，别急着谈闸门。")

    # 3 拦因频次
    sec("3. 有方向信号的拦因频次　（回源码把每道门定性为行情判断 or 工程状态）")
    c = collections.Counter()
    for s in dirs:
        for b in (s.get("blockers") or []):
            c[b] += 1
    for k, v in c.most_common(20):
        print(f"  {str(k):<26s} {v:5d}  {pct(v, len(dirs))}")

    # 4 只差一个条件
    sec("4. 「只差一个条件」子集　（离放行最近 = 修复杠杆最大）")
    only = collections.Counter()
    for s in dirs:
        b = s.get("blockers") or []
        if len(b) == 1:
            only[b[0]] += 1
    for k, v in only.most_common():
        print(f"  仅 {str(k):<24s} 挡住: {v}")
    print(f"\n  合计「只差一步」: {sum(only.values())}/{len(dirs)}")
    zero = sum(1 for s in sigs if not (s.get("blockers") or []))
    print(f"  零拦因信号: {zero}/{len(sigs)} = {pct(zero, len(sigs))}（接近 0 说明每一条都被拦）")

    # 5 拦因数量 + 等待家族
    sec("5. 拦因数量与等待家族　（同一件「不做」被记成几条）")
    cnt = collections.Counter(len(s.get("blockers") or []) for s in dirs)
    for k in sorted(cnt):
        print(f"  {k} 个拦因: {cnt[k]} 条")
    fam = collections.Counter()
    for s in sigs:
        hit = len(set(s.get("blockers") or []) & set(WAIT_FAMILY))
        if hit:
            fam[hit] += 1
    print(f"\n  至少撞 1 个等待家族拦因: {sum(fam.values())}/{len(sigs)}")
    print(f"  撞 K 个（K→条数）: {dict(sorted(fam.items()))}　K>=5 即为语义重复，汇报时折成 1 条主因")

    # 6 结果
    sec("6. 结果分布　（影子价位多半不可执行 -> 不能为闸门背书）")
    for h in ("h4", "h8", "h16"):
        print(f"\n  [{h}]")
        for st_name, _ in collections.Counter(o.get("final_state") for o in outs).most_common():
            sub = [o for o in outs if o.get("final_state") == st_name]
            hits = collections.Counter(((o.get("outcome") or {}).get(h) or {}).get("first_hit") for o in sub)
            rs = [r_of(o, h) for o in sub]
            print(f"    {st_name} n={len(sub)} 首触{dict(hits)} 期望{statistics.mean(rs):+.3f}R")
    dirs_ids = {s.get("signal_id") for s in dirs}
    sel = [o for o in outs if o.get("signal_id") in dirs_ids]
    print(f"\n  有方向且已标注: {len(sel)}")
    if sel:
        for h in ("h4", "h8", "h16"):
            hits = collections.Counter(((o.get("outcome") or {}).get(h) or {}).get("first_hit") for o in sel)
            neither = hits.get("none", 0)
            print(f"    {h}: 首触 {dict(hits)}")
            if neither / len(sel) > 0.6:
                print(f"      ↑ {pct(neither, len(sel))} 既未触及目标也未触及止损 → 样本不可执行，结果数据不可用于验证闸门")

    print("\n结论口径：只报「有方向候选」的裁决分布；把 0 次可执行授权定性为结构缺陷，")
    print("并说明卡在哪一层（第一层 Pine A 门槛 / 第二层 decision_loop 硬门）。")
    print("若问题是中间档没输出，先查 candidate_entry/watch_entry 是否渲染，别直接提政策改动。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
