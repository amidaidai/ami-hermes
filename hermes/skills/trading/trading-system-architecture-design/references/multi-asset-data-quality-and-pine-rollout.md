# 多资产数据质量与 Pine 上线验收

## 资产边界
- 加密：SVP 为结构主驾驶；AggVol/HALDRO 与 Binance Funding、Taker、OI、估算 CVD 仅可作确认、降级或否决。
- 黄金、外汇、股票、期货：不得采集、写入或渲染上述加密字段；使用各自的宏观、利率、板块、期权或库存验证源。
- `XAU`、`XAG`、`GOLD` 等必须由 ticker 字符串识别为贵金属，不能仅依赖 `syminfo.type`。

## TV 共享图表采集协议
1. 取得跨进程、可重入的采集锁；超时失败而非并发读取。
2. 切换 symbol/timeframe 后等待指标重算：主/副指标 15–30 秒。
3. 读取前校验图表实际 symbol/timeframe；读取完成后再校验一次。
4. 只有 `identity_valid=true`、行动格核心字段完整、时间戳新鲜、价格量级合理时才写入新缓存。
5. 失败时保留上一份同品种缓存，但标注 `stale_cache`；不得将当前图数据贴为目标品种。
6. 截图必须与同一次采集的 symbol/timeframe 一致；加密正式分析截图为 15m，黄金为 5m，且含价格轴与 CVD 窗格。

## 源级降级
- 所有免费/受限源应返回：`live`、`cache`、`stale_cache`、`unavailable` 或 `quota_cooldown`。
- 对 HTTP 429、额度耗尽或限频持久化 `blocked_until`，约15分钟内不再重复请求该源。
- `live/cache`可记为本轮完成；`stale_cache/unavailable/quota_cooldown`只能记为降级或缺失。
- 外部源失败不阻塞主流程，但数据质量闸门可将 FinalVerdict 降为 WAIT/NO-GO。

## Pine 增强与上线顺序
1. 先复制为日期化增强版，保持原版可回滚。
2. 添加机器可读的闭柱、等待原因、冲突、结构确认、执行有效性和数据质量字段；不要盲目增加重复交易信号。
3. 静态审计 request/plot 配额；保留免费账户余量，并保持 AggVol 五所成交量、四所 OI 覆盖。
4. 获取 TradingView 云端编译回执后，挂载测试图。
5. 逐层验收 D→4h→1h→15m→5m 的行动格、Data Window、Packed Bus、价格轴与 CVD。
6. 仅在现场字段与 Python 契约一致后，才替换生产版本；本地静态扫描不能代替云端编译。
