# TradingView 账号档位硬限制（免费 Basic 重点）与免费档优化

抓取日期：2026-08-02，来自官方定价页 `https://www.tradingview.com/pricing/`（浏览器渲染后 innerText 提取）+ 官方 Pine limitations 文档（curl --compressed 抓取）。用于免费账号下的 Pine 指标优化，避免堆功能后才发现配额/性能全部被档位卡死。

## 一、免费 Basic 与付费档对照（官方定价页实时数据）

| 维度 | 免费 Basic | Essential | Plus | Premium | Ultimate |
|---|---|---|---|---|---|
| 指标/图 | **2** | 5 | 10 | 25 | 50 |
| 历史K | **5,000 根** | 10K | 10K | 20K | 40K |
| 图表/页签 | 1 | 2 | 4 | 8 | 16 |
| 并发连接 | 2 | 10 | 20 | 50 | 200 |
| 价格告警 | **3** | 20 | 100 | 400 | 1,000 |
| **技术告警(脚本)** | **0** | 20 | 100 | 400 | 1,000 |
| 布告看板告警 | 0 | 0 | 0 | 2 | 15 |
| 分钟级回放 | 180 天 | 365 天 | 全部 | 全部 | 全部 |
| 计算时限 | **20s** | 40s | 40s | 40s | 100s |
| 秒级/即时数据 | ✗ | ✗ | ✗ | ✗ | ✓ |
| intrabars | 100K | 100K | 100K | 100K | 200K |
| Volume Footprint | ✗(需Premium+) | ✗ | ✗ | ✓ | ✓ |
| 图表布局 | 1 | 5 | 10 | 定制 | 定制 |

## 二、对免费账号的致命推论（审计双指标时必查）

1. **免费档技术告警 = 0 → `alertcondition()` 在免费账号是纯死重**。alertcondition 只创建"可被脚本告警触发的事件"，而免费档根本无法创建脚本/技术告警。因此免费账号下所有 `alertcondition()` 既不能触发、又各占 1 个 plot count → **应全部删除，改为 1 个动态 `alert()`（事件化 `state and not state[1]`），或直接交给外部 Python 扫描管线推送**（棠溪系统已用 Python 承担推送，TV 告警本就是冗余）。这是免费档收益最大的一刀。
   - 主指标实测 16 个 alertcondition、副指标 9 个 = 25 个 plot count 纯浪费。
2. **历史K 5,000 根**：5m 图仅 ~17 天、15m ~52 天、1h ~208 天、4h ~833 天；D/W 图 5000 根日K≈20 年全量。免费档主战周期天然是 5m/15m/1h/4h，关键位/前日高低/流动性扫描只依赖近期数据 → 免费档完全够用，不必追求超长历史。
3. **指标/图 = 2**：主+副正好占满，**不能再加第三个指标**。新功能（如 Footprint 升级）只能做独立脚本在 Premium+ 评估，塞不进现有双指标。
4. **计算时限 20s（付费 40s）**：主指标 SVP 全量重算 + lower-TF 精度是最大超时风险。见下方 calc_bars_count 杠杆。

## 三、免费档性能第一杠杆：`calc_bars_count`

**`request.security_lower_tf()` 不传 `calc_bars_count` 时按图表全量K拉取 intrabars**，且每根图表K都做全量重算：

- 5m 图挂 1m 精度 = 25,000 intrabars；4h 图挂 60m = 20,000；每根图表K重算 288 根×70 桶 ≈ 2 万次运算 × 5000 根 → 极易爆免费档 20s 限制。
- **修法**：lower-TF 请求加 `calc_bars_count=1000`（或更小，按需），intrabars 25,000→5,000，计算量降 5 倍，20s 限制稳过。CVD lower-TF 与 SVP 精度 lower-TF 两处都要加。
- 官方文档确认：`calc_bars_count` 限制单请求拉取的 intrabar 数；不传则等于图表K数。免费档非专业方案 intrabars 上限 100K。

## 四、社区/官方性能优化共识（2026）

- **官方 Profiler**（`/pine-script-docs/writing/profiling-and-optimization/`）：`memory.log()` + Profiler 面板定位慢点。改完性能相关代码必须跑，不能只靠静态扫描。
- **tuple 合并 request**：LuxAlgo 实测 9→1 请求 340ms→228ms；同 symbol/timeframe 多字段应合并。
- **预分配数组**：`array.new_float(N, 0)` 优于动态 push。
- **减法优先**：删重复投票、低价值变体、死告警；不堆模块。
- **Pine v6 动态请求**：`request.*()` 40 unique（Ultimate 64），相同参数重复调用只计 1 次；不同 symbol/timeframe 算不同 unique context。

## 五、取证技术备注（本次实测可用路径）

- 官方**文档**（limitations/profiling/other-timeframes/alerts）：`curl --compressed` 直抓 HTML，`--compressed` 必须加否则拿到压缩乱码。web_extract 对 tradingview.com 报 "private or internal network address" 拦死，不走它。
- 官方**定价页**（JS 渲染，curl 拿不到明细）：用浏览器工具 navigate + `browser_console` 执行 `document.body.innerText` 提取完整对比表。
- web_search 后端（Firecrawl）被封时，备用 `html.duckduckgo.com/html/`（curl + 正则 `class="result__a"`）可用但**限流快**（连续请求返回 0 结果），需 sleep 间隔；Bing 需过验证码不可靠。
