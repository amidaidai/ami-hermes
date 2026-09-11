# 重复进程根因：acquire_lock() 的 TOCTOU 竞态

## 症状

- monitor.log 出现幻影速率限制 / 重复心跳写入 / PID 跳变。
- `tasklist | grep python` 数出 **两个** `行情守望` 实例，或两个 `watchdog`。
- 两实例启动时间戳极接近（实测 17:10:13.044 vs 17:10:13.082，相差 38ms）。
- 其中一个是僵尸副本（心跳停在旧时间），另一个心跳新鲜，二者抢同一个 `data/monitor_heartbeat.json`。
- watchdog 误判心跳停滞强杀，反而把活的那个也带走 → 系统整体 DOWN。

## 根因

`scripts/行情守望.py` 的 `acquire_lock()` 是 **非原子的 check-then-write**：

```
L381  if os.path.exists(LOCK_FILE):        # 检查
          ...判断里面的 PID 是否存活...
L401  open(LOCK_FILE, "w").write(str(pid)) # 写入
```

检查和写入之间有时间窗。两个进程几乎同时启动时，都通过了"锁不存在/锁内 PID 已死"的检查，然后都写入自己的 PID → 两个实例同时存活。watchdog 自身用同样的锁逻辑，所以**重启时也会产生两个 watchdog**（本会话实测 PID 10444 + 7116 同在 21:34:18 启动）。

这是所有"重复进程"问题的**唯一根因**，不要逐个 taskkill 打地鼠 —— 锁不原子，杀完还会再生。

## 修法（原子锁）

用 `O_CREAT | O_EXCL` 原子创建锁文件，把"检查+写入"合并成一个不可分割的系统调用：

```python
import os
try:
    fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
except FileExistsError:
    # 锁已存在 —— 读里面的 PID，若进程已死则 unlink 后重试一次，否则退出
    ...
```

`O_EXCL` 保证只有一个进程能成功创建；其余全部抛 `FileExistsError`，干净退出。Windows 的 `os.open` 支持 `O_EXCL`，git-bash/MSYS 下同样有效。
陈旧锁清理：捕获 `FileExistsError` 后读锁内 PID，用 `tasklist //FI "PID eq N"` 确认是否真死，死了才 `os.unlink` + 重试一次（重试也要走原子创建，不能退回裸 write）。

## 重启程序铁律（本会话踩过的坑）

1. **脚本本身没问题，分离机制才是失败点**。前台实测 `timeout 12 venv python scripts/行情守望.py` 能正常启动并推送 Telegram（`[21:32:13] 推送成功 telegram_direct`）。问题出在后台分离方式，不是代码逻辑。
2. **不要用 `Start-Process -WindowStyle Hidden` 分离** —— 本会话失败。改用 Hermes `terminal(background=true)` + `exec venv python scripts/watchdog.py` 更可靠。
3. **重启前先清陈旧锁**：`rm -f data/monitor.lock`，否则原子锁修好前仍可能读到死 PID 误判。
4. **让 watchdog 拉起 monitor，不要手动直接起 monitor** —— 否则 watchdog 再拉一个 = 又重复。单一职责：watchdog 是唯一的 monitor 启动者。
5. **必须用 venv python**（装有依赖），不要用 uv python 或桌面运行时 python（无 numpy/pandas）。
6. 修复后盯 30s+ 确认单 watchdog + 单 monitor，无反复重启，再宣告稳定。

## 检测命令（git-bash）

```bash
# 数实例数 —— 应各为 1
tasklist //FI "IMAGENAME eq python.exe" //V //FO CSV | grep -c 行情守望   # 期望 1
tasklist //FI "IMAGENAME eq python.exe" //V //FO CSV | grep -c watchdog   # 期望 1

# 锁文件 PID vs 实际存活 PID 对账
# (用 read_file 读 data/monitor.lock 取 PID，再 tasklist //FI "PID eq N" 确认)
```

若任一计数 ≥ 2 → P0 重复进程，根因即 TOCTOU 锁竞态，必须改原子锁，不能只杀进程。
