# 已评估平台档案

每个平台一节：定位 / 实测对账 / 能补的空白 / 门卡 / 风险 / 结论。新平台按末尾模板追加，**不要为单个平台另建文件**。

> 门卡一节只写**实测过的**结论：密钥有没有权限、接口有没有被加密/签名锁住、分享链接要不要登录态。没实测到的写「未验证」。

## OpenMarket（openmarket.xyz，原 kiyotaka.ai）

- **定位**：专业级加密订单流终端，中文原生界面；聚合 6 家场所（Binance.f / OKX / Bybit / Deribit / Hyperliquid / Polymarket）。卖点 = 聚合订单簿热图（单一/聚合可切、含 HL 清算与 TP/SL 图层）、Footprint、TPO/Market Profile、分交易所 CVD、清算热图、Deribit 期权 12 指标（GEX profile/heatmap/curve、max pain、call/put wall、gamma flip、IV smile、期限结构、vol matrix、implied move、options flow）、kScript 指标语言 + IDE、K 线回放、多图工作台（16 图）。变现 = PLUS 订阅 + 推荐制（kScreener Tier 1-5 递增标的数/刷新频率/列数；Tier 2 解锁 1 秒 K 线与 4K 热图）。
- **实测对账（BTCUSDT 永续 vs Binance fapi）**：最新价差约 10 美元（快照延迟）；OI 美元值完全一致（openInterest × markPrice）；资金费率一致（换算小数位后）；24h 最低价一分不差；24h 最高价偏高（滚动窗内早期极值未滚出）；24h 成交额偏差约 1.3%。**结论：单交易所口径准确，可当证据。**
- **能补的空白**：① 分交易所 / 聚合订单簿热图与 CVD（我们只有 TV 副图 + Binance 单所 CVD）② 期权 GEX / IV 整层（我们完全空白）③ 清算与 TP/SL 挂单热图 ④ 官方聚合数据 API。
- **门卡（决定结论的那条）**：官方 FAQ 明确「Data API not open to new subscriptions right now」—— 老订阅继续可用，新订阅关闭。现阶段**接不进管线，只能人眼看图**。已记档的数据类型：`TRADE_AGG`（分买卖方向 K 线）、`TRADE_SIDE_AGNOSTIC_AGG`、`OPEN_INTEREST_AGG`、`FUNDING_RATE_AGG`、`LIQUIDATION_AGG`、`VOLUME_PROFILE_AGG`、`TPO_AGG`、`BLOCK_BOOK_SNAPSHOT_AGG`、`HYPERLIQUID_LIQUIDATION_AGG`、`HYPERLIQUID_TRIGGER_LIQUIDITY_AGG`（Advanced+）、`IMPLIED_VOLATILITY_OPTION_SUMMARY_AGG`、`SKEW_OPTION_SUMMARY_AGG`。等它重开订阅再评估接入。
- **风险**：跑 kScript 不跑 Pine → SVP 主指标与执行授权搬不过去；执行端宣称跨所路由且「成交可撤销」，属第三方托管/代理语义，不用；无头浏览器只拿到移动外壳（容器 class `app-container--mobile`，图表 canvas 在视口外 `x=1920`），桌面工作台需真实浏览器。
- **结论**：注册免费号，当订单流 + 期权交叉验证的副战场；重点用分所 CVD 背离、清算簇、Deribit GEX 磁吸位；主战场仍是 TradingView + SVP；不接它的下单通道。

## CoinGlass / CoinGlass Legend（legend.coinglass.com）

- **定位**：加密衍生品/期权/链上聚合数据平台。Legend 是它的高阶看盘产品（流动性热力图、Footprint 足迹、大单、盘口热力图），分享链接形如 `legend.coinglass.com/zh/chart/<id>`。
- **实测对账 / 门卡**：官方 API 在 `open-api-v3.coinglass.com`，**鉴权头是 `CG-API-KEY`**（误用 `coinglassSecret` 返回 `30001 API key missing`）。我们 `secrets/coinglass_api_key.txt` 能过鉴权，但 OI / 资金费率 / 多空比 / 恐慌贪婪等端点一律 `401 Upgrade plan`（免费档）；旧 `open-api.coinglass.com/public/v2/*` 已 500 下线。定价（实测页）：业余 $29/月 80+ 端点 · 初创 $79 130+ · 标准 $299 150+ 端点/300 次每分钟/商业使用 · 专业 $699 160+。逐笔 L2/L3、足迹图（90 天）、订单簿热力图、聚合 CVD 都在端点清单里，属高档。
- **能补的空白**：清算热力图（模型 1/2/3）、订单簿热力图、足迹图、聚合 CVD、大额挂单、Hyperliquid 鲸鱼仓位。
- **门卡（决定性）**：① Legend 分享链接是**登录墙** —— 未登录打开会跳到 `www.coinglass.com/zh/login?act=legend`；Legend 无独立公开定价页（`/plan`、`/pricing/legend` 均 404），权限只在账号后台可见。② 网页端数据接口可抓（`capi.coinglass.com/api/index/v2/liqHeatMap?merge=true&symbol=<EX>_<PAIR>&interval=5&limit=288&data=<签名 token>`），但响应 `data` 字段**加密**、token 一次性；把页面 token 拿到 Python 重放只回 `{"code":"0","success":true}` 空壳（去掉 token 回 `40001`）→ **纯脚本路径不通，只能浏览器内取**。③ 无头浏览器默认 UA 被 legend 边缘 nginx 直接 404，需伪装 UA（见 `browser-evidence-capture.md`）。
- **风险**：Legend 的增量主要是逐笔 footprint 与盘口热力图；我们现有栈（Binance 深度/OI/资金费率/爆仓 + TV 的 SVP/AggVol）已覆盖大部分流动性视角 → 属交叉验证增益，不是刚需。要变成常驻数据源得走标准档 $299/月。
- **结论**：能用，但先要凭据。首选「用户登录态 + 浏览器取数（全屏截图 + 读值）」——登录走 vault，不索取密码；现成可白嫖的只有普通 pro 页 `/pro/futures/LiquidationHeatMap` 的清算热力图，且需页面内解密，只当交叉验证源；只有在需要 footprint/CVD 常驻供数时才考虑付费接 API。

## Cryexc（cryexc.josedonato.com，原水印 cryexc.jasonchia.cc）

- **定位**：免费加密订单流终端，作者 José（OpenBB 全职工程师）的个人副项目，「as-is、永远免费、靠捐赠」；无账号。浏览器**直连交易所 ws**（资产清单实测含 binancef / bybit / bitget / okx / mexc / aster / coinbase / kraken / hyperliquid / lighter / blofin），wasm(ImGui) 渲染 + WebGL canvas，PWA。面板：Footprint、DOM ladder（逐档挂单 + 已成交量 + tape）、Trades tape（多所实时吃单，×N 折叠）、Orderbook（多所合成，Σ 聚合 chip）、Historical chart（含 TPO market profile）、Alerts（11 类：Price / Large trade / **Liquidation** / Volume spike / Delta spike / Finished auction / CVD divergence / Exhaustion print / Large wall / Absorption / Sticky wall / Price velocity，全部浏览器内评估）、TV 嵌入容器 + 财经日历 iframe + gtrends 容器、HL 地址追踪（/hl-addresses）与 hl-screener、/embed footprint 嵌入构建器、/tools、Watchlist、Flip。
- **实测对账**：默认视图 BTCUSDT 4H 现价 76,986（2026-09-15 18:23 BJT，状态栏 1m ago）vs Binance fapi mark 76,985.41（同日 18:24:56）→ 一致。**数据面本身是交易所公开流的直连，无独立口径**，对账意义有限；真正的加工只在 Full history 层（TapeSurf）。
- **能补的空白**：① 逐价位 footprint（每档 bid/ask 量、delta、POC、imbalance）② DOM ladder 逐档挂单 + 已成交量 + 实时 tape ③ 多所合成订单簿与分所 tape/CVD ④ 多所（含 Hyperliquid）实时强平 tape/气泡 + 清算热图层 —— wasm UI 字符串实测含 `heatmap liquidations`、`hl liquidations`、`has_liquidations`、`No recent liquidations`、`Count of short liquidations in candle. Market-wide.` ⑤ Hyperliquid 地址追踪/鲸鱼筛选 ⑥ TPO market profile。
- **门卡（决定性）**：无账号、无 API、无文档化接口。托管层端点 `hl-node.josedonato.com/public/{info,footprint,liquidations}?exchange=binancef&symbol=BTCUSDT&start_ms=…&end_ms=…&limit=…` 实测 **401 `missing or invalid bearer token`**（不带 Origin/Referer 同样 401，不是 CORS 问题）；token 不在 wasm 明文字符串里，`/api/tokens` 只是 CoinGecko 代币元数据 → **纯脚本路径不通，只能浏览器内看**；robots.txt 明写 `Disallow: /api/`。
- **风险**：个人副项目、无 SLA、随时改前端 / 停服；Full history 标 alpha 且**依赖 TapeSurf**；wasm 闭源（11.7 MB）；**有执行入口**——`window.cryexcWallet / cryexcHlSigner / cryexcLighterSigner / cryexcExtSigner`（Hyperliquid、Lighter、浏览器扩展签名）→ 属第三方钱包/下单语义，本用户只手动交易，**不碰**；无 Pine，SVP 主指标与执行授权搬不过去 → 最高只能当副战场。
- **结论**：当**免费人眼副战场**用（footprint + DOM ladder + 多所 tape + 强平图层），重点看分所吃单背离与清算簇位置；**不接管线、不碰钱包/下单通道、不逆向 hl-node token**。清算要进管线走 OKX 公共逐笔强平 API（已实测可用）+ Binance ws `!forceOrder@arr`；想看现成清算 feed/热图用 **TapeSurf**（tapesurf.com，免注册免费，5 所 Binance/Bybit/OKX/Bitfinex/HTX 实时清算流 + 清算热图 + 订单簿热图）—— 列为下一轮评估对象。

## TapeSurf（tapesurf.com）

- **定位**：加密订单流看板（order book / 聚合订单簿 / 订单簿热图 / Hyperliquid TP-SL 与清算热图 / Live Tape（成交+强平））。号称覆盖 13 家交易所（Binance、Binance Futures、Coinbase、Kraken、Bitfinex、OKX、Bybit、Hyperliquid、Aster、Lighter、HTX、Bitstamp、BitMEX、Deribit；营销页写「5 所清算流：Binance/Bybit/OKX/Bitfinex/HTX」）。
- **实测对账 / 门卡**：SEO 着陆页（`/coin/btc/liquidations`、`/coin/btc/liquidation-heatmap` 等）**免登录可读**，但页上只有营销与 FAQ，**无实时数字可对账**；实时 feed 在 `/app` 内（要注册）。
  - **Free 档**：$0 — “Major Spot Markets” + 1 board + 全指标 + 2,500 bar 历史 + 预定义主题；表中带 `*` 的项（Live Order Book / 聚合订单簿 / 订单簿热图 / HL TP-SL / HL 清算热图 / Live Tape）注为 “Limited to Major Spot Markets”，**衍生品全量明确列在 Pro**。
  - **Pro**：$25/月（年付 $299）— 10,000+ 市场、无限 board、Full Derivatives Access、**Hyperliquid TP-SL & Liquidations on every market**、全历史、自定义主题。
  - **Enterprise**：from $999 — 含 **API access**、专属服务器、定制交易所接入（即“接进管线”需付费档，且 Pro 名单里也列了 API access，未实测确认）。
- **能补的空白**：① Hyperliquid 清算与 TP/SL 图层 ② 多所合成订单簿 + 订单簿热图 ③ 多所 live tape ④（声称的）Bitfinex / HTX 逐笔强平 —— 后两项是我们尚未实测过的源。
- **风险**：它自标“5 所清算流”包含 **Bybit**，而我们 2026-09-15 实测 Bybit 的 REST 与 WS 清算主题均已下线（`handler not found`）→ 平台的能力描述存在口径偏差（也可能它自建采集到了别处），引用其清算覆盖时不得直接采信。API access 至少 Pro 档；无免费 API。
- **结论**：**不需要**。清算**规模口径**我们已有免费的 OKX 逐笔全量（比它的 Free 档更完整），堆积带已有 CoinGlass（免 key，仅 BTC）；它真正的增量（HL 清算/TP-SL、多所盘口热图）都压在 $25/月且要接管线还得上 Enterprise。
  —— 它自标的「5 所清算流」线索我们**已逐家验证**：Bitfinex WS `liq`/`liquidations` 均回 `10300 channel: unknown`；HTX `liquidation_orders` 代理下被 `1003` 断开、直连超时；Bybit REST 404 + WS 主题 `handler not found`；Hyperliquid 官方 `WsTrade` 无 liquidation 字段（全市场清算无公开流）。**即 5 家里四家的免费公开清算都拿不到**，它若真在跑，靠的是自有采集/付费基础设施，不能靠它的名单反推免费源存在。

## PERPDEXLIST（perpdexlist.com）

- **定位**：perp DEX/CEX 资金费率与价差扫描器 —— 46 场所、约 16.8 万个组合，`cycle_secs=30`，逐字段带 `age` 新鲜度。页面：交易所 / 套利机会（价格套利·资金费套利）/ 创建价差图表（BBO 历史 in-out）/ 开仓成本 / RWA 永续。**纯数据站、无下单通道**（加分：无托管与代理执行语义，故不适用「执行通道不碰」那条——它本来就没有）。作者 @cryppimagic；`/api/venues` 的 `url` 全带推荐码（`ref=`），另有免费套利群与自动推机会 bot。
- **实测对账**：Binance OPENAIUSDT 站点 1459.83 / 资金费 +0.0050%/8h / 24h 量 $19.0M vs fapi 现价 1458.3~1458.8、`lastFundingRate` 0.00005、`quoteVolume` $18.86M ✓；MEXC BONER 资金费 站点 0.000117 vs `contract.mexc.com` 0.000117（完全一致）✓；Gate.io BONER bid/ask 0.04069/0.04088 vs 官方 mark 0.04086 / last 0.04068 ✓。**单场所口径准确，可当证据。**
- **能补的空白**：① 46 场所资金费/价差全景（我们只有 Binance + TV 自选）② 24h/7d/30d **已实现**资金费（真实结算额，不是预测）③ 开仓成本模型（taker fee + $10k/$100k/$1M 订单簿滑点，24h 小时中位数）④ 任意两场所的双腿 BBO 价差图（in/out 分列）。
- **门卡（决定性）**：**免登录可直连 JSON，无需密钥** → 能进管线（白嫖级）。已实测端点：`/api/dashboard/opportunities-v2?mode=basis|funding&sort=<字段>&page=&per_page=&desc=&filters=long_vol:100000::;short_vol:100000::`、`/api/dashboard/markets-v2?asset=<币>`（全场所实时 bid/ask/rate/interval_h/volume_24h/open_interest + `age`）、`/api/execcost/live?asset=&sizes=10000,100000,1000000`、`/api/execcost/window?asset=&days=`、`/api/execcost/best?days=&size=&class=`、`/api/execcost/assets`、`/api/venues`（`/api/arbitrage/test/*` 被 robots.txt 屏蔽、`/dashboard/execution-cost` 无此路径）。注意直连需走本机代理。
- **风险（按严重度）**：① 默认按「开仓价差」排序 → 榜首是 RWA 同名不同工具（OPENAI 8.4% / SAP 16.1% / ISRG 13.4%，其 24h「实际」仅 +0.0002%）；站点 >10% 标 `suspect`（文案在俄文串里）、>20% 直接隐藏，8% 这一档不标。② 资金费榜榜首是年化快照（LSK 年化 +1,289%，该对 7d 实际 -6.4%、30d -5.0%）。③ 高收益腿集中在新 DEX（arcus / gains / phoenix / edgex / asterdex / risex / variational / pacifica…，OI $0.3M~$12M）= 收益即对手方风险溢价。④ 变现闭环：场所链接带推荐码 + 免费群「我分享自己的仓位」；营销「每天 20-30 个机会、1%/小时起」与实测不符（主流币现价差量级约 0.2~0.3%/天）。⑤ 价差列只用最优一档 bid/ask，**不计 size**（$100k 级深度只在开仓成本页给出）。
- **结论**：**当副战场数据源用，只读进管线**。候选必须按「已实现资金费 + 现价差方向 + 成本回本天数」三重门槛自算，不照默认榜做单；不碰 RWA 同名对；不接任何执行通道（它也没有）。

## 模板（新平台照此追加）

- **定位**：
- **实测对账**：（项目 | 平台 | 官方）逐项写，末尾给一句结论
- **能补的空白**：
- **门卡**：
- **风险**：
- **结论**：
