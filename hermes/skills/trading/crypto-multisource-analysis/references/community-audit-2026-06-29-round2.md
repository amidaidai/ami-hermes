# 第二轮深度社区审计 (2026-06-29)

审计源：Reddit r/algotrading、GitHub Vibe-Trading(14.7k★)/Arbitra/Freqtrade MCP、TradingView Pine v6、X Vibe Trading趋势、知乎五层架构

## 五大核心发现

### 1. Vibe-Trading 对标 (14.7k★ 社区标杆)

| 能力 | Vibe-Trading | 我们 |
|------|:--:|:--:|
| 数据源数量 | 18源+IP-ban回退链 | 17源·单源无回退 |
| 预置Alpha因子 | **456个** (QLib/Kakushadze/GTJA/学术) | **0个** |
| Shadow Account | 从交易日记提取策略自动回测 | 52行trade_journal未用 |
| Hypothesis Registry | 假设注册+证据+回测+生命周期 | 无 |
| Research Autopilot | 假设→信号→回测端到端 | 无 |
| Cross-session Memory | 自改进agent | Hermes memory无agent自改进 |
| Multi-agent Swarm | 29 swarm presets | 单体agent |

**鸿沟**：因子库0 vs 456，研究闭环无。

### 2. Pine Script v6 升级紧迫性 (2024年11月发布·已18个月)

SVP v10仍用v5。v6关键能力及对棠溪影响：

| v6能力 | 影响 |
|------|------|
| 动态request（循环内调request.security） | 单指标多品种扫描·不再计数限制 |
| 无限作用域深度 | 不再有550 scopes硬限 |
| 枚举类型 | 设置面板下拉菜单·类型安全 |
| runtime日志(log.info/warn/error) | 调试不占plot·Pine Logs面板 |
| 活跃输入(active参数) | 条件化设置面板·灰显 |
| 折线图对象 | 替代数十个line对象 |

**v5→v6迁移预期收益**：
- TV数据配额降低50%+（动态request替代静态多request.security调用）
- 副指标HALDRO聚合量突破27/40限制（无限作用域）
- OI×价背离检测无需独立请求（零配额纯逻辑）

### 3. 知乎五层架构对标 (2026行业报告)

| 层级 | 定义 | 棠溪 | 评分 |
|------|------|:--:|:--:|
| 数据层 | 行情/基本面/另类数据 | ✅ 17源 | 4.5 |
| 信号层 | 因子构建/特征工程 | ⚠️ 仅SVP单一信号 | 2 |
| 策略层 | 组合优化/仓位管理 | ⚠️ risk_constitution未接线 | 2.5 |
| 执行层 | 订单路由/冲击成本 | ❌ trading_system孤立 | 1.5 |
| 风控层 | 熔断/限制/监控 | ⚠️ watchdog缺熔断 | 2 |

最大鸿沟：信号层（需多因子融合）和策略层（需接线risk_constitution）。

### 4. 警报治理对标

社区共识"alert fatigue"是专业系统头号杀手。17 cron全部定时推送无去重。需：
- 状态机去重（内容hash相同→跳过）
- P0/P1分级（爆仓/大OI异动=P0，常规更新=P1）
- "首次异动"标记（静默期后首次信号突出显示）
- 条件不变静默模式（btc_daemon已有雏形·可推广）

### 5. 代理回退模式（已实战验证）

cron环境与直接环境的代理配置不同，导致Binance API在cron中SSL握手超时。**双策略回退**(proxy → direct)已在Orion和清算采集中验证有效：

```python
def _fetch(url, timeout=10):
    """代理回退HTTP GET — cron与直接环境通用"""
    for proxy_handler in [None, {}]:  # proxy → direct
        try:
            if proxy_handler:
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler(proxy_handler))
            else:
                opener = urllib.request.build_opener()
            req = urllib.request.Request(url, headers={"User-Agent": "H/1"})
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception:
            continue
    return None
```

所有面向cron的no_agent脚本的HTTP请求必须使用此模式。

## 优先级矩阵

| P | 条目 | 工作量 | 效果 |
|:--:|------|:--:|------|
| P0 | SVP v10 升Pine v6 | 重写指标 | TV配额降+功能升 |
| P1 | QLib因子库接入(30因子) | 2h | 量化深度跳级 |
| P1 | 警报去重逻辑全局注入 | 2h | 防刷屏疲劳 |
| P1 | 分析历史胜率注入auto_card | 1h | 信号可验证 |
| P2 | 数据源IP-ban回退链 | 2h | 防静默失败 |
| P2 | 五层架构执行层接线 | 3h | 端到端闭环 |
| P3 | Hypothesis Registry | 3h | 研究可追溯 |
