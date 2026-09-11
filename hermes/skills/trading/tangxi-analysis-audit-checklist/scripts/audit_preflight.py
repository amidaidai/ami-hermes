#!/usr/bin/env python3
"""
棠溪交易系统 · 分析系统预检脚本（可直接复制执行）
终端执行：python scripts/audit_preflight.py
输出即是证据：TV/CDP/守护/数据/Cron 全维度快照。
"""
import os, json, socket, subprocess, sys
from datetime import datetime

BASE = r"D:\Hermes agent"
DATA = os.path.join(BASE, "data")

def read_json(p):
    try:
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def age_hours(ts_str):
    if not ts_str: return 999
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return (datetime.now(dt.tzinfo) - dt).total_seconds() / 3600
    except Exception:
        return 999

def file_age_h(path):
    try:
        return (datetime.now().timestamp() - os.path.getmtime(path)) / 3600
    except Exception:
        return 999

def section(title):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")

def main():
    print(f"\n{'='*55}")
    print(f"  棠溪分析系统预检 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}")

    # === 1. TV / CDP ===
    section("【1. TV Desktop & CDP 9222】")
    try:
        import psutil
        tv = [p.info['cmdline'] for p in psutil.process_iter(['cmdline'])
              if p.info['cmdline'] and 'TradingView.exe' in str(p.info['cmdline'])]
        print(f"  TV进程: {'✅ 运行中' if tv else '❌ 未运行'}")
    except Exception as e:
        print(f"  TV进程: ⚠️ 探测失败 {e}")
    s = socket.socket(); s.settimeout(2)
    r = s.connect_ex(('127.0.0.1', 9222)); s.close()
    print(f"  CDP 9222: {'✅ 开放' if r == 0 else f'❌ 关闭/拒绝 ({r})'}")

    # === 2. 守护心跳 ===
    section("【2. 守护进程心跳】")
    for label, fpath, key in [
        ("行情守望", os.path.join(DATA, "monitor_heartbeat.json"), "time"),
        ("BTC守护",  os.path.join(DATA, ".btc_daemon_heartbeat.json"), "ts"),
        ("关键位守护", os.path.join(DATA, ".keylevel_guard_heartbeat.json"), "ts"),
    ]:
        d = read_json(fpath)
        if d:
            ts = d.get(key) or d.get("time") or d.get("ts")
            age = age_hours(ts)
            status = d.get("status", "?")
            pid = d.get("pid", "?")
            tag = "✅" if (age < 1 and status == "running") else "⚠️" if age < 5 else "❌"
            print(f"  {tag} {label:8s}  age={age:.1f}h  status={status}  pid={pid}")
        else:
            print(f"  ❌ {label:8s}  文件缺失或不可读")

    # === 3. 关键数据新鲜度 ===
    section("【3. 关键数据文件新鲜度】")
    critical = [
        ("source_snapshot_BTCUSDT.json", 1),
        ("source_snapshot_XAUUSD.json", 1),
        ("tv_live.json", 2),
        ("tv_dmi_cache.json", 2),
        ("btc_ref_levels.json", 24),
        ("monitor_levels.json", 24),
        ("keylevels_config.json", 24),
        ("protections_state.json", 72),
    ]
    for fname, thresh in critical:
        fpath = os.path.join(DATA, fname)
        if os.path.exists(fpath):
            age = file_age_h(fpath)
            sz = os.path.getsize(fpath)
            tag = "✅" if age < thresh else "⚠️" if age < thresh*2 else "❌"
            print(f"  {tag} {fname:35s}  age={age:.1f}h  thresh={thresh}h  {sz}B")
        else:
            print(f"  ⚠️ {fname:35s}  文件缺失")

    # === 4. Python 守护实例计数 ===
    section("【4. Python 守护进程实例】")
    try:
        import psutil as ps
        for name in ["行情守望.py", "btc_daemon.py", "btc_watchdog.py", "market_watchdog.py"]:
            pids = []
            for p in ps.process_iter(['pid', 'cmdline']):
                try:
                    cmd = ' '.join(p.info['cmdline'] or [])
                    if name in cmd and 'bash' not in cmd and '-c import psutil' not in cmd:
                        pids.append(p.info['pid'])
                except Exception:
                    pass
            tag = "✅" if len(pids) == 1 else ("⚠️" if len(pids) == 0 else "❌")
            print(f"  {tag} {name:20s}  实例={len(pids)}  PIDs={pids}")
    except Exception as e:
        print(f"  ⚠️ psutil 不可用: {e}")

    # === 5. Cron 任务 ===
    section("【5. Cron 任务状态】")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "hermes_cli.main", "cron", "list", "--json"],
            capture_output=True, text=True, timeout=15, cwd=BASE)
        if result.returncode == 0:
            jobs = json.loads(result.stdout).get("jobs", [])
            en = [j for j in jobs if j.get("enabled")]
            print(f"  总计:{len(jobs)}  启用:{len(en)}  暂停:{len(jobs)-len(en)}")
            keys = ["BTC关键位同步","XAU TV现场同步","BTC守护看门狗","行情守望看门狗","每日运维聚合"]
            for j in jobs:
                if any(k in j["name"] for k in keys):
                    st = j.get("state", "?")
                    last = j.get("last_run_at", "-")[:16] if j.get("last_run_at") else "-"
                    tag = "✅" if j.get("enabled") and st == "scheduled" else "⚠️" if j.get("enabled") else "❌"
                    print(f"    {tag} {j['name'][:26]:26s} {st:8s} last={last}")
        else:
            print(f"  ⚠️ cron list 失败: {result.stderr[:120]}")
    except Exception as e:
        print(f"  ⚠️ Cron 检查异常: {e}")

    # === 6. 脚本规模 ===
    section("【6. 脚本规模】")
    scripts_dir = os.path.join(BASE, "scripts")
    py_files = [f for f in os.listdir(scripts_dir) if f.endswith('.py')]
    print(f"  scripts/*.py 总数: {len(py_files)}")
    print(f"  关键脚本(21个): data_gatherer, multi_model_engine, auto_card等")

    # === 7. 结论 ===
    section("【结论】")
    print("  修复顺序: TV/CDP → 守护心跳 → 数据快照 → Cron → 其他")
    print("  发现 ❌ 项 = 必须先修复，再跑深度审计/出分析卡")
    print(f"  预检完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    main()