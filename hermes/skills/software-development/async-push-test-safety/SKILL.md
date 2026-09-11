---
name: async-push-test-safety
description: 防止异步推送/通知模块的单元测试把真实消息漏发到 Telegram/Discord/飞书等线上通道。当测试用例触发了发送函数、出现 "test message"、占位告警漏到线上、或要为异步队列+monkeypatch 的推送代码写安全测试时使用。
---

# 异步推送测试安全（三层防护）

## 适用场景
- 线上通道（Telegram/Discord/飞书）突然收到 `test message`、占位告警、调试文案
- 推送模块用「入队 + 后台 worker 异步发送」结构，且测试用 monkeypatch 拦发送
- 要为这类异步推送函数写「不阻塞主循环」「超时被吞」之类的单元测试

## 根因模型（两个缺陷叠加才会漏发）
1. **monkeypatch 拦错了层**：测试只 patch 了 `subprocess.run`，但真实发送有多条通道——比如 Telegram 走的是直连 HTTP（`telegram_direct.send_telegram_direct`），根本不碰 subprocess，patch 形同虚设。
2. **异步 worker 的竞态**：`push()` 把消息入队后立即返回，真正发送由**后台 daemon 线程**串行执行。该线程常在测试函数退出、monkeypatch 已还原**之后**才跑，于是用的是真实发送通道。`target` 为空时还会回落到默认线上话题，甚至顺带发一份到第二通道（如 Discord）。

→ 记住：**patch 子进程 ≠ 拦住发送**。只要存在任意一条不经子进程的发送路径，或 worker 异步执行，假消息就会漏出去。

## 三层防护方案

### 第一层 · 代码里加进程级 kill-switch
在所有发送的**唯一咽喉函数**（如 `_send_one`）顶部加环境变量短路，触达任何真实通道前返回成功：
```python
def _send_one(target, msg):
    if os.environ.get("HANGQING_NO_SEND") == "1":
        log(f"NO_SEND 拦截 {target}: {str(msg)[:60]}")
        return True
    # ...真实发送逻辑（telegram_direct / subprocess / sidecar 等）
```
关键：开关必须放在**最早**、在分流到各通道**之前**。环境变量名按项目命名（此仓库用 `HANGQING_NO_SEND`）。

### 第二层 · conftest.py 全局默认开启
仓库根建 `conftest.py`，pytest 收集用例前自动加载，零插件依赖：
```python
import os
os.environ.setdefault("HANGQING_NO_SEND", "1")
```
- 用 `setdefault` 而非赋值——本地想真联调发送时仍可显式覆盖。
- 不要用 `pytest.ini` 设环境变量（需 `pytest-env` 插件）；conftest 是官方机制且加载时机更早。

### 第三层 · 测试桩掉发送咽喉 + 退出前排空队列
- patch **咽喉函数本身**（`_send_one`），不要 patch `subprocess.run`：
```python
monkeypatch.setattr(watch, "_send_one", slow_send)  # slow_send(target, msg)
```
- 异步用例在 `monkeypatch` 还原**前**主动排空队列，确保 worker 用的是桩而非真实发送：
```python
result = watch.push("test message · 紧急")
assert elapsed < 1.0       # 不阻塞主循环
watch.drain_push_queue(timeout=20)   # ← 关键：还原前排空
```

## 验证方法
- 跑目标推送测试，确认全过。
- **独立证明 conftest 真生效**（别让测试文件自带的 setdefault 掩盖）：在干净进程里清掉环境变量再跑探针用例：
```bash
printf 'import os\ndef test_probe():\n    assert os.environ.get("HANGQING_NO_SEND")=="1"\n' > tests/_probe.py
env -u HANGQING_NO_SEND python -m pytest tests/_probe.py -v; rm -f tests/_probe.py
```
通过即证明保护来自 conftest，不靠测试文件兜底。
- 最后跑全量回归，确认无连带破坏。

## 给 CI/本地的建议
本地与 CI 跑测试统一带 `HANGQING_NO_SEND=1`（有 conftest 后即便忘带也安全）。新增推送通道时，确保它也经过同一个咽喉函数，kill-switch 才覆盖得到。

## 排查命令（定位漏发源头）
```
# 在仓库里搜漏发的占位文案
search_files(pattern="test message", path="<repo>")
# 找发送咽喉与队列实现
search_files(pattern="def _send_one|def push|def drain_push_queue|_PUSH_QUEUE|send_telegram_direct")
```

## 任务报告排版（此用户偏好）
纯中文、纵向递进、圈号①②③、冒号对齐、关键值用反引号；**禁止任何机器字段**（setup_id/entry_tag 等）、禁方括号标签、禁 `｜` 分隔、禁装饰 emoji。
