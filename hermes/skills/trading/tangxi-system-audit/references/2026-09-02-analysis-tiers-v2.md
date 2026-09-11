# 分析档位 v2 定稿（pipeline_router 实测）

> 来源：`scripts/pipeline_router.py`（v1.1 2026-06-29），`scripts/auto_card.py:3182-3213` 路由调用方。
> 测试时间：2026-09-02。文件变更即时反映到 memory "分析分档定稿v2" 条目。

## 一、4 档定义

| 档位 | 步数 | 主周期 | 上下文继承 | 触发词 | 适用场景 |
|------|------|--------|-----------|--------|----------|
| **quick** | 4 步（tv/binance/card + cg_pro 仅 crypto） | BTC=15m / XAU=5m 单周期 | 不继承 | "看下/看看/快速过一遍/扫一眼" | 快闪看价，快进快出执行 |
| **inherit** | 同 quick | 同 quick | 继承 4h 内高周期上下文 | "现在呢/继续/接着/更新/继承" | 上下文新时免重扫高周期 |
| **full** | crypto 10 / gold 8 / forex 7 / stock 8 / futures 6 / option 8 | 全 5 层 D/4h/1h/15m/5m | 不继承 | "分析/全面/全周期/深度/完整卡" | 完整卡、cron 到价、深度复核 |
| **monitor** | 4-5 步 | 简 | 不继承 | cron 内部 | 仅关键数据刷新 |

## 二、quick 模式完整管线

```
auto_card(symbol, mode='quick')
  ↓
  pipeline_steps = ["tv", "binance", "card"]   (auto_card.py:3223)
  ↓
  Step ① TV MCP 切主周期 (15m BTC / 5m XAU)
  ↓
  Step ② Binance 衍生品（OI/费率/Taker/多空比/cg_pro）
  ↓
  Step ③ 多模型引擎（grok 跳过、宏观/情绪/订单流合并）
  ↓
  Step ④ 出卡（不写 source_snapshot 是设计）
```

## 三、inherit 模式升级 full 的两个条件（auto_card.py:3203-3213）

```python
if mode == "inherit":
    context = load_analysis_context(symbol)
    if context is None:                    # 条件 1: 4h 内无完整卡
        effective_mode = "full"
    except Exception as exc:                # 条件 2: 加载异常
        effective_mode = "full"
```

**继承的载体文件**：`data/analysis_context_{symbol}.json`（4h TTL）

## 四、full 模式分资产管线（pipeline_router.STEPS）

### 通用步骤（5 步）
1. `tv` — TV MCP 五层 + 截图
2. `binance` — 衍生品
3. `macro` — SPX/VIX/DXY/US10Y + 金十日历 + Poly + CMC Fear&Greed
4. `x_sent` — x_search 实时 X/Twitter 情绪
5. `cron_read` — 读 cron 输出

### 资产专属步骤
- **crypto (10 步)**: + `cg_pro`(板块/市值) + `cvd` + `depth`
- **gold (8 步)**: + `cvd` + `corr` + `gold_macro`(OANDA+gold-api+金十)
- **forex (7 步)**: + `corr` + `forex_rate`
- **stock (8 步)**: + `corr` + `fmp`(财报)
- **futures (6 步)**: + `corr` + `cme_fut`(COT/持仓)
- **option (8 步)**: + `greek` + `chain`

### 共通收尾
- 🔚 `card` — 写 source_snapshot_*.json + 出卡

## 五、XAU vs crypto 前置差异（auto_card.py:3231-3258）

### XAU 路径
```python
xau_sync = subprocess.run([sys.executable, "scripts/xau_tv_sync.py"], timeout=20)
# xau_tv_sync.py 内部: TV MCP 拉 OANDA:XAUUSD 五层 K 线 → 写 data/xau_tv_state.json
# 跳过 tv_live_dump 避免双倍等待
```

### crypto 路径
```python
tv_refresh = subprocess.run(
    [sys.executable, "scripts/tv_live_dump.py", "--symbol", symbol, "--timeframe", "15"],
    timeout=45
)
# tv_live_dump.py: 84 行 wrapper, 调 fetch_tv_mcp.collect_and_cache → 写 data/tv_live.json
# ⚠ 注意: tv_live_dump.py 9/2 仍缺失, 但 xau 路径不依赖它; crypto 路径会失败但 catch 在 try/except
```

## 六、source_snapshot 写盘的不对称性（重要！）

| 模式 | 调 `_refresh_and_mark_snapshot` | 写 source_snapshot_*.json | 调 render_card_locked 写盘 |
|------|------|------|------|
| **quick** | ✅ 只读不写 | ❌ 不写 | ❌ |
| **inherit** | ✅ 只读不写 | ❌ 不写 | ❌ |
| **full** | ✅ 只读不写 | ✅ 写 | ✅ |
| **monitor** | ✅ 只读不写 | ❌ 不写 | ❌ |

**根因**（auto_card.py:2810-2823 注释）：
> "GO/NO-GO previously used a hard-coded 24h default because auto_card never stamped engine_data['_snapshot_age_h']. That made the freshness gate a warning-only decoration instead of a real accuracy control. This helper is deliberately file-based so it works after either source_snapshot() refreshes data or a cron/daemon refreshed it out of band."

→ 写盘只在 full 模式 `render_card_locked` 之后由 cron/外部触发；quick 模式**故意**只读不写以省成本。

## 七、CLI 调用

```bash
# 完整卡（默认）
python scripts/auto_card.py BTCUSDT
python scripts/auto_card.py BTCUSDT --full
python scripts/auto_card.py XAUUSD --full

# 快速看
python scripts/auto_card.py BTCUSDT --quick
python scripts/auto_card.py XAUUSD --quick

# 继承上下文
python scripts/auto_card.py BTCUSDT --inherit
```

auto_card.py:4801-4806 路由逻辑：
```python
_mode = "quick"  # 默认
if len(sys.argv) > 1 and sys.argv[1] == "--full": _mode = "full"
if "--inherit" in sys.argv: _mode = "inherit"
```

## 八、与记忆条目的对应

记忆条目 "分析分档定稿v2(8/31 pipeline_router 实测)" 是 380 字高密度版本，本文件是**完整技术细节**。两者必须**保持一致**——若本文件更新（如路由改动），需同步 memory。

## 九、典型陷阱

1. **用 --quick 测试 source_snapshot** → 永远看不到写盘
2. **用 --full 做"快闪"** → 慢 8-10 倍
3. **inherit 找不到 context 就升 full** → 8/29 修 cvd_analyzer 后 inherit 才有意义
4. **XAU quick 跑 xau_tv_sync** → 20s 同步不是即时
5. **monitor 走 cron_read 不调 macro** → 监控时不读宏观，情绪信号缺失
