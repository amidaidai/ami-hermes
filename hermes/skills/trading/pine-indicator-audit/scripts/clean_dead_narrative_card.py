#!/usr/bin/env python3
# clean_dead_narrative_card.py
# 安全批量删除 SVP 行动格 v2 取代的旧叙事卡死代码。
#
# 死变量(声明+赋值全删): stateText, cardLine1, cardLine2, cardLine3,
#                         directionGuideText, actionGuideText, detailText
# 保留变量(绝不删):      watchText, invalidText
#
# 三道护栏:
#  1. 删除前 grep table.cell(...VAR) 确认死变量 0 消费；若有消费则报错退出，不删。
#  2. 删除行扫描时，凡遇 watchText/invalidText 的声明或 := 行一律跳过并告警(误删护栏)。
#  3. 删除后回扫，确认死变量无声明/赋值残留，且保留变量仍有声明。
#
# 用法: python clean_dead_narrative_card.py <主指标.txt>
import re, sys

DEAD = {"stateText", "cardLine1", "cardLine2", "cardLine3",
        "directionGuideText", "actionGuideText", "detailText"}
KEEP = {"watchText", "invalidText"}


def main(path):
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    joined = "".join(lines)

    # 护栏1: 消费检查 —— 仍被 table.cell 消费则放弃
    for v in DEAD:
        if re.search(rf"(?m)^\s*table\.cell\([^)]*\b{v}\b", joined):
            print(f"!! 危险: {v} 仍被 table.cell 消费，放弃删除。先确认是否真死。")
            sys.exit(1)

    remove = set()
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        hit = False
        for v in DEAD:
            if s.startswith(f"string {v} =") or s.startswith(f"bool {v} =") or s.startswith(f"float {v} ="):
                remove.add(i)
                hit = True
                break
        if not hit:
            for v in DEAD:
                if s.startswith(f"{v} :="):
                    remove.add(i)
                    break
        # 护栏2: 保留变量误删检查
        for v in KEEP:
            if s.startswith(f"string {v} =") or s.startswith(f"{v} :="):
                if i in remove:
                    print(f"!! 误删护栏触发: 行 {i} 的 {v} 被标记删除，已撤销。")
                remove.discard(i)

    new = [ln for i, ln in enumerate(lines, 1) if i not in remove]

    # 护栏3: 残留检查
    nj = "".join(new)
    for v in DEAD:
        if re.search(rf"(?m)^\s*(string|bool|float)\s+{v}\s*=", nj) or re.search(rf"(?m)^\s*{v}\s*:=", nj):
            print(f"!! 残留: {v} 仍存在，删除不完整。")
    for v in KEEP:
        if not re.search(rf"(?m)^\s*string\s+{v}\s*=", nj):
            print(f"!! 保留变量丢失: {v}")

    if len(new) == len(lines):
        print("无需删除，文件未改。")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new)
    print(f"删除 {len(lines) - len(new)} 行 ({len(lines)}→{len(new)})。误删护栏确保 watchText/invalidText 保留。")
    print("随后请跑 pine_static_scan.py 复核配额与 def 顺序，确认无 Undeclared identifier。")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python clean_dead_narrative_card.py <主指标.txt>")
        sys.exit(1)
    main(sys.argv[1])
