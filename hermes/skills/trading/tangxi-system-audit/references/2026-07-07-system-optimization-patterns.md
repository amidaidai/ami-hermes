# 2026-07-07 系统优化模式（cron合并 / XAU TV现场 / skill安装 / 工具限制）

本文件沉淀 2026-07-07「全方位优化」会话的可复用模式。会话从 20 个 cron + 占位XAU + v8命名误导 + BTC关键位偶发失败，收敛到 17 cron + TV真实XAU + 准确命名 + 降级完备。

---

## 一、cron 合并实战模式（20→17）

**可合并信号**（满足任一即合并）：
1. 同一份数据「采集 cron（local）」+「分析 cron（推TG）」拆两个 → 采集完直接渲染推TG，删独立分析 cron。
   - 实例：`Orion全市场雷达`(local) + `Orion雷达分析`(tg) → 在 `orion_screener_radar.py` 末尾 import 并调 `orion_radar_card.main()`，改 Orion全市场雷达 deliver=tg，删 Orion雷达分析。
2. 多个低频维护 cron 同窗口（6-7点）→ 聚合脚本顺序调各 `main()` 拼接输出，一次推TG。
   - 实例：`daily_ops_bundle.py` 调 skill_update_main + audit_main + backup_main + freerouter.main，删 4 旧 cron 建 1 聚合。

**不可合并（保留）**：
- 数据源不同：X情绪采集（X实时）vs X情绪LLM（FNG+CG综合）→ 功能不重叠。
- 监控对象/重启逻辑不同：3 看门狗（BTC守护120s / 行情守望300s / 数据新鲜度文件mtime）→ 合并风险高。
- 各自独立数据源、频率不同：Dune/COT/Deribit/清算/稳定币/QLib/宏观Poly/BTC关键位/交易执行桥接 → 无重叠。

**cron 操作命令铁律**（2026-07-07 实测）：
- 删除：`hermes cron delete <id>`（从 `C:/Users/Administrator/AppData/Local/hermes/cron/jobs.json` 读 id；`hermes cron list` 不输出 id，需 parse jobs.json）
- 创建：`hermes cron create "5 7 * * *" --name "X" --script repo-maintenance/daily_ops_bundle.py --no-agent --workdir "D:/Hermes agent" --deliver telegram:-1003733144325:846`
  - 注意 `--no-agent`（无值标志），不是 `--mode no-agent`（报错）
  - script 路径带子目录前缀 `repo-maintenance/` / `monitor/`，否则解析失败
- 改 deliver：`hermes cron edit <id> --deliver telegram:-1003733144325:846`

---

## 二、XAU TV MCP 现场读取模式（修正旧 Pitfall）

**旧 Pitfall 错误**：「SVP v10 在 OANDA:XAUUSD 不返回 Pine 数据，TV 只能作 BTC 专用」。
**实测修正**：`OANDA:XAUUSD` 的 `chart_get_state` + `data_get_ohlcv` **能返回真实 OHLCV**（TV MCP 走 CDP 到 TV Desktop，不依赖 SVP 的加密字段）。所以 XAU 五层结构可以 TV 现场读，不必只用 gold-api 占位推算。

**落地模式**（`scripts/xau_tv_sync.py`）：
```python
from mcp.client.stdio import stdio_client, StdioServerParameters
from fetch_tv_mcp import call_tool, set_symbol, set_timeframe, get_chart_state, get_ohlcv, parse_result
server_params = StdioServerParameters(command="node", args=[str(ROOT/"tools/tradingview-mcp/src/server.js")])
async with stdio_client(server_params) as (read, write):
    from mcp import ClientSession
    async with ClientSession(read, write) as session:
        await session.initialize()
        await set_symbol(session, "OANDA:XAUUSD")
        for tf in ["5m","15m","1h","4h"]:
            await set_timeframe(session, tf); await asyncio.sleep(3)
            ov = parse_result(await get_ohlcv(session))
            # 从 OHLCV 文本提末尾 1000-5000 区间数字 → high/low/close/open
            OUT.write_text(json.dumps(result), encoding="utf-8")
```
- `auto_card.py` XAU 分支优先读 `data/xau_tv_state.json`（<30min 新鲜）→ 真实覆盖占位；无则占位但标 `⚠️非TV现场` + 状态降 B（conf-2）。
- TV 不可用时 `xau_tv_sync.py` 优雅退出（不写文件），auto_card 走占位降级。
- 可选：把 xau_tv_sync 接入 cron（每15min）让手动分析始终有真实五层。

**修正旧 Pitfall 措辞**：SVP v10 的 *行动格/Composite/CVD* 在 XAU 不可用（依赖加密Funding/OI），但 *基础 OHLCV 结构* 可通过 TV MCP 现场读取。审计 Step 5 对 XAU 不再「跳过 TV 校验」，改为「优先 TV 现场 OHLCV，缺失才 gold-api 兜底」。

---

## 三、社区 skill 联网发现 + 安装模式

**发现源**（按顺序）：
1. `hermes skills search <kw>` — 本地 Hub（25条起）
2. `web_search` "skills.sh trending crypto trading binance" / "Heurist Mesh TraderMonty" / "Binance Skills Hub 13 skills"
3. GitHub 直链：`kukapay/crypto-skills`、`tradermonty/claude-trading-skills`（667⭐ 活跃）
4. Binance 官方 Skills Hub（13个，安全审查，但全需 Binance API key 鉴权）

**安装**（Hermes 支持 GitHub URL 直装）：
```bash
hermes skills install "https://github.com/kukapay/crypto-skills/raw/main/skills/market-sentiment/SKILL.md" --name crypto-market-sentiment --yes
hermes skills install "https://github.com/tradermonty/claude-trading-skills/raw/main/skills/options-strategy-advisor/SKILL.md" --name options-strategy-advisor --yes
```
- security scan 判定 SAFE/MEDIUM 均可装（MEDIUM 仅提示依赖如 pip install numpy）
- 装后 `hermes skills list | grep <name>` 确认 enabled

**本会话装的两个（补全系统缺口）**：
- `crypto-market-sentiment`（kukapay）— 多源RSS情绪聚合(-1~+1)，增强X情绪cron
- `options-strategy-advisor`（TraderMonty）— Black-Scholes/Greeks/收益前波动率，补期权理论层

**不装**：Binance官方期权/COIN-M/组合保证金（需开期权账户+API key，用户明确暂不开）；kukapay trading-strategist（重复SVP）；meme-scout/token-minter/yield-opportunities（DeFi土狗，与定位无关）。

**清理 disabled skill 的限制**：`hermes skills uninstall <name>` 对 builtin/local 源报「not a hub-installed skill」，无法卸载且不占负担 → 不强制清理。重点改为「自研脚本 vs Hermes 内置 trading 套件整合」（options-trading-strategies / professional-finance-data / crypto-onchain-flow 已内置，可后续整合）。

---

## 四、BTC关键位 cron 偶发失败降级模式

**根因**：TV MCP/CDP 偶发断开 → `refresh_tv_cache()` 3次失败 raise → `pick_cache()` 过期 raise → exit 1（cron 报 error）。

**修复**（`scripts/btc_ref_levels_sync.py`）：
1. `refresh_tv_cache()` 失败不 raise，转 warning 继续（Binance 直取兜底）。
2. 新增 `_pick_cache_relaxed()`：TV 刷新失败时放宽 cache 年龄到 120min 兜底一次（不卡30min再 raise）。
3. catch 块保持原降级告警卡（exit 1 只发告警不空跑）。

**铁律**：cron 采集类任务不得因单一数据源（TV）偶断而 exit 1。必须有「次级源/Binance直取/放宽cache年龄」三级降级，保证关键位始终有输出。
