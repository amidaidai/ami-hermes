# Git 删除安全检查 (2026-09-03 实盘)

## 场景
`git status` 出现大量 `D <script>.py`（工作树删除、HEAD 仍跟踪），且部分被删模块仍被**活跃脚本** import。直接用 `git add -A` 提交会把删除落地 → 活跃脚本 ImportError（import 时静默崩，可能隔天才被发现）。

## 关键判定：别把「被引用」一律当「打挂」

命中引用 ≠ 必崩。看**引用方式**（import 风格决定运行时是否崩）：

| 引用方式 | 删除后结果 | 处理 |
|---|---|---|
| `from X import Y` 裸 import（无 try/except） | import 时抛 ImportError | **必须 restore** |
| 动态 `spec_from_file_location("X", ...).exec_module()` | 缺失即 raise（若未 catch） | **必须 restore** |
| `from X import Y` 在 `try/except ImportError` 内 | 降级走 fallback（如「直接推不丢报告」） | 可安全删除 |
| 字符串/子进程路径引用（`ROOT / "scripts/X.py"`） | 仅在该脚本被主动运行时崩 | 看该引用方是否退休 |

## 5 步提交前检查

```bash
# ① 枚举被删脚本
git status --short | grep '^ D' | grep '\.py$'

# ② cron 安全交叉：读 jobs.json，只对 enabled=True 的任务取 script basename 比对被删集
#    （重点：看 enabled/state，勿信 history last_status）

# ③ 活跃代码 import 交叉：对每个被删模块 basename
for m in $(git status --short | grep '^ D' | grep '\.py$' | sed 's#.*/##;s#\.py$##'); do
  grep -rlE "(from|import) ${m}\b" scripts/ --include='*.py' 2>/dev/null \
    | grep -vE '_archive|_disabled|__pycache__'
done

# ④ restore 命中即崩的模块
git checkout HEAD -- scripts/<magic>.py ...

# ⑤ 只暂存已跟踪修改+删除，不纳入歧义未跟踪产物
git add -u        # 而非 git add -A

# 提交前查机密
git diff --cached --name-only | grep -iE '\.env|auth|secret|token|\.pem'
```

## 本会话实测 (2026-09-03)

- **无任何 enabled cron 指向被删脚本**（关键安全点）。
- 59 删里真正被活跃代码依赖的只有：
  - `five_model_matcher` ← `backtest_runner.py`（裸 import → **restore**）
  - `orion_radar_card` ← `orion_screener_radar.py`（动态 spec_from_file_location，缺失即 raise → **restore**）
  - `alert_dedup` ← `orion_screener_radar.py`（在 `try/except ImportError` 内 → 有 fallback，可删；为稳妥也 restore）
- `btc_daemon.py` 字符串引用 `dmi_decision.py`/`btc_card_gen.py`/`tv_levels_collector.py` → btc_daemon 已退休（非 cron、无人 import），不算活跃依赖。
- 提交前 `py_compile` 确认活跃脚本（orion/backtest_runner/data_freshness/deribit）仍编译通过。

## 额外教训

- **未跟踪诊断产物**（`*.txt`/`*.pine`/`_diag*`/`.pytest-cache`/node 诊断）不该提交，推荐 `.gitignore`，不要 `git add -A` 把它们一起纳入。
- **"cron last=error" 不一定代表活跃故障**：先看该任务 `enabled`/`state`（disabled/paused 的 last_error 是历史）；唯一活跃且报错的才是要修的。本会话 `宏观Poly刷新`、`liq_listener_btcusdt`、`黄金宏观刷新` 均为 disabled/paused，非活跃问题。
- **大量 `D` 删除 + 有活跃 import 命中 = 独立清理工程**，不是批处理；先专项列出会打挂的引用交用户确认，不要 `git add -A` 无脑提交。
