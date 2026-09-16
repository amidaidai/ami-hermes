---
name: pipeline-hand-run-verification
description: "Use when hand-running a pipeline's internal modules."
category: software-development
tags: [verification, pipeline, silent-failure, data-freshness, gates]
---

# 手动跑管线步骤时的静默降级防护

适用场景：某个模块平时是编排器（`auto_card.py` 这类）的内部消费者，这一次你要绕过编排器**手动直调**它——因为编排器不可用、或用户要的是一张手工完整卡、或你在做诊断。

核心风险不是报错，而是**静默给出一份看起来完整的错结果**：

| 静默失败形态 | 表现 | 为什么危险 |
|---|---|---|
| 输入键名不匹配 | 模块找不到预期字段 → 走默认值分支 | 默认值常常在“安全侧”（绿灯/24h/未检测），结果看起来正常 |
| 安全闸门假绿 | 强制拦截门报 `green · 无事件` | 在真正应该拦截的窗口里放行 |
| 组合缓存内层陈旧 | 外层文件 mtime 几分钟前 | 内层字段可能是几周前的抓取 |
| 未等重绘就读 | 读到上一状态的同构数据 | 结构相同、数字不同，不报错 |
| 假违规噪声 | 缺输入算出的“违规”被当真 | 报告里出现并不存在的风控问题 |

**一条铁律：宁可大声失败，不可静默降级。** 凡是你绕过了编排器，就必须用下面三步把“静默”变回“可见”。

## 第一步：动手前先读源码，找到真正的输入键

不要按业务语义猜参数名。直接看模块读了什么：

```bash
python - <<'PY'
import inspect, sys
sys.path.insert(0, "scripts")
import the_module as m
print(inspect.signature(m.the_entry))
print(inspect.getdoc(m.the_entry))
PY
```

然后 `search_files` 在模块里搜它真正 `get()` 的键。**内部消费者经常读带下划线前缀的私有键**（`_banned_live`、`_snapshot_age_h`、`_tv_pine`…），这些键名绝不会出现在你的业务参数里——只读源码能发现。

同时把**默认值**记下来：默认值是 `"C"` / `24` / `"未检测"` 这类“偏安全”的值，就意味着漏传不会报错、只会静默降级。

注意签名形态：内部模块常常是**全 keyword-only**（如 `classify_decision_regime(*, adx, atr_ratio, ...)`），多传一个业务键（`symbol=...`）就直接 TypeError——这不是“模块坏了”，是它本就不接受编排器之外的调用方式。

## 第二步：跑完必须回读逐项状态，不能只看总判定

```python
r = module.entry(...)
for name, d in r["gates"].items():          # 或 r["sources"], r["checks"], r["checks"]
    print(name, d["status"], d["reason"])
```

**只信“总判定”是踩坑的主要方式。** 总判定可能是 `WAIT`（看着合理），但里面某一门本该是 `red` 却被静默判成 `green`——只有逐项回读才看得见。

逐项回读时重点看三类：
- **本该红却是绿**的强制门（最危险）；
- `reason` 里出现「未检测 / 未接入 / 未评估 / 不适用」的项——那是缺输入，不是通过；
- 因缺输入而产生的**噪声结论**（见下）。

**假违规必须过滤**：风控/评分类模块在缺输入（如无入场价、无止损）时会算出“单笔风险 100% > 上限”之类的违规。那是缺输入算出来的，**不得当真实违规写进报告**。只报模块自己声明的状态降级（如 `risk_state_status`）。

## 第三步：陈旧数据要么标出来，要么不用

两层新鲜度，缺一不可：

1. **外层文件 mtime**；
2. **内层字段自己的时间戳 / 状态位**。

组合型缓存（一个 JSON 里装多个数据源的快照）会被整篇重写，于是外层 mtime 一直很新，而内层某些字段可能几周没更新。实测过一个情绪缓存：外层 mtime 12 分钟，而里面的价格快照停在 **64,658**、实盘已 **76,000+**，脚本自己的 `refresh_status` 就写着 `kept_previous`。

三层校验：

```python
d = json.loads(path.read_text(encoding="utf-8", errors="replace"))
# ② 逐源状态：非 live 一律不采用
for k, st in (d.get("refresh_status") or {}).items():
    if st != "live":
        print(f"不采用 {k}: {st}")          # kept_previous / stale / error
# ③ 量级体检：内层数值 vs 实时值，偏离 >5% 即判 stale
```

要点：**`refresh_status` 里没列出的字段 = 没被本轮刷新**，与 `kept_previous` 同等对待。内层陈旧时，在报告里按「本轮无有效字段」记，并且**不得混写成「源设计性停用」**——那是两个不同语义，混写会把可修的问题写成设计决定。

## 源降级时：给出真实可用的替代路径，并写明口径

一个源拿不到就标 `⚠️` 跳过是可以的，但**更好的做法是先给一条真跑得通的替代**，再在报告里写明换源。替代路径必须实测跑过，不能是“应该可以”的猜测。

例：宏观指数主源不可用时的可用替代（走本地代理，符号需 URL 编码）：

```
https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=10d&interval=1d
```

符号：`%5EGSPC` 标普 · `%5EVIX` · `%5EIXIC` 纳指 · `DX-Y.NYB` DXY · `%5ETNX` 美10Y · `GC=F` 黄金。

**日变动必须自己从日线 close 序列算**（取最后两个非空收盘求百分比），不要用 `meta.chartPreviousClose`——两者时间基准不同，实测 VIX 会算出 −6.2% 而序列真值是 −2.67%。

## 出图 / 出报告前的自检

生成类工具返回 `success: true` **只证明文件落地，不证明内容对**——符号被别的任务切走、窗口没最大化、副图被折叠，都会照样返回成功。发布前对产物做一次独立自检：

- 图：周期标签 / 右侧数值轴 / 副图窗格 / 图例数值与实时值偏差是否在容差内；
- 报告：声明的总数与逐项枚举数是否一致（不一致就重新取数，不要“按手上的写”）。

自检一次的成本，远低于让用户看出返工。

## 交付前清单

- [ ] 直调模块的输入键是**读源码确认**的，不是按业务语义猜的
- [ ] 已记下每个“偏安全”的默认值，并确认本轮没有依赖到它
- [ ] 逐项回读了门/源状态，不只看总判定
- [ ] 本该拦截的强制门确认是拦截态（不是静默绿）
- [ ] 缺输入产生的假违规已过滤，没写进报告
- [ ] 组合缓存做了逐字段新鲜度 + 量级体检
- [ ] 内层陈旧的源标成「本轮无有效字段」，未混写成「设计性停用」
- [ ] 换用的替代源是实测跑通的，并在报告里写明换源
- [ ] 图/报告产物做过独立自检

## 参考
- `references/silent-green-gates.md` — 强制闸门的键依赖表与回读配方（哪些门缺输入会变绿）
- `references/composite-cache-freshness.md` — 组合型缓存的逐字段体检脚本与判定
- `references/local-engine-call-recipes.md` — 本地引擎/数据源直调配方（签名陷阱、特征算法、深度/清算解析）
