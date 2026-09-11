# 交易系统多源降级与 TV MCP 稳健性模式

## 1. Binance公共数据统一入口

不要让业务脚本各自硬编码 `api.binance.com` / `fapi.binance.com`。建立统一公共数据模块并集中处理：

- 现货价格、K线、深度、aggTrades：主域失败后切官方 market-data-only 域 `data-api.binance.vision`。
- 主机失败后设置短期熔断（如300秒），避免每个周期、每个模块重复等待TLS超时。
- Provider流量直连，不继承本机代理；失败信息必须显式落到质量字段。
- Futures专属OI/Funding不可错误切到Spot端点。直连失败时可用可信聚合源（如Orion的Binance feed）降级，但必须标来源和B级质量，不能冒充Binance直连A级。
- LSR/Taker等降级源没有的字段保持缺失，交由HALDRO或FinalVerdict处理，禁止补默认中性值伪装健康。

验证：统一入口单测必须覆盖主域失败→Vision成功、衍生品回退的来源/质量、熔断后不重复请求。

## 2. 清算/OI诚实性

- 清算压力脚本应区分“有效且常态”与“数据全失败”。
- Orion类快照若含 `openInterest`、`tf1h.oiChange`、`tf1h.changePercent`，可直接生成OI×价格四象限；不要再用陈旧本地快照反推实时变化。
- 所有源失败：输出“不能判断”，写质量失败状态；不得输出“无爆仓/市场常态”。
- 新鲜度看门狗同时检查mtime与内容质量；调度每2小时的文件阈值应略大于2小时，避免任务间隙假告警。

## 3. XAU现场链

- 非加密HALDRO显示“不适用”，Valid Code=0，不参与冲突。
- Binance不存在/不可用的XAU K线不能导致VWAP/EMA引擎直接跳过；优先从品种独立 `tv_live_XAUUSD.json` 的Data Window读取 `s_vwap`、`ema_9`、`ema_55`、MCP CVD。
- TV格式数值可能含逗号、Unicode负号、窄不换行空格和K/M/B后缀；统一数值化后再参与判断。
- XAU TV同步成功后按时间门刷新多源 `source_snapshot_XAUUSD.json`；失败则保留短期旧缓存，否则写 `stale=true`，cron保持可诊断而不是伪新鲜。

## 4. TV MCP稳健性

- 多Monaco：按DOM可见尺寸、连接状态和焦点选择活动编辑器，禁止固定 `getEditors()[0]`。
- 中文界面：Pine动作按钮同时识别text/title/aria-label及中文“添加到图表/图表更新/保存并添加到图表”。
- Node直连`pine-facade`失败时，在已登录TradingView Desktop页面上下文调用`translate_light`；源码用URI编码安全注入，返回HTTP状态、errors2、warnings2。
- 当前底栏API可能没有`hideWidget()`；关闭面板依次兼容`hideWidget`→`toggleWidget`→`close`。
- E2E操作同一TV实例时用单并发，避免多个测试文件同时切品种、周期和面板。
- Replay测试分开验证“工具栏可用”和“服务端回放真正started”；不能把工具栏打开等同于回放已启动。

## 5. 完成验证

1. Python全量pytest。
2. TV MCP全量npm测试（含E2E、Pine编译、中文按钮、多Monaco）。
3. BTC/XAU分别写品种独立TV缓存并实跑auto_card。
4. 复查cron最近状态、两类守护心跳、数据新鲜度与内容质量。
5. 修改共享底层模块后，逐个复跑依赖cron，不只手动运行脚本。
