# 2026-09-16 审计证据链：口径单点遗留 / 自持标记半成品 / 静默零值与静默轮次

用户请求：「看一下我们刚刚做的全部是否已经整合一起了，还有什么问题吗」——审计对象是当日
CoinLobster 外部验证层接入（未提交工作树）+ 系统常用件（分析卡流程）。

## 0. 开工基线（并发写入方检测）

```
$ git status --short
 M docs/指标驱动分析与策略合同.md
 M scripts/pipeline_router.py
 M scripts/render_v96.py
 M tests/test_pipeline_router_asset_sources.py
?? scripts/coinlobster_collector.py
?? scripts/coinlobster_refresh.py
?? tests/test_coinlobster_evidence.py
$ python -c "import datetime;print(datetime.datetime.now())"
2026-09-16 13:14:34
```
结论：CoinLobster 接入本身是**未提交的工作树产出**，审计与修复都在其上叠加；
提交时拆两个 commit（前序会话产出 / 本轮修复），只 `git add` 自己的文件，不 push。

## 1. 外部验证层接入现状（结论：接通，四处收尾漏项）

```
$ ls -la data/coinlobster*        # 仓库 data/ 里没有
No such file or directory
$ find ~ -name "coinlobster*"
/c/Users/Administrator/AppData/Local/hermes/data/coinlobster_snapshot.json
```
工件落在 **Hermes 运行态 data/**（`coinlobster_collector.ARTIFACT`），而 `auto_card` 的
cron_read 审计按 `ROOT / "data"` 拼路径 → 永久判缺失。

实测同一张 BTC 卡（13:16 轮）：

```
| 外部验证 | 级联 $464M · 多单占89% · 费8h 0.0246~0.0050% | 背景/反证·非执行授权 |   ← 有数据
| Cron缓存 | ⚠️ | 新鲜:x_sentiment,liquidation_flow；…；缺失/过期:coinlobster(not_run) |  ← 说没有
```

cron 侧完好：`CoinLobster外部验证层刷新` `9,29,49` · `no_agent=true` · `last_status=ok`。
读侧三态按工件年龄（25/90 分）判定，`read_evidence('BTCUSDT') → state=live`。

## 2. P0 身份归一漏改（口径单点切换的遗留消费方）

```
$ python -c "import sys;sys.path.insert(0,'scripts');from source_health import symbol_matches;print(symbol_matches('XAUUSD','TVC:GOLD'))"
False
$ python - <<'PY'
import sys; sys.path.insert(0,'scripts')
import auto_card, tv_symbols; from tv_data_bridge import _norm_symbol_for_cache as b
for s in ('TVC:GOLD','OANDA:XAUUSD','XAUUSD'):
    print(s, auto_card._norm_symbol_for_cache(s), b(s), tv_symbols.norm_identity(s))
PY
TVC:GOLD      GOLD   XAUUSD  XAUUSD      ← auto_card 自带副本没跟上
OANDA:XAUUSD  XAUUSD XAUUSD  XAUUSD
XAUUSD        XAUUSD XAUUSD  XAUUSD

$ python -c "... auto_card._tv_cache_status(json.load(open('data/tv_live_XAUUSD.json')),'XAUUSD',13)"
{'usable': False, 'symbol': 'TVC:GOLD', 'age_minutes': 3.8, 'reason': '品种不匹配 TVC:GOLD'}
```

卡面后果（XAU full，13:25 轮）：

```
| 🔴 TV现场确认 | RED | TV缓存不可用·tv_live_XAUUSD.json: 品种不匹配 TVC:GOLD; … |
**裁决**: ✗ NO-GO · 硬闸门：tv_live/cross_source/…
| TV五层 | ⚠️ | TV主周期可用=False·五周期可用=True·覆盖5/5 |
```

预检后果：`python scripts/audit_preflight.py → exit=1`，唯一 FAIL 行即
`tv_live_XAUUSD.json … 品种不匹配: expected=XAUUSD, got=TVC:GOLD`。

修复后（13:29 轮实跑）：门2 `GREEN TV SVP已读·C等待·缓存新鲜`、`TV五层 ✅`、
preflight `exit=0`；裁决红灯只剩真实的 `rr_ratio`。

## 3. P1 租约自持只落地一半

```
$ tail data/xau_tv_sync_runs.jsonl
{"ts":"…13:15:50…","pid":21864,"reason":"enter"}                      ← 无终态标记
$ python -c "读 output/113655ad34b5/2026-09-16_13-16-40.md"
✅ 5m 校核通过（…） → 采用 API 五周期（twelvedata）                        ← 只有这一行
$ sqlite: executions → job 113655ad34b5 status=completed finished=13:16:40 error=None
```

```
$ tail data/xau_tv_sync_runs.jsonl   # 卡内前置同步那轮
{"reason":"enter"}
{"reason":"defer:cache_usable","remaining":899.1}                        ← 让自己的租约挡住了
```
结论：`TANGXI_ANALYSIS_OWNER` 只有 `keylevels_collect` 消费；`xau_tv_sync` 未读 →
卡自己声明租约 → 卡自己 spawn 的前置同步让路 → 卡读 6 分钟前的缓存 → 门2 红。

修复：`tv_data_bridge.ANALYSIS_OWNER_ENV/is_analysis_owner` 单点；
xau_tv_sync 读标记放行；auto_card XAU 前置采集 `env=_analysis_owner_env()`。
契约测试同步细化（后台脚本只许读、不许自称）。

## 4. P1 清算流静默零值

```
$ python -c "读 data/liquidation_flow.json"
BTC: 最新事件 10:36:38 → 距今 161.9 分；fetched_at 距今 7.7 分；status=live stale=False
  近1h: 0 笔 多 $0 / 空 $0
  近24h: 3418 笔 多 $41,011,008 / 空 $8,919,763
$ 直连 OKX: BTC-USDT 最新明细 ts=10:36:38（162 分前）；ETH-USDT 12 分前
卡面：清算流OKX 近1h 多$0/空$0 · 窗21.4h 多$41.0M/空$8.9M · …
```
上游停更（非我方丢数据）；缺陷在**读侧用抓取时刻判新鲜**，$0 无任何标注。

## 5. 全量回归与运行态

```
$ python -m pytest tests/ -q
1353 passed, 1 skipped          # 修复前
1370 passed, 1 skipped          # 修复后（+17 新增用例，其中 1 用例按新契约细化）

$ python scripts/audit_preflight.py      # 修复后 exit=0
TV CDP: OK · BTC/XAU 四份缓存 OK · BTC/XAU 五周期 OK · 批准关键位 8/8
关键位守护 processes=1 heartbeat_age=0.3s · Cron total=20 enabled=16 · CoinLobster… ok
```

其余核过无碍：heartbeat 三份新鲜；`coinlobster_snapshot.json` live；
`xau_tv_sync_status.json` consecutive_failures=0；`shadow/decision_signals.jsonl` 每轮写、
`outcomes` 落后 10h（15 分钟 cron + 4h 成熟期，正常）；`trade_events/risk_state/strategy_governance`
陈旧属设计性退役（用户手动交易）。

## 6. 遗留与建议（2026-09-16 已按建议逐项推进）

1. XAU 静默轮次：已加 `exit`/`exit:exception` 终态标记 + `last_round_unterminated()`，
   预检增行「XAU同步终态」（只报不判 red）。等下一例样本定根因。
2. 管线完成度表永久 `13/14` —— 有意设计（cron_read 含 3 个设计性停用源），
   已写进 `docs/上手速查.md` 的「什么算正常」表，避免被读成长期不健康。
3. XAU ① 表退化文案已修：真凶是 `tv_five_tf_contract._normalise_record` 的
   `or f"TV现场·{tf}"` 兜底（**不是** auto_card 的 klines 赋值——第一次改错地方，
   只有跑真卡才暴露）。新增单点 `position_label()`；实测输出
   `D🔴中位59%·跌0.10% · 4h🟢高位73%·涨1.05% · …`。口径边界：只给位置+涨跌，不编 BOS。
4. OKX 逐笔停更为上游行为：已在卡面标注「⚠最新事件N分前(疑似停更)」+ 币安快照附注
   「(仅存在性·不计入规模)」（规模口径唯一是 OKX 逐笔）。
5. 新增 `docs/上手速查.md`（一页版：命令/读卡/什么算正常/按症状排查/铁律），
   系统总览顶部加入指引。

### 6.1 本批验证快照

```
pytest tests/ -q  →  1376 passed / 1 skipped
python scripts/audit_preflight.py  →  exit 0（四项缓存 OK、五周期 OK、批准关键位 8/8、
                                    守护单实例 heartbeat 0.2s、cron 16/20、XAU同步终态 OK）
XAU full 实跑 → ① 位置+涨跌可读、门2 GREEN、TV五层 ✅、8 步完成 7/8
```

### 6.2 教训：先 trace 再改

改卡面文案前必须确认**谁真正生成那一行**；本次第一版改在 `auto_card`（未生效），
真凶在契约层兜底。判定方式：同字段的多个可能来源全部 `grep` 一遍，改完**跑真卡**看那一行。
