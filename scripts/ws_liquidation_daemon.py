#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
守护进程包装器：确保 ws_liquidation_listener.py 持续运行
- 监控子进程，异常退出自动重启
- 每日 00:00 自动轮转（由 listener 内部处理）
- 适配 cronjob no_agent=true 模式
"""
import subprocess
import sys
import time
import signal
from pathlib import Path

SCRIPT = Path(r"C:/Users/Administrator/AppData/Local/hermes/scripts/ws_liquidation_listener.py")
PYTHON = sys.executable  # 当前 venv 的 python

def run_listener():
    """启动 listener 子进程，返回退出码"""
    proc = subprocess.Popen([PYTHON, str(SCRIPT)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    # 实时转发输出到父进程 stdout（cron 会捕获）
    for line in proc.stdout:
        print(line, end="", flush=True)
    return proc.wait()

def main():
    print(f"[{__import__('datetime').datetime.now().isoformat()}] 🚀 守护进程启动，监控 {SCRIPT.name}")
    restart_count = 0
    max_restarts_per_hour = 12  # 防止疯狂重启
    restarts_this_hour = []
    
    while True:
        # 清理 1 小时前的重启记录
        now = time.time()
        restarts_this_hour = [t for t in restarts_this_hour if now - t < 3600]
        
        if len(restarts_this_hour) >= max_restarts_per_hour:
            print(f"[{__import__('datetime').datetime.now().isoformat()}] ❌ 1 小时内重启 {max_restarts_per_hour} 次，暂停 5 分钟")
            time.sleep(300)
            restarts_this_hour.clear()
            continue
        
        exit_code = run_listener()
        print(f"[{__import__('datetime').datetime.now().isoformat()}] 🔄 子进程退出，code={exit_code}")
        
        if exit_code == 0:
            print("正常退出，守护进程结束")
            break
        else:
            restart_count += 1
            restarts_this_hour.append(now)
            wait_time = min(5 * restart_count, 60)  # 指数退避，最长 60s
            print(f"  等待 {wait_time}s 后重启... (第 {restart_count} 次)")
            time.sleep(wait_time)

if __name__ == "__main__":
    main()