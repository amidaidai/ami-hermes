---
name: tradingview-state-integrity
description: Use when verifying shared TradingView chart state.
category: trading
---

> **同族导航** — TV证据组 5 个技能各司其职，别加载错 （同族入口：`tradingview-consumer-evidence`）
> · **本技能 `tradingview-state-integrity`** = 共享图表状态一致性（身份/周期/指标/同轮一致）
> · 同族其余：`tradingview-consumer-evidence`（入口 · 消费 TV 证据的总口径（什么算已验证））、`tv-raw-plot-evidence`（packed 值丢精度时读原始 plot）、`tv-raw-study-evidence`（读原始 study 数值证据）、`pine-indicator-audit`（Pine 源码审计（正确性/配额/面板/合同/消费方核验））
> · 组内改动请同步其余成员的触发词，避免同名族抢触发。


# TradingView 共享状态完整性

用于 TradingView Desktop/CDP 单实例被人工分析、后台采集器、定时任务共同使用的场景。核心目标是防止跨品种污染、陈旧指标和后台任务覆盖用户最终看盘位置。

## 核心原则

- TradingView chart 是共享可变状态，不把“上次会话的品种”当作当前品种。
- 任何分析、截图或指标读取前，先验证目标 symbol、resolution 和 studies。
- 工具调用参数不等于实际图表状态；必须读取工具返回的身份字段再次核验。
- **工具返回的 `success: true` 不等于操作生效。** 这个 MCP 存在「静默空转」的工具：
  `tv indicator set` 返回 `success:true` 但 `updated_inputs:{}`（什么都没改）、
  `tab_new` 无条件返回 `new_tab_opened` 而根本没开页签、`indicator get` 对未缓存的
  study 返回 `inputs: []`。**凡是写操作都必须用行为验收**（面板文案 / Data Window 值 /
  CDP 直查），不能信返回值。详见 `references/mcp-silent-noop-and-bus-wiring-20260911.md`。
- 后台采集可以临时切换图表，但结束时必须恢复用户进入前的 symbol/timeframe；不得无条件停在某个默认品种。
- 外部报价必须核验返回的 symbol、description、exchange、type 和数量级，防止请求BTC却拿到黄金报价。
- **MCP 工具名必须用完整形 `mcp__<server>__<tool>`（2026-09-11 实测）**：`mcp` 后是**双**下划线，server 与 tool 之间也是**双**下划线。写成 `mcp_tradingview__tv_health_check`（单下划线夹 server）会直接报 `is not a deferrable tool`；改成 `mcp__tradingview__tv_health_check` 即通。本会话实测走通：`mcp__tradingview__tv_health_check` / `chart_get_state` / `chart_set_symbol` / `chart_set_timeframe` / `data_get_study_values` / `data_get_pine_tables` / `data_get_ohlcv` / `capture_screenshot` / `ui_fullscreen`。名字一律以工具目录为准，不凭肌肉记忆拼写；报 `not a deferrable` 九成是下划线数不对，重搜一次即可。

9. 对已保存 Pine 源码的发布验收，不能只看本地哈希或 plot 对齐：分别 `pine_open` 主/副脚本并用 `pine_smart_compile` 验证 `has_errors=false`；随后回到活动图表，重新读 `chart_get_state`、`data_get_study_values` 和两张 action table。主 `协同` 行与副 `信号` 行的 S-code 必须一致；即使最终状态是 S3/WAIT，也证明 fail-closed 正常。最后在状态复核后立即生成 full 截图并记录 symbol、resolution、study IDs、source-bar time 和截图路径。

## 分析前置协议

1. 调用 `chart_get_state` 或 `tv_health_check`。
2. 比较实际 symbol 与目标品种；不一致时调用 `chart_set_symbol`。
3. 设置目标主周期：BTC/加密15m（TV参数 `15`），XAU黄金5m（TV参数 `5`）。
4. 品种切换后再设置周期，等待图表和指标刷新；快速状态通常约1–2秒，SVP/CVD等指标约15–30秒。
5. 再次读取 `chart_get_state`/`tv_health_check`，确认 symbol、resolution、studies 全部正确。
6. **校验主→副指标接线**（见下文「指标接线也是图表状态」）：读主、副两个面板，
   主「协同」行的 S-code 必须等于副「信号」行的 S-code。不一致就先重接再继续，
   未确认接线前不得引用副指标的确认/否决结论，也不得判 A 级。
7. 只有通过身份校验后，才读取 pine tables、study values、labels/lines、截图和TV报价。
8. 分析结束后保持用户目标品种及主周期，不主动切回黄金或其他默认品种。

## 指标接线也是图表状态（2026-09-11 实测）

主副指标之间的连线（`input.source` 指向另一个 study）**属于图表状态，会无声丢失**。

现象：主指标显示「副S0未接·A禁」、主 OI 行「OI未接」，而副指标照常有值 → S-code 不一致。

机理：**切品种会让主指标被重新实例化**（entity id `ZI6AGV` → `Rp0kZZ`），
它 `input.source` 里那条指向副指标的引用（形如 `sQC3ma$49`）随旧实例一起消失 → 回退 `close`。
副指标 id 不变，所以只有主这一侧坏掉。**任何会切品种的后台任务都会打断它。**

修复只有一条路管用（CLI 的 `indicator set` 静默空转）：

```python
# id 会变，每次都重新取；不要缓存
by_name = {s["name"]: s["id"] for s in chart_state["studies"]}
indicator_set_inputs(
    entity_id=by_name["SVP+ICT+VWAP+CVD"],
    inputs='{"in_164": "%s$49"}' % by_name["Volume Aggregated Spot & Futures"],
)   # → 等 15–30s 重算，再比 S-code 验收
```

接线值必须是 `<副指标id>$49` 形式（`$49` = Basic Packed Bus 在本仓 AggVol 输出里的序号）；用「<id>_<plot名>」或中文 plot 名等其它字符串会静默空转/不生效——**写完必须回读核验**：等 15–30s 重算后，主指标结论行不再出现「副S0未接」且 `in_164` 不再是 `close` 才算接上；**重挂/重启恢复出的新实例同样回退 `close`**，重挂后立即重接。

**主指标 fail-closed 显示「副S0未接·A禁」本身是对的**（宁可禁 A 也不能用错数据）——
要修的是让它自愈，不是让它放行。**不要**为了自愈在同步脚本里加自动重接：
脚本只能走 CLI，而 CLI 是静默空转 + 读回必然失败 → 每轮刷假告警。
一个「看着成功其实没做」的修复比不修更糟。正确位置是**分析前置流程**（第 6 步）。

## 报价与指标污染防护

- `quote_get` 即使传入目标 symbol，也必须检查返回对象的 `symbol`、`description`、`exchange`、`type`。
- 例如目标是 BTC，但返回 `description: Gold`、`exchange: OANDA` 或 `type: commodity`，应丢弃该报价并重新切图/重取，不能使用。
- **采集器报价身份必须跟 `expect_symbol` 走**（2026-09-12）：不能写死 `BINANCE:BTCUSDT.P` + `exchange=BINANCE` + `type=swap`。写死后黄金报价被拒、BTC 报价反而能给黄金授权。XAU 要 OANDA/cfd 量级，禁止拉 Binance 合约交叉；XAU 只写 `tv_live_XAUUSD.json`，不得覆盖通用 `tv_live.json`。
- TV与Binance属于不同来源、不同时间戳，正常小幅价差不否决；品种错配、资产类型不符或数量级明显不符则硬否决。
- Pine action grid 的结论只能在 symbol/timeframe 已确认后使用；共享图表被其他任务切换时，旧表格可能格式正确但属于另一品种。

## 后台采集恢复协议

后台脚本进入时记录 `previous_symbol` 和 `previous_timeframe`。临时切到采集目标并完成数据写入后，在 `finally` 中：

1. 恢复 `previous_symbol`；
2. 恢复 `previous_timeframe`；
3. **有界重试确认到位**（不是「等一会再看一眼」）：最多 6 次 × 5 秒，
   每次都读回 symbol **和** resolution，两者同时到位才算成功；
   耗尽仍未到位才判失败，并打印最后一次实际观测（否则无从定位）。
4. 异常、超时、部分采集失败也必须走恢复路径。

### ⚠️ 「等固定秒数 + 单次检查」是本类故障的最大来源（2026-09-11 实测，同一缺陷三处）

TV 的品种/周期切换是**异步**的，固定等待在负载高时必然不够。同一个写法在同一个仓库里
出现了三次，且前两处的修复都没传播出去：

| 位置 | 写法 | 后果 |
|---|---|---|
| 关键位采集的切周期确认 | 原为单次 | 失败 54 次、五周期 age 2254s |
| `_prepare_xau_main_chart` | `sleep(20)` + 单次 | XAU 同步**失败率约 1/3**（OHLCV 五周期明明全采到却被整轮丢掉） |
| `_restore_chart` | 同一个写法 | 归还时**品种回去了、周期没回去** |

**症状指纹（很隐蔽）**：`_restore_chart` 失败时**品种已经切回**（立即生效），只有**周期**滞后
→ 用户看到「图是我的币，但周期不对」（现场：归属记录 `user_timeframe=15`，图停在 `5m`）。
**出现「品种对、周期不对」就直接去看那个确认是不是单次检查。**

```bash
# 审计动作：列出所有「切图 → 等一会 → 检查」的确认点
grep -n "time.sleep(" scripts/xau_tv_sync.py scripts/keylevels_collect.py \
  scripts/btc_tv_refresh.py scripts/tv_screenshot.py 2>/dev/null
# 每个 sleep 后面只有一次 _chart_state() 的，就是薄弱点
```

**教训形态：同一根因、多处理器、只修了一处 → 必须回头全库扫同类调用点再交付。**
正确形状（6 次 × 5s，上限 30s，耗尽才判失败并打印现场）：

```python
for attempt in range(1, ATTEMPTS + 1):
    time.sleep(WAIT)
    actual = _chart_state()
    if <期望的 品种/周期/研究 全部就位>:
        return True
    last = f"symbol={...} tf={...}"      # 记住最后一次观测
print(f"  ✗ 确认失败，最后观测: {last}")
return False
```

配套验收两例都要：**慢图能恢复**（前两次读旧状态、第三次到位）与**一直不就位时有界退出**。

如果进入状态不可读，不应擅自把图表留在采集目标；数据缓存发布与用户最终显示状态必须解耦。

### ⚠️ 「记进什么就恢复成什么」会形成棘轮（2026-09-10 实战）

上一节的恢复协议在正常路径下是对的，但**有一个致命缺口**：它把
`previous_symbol = chart_get_state()` 当作“用户的图表”。一旦某次运行
被 cron 超时杀掉、进程被杀、或恢复本身失败，图表就停在采集目标上；
**下一次运行记录的 previous 就是采集目标**，于是它尽职地把图表“恢复”成采集目标。
之后永久锁死 —— 用户怎么切都没用，表现为“图表总自己跳回 XAUUSD 5m”。

现场判据：用户抱怨“图表总在某个固定品种/周期”，而脚本日志显示恢复成功。

**正确做法：把「用户的图表」持久化，而不是从进入状态推断。**
维护一个归属状态文件（例 `data/tv_chart_owner.json`），记录 `user_symbol`、
`user_timeframe`、以及 `pending_restore`：

| 进入时看到 | 处理 |
|---|---|
| 非采集目标品种 | 这是用户的图 → 更新 `user_*`，并记 `pending_restore` |
| 采集目标品种，且 `pending_restore` 存在且不是采集目标 | **上次没还 → 用记录修回来**（打断棘轮） |
| 采集目标品种，`pending_restore` 已清，但记住的 `user_symbol` 仍不是采集目标 | **图被留在采集品种上**（失败路径/杀进程）→ 用 `user_symbol` 修回，不能当成「用户真的在看 XAU」（2026-09-12） |
| 采集目标品种，无待归还记录且无记住的用户品种 | 用户真的在看它 → 不动 |

成功归还后清掉 `pending_restore`。这样**一次失败最多多留一个采集周期**，
下一轮自动修回。若进程在 `finally` 之前被杀，`pending_restore` 仍在 → 下次修回。

验收必测五个场景：正常路径 / 残留修复 / 连续两次残留不漂移 /
用户真在看采集目标时不干扰 / 图表状态读不到时不误改。

### ⚠️ 共享缓存被别的品种整份覆盖

采集器常常共用一个“主缓存”文件名（例 `data/tv_dmi_cache.json`）。
带 `--symbol`/`expect_symbol` 的调用如果绕过了品种门禁，会把**其它品种的整份数据**
写进这个文件 —— 实测该文件里全是黄金数据（`symbol=OANDA:XAUUSD`, 4374），
而 BTC 消费者读它会拿黄金价当 BTC 价。

- 写入侧必须品种感知：非主品种写各自的 `tv_live_{KEY}.json`，不碰共享主缓存。
- 读取侧不能只看文件新不新，**必须校验 `symbol` 字段**与预期品种一致；
  不匹配就当作无数据，不得降级使用。
- 派生指标（结构复核、关键位校验、信号落库）拿到快照后第一件事就是核品种；
  否则会得出“漂移 1600%”这类看着像真结论的假结论。

复现细节与代码骨架见 `references/collector-chart-ratchet-and-cache-poisoning.md`。

### ⚠️ 在 Pine 编辑器里试外来脚本会顶掉生产脚本（2026-09-13 实测，本类事故代价最高）

想「只看一眼某个外来指标长什么样」时，直接 `pine_set_source(新源码)` + 编辑器「Update on chart」
会同时做两件破坏性的事：

1. 编辑器**当前绑定的保存脚本被改写**（实测：`Volume Aggregated Spot & Futures` 的源码被换成试验脚本，
   标题一度变成 `Liquidity Hunter | Aligned`，`modified` 刷新 → 账号里的生产源码被覆盖）；
2. 图上绑在编辑器上的那个 study 实例被换成试验脚本（实测 AggVol 实例被替换）。

**规矩**：

- 试验外来脚本前先 `pine_new` 另存新名，或确认编辑器当前指向的不是生产脚本；
  绝不在「当前指向生产脚本」的状态下 `pine_set_source`。
- 事后恢复：仓库源码 + `python scripts/install_pine_source_v2.py <file.pine> "<旧名>" "<旧名>"`，
  再回读 `pine_open` 的 `lines` 与数据窗字段验收（本仓 AggVol fixed14 = 本地 966 行 / `lines_set` 967）。
- 挂图前后都要记 `chart_get_state` 的 `studies`（id + name）并逐条比对，不能只看「数量还是三个」。
- `pine_list_scripts` 可能留下多余的保存脚本条目（MCP 无删除工具，需人工在编辑器删）——必须在交付说明里写明。

### ⚠️ 脚本层故障的恢复阶梯（红叹号 / 研究掉图）

自定义脚本（SVP/AggVol）图例带**红色感叹号**、无输出、读表持续 `study_count:0`，而内置 Volume 正常 → 脚本层故障，**不要继续重读表**。阶梯（单级最多试一次，无效立即升级；在低级别手段间反复重试是本类故障最大的时间坑）：`Ctrl+R` 刷新 → 品种/周期往返（复位后必须重读表）→ `indicator_toggle_visibility` 关开 → **`tv_launch(kill_existing=true)` 重启 TV 桌面**（最后手段：重启有代价，确认无其他自动化在跑再执行；重启后图回到 owner 持久状态、常为 4h，需重设工作周期；自定义研究可能全部掉图，用「指标」对话框（aria-label `指标、衡量标准和策略`）→「我的脚本」重挂，比编辑器路线可靠；重复实例用 `chart_manage_indicator remove` 去重；**重挂后立即重接主副总线**）。分层诊断表、槽被覆盖判定（`pine_open` 成功≠内容已切换，读 Monaco 验证）与重装命令见 `references/chart-layer-recovery.md`。

### ⚠️ 分析租约必须同进程长驻，否则等于没持有

`python scripts/tv_analysis_lease.py start --minutes 8; sleep 400` 这种写法**无效**：
租约记的是那次短命 python 的 pid，`status` 立刻报「租约持有进程已退出」，
后台任务照切图。持有必须在**同一个进程**内 start 后长驻（同 pid 睡眠），或让分析脚本自己 start 完再干活。

**现在契约层已修**（`tv_data_bridge.begin_analysis_lease` 新增 `liveness` 字段）：

| `liveness` | 语义 | 用途 |
|---|---|---|
| `ttl`（默认） | 只认 TTL，**不看 pid 存活** | CLI `start` / 交互式分析——短命进程写租约的正确语义 |
| `pid` | 保留存活性判定 | 常驻守护进程自持租约 |

**无论哪种模式，`start` 之后必须跑一次 `status` 确认 `active: true`。** 看到
「租约持有进程已退出」就等于**根本没有租约**——此时多周期读数必然被抢，先修再读，
不要硬读，更不要把抢到的数当成目标周期出卡。「返回 success 就是持有成功」和
本文件其他静默空转是同一类错误。

诊断一行（判断到底谁没让路）：

```bash
python -c "import sys,json;sys.path.insert(0,'scripts');from tv_data_bridge import analysis_lease_status;print(json.dumps(analysis_lease_status(),ensure_ascii=False))"
grep -rln 'set_timeframe' scripts/ monitor/   # 谁在切图；再核对这些脚本是否读 analysis_lease_status()
```

另注：**租约是让路信号、不是硬锁**——`*/15` 的 XAU 同步等定时任务可能恰在租约生效前后启动、整轮压进分析窗口；别拿 `status` 字段当安全证明，分析全程按抢图协议复核＋复位。

## 并发注意事项

- 恢复逻辑只能解决单个任务的尾部状态，不能解决另一个任务随后覆盖图表的问题。
- 所有会调用 `set_symbol`/`set_timeframe` 的后台路径应共享跨进程锁；人工分析也应尽量避开采集临界区。
- 若无法让人工调用纳入同一把锁，应在人工分析的最后重新设置目标品种/主周期并做最终 health check；不要仅凭脚本“打印恢复成功”认定状态稳定。
- 现场验收至少包含：设置BTC/15m→运行一次黄金采集→等待并发窗口→health check仍为BTC/15；再反向测试黄金/5m。

### 人工分析侧：被 cron 抢图时的读取协议（2026-09-11 实战）

前面几节都站在**采集器**一侧（脚本怎么借图、怎么还图）。本节补上**人工分析**一侧：图被后台抢走时，分析该怎么读、怎么判、怎么诚实出卡。

**场景**：`btc_tv_refresh`（排程 `7,27,47` 分）循环切图续航（1D→4h→1h→15m→5m），与人工分析共用同一张图。人工分析在两次 cron 之间抢时间窗。

**症状指纹**（BTC 轻量档实况）：

| 你以为 | 实际 | 判据 |
|---|---|---|
| 切周期已生效 | 图在另一个周期 | `chart_set_timeframe` 返回 `success:true, chart_ready:true`，但紧接着 `chart_get_state` 的 `resolution` 不是目标周期 |
| **`chart_get_state` 说的就是真的** | **它可能只是在回显你请求的值** | 请求 `240` → state 报 `240`，但读回来的 OHLCV 相邻 K 线间距是 **300s**（5m）；同一轮「1D」与「4h」两组数值完全一致。**state 是弱证据，数据间距才是硬证据** |
| 该周期 SVP 不渲染 | 抢图瞬间读到空档 | `data_get_pine_tables` → `study_count: 0`（**这是争用信号，不是「无数据」，要重读**） |
| 在看 5m 的副指标 | 读到的其实是 1D 的表 | 表内容格式正确但有**锚定词**：`月·单所1m…`=1D/4h 层，`日·单所1m…`=15m 层，`本锚` 指当前锚定周期 |
| 报 4h 就是 4h | 静默读到 5m | `(period.to - period.from) / (bar_count - 1)` 应为 14400s，实为 300s |

**周期写法**：一律用 `"1D"` / `"240"` / `"60"` / `"15"` / `"5"`。带单位的 `"4h"` / `"5m"` 会出现「返回 success 但周期没切过去」；`"5m"` 另会被误解释成异常高周期（OHLCV 只剩极少根、标签蹦出跨年月日期）。`studies[].resolution` 字段会滞后一两拍，同样不能当判据。

**协议**：切周期 → `chart_get_state` 复核 `resolution` → 不一致就重切一次再复核 → **再读 OHLCV 校验 K 线间距**（容差 5%：1D 86400 / 4h 14400 / 1h 3600 / 15m 900 / 5m 300）→ 两项都过才读表。`study_count: 0` 一律按争用处理并重读。

**K 线间距校验是唯一能拦住静默污染的门**——`chart_get_state` 会回显请求值、`success` 恒为 true、`studies[].resolution` 会滞后，三者都拦不住「报 4h 实读 5m」。校验必须作用在**最终落盘的那批读数**上，不能只验一次就往下写。对不上就重锁重读，连试 4 次仍对不上就标注「该周期本次不可用」，**绝不把 5m 的数当 4h 写进卡里**。

现成实现：`python <skill_dir>/scripts/tv_read_verified_tf.py --symbol BINANCE:BTCUSDT.P --out outputs/btc_5tf_verified.json`（逐周期锁定 + 间距校验 + 重试 + 落盘，末尾回主执行周期）。多周期分析优先跑它，不要手打几十次 MCP 调用——手打时极易漏掉校验。

重读仍为 0 时换假设：图例带红叹号（截图＋vision 确认）＝脚本层故障，转恢复阶梯，继续重读不会有结果。

**截图时机**：主执行周期截图**切好并复核后立刻拍**，不要等把所有周期表格都读完再回头拍——那正是 cron 最可能介入的窗口。（本次 15m 图就是趁 14:06 空档抢下的。）

**归属文件是判据、不是噪音**：`data/tv_chart_owner.json` 的 `user_timeframe` 记的是**用户**的周期。实战里 `user_timeframe=5` 而图先后停在 `1D`/`240`/`15` —— 这恰好说明归属机制在正常工作，是 cron 在借图，而不是归属坏了。**别急着改脚本**。

**诚实出卡**：某周期多次重切仍读不到，就在「缺失备注」写明「被 btc_tv_refresh 抢图未能读到·仅取到 OHLCV」。**不得用别的周期数据冒充**，也不得标成「SVP 不渲染」—— 那是两种完全不同的原因，混淆会让人去查错方向。OHLCV（1–2 秒可用）比指标表格（15–30 秒重算）更难被抢，是可用的兜底。

**与上文的关系**：采集器侧的「减少切换」修复并不能消除人工分析侧的争用 —— 只要 cron 还在借图，人工就必须按本协议复核。两侧都要。

### 先做「切换源普查」，再谈减少切换（2026-09-11）

用户报「图表总自己切品种和周期」时，先量出**谁在切、切几次**，不要直接猜：

| 任务 | 频率 | 实际切图 |
|---|---|---|
| XAU TV现场同步 | 每 15 分 | 品种 + 5 周期 + 归还 = **7 次/轮 → 28 次/小时** |
| BTC TV五周期续航 | 每 20 分 | **条件触发**：快照 <22 分即整个跳过 → 实际约 40 分一次 |
| tv_screenshot | 按需 | `reuse_verified=True` 默认，图已就位就不切 |

普查时注意：`grep '"symbol"'` 命中的**可能是字典键而不是图表命令**（本次就误列了
一个不切图的脚本）。必须回看上下文。

**加一行切换计数**（`图表切换 品种(实切N/跳过N) 周期(实切N/跳过N)`）能让「是切得太频繁」
与「是还原坏了」一眼分开。**任何「减少干扰」的修复都必须实测验证** ——
本次做了「已是目标状态就跳过」，实跑却是 `实切1/跳过0`、`实切6/跳过0`，
证明那 7 次全是必需的、本修复没有减少切换。**如实报告，不要把它说成修好了。**

### ⚠️ 减少切换的根本限制

- **专用标签页隔离在当前工具下不可行**：TV Desktop 这个配置没有图表页签条，
  且 `tab_new` 静默空转（详见 `references/mcp-silent-noop-and-bus-wiring-20260911.md`）。
  **不要把它写成推荐方案。**
- `data_get_ohlcv` **没有周期参数**，只能读当前图的周期 → 走 MCP 取多周期 K 线绕不开切图。
- **但先查清楚每个周期到底读了什么**：本次发现 XAU 那 5 个周期的循环**只读 OHLCV**、
  完全不读指标，即 **5/7 次切换是可省的**（K 线可换数据源）。代价是数值源改变、
  会与用户对图核对的习惯冲突 —— **属于产品取舍，需用户拍板，不要自行替换。**

## 消费层证据读回（2026-09-11）

图表对象已能通过 CLI/MCP 进入卡片时，仍要区分“读回完整”与“类型完整”：box 返回可能叫 `zones`，quote 必须保留同一响应的 O/H/L/C，不能只留 last；无类型标签的区域只能记录为通用 zone，不得猜成 FVG/OB。请求 symbol 与返回报价身份不一致时整份丢弃。`verified` 是身份、周期、价格栏和结构化证据通过，不代表每种 ICT 子类型都非空；缺少对象时 `partial/visual_only` 只允许 WAIT，identity mismatch 必须 NO-GO。

完整复现、兼容字段和回归验收见 `references/consumer-layer-chart-evidence.md`；最新现场复核与可重跑命令见 `references/consumer-layer-live-recheck-20260912.md`。

## 最小验收清单

- [ ] 目标 symbol 与实际 chart symbol 一致
- [ ] 目标主周期与实际 resolution 一致（**切周期后必须复核过 `chart_get_state.resolution`，不能只看 `success:true`**）
- [ ] **每周期 OHLCV 的 K 线间距与目标一致**（容差5%：1D 86400 / 4h 14400 / 1h 3600 / 15m 900 / 5m 300）——防「报4h实读5m」；state 回显不算证据
- [ ] 分析租约 `status` = `active: true`（否则后台抢图，多周期读数不可信）
- [ ] `data_get_pine_tables` 的 `study_count` 不为 0（为 0 先按抢图重读；重读仍 0 且图例红叹号 → 走脚本层恢复阶梯）
- [ ] studies 已加载且与目标分析匹配
- [ ] action grid 与目标品种数量级相符
- [ ] quote 的身份字段与目标资产相符
- [ ] 截图为最终状态生成，`region=full`，含价格轴和CVD窗格
- [ ] 试验脚本后：`pine_list_scripts` 无多余脚本、编辑器当前脚本已还原、图上 studies 逐条比对一致
- [ ] 后台采集完成后最终状态仍是用户目标品种/周期

## 参考资料

- **多源交叉验证别把同一数据数两次（2026-09-11 实测）**：TV 副指标 DW 的 `LSR` 与 Binance `futures/data/globalLongShortAccountRatio` 是**同一数据**（本会话两者同为 `1.6575`）。它们只能算 **1 个源**，写成「TV 说 1.66 + Binance 说 1.66 → 双源确认」是自证。真正独立的是**大户** `topLongShortPositionRatio`（本次 2.13）与**全局账户**（1.6575）—— 两者背离才是有效证据。凡是「两个源数字一模一样」，先怀疑同源，再算独立源数。

- **`scripts/tv_read_verified_tf.py`** — 多周期读取器：逐周期「锁定 → 验 resolution → 读 OHLCV → 验 K 线间距 → 不符重试」才落盘，末尾回主执行周期。做五层分析时优先跑它，不要手打几十次 MCP 调用（手打必漏校验）。
- 共享状态污染的复现、恢复和验收细节见 `references/shared-chart-state-recovery.md`（未落地·勿引）。
- **MCP 静默空转的行为验收、主→副总线断线机理与重接 recipe、切换源普查与实测数字**
  见 `references/mcp-silent-noop-and-bus-wiring-20260911.md`（2026-09-11，含 CDP 验证命令）。
- 脚本层故障（图例红叹号 / 自定义研究掉图 / 云端脚本槽被覆盖）的分层诊断、恢复阶梯（含 `tv_launch` 重启与对话框重挂）与重装流程见 `references/chart-layer-recovery.md`。
- 加密分析的多源管线和主副指标裁决见 `crypto-multisource-analysis`。
- 加密15m/黄金5m执行周期和执行卡格式见 `tradingview-execution-card`。
- 主副指标字段映射与契约见 `tradingview-indicator-analysis`（内已含分析前置的总线检查）。
