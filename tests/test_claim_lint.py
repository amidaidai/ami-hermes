"""claim_lint 契约测试：把我 2026-09-15 实际犯的两类错钉成回归用例。

跑法：python -m pytest tests/test_claim_lint.py -q
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from claim_lint import lint  # noqa: E402

ASOF = date(2026, 9, 15)

# 实测错误 1：把「假期缩短周（周二+周三）」的数字挂到「昨日两日合计」
BAD_WINDOW = (
    "现货 ETF 昨日两日合计净流出 1.668 亿美元"
    "（周三 1.202 亿 + 周二 4660 万），来源 https://finance.biggo.com.tw/news/427bb673-0b26-450e-83ac-f08e16591480。\n"
)
# 实测错误 2：把 2026-08-31 的文章与 9/11 事件拼成无日期因果链
BAD_URLDATE = (
    "沃什放鹰，昨日 9 月加息概率从 35% 飙到 60%"
    "（来源 https://wap.eastmoney.com/a/202608313859578146.html），这是本次下跌的原因。\n"
)
# 合格写法：带具名来源 + 两个日期 + 窗口
GOOD_SOURCED = (
    "据 Reuters（发布 2026-09-14，原文 2026-09-11）：rate futures price about 85% chance of "
    "quarter-point hike at September 15-16 meeting（https://www.reuters.com/business/fed-seen-likely-raise-rates-next-week-after-inflation-report-2026-09-11/）。\n"
)
# 本地实拉数据（可核，不需要外部出处）
LOCAL_OK = "现价 78,021，OI 103501，费率 0.003862。\n"


def test_bad_window_mismatch_is_blocked():
    """实测错 1：URL 无日期 + 相对时间词 → 缺出处日期，必须拦。"""
    res = lint(BAD_WINDOW, local=[], asof=ASOF)
    assert res["violations"], "外部数字缺日期必须被拦"
    assert {v["num"] for v in res["violations"]} >= {"1.668亿", "1.202亿", "4660万"}
    assert all(v["verdict"] == "VIOLATION:no_source" for v in res["violations"])
    # URL 里的路径/ID 不得被当成数字
    assert not any(len(v["num"]) > 12 for v in res["violations"])


def test_missing_date_is_blocked():
    """实测错 2：URL 日期 2026-08-31（两周前）+「昨日」→ 时间窗错配，必须拦。"""
    res = lint(BAD_URLDATE, local=[], asof=ASOF)
    assert res["violations"], "陈旧 URL 日期 + 相对时间词必须被拦"
    assert any(v["verdict"] == "VIOLATION:window_mismatch" for v in res["violations"])
    assert any("2026-08-31" in (v.get("evidence") or "") for v in res["violations"])


def test_good_citation_passes():
    res = lint(GOOD_SOURCED, local=[], asof=ASOF)
    assert not res["violations"], f"合格引用被误杀：{res['violations']}"


def test_local_data_needs_no_external_source():
    res = lint(LOCAL_OK, local=[78021.0, 103501.0, 0.003862], asof=ASOF)
    assert not res["violations"], f"实拉数据被误杀：{res['violations']}"
    assert all(f["grade"] == "local" for f in res["findings"])


def test_url_date_parsing_handles_two_common_shapes():
    from claim_lint import url_date
    assert url_date("https://wap.eastmoney.com/a/202608313859578146.html") == date(2026, 8, 31)
    assert url_date("https://blockcast.it/2026/07/03/us-bitcoin-etfs-break-10-day-negative-streak/") == date(2026, 7, 3)
    assert url_date("https://www.reuters.com/business/x-2026-09-11/") is None  # 不猜，交给句子里的日期


def test_source_inherits_within_paragraph_but_not_across():
    """同段可继承上一句的出处/日期；换段必须重新给出处。"""
    same_para = ("据 Reuters（发布 2026-09-14）：概率 85%。\n上周合计净流出 4.63 亿美元。\n")
    r1 = lint(same_para, local=[], asof=ASOF)
    assert not r1["violations"], f"同段继承被误杀：{r1['violations']}"
    assert any(f.get("inherited") for f in r1["findings"] if f["grade"] == "external")

    new_para = ("据 Reuters（发布 2026-09-14）：概率 85%。\n\n上周合计净流出 4.63 亿美元。\n")
    r2 = lint(new_para, local=[], asof=ASOF)
    assert r2["violations"], "换段后缺出处必须被拦"


def test_fin_only_suppresses_line_refs_and_versions():
    """看门狗模式下：行号/版本号/倍率不得被当成外部数字断言（防误报刷屏）。"""
    audit = ("- model.default：deepseek-v4.1-flash（L2）\n"
             "- auxiliary.vision（L144–146）：provider = custom:b.ai\n"
             "- 工具调用 1.2–1.7s、reasoning 耗时 7.4 秒\n")
    noisy = lint(audit, local=[], asof=ASOF)
    quiet = lint(audit, local=[], asof=ASOF, fin_only=True)
    assert len(noisy["violations"]) >= 3, "全量模式本就该报"
    assert not quiet["violations"], f"看门狗模式仍有误报：{quiet['violations']}"


def test_fin_only_keeps_real_claims():
    """看门狗模式必须仍然抓得住真正的金融断言。"""
    txt = "现货 ETF 两日合计净流出 1.668 亿美元，爆仓 3.8 亿，加息概率 85%。\n"
    res = lint(txt, local=[], asof=ASOF, fin_only=True)
    nums = {v["num"] for v in res["violations"]}
    assert {"1.668亿", "3.8亿", "85%"} <= nums, nums


def test_watchdog_relevance_filter():
    """行情归因类消息才检查；config 审计/代码评审不得进入闸门。"""
    from claim_watchdog import relevant
    assert relevant("BTC 隔夜冲高 79,600 后回落，因为美联储加息定价 85%。")
    assert not relevant("- model.default：deepseek-v4.1-flash（L2）\n- auxiliary.vision provider = custom:b.ai")
    assert not relevant("pytest tests/ -q 结果：1197 passed。")


def test_unit_aware_matching_no_mantissa_collision():
    """审计发现的真缺陷：1.668亿 曾被本地 1.668 吃掉（单位不参与比对）→ 必须仍被拦。"""
    txt = "比特币现货 ETF 两日合计净流出 1.668 亿美元，机构在撤。\n"
    res = lint(txt, local=[1.668, 1.67, 1668.0], asof=ASOF, fin_only=True, scope_only=True)
    assert any(v["num"] == "1.668亿" for v in res["violations"]), res["violations"]


def test_table_row_cannot_borrow_neighbour_citation():
    """审计发现：一行里的 Reuters/9-14 会让整表数字‘看起来有源’→ 表格行必须自带出处。"""
    tbl = ("| 项目 | 读数 | 来源 |\n"
           "|:--|:--|:--|\n"
           "| 加息定价 | Reuters 9/14：85% | ✓ |\n"
           "| 现货 ETF | 两日净流出 1.668 亿美元 | — |\n")
    res = lint(tbl, local=[], asof=ASOF, fin_only=True, scope_only=True)
    assert any(v["num"] == "1.668亿" for v in res["violations"]), res["violations"]


def test_scope_filter_leaves_card_numbers_alone():
    """卡面价位/百分比不是外部断言，不该被要求出处（实测误报率 90% 的根因）。"""
    card = "| 近端转撑 | 78,336 | -0.25% |\n| 主观察 | 77,747–77,757 | -0.99% |\n"
    res = lint(card, local=[], asof=ASOF, fin_only=True, scope_only=True)
    assert not res["violations"], f"卡面数字被误拦：{res['violations']}"
    assert all(f["verdict"] == "out_of_scope" for f in res["findings"] if f["grade"] == "external")


def test_short_date_with_named_source_counts():
    """具名来源 + M/D 简写日期算有效出处（Reuters 9/14）。"""
    txt = "| 加息定价 | Reuters 9/14 报 85% 概率 | ✓ |\n"
    res = lint(txt, local=[], asof=ASOF, fin_only=True, scope_only=True)
    assert not res["violations"], res["violations"]


# ---------- 看门狗：生命体征 + 静默失败防护（2026-09-15 审计 P1）----------

def test_watchdog_db_missing_is_not_silent(tmp_path, monkeypatch, capsys):
    """读不到 state.db 时必须出声（exit 2 + 心跳记 db_ok=false），不能看起来像“跑干净”。"""
    import claim_watchdog as cw
    monkeypatch.setattr(cw, "DB", tmp_path / "nope.db")
    monkeypatch.setattr(cw, "HEARTBEAT", tmp_path / "hb.json")
    monkeypatch.setattr(sys, "argv", ["claim_watchdog.py", "--hours", "1"])
    rc = cw.main()
    out = capsys.readouterr().out
    assert rc == 2, f"应返回 2，实际 {rc}"
    assert "无法运行" in out, out
    hb = json.loads((tmp_path / "hb.json").read_text(encoding="utf-8"))
    assert hb["db_ok"] is False and isinstance(hb["updated_epoch"], float)


def test_watchdog_heartbeat_written(tmp_path, monkeypatch):
    """成功跑完也要留生命体征，供 data_freshness_watchdog 判「闸门还在跑」。"""
    import claim_watchdog as cw
    monkeypatch.setattr(cw, "HEARTBEAT", tmp_path / "hb.json")
    cw._write_heartbeat(db_ok=True, checked=5, hits=1, hours=3)
    hb = json.loads((tmp_path / "hb.json").read_text(encoding="utf-8"))
    assert hb["db_ok"] is True and hb["checked"] == 5 and hb["hits"] == 1
    assert {"updated_epoch", "ts"} <= set(hb)


def test_single_source_causal_claim_is_weak_not_blocking():
    """幻觉形态：一条二手摘要撑整条因果链 → 默认只作弱提示，--strict 才拦。"""
    import claim_lint as cl
    txt = "据 Wu Blockchain（2026-09-12）报道，上周 ETF 净流出 4.63 亿美元。"
    soft = cl.lint(txt, [], ASOF, fin_only=True, scope_only=True)
    assert not soft["violations"]
    assert soft["warnings"], "单一来源应进 weak 档"
    assert soft["warnings"][0]["verdict"] == "weak_source"
    hard = cl.lint(txt, [], ASOF, fin_only=True, scope_only=True, strict=True)
    assert hard["violations"] and hard["violations"][0]["verdict"] == "VIOLATION:single_source"


def test_two_independent_sources_pass_cross_check():
    import claim_lint as cl
    txt = "据 Reuters 与 CoinGlass（2026-09-14）统计，24h 爆仓 2.14 亿美元。"
    r = cl.lint(txt, [], ASOF, fin_only=True, scope_only=True, strict=True)
    assert not r["violations"] and not r["warnings"]


def test_same_source_in_different_spellings_counts_once():
    """Reuters / 路透 / reuters.com 是一家：不能靠换个写法凑出「两个来源」。"""
    import claim_lint as cl
    assert cl.sources_in("据 Reuters（路透社）https://www.reuters.com/markets/x 报道") == {"reuters"}
    txt = "据 Reuters（路透社）2026-09-14 报道，ETF 净流出 1.668 亿美元。"
    r = cl.lint(txt, [], ASOF, fin_only=True, scope_only=True, strict=True)
    assert r["violations"], "同一家的三种写法不该通过交叉验证"


def test_assoc_unit_requires_exact_token_match():
    """亿/万 只能靠 token 精确命中判「可核」：数值容差在这两个量级上是撞车温床。

    构造：本地语料里有一个绝对量级相同的裸数值（1.668e8），但没有 "1.668亿" 这个 token。
    若容差路径对亿/万生效 → 会被误判为 local（无出处也放行）；有守卫 → 必须报无出处。
    """
    import claim_lint as cl
    txt = "单日净流出 1.668 亿美元。"
    r = cl.lint(txt, [1.668e8, 0.5], ASOF, fin_only=True, scope_only=True, local_tokens=set())
    assert r["violations"], "亿级数字必须 token 精确命中才算可核，不能靠数值容差放行"
    # 对照：真的 token 命中时必须放行
    txt2 = "单日净流出 1.668 亿美元。"
    r2 = cl.lint(txt2, [], ASOF, fin_only=True, scope_only=True, local_tokens={"1.668亿"})
    assert not r2["violations"]


def test_rounding_to_written_precision_counts_as_local():
    """写作舍入（0.134% → 0.13%）不算编造；但量级不同不能靠舍入蒙过去。"""
    import claim_lint as cl
    assert cl.rounds_match(0.13, 0.134, "0.13")
    assert cl.rounds_match(77742.6, 77742.63, "77742.6")
    assert not cl.rounds_match(1.668e8, 1.668, "1.668")
    assert not cl.rounds_match(0.13, 13.0, "0.13")
    # 端到端：现场核验行里写了 +0.13%（实拉 +0.134%）不该被判成外部无源
    txt = "现场核验：据 binance_deriv_bundle（2026-09-15 11:06 现场实拉）24h +0.13%，资金费率 0.0048%。"
    r = cl.lint(txt, [0.134, 0.0048], ASOF, fin_only=True, scope_only=True, strict=True,
                local_tokens=set())
    assert not r["violations"], [v["num"] for v in r["violations"]]
    # 符号由正文方向词承载，抽取器不保留负号 → 比对必须按绝对值
    txt2 = "据 binance_deriv_bundle（2026-09-15 现场实拉）OI 4h −1.04%。"
    r2 = cl.lint(txt2, [-1.041], ASOF, fin_only=True, scope_only=True, strict=True, local_tokens=set())
    assert not r2["violations"], [v["num"] for v in r2["violations"]]


def test_code_heavy_market_reply_is_not_skipped():
    """行情回复里顺口提了 tests/ 或脚本名，不能被整条跳过（老 SKIP 逻辑漏检）。"""
    import claim_watchdog as cw
    market = ("据 binance 现场实拉：现价 77,742.6，失守 77,456 则下看；CLARITY 法案程序性投票在 02:15，"
              "顺带修了 tests/test_claim_lint.py 与 scripts/claim_lint.py。")
    assert cw.relevant(market), "带价格的行情回复必须被扫"
    code = "把 tests/test_claim_lint.py 里的 import 改了，def relevant() 加一个条件。"
    assert not cw.relevant(code), "纯代码讨论不该进闸门"


def test_narrative_artifacts_never_become_local_evidence():
    """自我背书护栏：我写进 audit_/draft_ 存档里的错数字，不能反过来把幻觉"合法化"。"""
    import claim_lint as cl
    assert cl.is_narrative_artifact("outputs/audit_v1_20260915_1036.json")
    assert cl.is_narrative_artifact("outputs/draft_reply_1103.md")
    assert cl.is_narrative_artifact("outputs/hallucination_142191.md")
    assert cl.is_narrative_artifact("outputs/btc_card_v7_1103.md")
    # 实拉产物不能被误排除
    assert not cl.is_narrative_artifact("data/auto_card_BTCUSDT_full.md")
    assert not cl.is_narrative_artifact("outputs/binance_BTCUSDT_20260915_1106.json")
    assert not cl.is_narrative_artifact("data/tv_live_XAUUSD.json")
    # 端到端：审计文件被跳过 + 单位 token 化后，1.668亿 仍应被拦
    files, toks = cl.default_corpus()
    assert files and all(not cl.is_narrative_artifact(f) for f in files)
    txt = "| ② 现货承接消失 | 比特币现货 ETF 两日合计净流出 **1.668 亿**（周三 1.202 亿 + 周二 4660 万） |"
    r = cl.lint(txt, [], ASOF, fin_only=True, scope_only=True, local_tokens=toks)
    assert r["violations"], "真幻觉数字必须仍被拦（语料不能被 audit 存档污染）"


def test_watchdog_and_cli_share_one_standard():
    """审计发现：CLI 与看门狗口径不一致会让同一份文本得到两种结论 → 锁死默认口径。"""
    import claim_lint as cl
    card = "| 近端转撑 | 78,336 | -0.25% |\n| 失守 77,456 | 下看 77,213 |\n"
    # 默认（= 看门狗口径）不报；放宽 scope 才报
    assert not cl.lint(card, [], ASOF, fin_only=True, scope_only=True)["violations"]
    assert cl.lint(card, [], ASOF, fin_only=False, scope_only=False)["violations"]


def test_freshness_watchdog_tracks_gate_heartbeat():
    """闸门心跳必须被现有新鲜度看门狗覆盖（阈值 0.7h），否则闸门停摆无人知。"""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import data_freshness_watchdog as fdw
    cfg = fdw.WATCH_FILES.get("claim_watchdog_heartbeat.json")
    assert cfg, "新鲜度看门狗未登记闸门心跳"
    assert cfg["threshold"] == 0.7
