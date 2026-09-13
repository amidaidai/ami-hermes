---
name: skill-curation-tangxi
description: "棠溪交易系统的外部 Agent Skill 选型与安装方法论 — 从社区源(Hermes Hub/kukapay/TraderMonty/Binance官方)按系统画像匹配、安全扫描、装后验证。覆盖加密/黄金/外汇/股票/期货/期权六类，排除 DeFi/土狗/重复项。"
version: 1.0.0
author: 安禾 (棠溪)
tags: [skills, curation, install, trading-system, community]
---

# Skill Curation for 棠溪系统

当用户说「联网社区找适合我们系统的 skill」「看看社区有什么能用的」「推荐外部 skill」时，按本流程执行。目标：补系统缺口，不重复，不引入无关依赖。

## 系统画像（匹配基准）

- 多资产：加密(Binance U本位合约+现货) / 黄金(XAU，gold-api+金十) / 外汇 / 股票 / 期货 / 期权
- 指标：自研 SVP v10 + HALDRO 双指标（已有，不重复装同类）
- 基础设施：20个 hermes cron（no-agent 脚本直推），TV MCP 读图
- 风格：快进快出短线，数据驱动，多源交叉验证
- 缺口（截至 2026-07）：期权理论层(Greeks/波动率)、跨源情绪聚合

## 四源扫描优先级

1. **Hermes Skills Hub**（本地）：`hermes skills search <query>` — 先查已索引
2. **kukapay/crypto-skills**（GitHub，MIT）：DeFi/链上/情绪/策略生成
3. **TraderMonty/claude-trading-skills**（GitHub，667⭐，日更）：股票/期权/宏观/技术面，质量最高
4. **Binance 官方 Skills Hub**（13个，安全审查）：衍生品/支付/赚币/RWA，全部需 API key 鉴权

辅助发现：`find-skills` skill（加载它拿到 skills.sh / SkillsMP / Heurist Mesh / CryptoSkills 搜索入口）。

## 安装命令（已验证可用）

```bash
# 从 GitHub 直装单个 SKILL.md（hermes 支持 url 标识符 + 安全扫描）
hermes skills install "https://github.com/<owner>/<repo>/raw/main/skills/<name>/SKILL.md" --name <local-name> --yes

# 验证落地
hermes skills list | grep -i <local-name>
# 确认 python 依赖
python -c "import numpy, scipy"
```

安全扫描会自动跑：verdict SAFE → ALLOWED；MEDIUM（如 `pip install` 提示）→ 仍 ALLOWED 但需确认依赖已装。

## 匹配规则（装什么 / 不装什么）

**装**：补系统缺口且无重复。例：
- 期权理论层 → TraderMonty `options-strategy-advisor`（Black-Scholes + Greeks + 收益前波动率）
- 跨源情绪 → kukapay `market-sentiment`（RSS 聚合，评分 -1~+1）

**不装**（明确排除）：
- 与 SVP/HALDRO 重复的纯指标策略生成（kukapay trading-strategist）
- DeFi/土狗/发币（meme-scout / token-minter / yield-opportunities / evm-swiss-knife）—— 与币安合约现货定位无关
- 接非币安券商的下单 planner（TraderMonty VCP/breakout 接 Alpaca）—— 你不是美股券商账户

**需决策再装**（Binance 官方，需 API key + 开对应账户）：
- Derivatives Trading (Options) / COIN-M Futures / Portfolio Margin / Algo TWAP-POV
- 前提：用户开 Binance 期权账户并愿配 API key；当前交易执行走 `binance-trading` 社区 skill + 自研脚本

**已评估 → 不装**：
- `guangxiangdebizi/FinanceMCP`（750⭐，npm finance-mcp）—— 见 `references/financemcp-evaluation-2026-09.md`
- `Mathieu2301/TradingView-API`（4.5k⭐，npm @mathieuc/tradingview）—— 见 `references/tradingview-api-evaluation-2026-09.md`

## FinanceMCP 评估记录（2026-09-13 实测）

结论：**不装**。增量≈0，成本明确。

实测证据（脚本已归一至 `D:/Hermes agent/scripts/maintenance/`）：
1. `financemcp_tushare_probe.py` —— 用本机 `tushare_token.txt` 直打 23 个接口，**仅 7 个可用**：
   `daily` / `stk_mins` / `index_daily` / `cn_gdp` / `cn_cpi` / `shibor` / `shibor_lpr`。
2. 全部「系统缺口类」接口均**积分不足**：`moneyflow` / `moneyflow_hsgt`(北向) / `margin_detail` / `top_list`(龙虎榜)
   / `block_trade` / `cb_daily`(可转债) / `fund_nav` / `fina_indicator` / `hk_income` / `us_income` /
   `index_weight` / `index_dailybasic` / `fx_daily` / `fut_daily` / `us_daily` / `cn_m` / `cn_ppi` / `cn_pmi`。
3. `financemcp_stdio_probe.py` —— 无凭证时 tools/list 只给 4 个工具；**带本机 token 时给 17 个**
   （凭证存在即展示，不看积分等级）→ 装上后 17 个工具里 13 个是死工具，会污染工具选择。

重叠情况：crypto 走 Binance 公开接口（已有 binance MCP）、美股/宏观走 Tushare 但权限不足（已有
financekit/AV/TD/FMP）、新闻走百度/Twingly/Qveris（已有 jin10 + market-sentiment）。

唯一真实增量：**中国宏观序列**（cn_gdp / cn_cpi / shibor / shibor_lpr）—— 本系统 `macro_overview()`
是纯美国口径（SPX/VIX/10Y/DXY/Gold），没有任何中国宏观。但补这 4 个接口只需 ~30 行 Python 进
`multi_source_collector.py`，**不值得为此常驻一个 Node MCP**。

否决理由汇总：需 Tushare 2000/5000 积分才有缺口覆盖（当前免费档）；17 个工具 13 个死；
Qveris/Twingly 均需付费 key；引入后工具目录膨胀且模型易误选不通工具。

环境兼容性（已验）：Node v22.22.3 ≥ 20 ✓；npm registry 可达，`finance-mcp@4.11.2` 存在 ✓；
stdio 握手成功 ✓。所以「不能装」不是环境问题，是**数据权限 + 增量**问题。

## 装后动作

1. `hermes skills list` 确认 enabled
2. 确认 Python 依赖（numpy/scipy/requests 等）
3. 把 skill 用途 + 触发方式写进 memory 或本 skill references，避免重复搜索
4. 可选：用一次示例验证效果（如 options-strategy-advisor 算 BTC 某行权价 Greeks）

## 已验证可用清单（2026-07-07 实测）

| Skill | 源 | 状态 | 补全 |
|:---|:---|:---|:---|
| crypto-market-sentiment | kukapay | 已装 SAFE | X情绪 cron 多源升级 |
| options-strategy-advisor | TraderMonty | 已装 SAFE | 期权 Greeks/波动率理论层 |

详见 `references/financemcp-evaluation-2026-09.md`（本节即其摘要）。

## Pitfalls

- `hermes skills search` 本地 Hub 可能漏掉 GitHub 直装项 —— 装完用 `hermes skills list` 确认，不要只信 search 输出
- Binance 官方 skill 全需 API 鉴权，没开期权账户前不要装（装了也调不动）
- 不要装与已有双指标重复的「策略生成」类 skill —— 会污染分析管线
- hub-installed / bundled skill 受保护，不能 patch；要沉淀经验用本 umbrella 的 references/
