# cronjob update 工具沙箱限制（2026-08-31 实测）

## 现象
对 `no_agent=true` 任务执行 `cronjob(action='update', job_id=..., ...)`，**无法注入环境变量**到 `script` 调用的子进程里。
即便尝试把环境变量塞进 `update` 的 `arguments`（或 `environment`、`env` 等任何变体字段），都返回 `success: true` 但实际 cron 调度时子进程读不到。

## 复现
1. `cronjob(action='list')` 找一条 `no_agent=true`、`script` 字段非空的 job
2. 执行 `cronjob(action='update', job_id=<id>, ...)`，尝试附带环境变量
3. 返回值 success
4. 等到下一个调度点，脚本内 `os.environ.get("XAU_TV_NO_PUSH")` 仍为 `None`

## 根因（推测）
- `cronjob` 沙箱在序列化 `update` payload 时只白名单了少量字段（`schedule/name/prompt/skills/script/deliver/enabled_toolsets` 等）
- `no_agent` 路径直接 fork 子进程跑 `script`，环境变量仅从父进程继承，update payload 里的环境变量被丢弃
- LLM agent 路径（`no_agent=false`）会把 `prompt` 写进 agent context，环境变量可在 prompt 里 `$FOO` 引用，但 no_agent 没有 prompt

## 解决路径
1. **优先：脚本内读 `data/<flag>.json` 文件开关**（推荐），见 SKILL.md「Cron 推送静默开关模式」
2. **次选：直接修改脚本逻辑**（如加 `NO_PUSH = True` 常量或读环境变量后写进脚本默认）
3. **不可用：`cronjob update` 注入环境变量**（已验证失败）

## 工具调用踩坑清单（与本限制相关的字段）
| 字段 | 是否生效于 no_agent 任务 |
|---|---|
| `schedule` | ✅ |
| `name` | ✅ |
| `script` | ✅（替换运行的脚本） |
| `prompt` | ❌（no_agent 忽略） |
| `deliver` | ✅ |
| `skills` | ✅ |
| `enabled_toolsets` | ✅（仅 LLM agent 路径生效） |
| 环境变量相关 | ❌ |
| `monitor` 脚本路径 | ✅（替换守门狗脚本） |
| `workdir` | ✅ |

## 替代 pattern：标志文件

```python
# scripts/xau_tv_sync.py 头部
NO_PUSH_FLAG = ROOT / "data" / "xau_tv_no_push.json"

# 在调用 push_tg_rich 之前
if os.environ.get("XAU_TV_NO_PUSH") == "1" or NO_PUSH_FLAG.exists():
    print("⏸ XAU TV 推送已关闭（开关命中）")
else:
    push_tg_rich("telegram:...", output)
```

恢复推送：删 `data/xau_tv_no_push.json`。
