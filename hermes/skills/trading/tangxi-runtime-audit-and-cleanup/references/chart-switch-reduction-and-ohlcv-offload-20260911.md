# 减少共享图表切换 + 把只读 OHLCV 的采集移出图表（2026-09-11）

## 起因

用户报「我发现 TV 图表总是自己切品种和周期，全面的修复」。
注意这类投诉有两种完全不同的成因，**必须先分清**：

| 成因 | 症状 | 处置 |
|---|---|---|
| 图表**回不到**原位 | 切走之后就停在采集品种/周期 | 还原逻辑的 bug（见 SKILL.md「切周期确认重试强度不一致」与「棘轮」两节） |
| 图表**频繁切走** | 定位/品种/周期被来回改写 | 采集侧必须切图（本节） |

本次两条都命中：还原有三处单次检查缺陷（已修），**并且**采集本身确实每 15 分钟切 7 次。
只修前者，用户依然会觉得「它总在切」。

## 第一步：先量化「谁在切、切几次」

```bash
# 1) 找出所有会切图的脚本
grep -rn 'set_symbol\|set_timeframe\|_tv("symbol"\|_tv("timeframe"' scripts/*.py | head -40

# 2) 对照 cron，看每个脚本的调度频率与是否条件触发
python - <<'PY'
import json, os
from pathlib import Path
d = json.loads(Path(os.path.expanduser(r"~\AppData\Local\hermes\cron\jobs.json")).read_text(encoding="utf-8"))
for j in (d if isinstance(d, list) else d.get("jobs", [])):
    print(j.get("enabled"), j.get("name"), j.get("script"), (j.get("schedule") or {}).get("display"))
PY
```

本次结果（**别跳过这步，它会推翻你的直觉**）：

| 任务 | 频率 | 真实切图量 |
|---|---|---|
| XAU TV现场同步 | 每 15 分 | 品种 + 5 周期 + 归还 = **7 次/轮** ← 唯一大头 |
| BTC TV五周期续航 | 每 20 分 | **条件触发**：快照 <22 分就整个 return 0，实际约 40 分才跑一次 |
| tv_screenshot | 按需 | `reuse_verified=True` 默认已开，图已就位就不切 |
| keylevel_read_trigger | 每 2 分 | **不切图**（grep 命中的 `"symbol"` 是字典键，不是图表命令） |

教训：**先读 `main()` 有没有条件短路，再统计频率** —— 否则会把一个每 40 分钟才跑一次的任务
当成主犯。差点据此把一个正确的设计改坏。

## 第二步：给切换装计数器（否则改完无法证明）

在**共用工具层**（本例 `scripts/fetch_tv_mcp.py` 的 `set_symbol` / `set_timeframe`）里埋计数器，
所有调用方自动受益，不用改任何一个业务脚本：

```python
SWITCH_STATS = {"symbol_skipped": 0, "symbol_set": 0,
                "timeframe_skipped": 0, "timeframe_set": 0}

def switch_stats_line():
    s = SWITCH_STATS
    return (f"图表切换 品种(实切{s['symbol_set']}/跳过{s['symbol_skipped']}) "
            f"周期(实切{s['timeframe_set']}/跳过{s['timeframe_skipped']})")
```

并在每个采集任务结束时打印。**这一行的价值超过整个修复**：
它把「图表为什么在切」从不可观测变成可观测，下次再有类似投诉可以直接读数字。

实测输出（改前 / 改后）：

```
品种(实切1/跳过0) 周期(实切6/跳过0)      ← 0 次跳过：那 7 次全是必需的
品种(实切1/跳过1) 周期(实切0/跳过2)      ← 只读 OHLCV 的部分已移出图表
```

## 第三步：审计每个逐周期循环「到底读了什么」

这是本节最有价值的一刀。读循环体，问一个问题：
**它读指标，还是只读 K 线？**

```bash
# 逐周期循环里有没有出现这些「读指标」的调用？
grep -n "get_study_values\|get_pine_lines\|get_pine_labels\|get_pine_tables\|get_pine_boxes" scripts/xau_tv_sync.py
```

本次结果出乎意料：XAU 的五周期循环只有 `get_chart_state` + `get_ohlcv`，
**完全不读指标**；报告 `_build_xau_report` 也只用 OHLCV（high/low/close）。

→ **那 5 次周期切换纯粹为了取 K 线**，而 K 线可以走 API。

**判据：一个逐周期循环如果只读 OHLCV，它就不需要占用用户的图表。**
反过来，如果它读 SVP 画出来的 lines/labels/boxes（这些是**周期特有**的），
那就必须切图，切不掉 —— 不要试图优化掉它。

## 数据源候选（选源时按这个顺序试）

| 源 | 覆盖 | 结论 |
|---|---|---|
| **OANDA v20** `/v3/instruments/XAU_USD/candles?granularity=M5..D` | 5m/15m/1h/4h/1D 全覆盖 | **首选**：与图表品种 `OANDA:XAUUSD` **同源**，偏差为 0。需 token（见下） |
| TwelveData `/time_series?symbol=XAU/USD` | 5min/15min/1h/4h/1day 全覆盖 | 可用替代。实测与 TV 差 0.03%~0.17% |
| jin10 MCP `get_kline` | **只给分钟级、≤100 根、24 小时内** | ✗ 拿不到日线，不适合 |
| Yahoo `XAUUSD=X` | — | ✗ 404，Yahoo 没这个现货符号 |
| Yahoo `GC=F` | 全覆盖 | ✗ **黄金期货**，与现货常年差 ~$40（4350 vs 4310）。**绝不能拿来做现货卡面** |

**同源优先**：图表是 `OANDA:XAUUSD` 就用 OANDA API —— 不只是更准，
是**卡面数值与用户自己看到的那张图逐位一致**，用户不用怀疑。

### 密钥文件常是「注释 + 占位符」混排

读取时要跳过注释行与占位符，否则会拿一串 `PLACEHOLDER_…` 去发请求（表现为诡异编码报错）：

```python
def _read_secret(name):
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "//")):
            continue
        if line.upper().startswith(("PLACEHOLDER", "TODO", "CHANGEME", "YOUR_")):
            return ""          # 占位符＝没有，必须判为不可用
        return line
    return ""
```

顺带发现：缺 OANDA token 会让 XAU 数据质量**上限卡在 B 级**（见该文件自带的注释）。
这类「密钥缺失 → 能力静默降级」值得在审计时一并报出来。

## ⚠️ 口径陷阱：跨源的「正在形成 / 已闭合」K 线不是同一根

**这是本次最值钱的一条。** TV 那条路取的是 `last_5_bars[-2]` = **最后一根已闭合**；
而 TwelveData 的 `values[0]` 是**正在形成**的那根。

实测证据（2026-09-11 03:42 UTC）：

| 周期 | TD `values[0]` | 实情 |
|---|---|---|
| 5min | 03:40 | 覆盖 03:40-03:45，**正在形成** |
| 15min | 03:30 | 覆盖 03:30-03:45，**正在形成** |
| 1day | 2026-09-11 | **今天**，正在形成 |

不改口径的后果：卡片上的高/低**随盘口跳动**，且与用户图上对不上。

**更阴的是它曾经「校核通过」**：刚开盘 2 分钟，forming bar 的 H/L/C 恰好落在上一根范围内，
跨源比对显示 0.012% 差异 → 假通过。取 `values[1]` 后 1D 的 C 从 4308.31 → **4316.76**，
与 TV 的 4317.0 吻合。

**铁律：换数据源时，第一件事是确认「取哪一根 K 线」的口径与旧源一致，
并且警惕一次低差异的通过可能是巧合。**

## 换源的安全形状：旁路 + 对账 + 阈值 + 回退

绝不做「直接换掉、有问题再说」。形状固定为：

```
1. 新源取数
2. 顺手拿旧源的一根 K 线对账（本例：反正要切一次 5m 读指标面板，顺便读 5m OHLCV）
3. 差异 ≤ 阈值 → 采用新源；> 阈值 → 告警 + 回退到旧路径（旧路径一字未改地保留）
4. 新源失败/熔断 → 同样回退（fail-safe，行为与改前一致）
```

```python
def cross_check(api_frames, tv_bar, tolerance=0.0035):
    """用旧源校核新源；缺任何一项都判失败（fail-closed）。"""
    ...
    worst = max(abs(api_v - tv_v) / tv_v for field in ("high", "low", "close"))
    return (worst <= tolerance), msg
```

阈值取实测差异的 3 倍余量（实测 0.17% → 阈值 0.35%）。
**回退路径必须保留为一个独立函数**，不要把它删掉或塞进分支里 ——
它就是这套改动的安全网。

配套：**429 触发源级熔断**（约 15 分钟），熔断期间跳过该源直接降级，
**不拿旧缓存冒充实时**（对齐全系统的降级契约 live/cache/stale_cache/unavailable/quota_cooldown）。
免费额度下要注意调用次数：5 次/轮（每周期一次）在 15 分钟调度下安全，
但测试时连打十几次会立刻 429 —— 压测完记得清掉自己造成的熔断记录。

## 验证记录（本次实测）

```
✅ 5m 校核通过（high=0.000% low=0.023% close=0.095%） → 采用 API 五周期
   图表切换 品种(实切1/跳过1) 周期(实切0/跳过2)
```

| 周期 | API vs TV 偏差 |
|---|---|
| 1D | 0.102% |
| 4h | 0.044% |
| 1h | 0.029% |
| 15m | 0.035% |
| 5m | 0.172% |

切换 7 次 → ~3 次（约降 57%）。剩下的是**切不掉的**：1 次切到 5m 读指标面板 + 归还。

## ⚠️ 想用「第二个标签页」隔离？先验证那个 API 真的会开页

「让后台任务在独立标签页里跑」是这类问题的自然想法。**但在设计之前必须先验证。**

本次实测：MCP 的 `tab_new` **只发一个 Ctrl+T 就无条件返回 `success:true`**，从不校验；
CDP 直查 `http://127.0.0.1:9222/json/list` 证实**一个页都没开**；扫 DOM 也没找到图表页签条。

**通用教训（不是「某工具不能用」）：凡「打开/创建/添加」类的 MCP 操作，
成功返回都不等于真的发生了 —— 用独立通道复核副作用（CDP `/json/list`、读回值、面板文案、计数）。**
落地前先花两分钟验证能力存在，否则整套隔离方案会建立在一个空转的 API 上。

## ⚠️ 变体：还原正确，但「错的偏好」被永久传承

棘轮那条（SKILL.md）讲的是**恢复失败**造成的自持。本次发现一个更隐蔽的变体：
**恢复完全正常，但记录的「用户偏好」本身是错的。**

现场：归属记录 `user_timeframe: 5`，而用户的实际意图是 15。
成因是更早的某一次恢复失败把图留在 5m（即棘轮那条的产物），
**此后每一轮都忠实地把「5m」当成真理保留**。

```
captured_at 11:48:03 → 捕获到的就是 BTC 5m
restored_at 11:49:15 → 归还耗时 72 秒（有界重试在干活 ✓）
```

**排查手法**：看归属记录里 `captured_at` 与 `restored_at` 都在、`pending_restore` 已清空、
但周期不是用户说的那个 —— 那就是**源头错值被忠实传承**，不是这一轮还原失败。
不要把这种情况误判成还原 bug（本次差点误判）。

**处置**：把图表设回用户声明的值即可（下一轮捕获会跟着修正）—— 系统无从知道
「用户真正想要 15」，它只能记录「它看到什么」。要根治就得让用户偏好有一个独立于观测的来源。
