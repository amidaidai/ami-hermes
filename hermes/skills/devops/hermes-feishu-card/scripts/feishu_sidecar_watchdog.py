# -*- coding: utf-8 -*-
"""
飞书卡片 sidecar 看门狗（no_agent cron，静默运行）

职责：检查 127.0.0.1:8765 /health。正常 → 无输出（no_agent 模式下即沉默）。
不可用 → 用 venv python 以 detached 方式重启 sidecar，并打印一行结果供本地留档。

为什么需要：sidecar 在 Windows 上会随启动它的父进程静默退出；
2026-09-13 起它实际停摆了 3 天，直到 09-16 才被发现 —— 期间飞书卡片全部发不出去。

用法：hermes cron create "*/5 * * * *" --script feishu_sidecar_watchdog.py --no-agent --deliver local
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))
STATE = r"C:/Users/Administrator/.hermes_feishu_card"
HERMES_AGENT = r"C:/Users/Administrator/AppData/Local/hermes/hermes-agent"
REPO = r"D:/Hermes agent/sandbox/hermes-feishu-streaming-card"
PY = os.path.join(HERMES_AGENT, "venv", "Scripts", "python.exe")
CFG = os.path.join(STATE, "config.yaml")
ENVF = r"C:/Users/Administrator/AppData/Local/hermes/.env"
PIDF = os.path.join(STATE, "sidecar.pid")
LOG = os.path.join(STATE, "watchdog.log")
HEALTH = "http://127.0.0.1:8765/health"
DEFAULT_TOKEN = "direct-43b81c4c8ec77555"

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def now_str():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def log(line):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (now_str(), line))
    except Exception:
        pass


def health(timeout=4):
    """返回 (ok, 描述)。直连，绕开代理。"""
    try:
        with _OPENER.open(HEALTH, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        return True, "pid=%s v=%s delivery=%s" % (
            d.get("process_pid"), d.get("package_version"),
            (d.get("delivery") or {}).get("mode"))
    except Exception as e:
        return False, "%s: %s" % (type(e).__name__, e)


def read_token():
    try:
        return json.load(open(PIDF, encoding="utf-8")).get("token") or DEFAULT_TOKEN
    except Exception:
        return DEFAULT_TOKEN


def kill_stale():
    """停掉 pid 文件里那个已无响应的进程，避免端口被僵死实例占住。"""
    try:
        import psutil
    except Exception:
        return "psutil 不可用，跳过清理"
    try:
        pid = json.load(open(PIDF, encoding="utf-8")).get("pid")
    except Exception:
        return "无 pid 文件"
    if not pid:
        return "pid 文件无 pid"
    try:
        p = psutil.Process(int(pid))
    except Exception:
        return "pid %s 已不存在" % pid
    try:
        p.terminate()
        try:
            p.wait(timeout=8)
        except Exception:
            p.kill()
        return "已终止僵死 pid %s" % pid
    except Exception as e:
        return "终止 pid %s 失败: %s" % (pid, e)


def start_sidecar():
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO
    logf = open(os.path.join(STATE, "watchdog_restart.out.log"), "ab")
    flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [PY, "-m", "hermes_feishu_card.runner", "--config", CFG,
         "--hermes-dir", HERMES_AGENT, "--env-file", ENVF, "--token", read_token()],
        cwd=REPO, env=env, stdout=logf, stderr=logf, stdin=subprocess.DEVNULL,
        creationflags=flags)
    return proc.pid


def write_pid_file():
    ok, _ = health()
    if not ok:
        return
    try:
        with _OPENER.open(HEALTH, timeout=4) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        json.dump({"pid": d.get("process_pid"), "token": read_token()},
                  open(PIDF, "w", encoding="utf-8"))
    except Exception:
        pass


def main():
    ok, desc = health()
    if ok:
        return 0  # 健康：静默

    log("sidecar 不可用 (%s)，开始重启" % desc)
    cleaned = kill_stale()
    log("清理: " + cleaned)
    time.sleep(1)
    try:
        newpid = start_sidecar()
    except Exception as e:
        msg = "[%s] 飞书卡片 sidecar 重启失败：启动异常 %r" % (now_str(), e)
        log(msg)
        print(msg)
        return 1

    ready, last = False, ""
    for _ in range(12):
        time.sleep(2)
        ready, last = health()
        if ready:
            break
    write_pid_file()

    if ready:
        msg = "[%s] 飞书卡片 sidecar 已自动拉起（%s）；%s" % (now_str(), last, cleaned)
    else:
        msg = "[%s] 飞书卡片 sidecar 重启后仍不可用（%s）；启动 pid=%s；%s" % (now_str(), last, newpid, cleaned)
    log(msg)
    print(msg)
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
