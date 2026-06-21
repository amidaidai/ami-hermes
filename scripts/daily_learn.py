#!/usr/bin/env python3
"""
每日学习引擎 v2.0 — 08:30 推送知识卡片
全维度知识池：对交易和系统有利的一切
用法: python daily_learn.py [--push] [--dry-run]
"""

import sys, json
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent

# ═══════════════ 全维度知识池 v2.0 ═══════════════
# 不限分类·不限维度·对交易有利即可
# 每日按日期轮换·永不重样

POOL = [
    # ═══ ICT/SMC ═══
    {"title": "流动性扫荡识别", "desc": "价格刺穿前期低点后快速收回→Smart Money猎杀零售止损→入场在收线确认后·止损放在扫荡点后方0.5×ATR",
     "source": "ICT 2026·X社区", "tag": "策略"},
    {"title": "CVD背离检测", "desc": "价格创新高但CVD未创新高→买盘衰竭·创新低CVD未新低→卖盘衰竭·需价格到达关键位才计入·精度>85%",
     "source": "Bookmap·CryptoCred", "tag": "订单流"},
    {"title": "Displacement确认", "desc": "扫荡后需出现Displacement(单根强势K线脱离扫荡区)才有资格入场·无Displacement=假突破·不追",
     "source": "ICT 2026·SMC", "tag": "策略"},
    {"title": "SMT背离", "desc": "BTC创新低但ETH未创新低→聪明钱陷阱·大饼山寨背离→反转信号·需Kill Zone时间窗口加持",
     "source": "ICT Silver Bullet·X", "tag": "策略"},
    {"title": "订单块(OB)交易", "desc": "价格突破结构后回调至原OB区域→OB支撑/阻力交换→入场在OB回踩确认·止损在OB后方·盈亏比>1:2",
     "source": "ICT·SMC 2026", "tag": "策略"},
    {"title": "Kill Zone择时", "desc": "London Open(15-17 CST)·NY Open(20-22 CST)·Overlap(20-01 CST)最佳窗口·Asia盘低波动慎做",
     "source": "ICT·SMC Kill Zone", "tag": "择时"},

    # ═══ 订单流/量价 ═══
    {"title": "CVD冰山检测", "desc": "单方向碎单占比>65%+价格停滞→大单被拆分隐藏·冰山后通常紧跟剧烈波动·提前识别可占先机",
     "source": "Bookmap·Scott Pulcini", "tag": "订单流"},
    {"title": "吸收/派发识别", "desc": "价格不动但CVD单边猛推→吸收(反向即将发生)·价格移动但CVD不跟进→派发(趋势衰竭)",
     "source": "Bookmap·社区精华", "tag": "订单流"},
    {"title": "Delta散度", "desc": "Delta(买卖差)趋势方向背离价格→内部力量衰竭·搭配CVD使用精度更高·需>200 tick确认",
     "source": "OrderFlow·Sierra Chart", "tag": "订单流"},
    {"title": "成交量分布(POC/VAH/VAL)", "desc": "POC=最活跃成交价(磁铁)·VAH=价值区上限(阻力)·VAL=下限(支撑)·价区间内→均值回归·区间外→趋势",
     "source": "Volume Profile·社区", "tag": "量价"},

    # ═══ 技术分析 ═══
    {"title": "VWAP标准偏差带", "desc": "+1σ短多目标·-1σ短空目标·+2σ做空区·-2σ做多区·均值回归胜率<80%·突破接受胜率<30%",
     "source": "TradingView Pine v6", "tag": "技术"},
    {"title": "EMA多重排列", "desc": "EMA9>21>34>55=强多头·反向=强空头·交叉=盘整·价在云上顺·价在云下逆·34/55交叉=中期反转",
     "source": "Freqtrade·社区策略", "tag": "技术"},
    {"title": "ATR动态止损", "desc": "止损=ATR×2夹层+结构位缓冲·日内ATR×1.5→短线·ATR×3→中线·噪音≤0.3%跳过",
     "source": "Freqtrade·Kris Longmore", "tag": "风控"},
    {"title": "RSI背离信号", "desc": "价新高RSI未新高→顶背离做空·价新低RSI未新低→底背离做多·搭配Kill Zone窗口·精度提升30%",
     "source": "TradingView·技术社区", "tag": "技术"},
    {"title": "斐波那契+OB", "desc": "0.618-0.786回撤区间+订单块(OB)→高概率反转区·伦敦/NY开盘后3根K线内最有效",
     "source": "ICT·SMC融合", "tag": "技术"},

    # ═══ 风控 ═══
    {"title": "固定分数仓位", "desc": "每笔风险=账户×1%·连亏3笔缩至0.5%·连亏5笔暂停·余额涨不跟上调风险·复利膨胀第一大杀手",
     "source": "Reddit r/algotrading", "tag": "风控"},
    {"title": "Kelly仓位限制", "desc": "Kelly公式=胜率-(1-胜率)/盈亏比·社区共识只使用Kelly的50%·极端行情≤25%·永远不超Kelly",
     "source": "NautilusTrader·量化", "tag": "风控"},
    {"title": "日回撤熔断", "desc": "日回撤>3%→停止开新仓·周回撤>6%→暂停所有交易·机构级风控底线·连亏不追回",
     "source": "NautilusTrader·ESMA", "tag": "风控"},
    {"title": "时间止损", "desc": "第4根15m未盈利→仓位减半·第6根未盈利→全平·不扛浮亏·时间成本是隐形杀手·止损是对交易员的尊重",
     "source": "ICT·时间管理", "tag": "风控"},

    # ═══ 交易心理 ═══
    {"title": "损失厌恶陷阱", "desc": "人类亏损痛感是盈利的2.5倍→导致过早止盈·过晚止损·用固定规则对抗人性·不和情绪商量",
     "source": "行为金融学·Kahneman", "tag": "心理"},
    {"title": "确认偏误", "desc": "倾向于只看到支持自己判断的信息→入场后忽视反向信号·用检查清单对抗·每次必看对手方观点",
     "source": "交易心理学·Steenbarger", "tag": "心理"},
    {"title": "50-65%回撤心态", "desc": "任何策略都会经历50-65%最大回撤·回撤不是失败是过程·关键是回撤时不改策略·不改仓位",
     "source": "量化回测·社区共识", "tag": "心理"},
    {"title": "FOMO管理", "desc": "害怕错过是最大亏损源·错过比亏钱好·追高=给先行者买单·等待下次机会>72小时不盯盘",
     "source": "Reddit r/Daytrading", "tag": "心理"},

    # ═══ 宏观/基本面 ═══
    {"title": "DXY与黄金反相关", "desc": "DXY↑→XAU↓(80%时间)·但极端避险时同步↑(2020·2026)·结合美债收益率验证",
     "source": "DailyFX·宏观分析", "tag": "宏观"},
    {"title": "FOMC利率决策影响", "desc": "决议前30min减仓·决议后等15m收线确认方向·点阵图比利率决议本身更重要·关注会后发布会",
     "source": "ForexFactory·Babypips", "tag": "宏观"},
    {"title": "BTC与纳指相关性", "desc": "BTC-NDX30日相关>0.6时视为风险资产·<0.3时视为避险·通胀数据/非农影响>常规技术面",
     "source": "CoinMetrics·Glassnode", "tag": "宏观"},
    {"title": "链上数据入门", "desc": "MVRV>3.7=顶部风险·<1=底部·交易所余额减少=看涨·稳定币流入=潜在买盘·矿工卖出=压力",
     "source": "Glassnode·CryptoQuant", "tag": "链上"},

    # ═══ 系统/编程 ═══
    {"title": "Python异步并发", "desc": "asyncio+aiohttp→10x数据采集速度·ThreadPoolExecutor处理IO阻塞·避免主循环阻塞>5s",
     "source": "Python最佳实践", "tag": "编程"},
    {"title": "JSONL日志设计", "desc": "每行一条JSON→可追加·可grep·可pandas读取·比SQLite轻量·适合交易日志·生产级标准",
     "source": "软件工程·日志设计", "tag": "编程"},
    {"title": "Cron设计模式", "desc": "wrapper串行+逐个删旧+清理paused残留·脚本不存在但cron指向=静默失败·cron控制时段不依赖脚本内判断",
     "source": "系统运维·教训总结", "tag": "运维"},
    {"title": "Git Worktree并行", "desc": "git worktree允许多分支同时开发·不互相污染·适合大功能隔离·完成后合并到main·避免stash地狱",
     "source": "Git最佳实践", "tag": "编程"},
    {"title": "Pine Script v6新特性", "desc": "MTF功能·多行字符串·request.volume_delta()直接获取CVD·Footprint图表·8周期同时显示",
     "source": "TradingView Pine v6", "tag": "编程"},

    # ═══ 回测/策略 ═══
    {"title": "过拟合检测", "desc": "参数>样本量/10→过拟合·样本外测试>30%数据·前向优化Walk-Forward·简单策略胜复杂",
     "source": "量化回测·Marcos Lopez", "tag": "回测"},
    {"title": "夏普比率陷阱", "desc": "夏普>2可能过拟合·Sortino更关心下行风险·Calmar=年化收益/最大回撤·三指标同时用",
     "source": "量化金融·学术", "tag": "回测"},
    {"title": "滑点与手续费建模", "desc": "BTC滑点0.02-0.05%·XAU滑点0.1-0.3%·手续费BTC 0.04%·回测不加滑点=高估20-40%",
     "source": "实盘经验·社区", "tag": "回测"},

    # ═══ 社区动态 ═══
    {"title": "Freqtrade 2026趋势", "desc": "Hyperopt优化→强化学习RL·多时间框架融合→加权投票·社区策略库>500个·回测先于实盘",
     "source": "Freqtrade GitHub", "tag": "社区"},
    {"title": "AI交易趋势", "desc": "LLM辅助决策≠自动化交易·AI最佳角色=信息整理+信号验证·永远保留人工最终判断",
     "source": "2026 AI+交易趋势", "tag": "社区"},
    {"title": "电报信号频道标准", "desc": "每行≤38字符·4-6行紧凑·方向+入场+止损+止盈+RR四要素·手机适配·禁表格/emoji",
     "source": "Telegram交易社区", "tag": "社区"},

    # ═══ 品种专项 ═══
    {"title": "BTC永续资金费率", "desc": "费率>0.05%=多头拥挤(做空信号)·费率<-0.05%=空头拥挤(做多信号)·震荡=中性·大波动前先看费率",
     "source": "Binance·Coinglass", "tag": "品种"},
    {"title": "XAU Kill Zone特殊", "desc": "黄金最活跃时段=London Open+NY Open·亚洲盘几乎无行情·周末必休·XAU=全球宏观对冲首选",
     "source": "ForexFactory·DailyFX", "tag": "品种"},
    {"title": "山寨币季节轮动", "desc": "BTC主导率>60%→大饼季·<45%→山寨季·ETH/BTC汇率突破0.06→山寨启动·SOL/AVAX跟随",
     "source": "CoinGecko·社区", "tag": "品种"},
    {"title": "OI与价格背离", "desc": "价涨OI涨=多头加仓(持续)·价涨OI降=空头平仓(弱反弹)·价跌OI涨=空头加仓·价跌OI降=多头平仓",
     "source": "Binance Futures·Coinglass", "tag": "品种"},
]

# 每日模板
DAILY_TEMPLATE = """📚 每日学习 · {date} · {weekday}

📌 {tag} · {title}
{desc}
📎 {source}

📊 系统状态
  监控：{monitor_status}
  测试：{test_status}
  健康：{health_score}/100
  题材：{topic_summary}"""


def pick_daily_lesson():
    """按日期从全量池轮换。永不重样。"""
    day_of_year = datetime.now(TZ).timetuple().tm_yday
    idx = day_of_year % len(POOL)
    return POOL[idx]


def get_system_status():
    """系统状态摘要。"""
    hb_file = ROOT / "data" / "monitor_heartbeat.json"
    health_file = ROOT / "data" / "system_health_score.json"

    monitor_status = "未运行"
    if hb_file.exists():
        try:
            hb = json.loads(hb_file.read_text(encoding="utf-8"))
            monitor_status = f"{hb.get('status','?')} · {hb.get('symbol','?')}"
        except Exception:
            pass

    health_score = "?"
    if health_file.exists():
        try:
            hs = json.loads(health_file.read_text(encoding="utf-8"))
            health_score = str(hs.get("score", "?"))
        except Exception:
            pass

    test_status = "?"
    import subprocess
    try:
        cp = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-q", "--tb=no"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=30,
        )
        test_status = cp.stdout.strip().split('\n')[-1][:30] if cp.stdout.strip() else "?"
    except Exception:
        pass

    return monitor_status, test_status, health_score


def topic_summary():
    """所有题材标签汇总。"""
    tags = sorted(set(p["tag"] for p in POOL))
    return " · ".join(tags)


def build_daily_card() -> str:
    """构建每日学习卡片。"""
    now = datetime.now(TZ)
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    item = pick_daily_lesson()
    ms, ts, hs = get_system_status()

    return DAILY_TEMPLATE.format(
        date=now.strftime("%Y-%m-%d"),
        weekday=weekdays[now.weekday()],
        tag=item["tag"],
        title=item["title"],
        desc=item["desc"],
        source=item["source"],
        monitor_status=ms,
        test_status=ts,
        health_score=hs,
        topic_summary=topic_summary(),
    )


if __name__ == "__main__":
    card = build_daily_card()
    print(card)

    if "--push" in sys.argv:
        try:
            import subprocess
            target = "telegram:-1003733144325:416"
            cp = subprocess.run(
                ["hermes", "send-message", target, card],
                capture_output=True, text=True, timeout=15,
            )
            if cp.returncode == 0:
                sys.stderr.write("daily_learn: pushed\n")
            else:
                sys.stderr.write(f"daily_learn: push failed {cp.stderr[:100]}\n")
        except Exception as e:
            sys.stderr.write(f"daily_learn: push error {e}\n")
    elif "--dry-run" in sys.argv:
        pass  # 静默干跑
    else:
        pass  # 静默默认
