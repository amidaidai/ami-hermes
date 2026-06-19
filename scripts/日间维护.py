#!/usr/bin/env python3
"""凌晨维护 v1.0 — 串行执行每日三步骤：Hermes升级 → 私人仓库备份 → 每日验证。
   每天 3:20 触发，三步顺序执行，任一步失败不阻断后续。
"""
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_SCRIPTS = SCRIPTS.parent / "hermes" / "scripts" / "repo-maintenance"

STEPS = [
    ("Hermes官方升级", REPO_SCRIPTS / "daily_hermes_official_update.py", 120),
    ("私人仓库备份", REPO_SCRIPTS / "daily_private_repo_backup.py", 120),
    ("每日验证", SCRIPTS / "run_daily_validation.py", 180),
]

print("🟢 凌晨维护 开始")

ok = fail = 0
for name, script, timeout in STEPS:
    print(f"\n—— {name} ——")
    try:
        cp = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, timeout=timeout,
        )
        out = cp.stdout.strip()
        if out:
            print(out)
        if cp.returncode == 0:
            ok += 1
            print(f"✅ {name} 完成")
        else:
            fail += 1
            print(f"⚠ {name} 退出码 {cp.returncode}")
            if cp.stderr.strip():
                print(f"   {cp.stderr.strip()[:300]}")
    except subprocess.TimeoutExpired:
        fail += 1
        print(f"❌ {name} 超时 ({timeout}s)")
    except Exception as e:
        fail += 1
        print(f"❌ {name} 失败: {e}")

print(f"\n凌晨维护结束 · 成功 {ok} · 失败 {fail}")
# Day trading extension (added during phase2 push)
def run_day_trading_maintenance():
    print("—— 日间交易维护启动 ——")
    for name, script, timeout in DAY_STEPS:
        print(f"\n—— {name} ——")
        try:
            cp = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=timeout)
            if cp.stdout.strip(): print(cp.stdout.strip()[:500])
            print("✅" if cp.returncode==0 else "⚠", name)
        except Exception as e: print("fail", e)
    print("日间维护完成")

if __name__ == "__main__":
    import sys
    if len(sys.argv)>1 and "day" in sys.argv[1]:
        run_day_trading_maintenance()
    else:
        print("标准凌晨维护 (用 python 日间维护.py day 跑交易验证)")
