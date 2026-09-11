---
name: orion-screener-radar
description: Orion Terminal 全市场雷达 v2 — 四层多源验证(Orion Binance/HL + Binance API + CoinGecko)，扫描604+永续合约异动，置信度评分推送至Telegram
category: trading
---

# Orion Screener 全市场雷达（多源验证版 v2）

实时扫描 Orion Terminal （screener.orionterminal.com） 提供的 604+ 永续合约数据，**四层验证链**自动检测市场异动并推送告警。

## 验证架构（并行化 v2.2）

```
第1+2层: 并行扫描 Orion Binance (604品种) + Orion Hyperliquid (451品种)
  ↓ ThreadPoolExecutor(max_workers=2) 同时拉取两交易所
  ↓ url 必须显式传 exchange 参数: ?exchange=binance
  ↓ 网络容错: 代理优先 → 直连回退 (cron环境可能无代理)
  ↓ 检测异动候选项 + 跨交易所交叉验证
第3层: Binance REST API (HMAC签名)
  ↓ ThreadPoolExecutor(max_workers=3) 并行验证 5 个候选
  ↓ 每个候选内部 6 个 API 调用也并行 (max_workers=6)
  ↓ OI趋势 / 费率历史 / Taker量 / 多空比
第4层: CoinGecko Demo API
  ↓ 首败即停 (避免浪费配额)
  ↓ 市值排名 / 现货成交量 / 价格一致性
全局 90s deadline guard → 剩余时间不足时自动跳过深层验证
置信度评分 → 格式化告警
```

**性能**：v2.0 串行架构 120s+ 超时 → v2.2 并行架构 ~5s 完成

## 配套工具

### CoinGecko CLI（已安装）
```bash
cg price --ids bitcoin              # 查BTC价格
cg trending                         # 24h热搜
cg top-gainers-losers               # 涨跌榜(需付费Key)
cg history --ids bitcoin --days 7   # 7天历史
cg tui                              # 交互式仪表盘
```

### Grok 4.3 + X 情绪分析（x_search 实时）

**前提**：先执行 `hermes auth add xai-oauth` 浏览器登录X账号，授权后 x_search 工具自动启用。

Orion 只做数据扫描，X 实盘情绪需要手动触发。看到感兴趣品种后说：
> "看看 X 情绪" / "Grok 分析一下 XXX"

流程：
1. `x_search("$COIN sentiment crypto 2026")` → 实时 X 推文（grok模型，90s超时）
2. 提取方向（看多/看空/中性）、强度、大V观点
3. 整合进分析卡

**降级路径**：x_search 不可用时回退 `web_search site:twitter.com "$COIN"` 并标注来源。

## CoinGecko API 注意事项

| Key类型 | 域名 | 认证头 |
|---|---|---|
| Demo Key (CG-...) | `api.coingecko.com` | `x-cg-pro-api-key` |
| Pro Key (CG-...) | `pro-api.coingecko.com` | `x-cg-pro-api-key` |

⚠ Demo Key 不可用于 `pro-api.coingecko.com`，会报 400。脚本已自动处理域名切换。

## CoinGecko MCP Bridge（可选）

`scripts/coingecko_mcp_bridge.py` — stdio ↔ Streamable HTTP 桥，供 agent 深度分析时调用 CG MCP。需手动激活 config.yaml 配置。不必须——FinanceKit MCP 已提供相同数据。

## 依赖

- **Binance API Key**（环境变量 `BINANCE_API_KEY`、`BINANCE_SECRET_KEY`）— 第3层验证必需。Hermes 注入到 no_agent 脚本环境。HMAC 签名模板见 scripts/system_data_bridge.py。
- **Orion API** 公开免费，无需 key。

## 脚本 HMAC 签名模式

no_agent 脚本调用 Binance 签名端点时使用以下标准模式（来源于 system_data_bridge.py）：

```python
import os, hmac, hashlib, time, urllib.request

BK = os.environ.get("BINANCE_API_KEY", "")
BS = os.environ.get("BINANCE_SECRET_KEY", "")
ts = int(time.time() * 1000)
params = f"symbol=BTCUSDT&limit=1&timestamp={ts}"
sig = hmac.new(BS.encode(), params.encode(), hashlib.sha256).hexdigest()
req = urllib.request.Request(
    f"https://fapi.binance.com/futures/data/openInterestHist?{params}&signature={sig}",
    headers={"X-MBX-APIKEY": BK}
)
```

## 第三方数据集成状态

| 数据源 | 当前状态 | 用途 | 接入难度 |
|---|---|---|---|
| Orion Binance | ✅ 已接入 | 异动第一层检测 | REST/免费 |
| Orion Hyperliquid | ✅ 已接入 | 跨所验证 | REST/免费 |
| Binance API (签名) | ✅ 已接入 | 深度验证(OI/费率/Taker/LS) | 已有key |
| CoinGecko API (Demo) | ✅ 已接入 | 市值排名/现货量过滤垃圾币 | DEMO Key已有 |
| xAI Grok OAuth (x_search) | ✅ 需手动登录 | X实时情绪/叙事分析 | `hermes auth add xai-oauth` |
| CoinGecko CLI | ✅ 已安装 | 命令行行情查询 | `npm install -g @coingecko/cg` |
| Fear & Greed | ⏳ 待接入 | 宏观情绪基调 | REST/免费 |
| Bybit API | ❌ 未配置 | 多交易所对比 | 需生成Bybit API Key |
| CoinGlass | ❌ 已移除 | 全所爆仓热力图/OI聚合 | 无API Key，暂不使用 |

`references/capability-gaps.md` 记录了每个待接入源的详细集成方案。

## 候选后深度分析

当用户从 Orion 雷达看到候选后问「全面分析这几个有哪一个有机会的」时，走 `references/post-radar-deep-analysis.md` 流程：
1. 读取完整候选 JSON（不只看简报）
2. 硬过滤（OI≥$2M + |OI%|≥3% + 置信度≥5.0）
3. x_search 深度验证 Top 3-5
4. OI/价方向 + Funding + Taker + 多空比 四维交叉
5. 3表格式 verdict 输出

详见 reference 文件。

## 数据源

- **API**: `https://screener.orionterminal.com/api/screener`
- **无需 API Key**，免费公开
- **支持交易所**: Binance（604 品种）、Hyperliquid（451 品种）
- **数据维度**: 价格、OI、资金费率、多时间框架（5m/15m/1h/4h/8h/12h/1d）的涨跌/成交量/波动率/OI变化

## 置信度评分（1-10）

| 分数 | 等级 | 条件 |
|---|---|---|
| 7-10 | 🟢 高置信度 | Orion异动 + HL确认(一致度≥3/4) + Binance API佐证 |
| 4-6 | 🟡 中置信度 | Orion异动 + 至少一个其他源确认 |
| 1-3 | ⚪ 低置信度 | 仅Orion单源信号，需人工检查 |

## 判断逻辑

| OI方向 | 价格方向 | 判断 | 含义 |
|---|---|---|---|
| ↑ OI涨 | ↑ 价涨 | 📈 真突破信号 | 新资金进场，趋势可持续 |
| ↑ OI涨 | ↓ 价跌 | ⚠️ 接盘预警 | 有人在抄底，但价格不跟 |
| ↓ OI跌 | ↑ 价涨 | 💨 空头平仓反弹 | 轧空行情，快但可能短命 |
| ↓ OI跌 | ↓ 价跌 | 📉 趋势性下跌 | 多头止损，趋势确立 |

## 阈值配置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `ORION_EXCHANGE` | `binance` | `binance` / `hl` / `both` |
| `ORION_MIN_OI_USD` | `500000` | 最小 OI 过滤 |
| `ORION_MIN_VOLUME_1H` | `100000` | 最小 1h 成交量 |
| `ORION_OI_SPIKE_PCT` | `8` | OI 变化阈值 % |
| `ORION_BIG_MOVER_PCT` | `5` | 涨跌幅阈值 % |
| `ORION_FUNDING_THRESHOLD` | `0.0008` | 资金费率绝对值阈值 |
| `ORION_VOL_SURGE_PCT` | `200` | 成交量变化阈值 % |
| `MAX_CANDIDATES` | `5` | 深度验证候选数 |
| `MAX_OUTPUT` | `5` | 最终输出品种数 |
| `BINANCE_TIMEOUT` | `15` | Binance API per-call 超时秒数 |
| `DEADLINE_SECONDS` | `90` | 全局 deadline guard（cron 默认 120s，留 30s 余量） |

## 使用示例

### no_agent cron（推荐，零 token 成本）
当前配置：每30分钟 9:00-23:00 BJT，发回到源聊天。
```bash
hermes cron update {job_id} --schedule "*/30 9-23 * * *"
```

### 手动测试
```bash
cd ~/AppData/Local/hermes/scripts
python orion_screener_radar.py
```

## 输出格式（2026-07-01 用户最终确认）

### 核心原则

- **全部输出使用真实Markdown管道表**（`| 列 | 对齐 |`），禁止文字对齐或伪表格
- **禁止字段列表/项目符号降级**：不能输出 `①`、`②`、`• 源:`、`BREVUSDT\n• 现价:` 这类 Telegram 列表；每个候选必须是一行 Markdown 表格
- 禁止大段分析段落，所有信息打包进表格
- 时间格式：`2026年7月1日09：02`（中文，全角冒号）
- **no_agent 脚本**和 **LLM cron** 输出相同表格结构，两头对齐
- LLM cron 若曾把表格改成 bullet，必须在 prompt 内加入“必须包含 `|` 管道符和 `|:--|` 分隔行”的硬约束，并给出完整 Markdown 表格模板；参考 `references/telegram-table-hardening.md`

### 语言风格

- 尽量中文，只保留通用英文缩写：API、OI、PID、cron
- 不使用 `══════════`、`━━━` 等装饰性分隔符
- emoji 符号规范见 `references/report-format.md`

### 报告结构（no_agent 脚本输出）

`build_report()` 函数输出 3 张表。Telegram RichMarkdown 要求表格直接从管道表开始，不能在表格前紧贴 `表1 · xxx` 标题行：

| 层 | 源 | 状态 |
|:--|:--|:--:|
| ① | Orion Binance | ✅ N 候选 |
| ② | Hyperliquid | ✅/❌ |
| ③ | Binance REST | ✅/⏳ |
| ④ | CoinGecko | ✅/❌ |

| # | 品种 | 现价/OI/信号 |
|:--:|:----|:-------------|
| 1 | BTC | 价/OI/费率/置信压缩到本列 |

| 品种 | 判断 | 动作 |
|:----|:----|:----|
| BTC | OI+价+费率+Taker综合 | 追/等/禁 |

详情和列值规则见 `references/report-format.md`。

### 报告结构（LLM cron — ca1678011963）

LLM cron 也必须压缩为同样 3 张表，不再追加表4/表5。x_search 验证写入第二张表的“证据/信号”列，操作建议写入第三张表的“动作”列。

**陷阱：** 不要在表格后再加"详细分析"段落——这是用户明确反对的格式。所有信息已经打包在表格里。

## 候选筛选管线（从 118 候选中提取有效信号）

Orion 雷达通常产出 100-120 候选，但绝大部分（~95%）的 OI 变化 <3% 且置信度 <4。手动分析时使用以下快速筛选管线：

### 硬过滤条件

| 条件 | 阈值 | 通过率（典型） | 说明 |
|------|:----:|:-------------:|------|
| OI 最小值 | ≥ $500K | ~80% | 基本流动性过滤 |
| OI 变化绝对值 | ≥ 3% | ~5-8% | 排除噪声级波动 |
| 24h 涨跌幅 | ≥ 5% | ~3-5% | 仅保留有意义的价格变动 |
| 置信度 | ≥ 4.0 | ~20% | 至少有一次外部确认 |

### 三层精选流程

```
第1层（快速过滤）：OI≥$500K + |OI%|≥3 → 58→6候选
第2层（质量过滤）：+ 24h%≥5 + 置信度≥4 → 保留3-5候选
第3层（深度交叉）：+ BTC方向校验 + 判断逻辑匹配 + 资金费率极端度
```

### 数据读取方式

`orion_radar.json` 通常约 30KB，`read_file` 工具默认 500 行限制可能截断文件。**使用 Python 直接解析**：

```python
import json
with open("data/orion_radar.json", "r") as f:
    data = json.load(f)
# data["candidates"] 是完整列表，data["ts"] 是时间戳
```

## BTC 方向交叉验证

候选品种的信号强度与 BTC 市场背景直接相关。从 `data/source_snapshot_BTCUSDT.json` 获取 BTC 核心指标：

| 场最 | BTC 状态 | 对山寨信号的影响 |
|:----|:---------|:----------------|
| BTC 趋势明确（|24h%|>2%） | 山寨异动需要确认是否跟随 BTC — 跟涨的信号弱，逆势的强 |
| BTC 横盘（|24h%|<1%） | 山寨异动=独立叙事驱动，信号质量更高 |
| BTC Taker 卖方主导 | 山寨多头需警惕联动抛压 |

**检查方法**：比较 BTC 24h% 与候选 24h%。差异 >5% = 独立叙事 → 信号强度更高。

## 验证链降级处理（实战 2026-06-30）

四层验证链在 cron 环境中可能部分失效，需要识别并标注：

| 层 | 失效模式 | 表现 | 处理 |
|---|---------|------|------|
| ② HL 确认 | Hyperliquid 无对应品种 | 全部候选 `exchange: "Binance"` | 置信度评分退回「仅单源」，标注❌ |
| ③ Binance API | 单品种无 binance 嵌套块 | 部分候选只有 OI/价格数据 | 标记为「只过了一层 Orion」 |
| ④ CoinGecko | 未配置 API key | cron 日志无 CG 调用 | 标注「CG 未配置·跳过」 |

**关键规则**：当 HL 和 CG 层都不可用时，置信度评分 1-10 仍然保留但含义变更：
- 7-10：无 HL 确认时自动降为 4-6 等效（仅 Binance API 深度验证过关）
- 声明输出中标明「验证链未完整执行·仅基于 Binance 双源」

## 实测校验清单

- 手工修改 `build_report()` 后必须运行 `python scripts/orion_screener_radar.py`，不要只看diff。
- 输出必须恰好 3 张 no_agent Markdown 表；Telegram RichMarkdown 下不要输出 standalone `表1 · xxx` 标题行。
- 校验项：`table_blocks == 3`、无 `BJT`、无 `数据: Orion` 等表后尾注、CoinGecko失败时显示 `❌ 0确认` 而不是“已执行”。
- Windows Python 不支持 `strftime("%-m")`；中文时间用 `f"{NOW.year}年{NOW.month}月{NOW.day}日{NOW.hour:02d}：{NOW.minute:02d}"`。

## 陷阱

- **Orion API 参数强制**：必须显式传 `?exchange=binance`，不带参数返回空 → exit 1
- **Cron 代理环境差异**：cron 子进程可能不继承父进程的 `HTTPS_PROXY`，导致 Orion API 直连失败 → 脚本内置双策略回退（代理优先→直连）
- **HL 验证层常返回空（2026-06-30 实战）**：Hyperliquid 多数永续合约与 Binance 品种符号不匹配（无跨所对应品种），`exchange` 字段永远显示 `Binance`。这是数据覆盖问题，不是脚本故障。分析时需主动标注「无 HL 确认，置信度降级」。
- **CoinGecko 第 4 层可能未配置**：cron 环境可能没设 `CG_API_KEY`，导致 CG 层静默跳过。输出 `data/orion_radar.json` 中无 CG 字段 = 第 4 层未执行。分析报告首行「验证链状态」必须如实标注✅/❌每层。
- **Emoji 编码乱码**：cron stdout 存储层编码与 UTF-8 不兼容，⚠️📡🟢 等 emoji 会变成 `鈿狅笍`。错误信息用纯 ASCII
- **Binance API HMAC 签名**：第 3 层深度验证需要 `BINANCE_API_KEY` + `BINANCE_SECRET_KEY` 环境变量。Hermes 自动注入到 no_agent 脚本，但手工测试时需手动 export
- **小市值候选流动性陷阱**：OI<$2M + 24h量<$1M 的品种即使信号完美，实际滑点也可能吃掉利润。分析报告中必须包含 OI 和 24h 量，标注「小市值·高滑点风险」。
