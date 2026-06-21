#!/usr/bin/env python3
"""
每日学习引擎 v1.0 — 08:30 推送知识卡片
来源：10+ 社区最佳实践
内容：技能 · 交易技巧 · 系统进化

用法: python daily_learn.py [--push] [--dry-run]
  --push: 推送到Telegram
  --dry-run: 只打印不推送

cron: 0 8:30 * * *
"""

import sys, json, random
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent

# ═══════════════ 10+ 社区知识库 ═══════════════

KNOWLEDGE_BASE = {
    "技能": [
        # ICT / SMC
        {"title": "流动性扫荡识别",
         "desc": "价格刺穿前期低点后快速收回→Smart Money猎杀零售止损→入场时机在收线确认后·止损放在扫荡点后方0.5×ATR",
         "source": "ICT 2026·X社区"},
        {"title": "CVD背离检测",
         "desc": "价格创新高但CVD未创新高→买盘衰竭·价格创新低但CVD未创新低→卖盘衰竭·需价格到达关键位才计入",
         "source": "Bookmap·CryptoCred"},
        {"title": "Displacement确认",
         "desc": "扫荡后需出现Displacement（单根强势K线脱离扫荡区）才有资格入场·无Displacement=假突破·不追",
         "source": "ICT 2026·SMC社区"},
        {"title": "SMT背离",
         "desc": "BTC创新低但ETH未创新低→聪明钱陷阱·大饼山寨背离→反转信号·需Kill Zone时间窗口确认",
         "source": "ICT Silver Bullet·X社区"},
        {"title": "订单块(OB)交易",
         "desc": "价格突破结构后回调至原OB区域→OB作为支撑/阻力交换角色→入场在OB回踩确认后·止损在OB后方",
         "source": "ICT·SMC 2026"},

        # 风控
        {"title": "固定分数仓位",
         "desc": "每笔风险=账户×1%·连亏3笔缩至0.5%·连亏5笔暂停·余额涨了风险金额不跟着涨·这是防止复利膨胀的核心",
         "source": "Reddit r/algotrading·Freqtrade"},
        {"title": "Kelly仓位限制",
         "desc": "Kelly公式建议仓位=胜率-(1-胜率)/(盈亏比)·社区共识不超过Kelly的50%·极端行情不超过25%",
         "source": "NautilusTrader·量化社区"},
        {"title": "日回撤熔断",
         "desc": "日回撤>3%→停止开新仓·周回撤>6%→暂停所有交易·这是机构级风控底线",
         "source": "NautilusTrader·ESMA规范"},

        # 技术分析
        {"title": "VWAP标准偏差带",
         "desc": "+1σ是短多目标·-1σ是短空目标·+2σ是做空区域·-2σ是做多区域·均值回归<80%胜率·突破接受<30%胜率",
         "source": "TradingView Pine v6·社区精华"},
        {"title": "EMA排列判趋势",
         "desc": "EMA9>EMA21>EMA34>EMA55=强多头·反向=强空头·交叉交织=盘整·多头云+价在云上=顺势·价在云下=逆势",
         "source": "Freqtrade·社区策略库"},
    ],

    "交易技巧": [
        {"title": "分批止盈策略",
         "desc": "+1.5R出一半锁利润·剩余移止损至保本·+3R再出一半·尾部用趋势线追踪·永远不要让盈利变亏损",
         "source": "CrossTrade·Telegram信号社区"},
        {"title": "时间止损规则",
         "desc": "第4根15m未盈利→仓位减半·第6根未盈利→全平·不扛浮亏·时间成本是隐形成本",
         "source": "ICT·2026时间管理"},
        {"title": "周末仓位处理",
         "desc": "XAU周末不开仓（流动性枯竭·价差扩大）·BTC可持仓但减至50%·周五收盘前降低杠杆",
         "source": "ForexFactory·Reddit r/Forex"},
        {"title": "新闻事件避让",
         "desc": "FOMC/NFP/CPI前30分钟→减仓或平仓·数据后等15分钟收线确认方向再入场·不赌数据方向",
         "source": "ForexFactory·DailyFX"},
        {"title": "Kill Zone择时",
         "desc": "London Open(15:00-17:00 CST)·NY Open(20:00-22:00 CST)·Overlap(20:00-01:00 CST)是最佳交易窗口·Asia盘低波动慎做",
         "source": "ICT·SMC Kill Zone"},
    ],

    "系统进化": [
        {"title": "Pine Script v6新特性",
         "desc": "多行字符串·MTF功能升级·Footprint图表支持·可在一张图表显示8个周期的趋势方向·request.volume_delta()获取CVD",
         "source": "TradingView Pine v6 Release 2026"},
        {"title": "Bookmap Order Flow",
         "desc": "CVD冰山检测→单方向碎单>65%+价格未动→大单被拆分隐藏·吸收检测→价未动但CVD单边猛推→反转前兆",
         "source": "Bookmap·Scott Pulcini"},
        {"title": "NautilusTrader风控架构",
         "desc": "预交易风控门→仓位检查→日回撤检查→熔断开关系列·Rust核心+Python边缘·生产级回测引擎",
         "source": "NautilusTrader·GitHub"},
        {"title": "Freqtrade 2026策略",
         "desc": "ATR止损·多时间框架确认·成交量确认·社区策略库>100个·回测优先·Hyperopt参数优化",
         "source": "Freqtrade·GitHub社区"},
        {"title": "Telegram信号频道格式",
         "desc": "每行≤38字符·4-6行紧凑·方向+入场+止损+止盈+RR四要素·手机适配·不冗余",
         "source": "Telegram交易信号社区"},
    ],
}

# 每日学习模板
DAILY_TEMPLATE = """📚 每日学习 · {date} · {weekday}

—— {category} ——
📌 {title}
{desc}
📎 来源：{source}

📊 今日系统状态
  监控：{monitor_status}
  测试：{test_status}
  健康：{health_score}/100
"""


def pick_daily_lesson():
    """选择今日学习内容。轮换三个类别。"""
    # 按日期轮换类别
    day_of_year = datetime.now(TZ).timetuple().tm_yday
    categories = ["技能", "交易技巧", "系统进化"]
    cat = categories[day_of_year % 3]

    # 从该类别随机选一个
    items = KNOWLEDGE_BASE.get(cat, KNOWLEDGE_BASE["技能"])
    item = items[day_of_year % len(items)]  # 伪随机·按日轮换

    return cat, item


def get_system_status():
    """获取系统状态摘要。"""
    hb_file = ROOT / "data" / "monitor_heartbeat.json"
    health_file = ROOT / "data" / "system_health_score.json"

    monitor_status = "未运行"
    if hb_file.exists():
        try:
            hb = json.loads(hb_file.read_text(encoding="utf-8"))
            monitor_status = f"{hb.get('status','?')} · {hb.get('symbol','?')}"
        except:
            pass

    health_score = "?"
    if health_file.exists():
        try:
            hs = json.loads(health_file.read_text(encoding="utf-8"))
            health_score = str(hs.get("score", "?"))
        except:
            pass

    test_status = "?"
    import subprocess
    try:
        cp = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-q", "--tb=no"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=30,
        )
        test_status = cp.stdout.strip().split('\n')[-1][:30]
    except:
        pass

    return monitor_status, test_status, health_score


def build_daily_card() -> str:
    """构建每日学习卡片。"""
    now = datetime.now(TZ)
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    cat, item = pick_daily_lesson()
    ms, ts, hs = get_system_status()

    return DAILY_TEMPLATE.format(
        date=now.strftime("%Y-%m-%d"),
        weekday=weekdays[now.weekday()],
        category=cat,
        title=item["title"],
        desc=item["desc"],
        source=item["source"],
        monitor_status=ms,
        test_status=ts,
        health_score=hs,
    )


if __name__ == "__main__":
    card = build_daily_card()
    print(card)

    if "--push" in sys.argv:
        try:
            import subprocess
            # 发送到Telegram分析主频道
            target = "telegram:-1003733144325:416"
            cp = subprocess.run(
                ["hermes", "send-message", target, card],
                capture_output=True, text=True, timeout=15,
            )
            if cp.returncode == 0:
                print("✅ 已推送")
            else:
                print(f"❌ 推送失败: {cp.stderr[:200]}")
        except Exception as e:
            print(f"❌ 推送异常: {e}")
    elif "--dry-run" in sys.argv:
        print("📋 干跑模式（未推送）")
    else:
        print("📋 使用 --push 推送到Telegram · --dry-run 干跑测试")
