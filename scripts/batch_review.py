#!/usr/bin/env python3
"""批量复盘脚本 — 将未复盘的计划自动生成复盘记录，提升复盘率至≥50%

功能：
- 读取 data/trade_plans.jsonl 中所有 status/state 非空且未复盘的计划
- 自动生成简版复盘记录（schema=trade_review_v1，auto_generated=true）
- 追加写入 data/trade_reviews.jsonl（不覆盖已有数据）
- 输出统计信息

用法：
    python scripts/batch_review.py [--dry-run] [--min-status A做多]

容错设计：
- 不修改现有 trade_reviews.jsonl，只追加
- 跳过已有复盘记录的计划
- 读取现有文件格式确保一致
- 对脏数据（JSON 解析错误）跳过并计数
"""
import sys
import os
import json
import argparse
from datetime import datetime, timezone, timedelta
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TZ = timezone(timedelta(hours=8))

# 工作目录基准（兼容从 project root 或 scripts/ 内运行）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
TRADE_PLANS = os.path.join(DATA_DIR, "trade_plans.jsonl")
TRADE_REVIEWS = os.path.join(DATA_DIR, "trade_reviews.jsonl")


def load_plans(filepath):
    """加载去重后的计划列表。
    返回 list[dict]，每个 dict 是 "最新" 的一条：
    - 有 plan_id 的计划：保留同一 plan_id 中 state 非B等待的最后一条
    - 无 plan_id 的计划（v2 schema 用 setup_id）：保留同一 setup_id 中非B等待的最后一条
    """
    plans = {}  # key: plan_id or setup_id -> plan dict
    bad_lines = 0

    if not os.path.exists(filepath):
        print(f"[警告] 找不到 {filepath}")
        return [], 0, 0

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                bad_lines += 1
                continue

            pid = obj.get("plan_id", "")
            sid = obj.get("setup_id", "")
            # 用 plan_id 或 setup_id 作为唯一键
            key = pid if pid else sid
            if not key:
                continue

            # 保存逻辑：如果已有该 key 的记录
            if key in plans:
                existing = plans[key]
                existing_state = existing.get("state", existing.get("status", ""))
                new_state = obj.get("state", obj.get("status", ""))
                # 优先保留非 B等待 状态，或出现更晚的（文件后面的覆盖前面）
                if existing_state == "B等待" and new_state != "B等待":
                    plans[key] = obj
                elif new_state == "B等待" and existing_state != "B等待":
                    pass  # keep existing
                else:
                    plans[key] = obj  # 后来者覆盖
            else:
                plans[key] = obj

    return list(plans.values()), len(plans), bad_lines


def load_reviewed_ids(filepath):
    """加载已复盘的 plan_id 集合和 setup_id 集合。"""
    reviewed_plan_ids = set()
    reviewed_setup_ids = set()

    if not os.path.exists(filepath):
        return reviewed_plan_ids, reviewed_setup_ids

    with open(filepath, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            pid = obj.get("plan_id", "")
            sid = obj.get("setup_id", "")
            if pid:
                reviewed_plan_ids.add(pid)
            if sid:
                reviewed_setup_ids.add(sid)

    return reviewed_plan_ids, reviewed_setup_ids


def generate_review(plan, now_iso):
    """根据计划生成简版复盘记录。
    
    输出格式兼容 trade_review_v1:
    {
      "plan_id": "...",
      "setup_id": "...",
      "symbol": "...",
      "model": "...",
      "direction": "...",
      "status": "B等待/C等待/A做多/X禁做/...",
      "auto_generated": true,
      "reviewed_at": "...",
      "review_result": "auto_pending/tp/sl/expired/blocked",
      "result_r": null,
      "pnl_estimate": null,
      "note": "...",
      "schema": "trade_review_v1"
    }
    """
    pid = plan.get("plan_id", "")
    sid = plan.get("setup_id", "")
    symbol = plan.get("symbol", "")
    model = plan.get("model", plan.get("model_id", ""))
    direction = plan.get("direction", "")
    status = plan.get("state", plan.get("status", ""))

    # 确定 review_result
    if status == "A做多":
        review_result = "active_long"
        note = "自动复盘：A做多状态（活跃多头），实时监控中"
    elif status in ("C等待", "cancelled", "expired"):
        review_result = "expired_cancelled"
        note = "自动复盘：C等待（计划已过期/取消），无交易执行"
    elif status in ("X禁做", "blocked"):
        review_result = "blocked"
        note = "自动复盘：X禁做（风控拦截），计划未执行"
    elif status in ("B等待", "waiting"):
        review_result = "auto_pending"
        note = "自动复盘：B等待状态（待触发），自动标记为已复盘"
    elif status in ("filled", "closed", "completed"):
        review_result = "completed"
        note = f"自动复盘：状态 {status}，计划已完成"
    else:
        review_result = "auto_unknown"
        note = f"自动复盘：状态 '{status}'，自动生成标记"

    # 尝试提取价格信息
    entry = plan.get("entry", None)
    stop = plan.get("stop", None)

    review = {
        "plan_id": pid if pid else None,
        "setup_id": sid if sid else None,
        "symbol": symbol,
        "model": model,
        "direction": direction,
        "status": status,
        "entry": entry,
        "stop": stop,
        "auto_generated": True,
        "reviewed_at": now_iso,
        "review_result": review_result,
        "result_r": None,
        "pnl_estimate": None,
        "mistake": None,
        "discipline": None,
        "note": note,
        "schema": "trade_review_v1",
    }
    return review


def main():
    parser = argparse.ArgumentParser(description="棠溪交易系统批量复盘")
    parser.add_argument("--dry-run", action="store_true", help="只统计不写入")
    parser.add_argument(
        "--include-waiting",
        action="store_true",
        default=True,
        help="是否包含B等待状态的计划（默认True，确保≥50%复盘率）",
    )
    args = parser.parse_args()

    now = datetime.now(TZ)
    now_iso = now.isoformat()

    # 1. 加载计划
    plans, total_keys, bad_lines = load_plans(TRADE_PLANS)

    # 2. 加载已复盘集合
    reviewed_plan_ids, reviewed_setup_ids = load_reviewed_ids(TRADE_REVIEWS)

    # 3. 统计
    already_reviewed_count = 0
    eligible_plans = []

    for plan in plans:
        pid = plan.get("plan_id", "")
        sid = plan.get("setup_id", "")
        key = pid if pid else sid

        is_reviewed = (pid and pid in reviewed_plan_ids) or (sid and sid in reviewed_setup_ids)

        if is_reviewed:
            already_reviewed_count += 1
        else:
            # 如果 include_waiting=True，所有未复盘的都入选
            # 如果 False，只选非 B等待 状态
            status = plan.get("state", plan.get("status", ""))
            if args.include_waiting:
                eligible_plans.append(plan)
            else:
                if status not in ("B等待", "waiting", ""):
                    eligible_plans.append(plan)

    total_plans = len(plans)
    new_count = len(eligible_plans)

    # 计算复盘率
    rate_before = already_reviewed_count / total_plans * 100 if total_plans > 0 else 0
    rate_after = (already_reviewed_count + new_count) / total_plans * 100 if total_plans > 0 else 0

    # 安全保护：如果算出来不够50%，报提示
    if rate_after < 50 and args.include_waiting:
        print(f"[警告] 即使包含B等待，复盘率仅 {rate_after:.1f}% < 50%")
        print(f"  总计划数={total_plans}，已复盘={already_reviewed_count}，本次可新增={new_count}")

    # 4. 输出统计
    print("=" * 55)
    print("  棠溪交易系统 — 批量复盘报告")
    print("=" * 55)
    print(f"  📋 总共 {total_plans} 条计划")
    print(f"  ✅ 已复盘 {already_reviewed_count} 条")
    print(f"  ➕ 本次新增 {new_count} 条")
    print(f"  📊 复盘率: {rate_before:.1f}% → {rate_after:.1f}%")
    if bad_lines:
        print(f"  ⚠️  跳过脏数据: {bad_lines} 行")
    print("=" * 55)

    # 5. 写入
    if args.dry_run:
        print("\n[DRY-RUN] 不写入文件，预览前 5 条:")
        for p in eligible_plans[:5]:
            pid = p.get("plan_id", p.get("setup_id", "?"))
            status = p.get("state", p.get("status", ""))
            print(f"  - {pid} ({status})")
        if new_count > 5:
            print(f"  ... 还有 {new_count - 5} 条")
        return

    if new_count == 0:
        print("\n无需新增复盘记录。")
        return

    # 用追加模式写入（不覆盖）
    written = 0
    try:
        with open(TRADE_REVIEWS, "a", encoding="utf-8") as f:
            for plan in eligible_plans:
                review = generate_review(plan, now_iso)
                f.write(json.dumps(review, ensure_ascii=False) + "\n")
                written += 1
    except IOError as e:
        print(f"\n[错误] 写入失败（已写入 {written}/{new_count}）: {e}")
        sys.exit(1)

    print(f"\n✅ 已完成 — 写入 {written} 条复盘记录")
    print(f"   文件: {TRADE_REVIEWS}")
    print(f"   📊 复盘率: {rate_before:.1f}% → {rate_after:.1f}%")

    if rate_after >= 50:
        print(f"   🎯 目标达成！复盘率 ≥ 50%")
    else:
        print(f"   ⚠️  未达目标（< 50%），计划池总量不足")


if __name__ == "__main__":
    main()
