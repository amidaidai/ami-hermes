# 闸门饥饿审计 —— 用户说「你总是不做／总是不给方案」时的标准处置

用户表达「我发现你总是不做」「你总是不给方案」「总是禁止做」，且该现象跨多次会话或跨多日重现时：
**用数据回答，不要用「今天没有优势」解释一个系统现象，也不要写态度表态（「我以后会更积极」）。**

## 脚本位置（踩过的坑）

```
~/AppData/Local/hermes/skills/trading/trading-system-architecture-design/scripts/gate_starvation_audit.py
```

仓库 `D:/Hermes agent/scripts/` 下**没有**这个文件（那里面只有无关的 `go_nogo_gate.py`）。
在仓库根 `ls scripts/ | grep -i gate` 查不到 ≠ 脚本不存在 —— 去技能目录 `scripts/` 找。

## 跑法与落档

```bash
python "$SKILLDIR/scripts/gate_starvation_audit.py" > outputs/gate_starvation_audit_$(date +%Y%m%d).txt 2>&1
head -60 outputs/gate_starvation_audit_*.txt
```

输出很长（含结果分布、h4/h8/h16 三段），**先重定向落文件再分段读**；直接 `tail` 会只看到末段结论而丢掉前面的分布与拦因表。

## 判读口径（决定你给什么结论）

| 审计行 | 判读 |
|:--|:--|
| `可执行授权 ('GO-A',) 次数: 0` | **结构缺陷**（审计原话：不要解释成「行情不好」）。用户的感觉是对的，责任在门不在行情 |
| `side=neutral` 占比（常 ~78%） | 那是**没产生方向**的扫描 tick，不是「被否决」；报任何比例时分母只用**有方向候选**（`有方向候选 N/M`） |
| 拦因频次表 | 按次数排序就是修复优先级；`haldro_invalid` / `b_wait` 这类高频门要单独验一次是不是读取缺陷 |
| 「只差一步」子集 | `仅 <某门> 挡住: N` —— N 最大者杠杆最高，先修它 |
| `h4/h8/h16` 结果分布 | 若 85% 以上「既未触及目标也未触及止损」→ 样本不可执行，**结果数据不能用来给闸门背书**，也别据此说闸门拦对了 |

## 账本自身就是证据（比审计脚本更细）

`data/shadow/decision_signals.jsonl` 每行自带：`ts`(epoch ms) · `side` · `haldro_valid_code` · `final_state` ·
`blockers[]` · `final_verdict.gates` · `signal_id`。逐条统计即可把「哪道门坏了」定到字段级：

```python
import json, collections
rows = [json.loads(l) for l in open('data/shadow/decision_signals.jsonl', encoding='utf-8') if l.strip()]
dirs = [r for r in rows if r.get('side') in ('long', 'short')]
print(collections.Counter(r.get('haldro_valid_code') for r in dirs))
print(collections.Counter(r.get('final_state') for r in rows[-150:]))
b = collections.Counter(k for r in rows[-60:] for k in (r.get('blockers') or []))
print(b.most_common(12))
```

两类典型读数：

- **有方向样本里 `haldro_valid_code=0` 占比极高**（实测 111 条有方向、88% 为 0）**不等于读取缺陷** ——
  账本存的是历史，现场同时刻读到的可能是 2。判缺陷前必须做两件事，缺一件就会修错层：
  ① **按时间切片**：0 若全部落在某段日期内（实测 0 都在 07-10～09-06、且之后不再产生有方向样本），
     那是**该窗口的采集历史**，不是当前缺陷；报「最大杠杆」前用最近 60/150 条重算一次。
  ② **核契约与现场字段**：打印 `tv_indicator_contract.DW_ALIASES_SUB['haldro_valid_code']` 的 title，
     与**现场** `data_get_study_values` 返回的真实键逐条比对 —— 一致（实测都是 `'HALDRO Valid Code'`、现场值 2）
     即链路通，别再顺着 grep 出来的键名 (`sub_haldro_valid_code`) 找 bug：
     该键由 `main["sub_" + key] = tv_vals[title]` 从契约 ASUB 表生成，契约有它就会生成。
     比对**必须用现场返回的原键名**：契约 title 自带括号后缀
     （`HALDRO State Pack (0无效/1支持多/2支持空/3冲突/4降权)`、`CVD Method Code (1=当前所K线方向/2=当前所1m方向)`），
     手写一份简化名列表会把它们全判成「不匹配」＝假报警，然后你会去修一个不存在的字段漂移。
- **最近 N 条 `side` 全是 neutral** → 瓶颈已**前移**到第一层（主指标不给方向 / SVP 授权不通过），
  此时再去修 `haldro_invalid` 是修错层。先看第一层的 `svp_wait_language` / `svp_no_trade_reason` / `location` / `trigger`。

## 交付形状

1. 结论先行：`0 次 GO-A = 结构缺陷`（带审计原话，别自己概括成「系统有点保守」）。
2. 三道门频次表（门 / 次数 / 占比）。
3. **行情 vs 系统两栏表** —— 这是用户真正要的答案：

| 门 | 性质 | 能不能动 |
|:--|:--|:--|
| `rr_ratio`（空间不够 2R） | 行情判断 | 不能修，做了就是亏 |
| 缩量 / 价量背离 / 主副方向票打架（`b_wait`/`dual_*`） | 行情判断 | 不能修 |
| `haldro_invalid`（valid_code 长期 0） | 疑似工程缺陷 | 查读取路径 |
| `risk_constitution` 里的风控快照 | 系统状态（快照停在两个月前） | 刷新 |
| 组合暴露 / WFO | 系统状态（未接持仓 / 未计算） | 接数；WFO 需先修影子账本几何 |

4. 本轮这张卡具体卡在哪（引卡面闸门表：🔴 R:R `/` 🔴 双指标共振 `/` 黄灯快照陈旧）。
5. 按杠杆排序的待修项（谁先修、修完黄灯会变什么）。

收尾务必给用户能自查的一句话，例如「上方空间不够 2R」或「止损只能摆在阻力簇里＝把止损交给插针」——
只写「R:R 不足」他不满意（他会回「那到底什么时候能做」）。

## 常见误判

- 把 `neutral` 扫描 tick 算进「被否决」→ 分母虚高、结论变成「系统什么都拦」。
- 拿 `h4/h8/h16` 的期望值（如 `-0.113R`）说「所以拦对了」—— 85% 样本既没触目标也没触止损，这份结果不具判断力。
- 看到 `Last run: ok` 就认为链路健康 —— 那只说明脚本跑过，不说明产出可用（投递/裁决另看）。
- 把「只差一步」排名当成当前杠杆：它建立在**累计历史**上，可能指向一个早已不再触发的门（实测审计把 `haldro_invalid`
  列为最大杠杆，按时间切片后发现当前瓶颈其实是第一层「不产生方向候选」）。报修复顺序前用最近窗口重排。
- 把「投递失败」当真：`data/trigger_<SYM>.json` 的 `push_status=failed_or_missing` 可能只是**有意不推**被记成了失败 ——
  `auto_card` 对非 GO-A 卡会打印「未推送：FinalVerdict不是完整GO-A可执行裁决」，而 dispatcher 一度把它当投递失败，
  `push_retry_count` 空转到三位数。**故意的 no-push 必须落 `skipped_not_goa` 且 `push_retry_required=False`**，
  否则重试计数永不收敛、面板上长期挂着幽灵投递失败（判「哪一道门拦的」时也会被这条噪音误导）。
