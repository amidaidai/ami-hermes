#!/usr/bin/env python3
"""
告警去重模块 v1.0
供所有 no_agent cron 脚本导入使用。
原理: 计算输出内容的hash，与上次相同则跳过推送。
"""
import hashlib, json, os, time
from pathlib import Path

STATE_DIR = os.path.expanduser("~/AppData/Local/hermes/data/dedup")
os.makedirs(STATE_DIR, exist_ok=True)


def should_send(job_name: str, content: str, force_every_seconds: int = 3600) -> bool:
    """
    决定是否发送此告警。
    
    参数:
      job_name: cron任务名（用作状态文件名）
      content: 要推送的文本内容
      force_every_seconds: 即使内容相同，每N秒强制发送一次（默认1小时）
    
    返回: True=发送, False=跳过
    """
    fp = os.path.join(STATE_DIR, f"{job_name}.json")
    content_hash = hashlib.md5(content.encode()).hexdigest()
    now = time.time()
    
    try:
        with open(fp) as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        state = {"last_hash": "", "last_sent": 0}
    
    # 内容变化 → 发送
    if content_hash != state.get("last_hash", ""):
        state["last_hash"] = content_hash
        state["last_sent"] = now
        with open(fp, "w") as f:
            json.dump(state, f)
        return True
    
    # 内容相同但超过强制间隔 → 发送
    if now - state.get("last_sent", 0) > force_every_seconds:
        state["last_sent"] = now
        with open(fp, "w") as f:
            json.dump(state, f)
        return True
    
    # 内容相同且在间隔内 → 跳过
    return False


def dedup_wrapper(job_name: str, content: str, force_seconds: int = 3600):
    """
    包装函数：如果should_send返回True则打印content，否则静默。
    用于cron脚本的标准模式:
    
    output = generate_report()
    dedup_wrapper("my_job", output)
    """
    if should_send(job_name, content, force_seconds):
        print(content)
        return True
    # 静默退出 — cron会标记为"silent (empty output)"，这就是去重效果
    return False
