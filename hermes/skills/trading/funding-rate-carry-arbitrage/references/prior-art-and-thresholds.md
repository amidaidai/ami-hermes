# GitHub 先例与生产阈值（跨场所资金费 carry）

用途：写方案/订阈值前先抄这里的生产值，别自己拍；也用来说明「这条路有多拥挤、边际在哪」。

## 侦察方法

```bash
gh search repos "funding rate arbitrage" --limit 12 --sort stars --json fullName,stargazersCount,description,pushedAt
gh search repos "delta neutral funding" --limit 10 --sort stars --json ...
gh api "repos/<owner>/<repo>/readme" -H "Accept: application/vnd.github.raw" > readme.md
gh api "repos/<owner>/<repo>/git/trees/HEAD?recursive=1" --jq '.tree[].path'   # 找 docs/STRATEGY.md 这类
```

- 阈值通常不在 README 而在 `docs/STRATEGY.md` 或回测段 —— 先看仓库树再抓文件。
- 顺手查用户自己的星标（`gh api users/<u>/starred`）：若全是 agent/框架类，说明没有可复用的自有先例，别假设存在。
- 数据站大多**没有官方仓库/SDK**：搜不到仓库与作者账号是常态，它的接口只能靠自己实测（见 `external-market-platform-evaluation`）。

## 先例分档

| 仓库类型 | 代表 | 它真正在做什么 | 可用性 |
|---|---|---|---|
| 双腿机器人 + 策略文档 | `vooi-app/vooi-funding-bot-example`（Hyperliquid+Lighter，配套 `docs/STRATEGY.md`） | 整套生产阈值与风控（见下） | 最值钱，等于别人替你付了实盘学费 |
| skew 模型分析 | `50shadesofgwei/funding-rate-arbitrage`（Synthetix+CEX） | 资金费速度 `dr/dt = c×skew`、`c = maxFundingVelocity / skewScale`；回测发现 DEX 侧费率比 CEX 侧波动大 → DEX 当收益腿、CEX 当对冲腿 | 解释「自有下单推坏费率」与选腿方向 |
| 新 DEX 农场 | `djienne/CROSS_EXCHANGE_DELTA_NEUTRAL_*`、`djienne/ASTER_DELTA_NEUTRAL` | 48h 轮换刷量拿积分/空投，资金费是副产品 | 说明新场所真实收益来源 |
| 散户化全流程 | `kohtabeloff/funding-arb-bot`（Backpack/Lighter/Hyperliquid/GRVT/Aster，VPS+TG，$100 起） | 门槛已低到散户可跑 | 边际会被压薄的反证 |
| 扫描/分析库 | `supervik/funding-rate-arbitrage-scanner`、`aoki-h-jp/funding-rate-arbitrage` | CCXT 取费率、算 APY 历史均值与日内振幅 | 思路可参考，实现偏旧 |
| 低延迟基建 | `godzilla-foundation/godzilla-community` | C++ 执行核、中位 tick-to-trade ~125µs、要求 colocation | 散户不适用（反向证据） |

## 生产阈值（可抄）

- **摩擦**：每 $50 腿往返 5~7¢（≈10~14bp/腿）；50~100% APR 下每腿每小时只收 $0.001~0.0016 → **摩擦要 40~70 小时才回本**，且这期间 APR 必须一直为正。规模越大，摩擦占名义比越低、回本越快，可适当放宽候选池。
- **入场门槛**：最低净 APR 70%；要求 `apr_24h ≥ 0` 且 `apr_7d ≥ 0`（防「只有尖峰」），并限制 `apr_1h/apr_24h` 与 `apr_24h/apr_7d` 比值上限。
- **退出**：硬止损 = 两腿抵押额 × 5%（永远先于最小持有期触发）；最长持有 96h；最少持有 12h（更短的 4~6h 会在资金费回本前就砍掉）；连续 6 次读数 <10% APR 才平（已回本的仓位可豁免）。
- **腿级保护**：每腿止损设在强平价之前；跨腿 TP = 对手腿的 SL 价（一条腿冲强平时另一条腿在等价位止盈，用来买单）。
- **组合规则**：同一资产最多 1 对；同资产 48h 内连亏 2 次则冷却；按场所分别设保证金上限、余额须 ≥ 单腿抵押 × 1.1。
- **主亏模式**（照单防守）：① 价差在回本前衰减（主导）② 入场价差过宽且不回归 ③ 半腿事件（限价腿部分成交 + 市价腿全成）④ 场所/API 故障。

## 场外检查

- 新场所不是「年化更高」而是「风险更高」：收益里混着对手方风险与空投预期，按可归零的钱立项。
- 变现关系要写明：扫描站的场所跳转链接多为推荐码（`ref=<CODE>`），免费群「分享自己的仓位」是引流闭环 → 只作线索不作证据。
