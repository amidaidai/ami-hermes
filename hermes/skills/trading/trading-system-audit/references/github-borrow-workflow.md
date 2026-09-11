# GitHub 借鉴工作流

如何搜到、评估、集成GitHub上的现成交易系统模块。

## 搜索策略

GitHub REST API > web_search（Firecrawl配额不可靠）

```bash
curl -s "https://api.github.com/search/repositories?q=<query>&sort=stars&per_page=5" \
  -H "Accept: application/vnd.github.v3+json" -H "User-Agent: TangXi"
```

API限流后用 `web_extract` 读README页面。

## 评估矩阵

| 维度 | 判断标准 |
|------|---------|
| 匹配度 | 功能重叠度·是否双品种(BTC+XAU)·是否SMC/ICT |
| 集成成本 | 依赖复杂度(Python only > 需要Docker > 需要DB) |
| 代码质量 | 行数·注释·测试·提交频率 |
| 许可 | MIT/Apache2优先·GPL需谨慎 |

## 已知可用源

| 仓库 | 可借用的 | 不适合的 |
|------|---------|---------|
| **aurumcrypto** (⭐1) | 回测成本模型(BTConfig·fee_bps·max_hold)·数据管道·ML pipeline | 整个项目太小（15 commits） |
| **BAKOME Gold Scalper** (⭐1) | 黄金时段过滤·Kill Zone·FVG/Order Block检测 | 合成数据·仅黄金 |
| **stunning-octo-robot** (⭐1) | 多模型集成架构图·特征工程清单 | Docker/postgres/redis太重 |
| **pybroker** (⭐3425) | 回测框架设计理念 | 通用框架·非加密专用 |

## 集成三原则

1. **不整个搬项目** — clone到sandbox，只拆需要的模块
2. **保持MIT协议** — 在源文件头部标注借鉴来源
3. **先跑测试后改代码** — 31 tests baseline，不能回退

## 借鉴记录

| 日期 | 从哪借 | 借了什么 | 集成到 |
|------|--------|---------|--------|
| 2026-06-18 | aurumcrypto | BTConfig·fee_bps·max_hold | backtest_runner.py v1.1 |
| 2026-06-18 | BAKOME | session_filter·Kill Zone | scripts/session_filter.py |
