# 社区 Skill 获取与落地验证（2026-07-07）

棠溪系统能力过剩但存在「真缺口」（如期权 Greeks 理论层、多源情绪聚合）。从社区拉 skill 补全缺口的可复用流程。

## 搜索源（多源交叉）

- `hermes skills search <query>` — 本地 Hub（Skills Hub / ClawHub / skills.sh）
- `hermes skills list` — 看已装 + 来源(local/community/builtin) + enabled/disabled
- GitHub 直搜：`kukapay/crypto-skills`、`tradermonty/claude-trading-skills`（667⭐，活跃维护）
- Binance 官方 Skills Hub（13 个，安全审查）：Derivatives Options / COIN-M Futures / Portfolio Margin / Algo TWAP-POV — **全部需 Binance API key 鉴权**
- web_search：`skills.sh trending` / `Heurist Mesh` / `CryptoSkills` 找加密/金融类

## 安装（实测可用）

`hermes skills install` 支持 GitHub raw URL 指向 SKILL.md：

```bash
# kukapay 市场情绪（多源RSS聚合，-1~+1评分）
hermes skills install "https://github.com/kukapay/crypto-skills/raw/main/skills/market-sentiment/SKILL.md" --name crypto-market-sentiment --yes

# TraderMonty 期权顾问（Black-Scholes/Greeks/收益前波动率）
hermes skills install "https://github.com/tradermonty/claude-trading-skills/raw/main/skills/options-strategy-advisor/SKILL.md" --name options-strategy-advisor --yes
```

- CLI 自动跑 **security scan**，输出 Verdict（SAFE / MEDIUM / BLOCKED）。
- MEDIUM（如 `pip install numpy scipy requests`）≠ 阻断，看清提示即可。
- 仍可用：`hermes skills install <registry-id>`（Hub 源）。

## 落地验证（装完必须做）

1. 确认载入：`hermes skills list | grep <name>` → 状态 enabled。
2. 依赖检查：skill 要 numpy/scipy 等 → `python -c "import numpy, scipy"` 确认现成（棠溪环境 numpy 2.4.3 / scipy 1.17.1 已具备）。
3. 冒烟：直接调 skill 的脚本/函数跑一次最小用例（如 options-strategy-advisor 的 `black_scholes.py --stock-price 180 --strike 185`）。

## 匹配判定（棠溪画像）

| 缺口 | 推荐 skill | 卡点 |
|:---|:---|:---|
| 期权 Greeks/波动率理论 | TraderMonty options-strategy-advisor | 无（纯理论，不需实时数据） |
| 多源情绪聚合 | kukapay crypto-market-sentiment | 无 |
| 期权执行层/COIN-M/组合保证金 | Binance 官方 Derivatives/COIN-M/PortfolioMargin | 需 Binance API key + 开期权账户 |
| 回测/策略 | kukapay trading-strategist | 与 SVP v10 重复，不装 |

不装：DeFi/土狗类（meme-scout/token-minter/yield-opportunities/evm-swiss-knife）与棠溪「币安合约+现货+快进快出」定位无关。

## 装完建议写入 memory

新装 skill 的用途 + 触发场景，避免后续会话重复搜索。例：「options-strategy-advisor 算 BTC 行权价 Greeks 时用」。
