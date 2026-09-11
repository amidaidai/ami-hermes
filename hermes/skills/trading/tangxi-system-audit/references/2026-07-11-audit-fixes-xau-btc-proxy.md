# 2026-07-11 棠溪审计修复实例：XAU K线 · Binance代理 · BTC守护多实例

## 背景
用户要求「审计」棠溪交易系统。本次审计为 Level 2 深度运行态审计，发现并修复 3 个 P0 问题。

## 问题 1：XAU VWAP/EMA 引擎无 K 线（P0）

### 症状
`auto_card.py XAUUSD` 输出：
```
⏭ VWAP/EMA引擎：无K线数据，跳过
```

### 根因
`_collect_binance_data` 对 XAU 调用 `fetch_spot('/api/v3/klines', symbol='XAUUSDT')`。但 `XAUUSDT` 在 Binance **现货不存在**，只存在于 **U本位期货**。

```bash
# Binance 现货返回
{"code":-1121,"msg":"Invalid symbol."}
```

### 修复
1. `scripts/binance_public.py` 新增 `fetch_futures(endpoint)` 函数，使用 `fapi.binance.com`。
2. `scripts/auto_card.py` 的 `_collect_binance_data` 中，XAU/GOLD 分支改走 `fetch_futures('/fapi/v1/klines')`。
3. BTC 等加密仍走现货，互不冲突。

### 验证
```bash
python -c "import auto_card; print(auto_card._collect_binance_data({'symbol':'XAUUSD'}, 'XAUUSD'))"
# 输出 klines['15m']、['1h'] 各有 100 条
```

---

## 问题 2：binance_public 代理绕过导致所有 fetch 返回 None（P0）

### 症状
`_collect_binance_data` 即使 BTC 也拉不到 K 线；`fetch_spot('/api/v3/time')` 返回 None。

### 根因
`binance_public.py` 的 `_opener()` 强制 `urllib.request.ProxyHandler({})` 直连。但 Hermes 桌面环境必须走代理 `HTTPS_PROXY=http://127.0.0.1:7897` 才能访问外网。

### 修复
检测 `HTTPS_PROXY` / `HTTP_PROXY` 环境变量：
```python
import os
if os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY'):
    return urllib.request.build_opener()
return urllib.request.build_opener(urllib.request.ProxyHandler({}))
```

### 验证
```bash
python -c "from binance_public import fetch_spot; print(fetch_spot('/api/v3/time'))"
# 返回 {'serverTime': ...}
```

---

## 问题 3：BTC守护多实例复发（P0）

### 症状
`psutil` 检查发现 2-7 个 `btc_daemon.py` 实例并存，心跳文件混乱。

### 根因
旧 `btc_watchdog.py` 使用 Windows `start /B python btc_daemon.py` 拉起，PID 文件追踪不可靠。手动启动与 cron 看门狗无互斥。

### 修复
`scripts/monitor/btc_watchdog.py` 重写：
1. `psutil` 列出所有 cmdline 含 `btc_daemon.py` 的进程，全部 terminate/kill。
2. 删除 `.btc_daemon.pid` 和 `.btc_daemon.lock`。
3. `subprocess.Popen([sys.executable, DAEMON])` 直接启动。
4. sleep 2 秒后 psutil 验证进程存在。
5. PID 写回文件。
6. 心跳失联则推 TG:846 告警。

### 验证
```bash
# 过滤虚警后检查真实实例
python -c "
import psutil
for p in psutil.process_iter(['pid','cmdline']):
    cmd=' '.join(p.info['cmdline'] or [])
    if 'btc_daemon.py' in cmd and 'bash' not in cmd and '-c import psutil' not in cmd:
        print('PID', p.info['pid'], cmd)
"
```

### 关键注意
审计命令自身会被 `psutil.process_iter()` 误判为守护进程。过滤条件：
- `cmdline` 含 `bash -c` → 排除
- `cmdline` 含 `-c import psutil` → 排除
- `pid == os.getpid()` → 排除

真实守护进程判断示例：
```python
def is_real_daemon(proc, daemon_path):
    cmd = ' '.join(proc.info['cmdline'] or [])
    return (str(daemon_path) in cmd
            and 'bash' not in cmd
            and '-c import psutil' not in cmd
            and proc.info['pid'] != os.getpid())
```

---

## 修复后状态
- `auto_card BTCUSDT`：管线完成度 10/10，VWAP/EMA 引擎正常，NO-GO（regime_model 红灯）。
- `auto_card XAUUSD`：管线完成度 8/8，VWAP/EMA 引擎已恢复，NO-GO（regime_model 红灯）。
- `btc_daemon`：单实例运行，心跳正常。
- Git 提交：`d3489ef` fix(audit): XAU klines via futures, proxy-aware binance_public, robust btc watchdog singleton
