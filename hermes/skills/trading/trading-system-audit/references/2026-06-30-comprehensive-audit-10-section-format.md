# 棠溪综合审计10段报告格式 v1.0

> 2026-06-30 全量审计后沉淀。用于"全方位多维度检查"场景——整合运行态、数据、引擎、技能、多资产、社区对标、能力综合率的全景审计。

## 触发词

- "全方位多维度检查"
- "全面检查我的能力"
- "审计看看全部"
- 单次看全貌而非逐项排查时

## 10段式报告结构

### 1️⃣ 运行态健康（先验活）

| 检查项 | 状态 | 详情 |
|:---|:---:|:---|
| 行情守望守护 | ✅/❌ | 心跳时间+新鲜度 |
| BTC daemon守护 | ✅/❌ | 心跳时间+score |
| Cron 活跃数 | ✅/❌ N个ok | 全部active/有error |
| MCP服务器 | ✅/❌ N个配置 | 逐项列 |
| Git状态 | ✅/❌ | 干净/脏 |
| SOUL.md Persona | ✅/❌ | 关键词匹配 |

**检查命令**：
```bash
cat data/monitor_heartbeat.json | python -c "import sys,json; d=json.load(sys.stdin); print(f'status={d[\"status\"]} time={d[\"time\"][:19]}')"
cat data/.btc_daemon_heartbeat.json | python -c "import sys,json; d=json.load(sys.stdin); print(f'ts={d[\"ts\"][:19]} score={d[\"score\"]}')"
python -m hermes_cli.main cron list
git status --short --branch
grep -c "安禾\|棠溪\|交易" ~/AppData/Local/hermes/SOUL.md
```

### 2️⃣ 数据新鲜度（按严重度排序）

| 文件 | 过期时长 | 等级 | 影响 |
|:---|:---:|:---:|:---|
| `protections_state.json` | N天 | ❌ P0 | 风控失效 |
| `source_snapshot_BTCUSDT.json` | N分/时 | ❌ P0/P1 | 分析卡基座 |
| ... | ... | ... | ... |

**P0判定标准**：
- 风控文件（protections/strategy_governance）>24h = P0
- 快照文件（source_snapshot）>6h = P0
- 信号文件（btc_signal）>24h = P0
- 其他 >24h = P1

**检查命令**：
```bash
for f in data/source_snapshot_BTCUSDT.json data/protections_state.json data/strategy_governance.json data/btc_signal.json; do
  age_m=$(( ($(date +%s) - $(stat -c %Y "$f")) / 60 ))
  echo "$f: ${age_m}m old"
done
```
### 3️⃣ 复盘闭环

```
trade_plans.jsonl:  N 条
trade_reviews.jsonl: M 条
复盘率: X%
社区标准: ≥10%
```
- <10% = P1，闭环断裂
- 计算必须用 `trade_plans.jsonl`（真计划），不用 `trade_events.jsonl`（系统事件）

### 4️⃣ 隐藏引擎孤岛

**检查 scripts/ 下的引擎是否被实际管线调用**：

| 引擎 | 行数 | 功能 | 接线状态 |
|:---|:---:|:---|:---:|
| `trading_system.py` | 980 | 交易执行 | ❌ 未接 |

**检查方法**：
```python
# 查 auto_card 实际 import
grep -nE '^from |^import ' scripts/auto_card.py | sort -u
# 与 scripts/*.py 引擎清单比对
```

### 5️⃣ 孤儿脚本

已实现、功能完整、但 `auto_card` 未 import 的脚本：

| 脚本 | 行数 | 核心函数 | 接入价值 |
|:---|:---:|:---|:---|
| `meta_labeler.py` | 225 | `check_meta_label()` | 共振闸门 |
| ... | ... | ... | ... |

**6孤儿标准清单**：meta_labeler / orderflow_absorption / cvd_analyzer / fvg_detector / order_block / correlation_matrix

### 6️⃣ auto_card 架构评价

```python
auto_card.py: N 行
实际 import 本地模块数: M
引擎调用数: K/K_total
评价: 巨石/模块化
```

**管线完成度审计**：不要在渲染后的卡文本里搜关键词（太脆弱——render 输出未必含关键词）。

✅ 正确做法——用 `engine_data` 键值追踪：
```python
# 采集阶段注入 engine_data
engine_data["x_sentiment"] = _x_data    # X情绪有数据
engine_data["depth"] = {...}             # 深度有数据

# 审计阶段用 engine_data 判定
if engine_data.get("x_sentiment"): completed_steps.add("x_sent")
if engine_data.get("depth"): completed_steps.add("depth")
```

❌ 错误做法——卡文本关键词匹配（render 后可能不含目标词）：
```python
if "X情绪" in card: completed_steps.add("x_sent")
```
**特征**：
- 巨石=大部分逻辑自包含，不调用已有引擎
- 模块化=通过 pipeline_router 委托给各引擎

### 7️⃣ 多资产管线利用率

| 市场 | 步骤数 | 实际运用 | 缺失 |
|:---:|:---:|:---|:---|
| 🪙 加密 | 10步 | TV/Binance/Macro/X | CG Pro/深度墙 |
| 🥇 黄金 | 8步 | TV/Macro/X | COT/金十 |
| 💱 外汇 | 7步 | 模板定义 | **从未实战** |
| 📈 股票 | 8步 | 模板定义 | **从未实战** |
| 📊 期货 | 6步 | 模板定义 | **从未实战** |
| 📋 期权 | 3步 | 模板定义 | **从未实战** |

**铁律**：标记为"从未实战"表示该管线定义存在但从未在实际分析中验证过。

### 8️⃣ MCP利用度

| MCP服务器 | 工具数 | 利用率 | 备注 |
|:---|:---:|:---:|:---|
| ✅ TradingView | 78 | 高频 |  |
| ✅ Binance | 15 | 高频 |  |
| ⚠️ Stock-API | ? | **从未调用** | 股票分析从未实战 |

### 9️⃣ 社区对标差距

| 社区标准 | 棠溪现状 | 优先级 |
|:---|:---|---:|
| 盘前GO/NO-GO | ✅ 已实现 | — |
| 交易执行质量评分 | ❌ 缺失 | P1 |
| 复盘率≥10% | X% | P1 |
| ... | ... | ... |

### 🔟 能力综合运用率

```
┌─────────────────────────────────────────────┐
│                  综合运用率估值                │
├─────────────────────────────────────────────┤
│  ✅ 加密分析管线：            XX%            │
│  ⚠️  黄金分析管线：            XX%            │
│  ❌  外汇/股票/期货/期权：     XX%            │
│  ⚠️  隐藏引擎接线率：          XX%            │
│  ✅  Cron自动化：              XX%            │
│  ❌  数据新鲜度：              XX%            │
│  ❌  复盘闭环：                XX%            │
│  ✅  SOUL persona：            XX%            │
│  ⚠️  守护进程：                XX%            │
│  ✅  MCP配置：                 XX%            │
│  ⚠️  MCP利用：                 XX%            │
│  ⚠️  孤儿脚本：                 XX%            │
├─────────────────────────────────────────────┤
│  综合运用率估值：约 XX%                      │
│  核心差距：前3项                             │
└─────────────────────────────────────────────┘
```

**估算规则**：
- 100% = 该市场/维度完全可用、实战验证过、数据新鲜
- 50% = 代码存在但有空档（数据过期/未实战/未接线）
- 0% = 从未实现或从未调用
- 综合率 = 各维度平均值，不加权

## P0/P1/P2 修复优先级

| 等级 | 定义 | 典型修复 |
|:---:|:---|---:|
| P0 | 立即修复 | 数据过期/风控失效/进程崩溃 |
| P1 | 本周修复 | 孤儿脚本接入/复盘率/隐藏引擎 |
| P2 | 优化方向 | 多资产实战/Walk-Forward/技能精简 |

## 收尾铁律

- 每个 P0/P1 必须有可操作修复建议
- 不标注文档洁癖项为 P0/P1
- **审计发现 ⚠️ 必须先实测再下结论** — 详见 `references/audit-test-dont-assume.md`
- 审计收尾必须包含"你想先修哪些？"或直接给出优先级推荐
