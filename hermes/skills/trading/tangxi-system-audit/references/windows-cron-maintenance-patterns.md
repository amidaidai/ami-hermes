# Windows Cron 脚本维护模式

## UTF-8 编码修复模式

Windows no_agent cron 脚本输出中文/emoji 时产生乱码的根因：cron 环境默认使用 GBK 编码。

**修复模板**（在 import 段后、任何 print 之前插入）：

```python
import io as _io
if hasattr(sys.stdout, "buffer"):
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
```

**审计检查**：`head -20 scripts/xxx.py | grep TextIOWrapper` — 无则标记 P2。

## uv Trampoline 修复模式

cron/Git-Bash 环境中 `hermes` 命令的 uv 包装器可能报 `uv trampoline failed to canonicalize script path`。

**脚本内修复**：所有 subprocess 调用 hermes CLI 的地方用：
```python
[sys.executable, "-m", "hermes_cli.main", "skills", "check"]  # 替代 ["hermes", "skills", "check"]
```

**交互/终端修复**：若 `which hermes` 命中 Windows PE launcher（如 `.hermes-web-ui/.../python/Scripts/hermes`），在 PATH 更靠前的 `~/.local/bin/hermes` 写 bash wrapper：
```bash
#!/usr/bin/env bash
exec python -m hermes_cli.main "$@"
```
然后 `chmod +x ~/.local/bin/hermes && hash -r && hermes --version && hermes doctor` 验证。不要改桌面runtime原始PE启动器。

**审计检查**：`grep -rn '"hermes"' scripts/repo-maintenance/*.py` — 如果有则标记 P2。

## ThreadPoolExecutor 并行化模式（解决 cron 超时）

串行任务导致 cron 超时时，用 `concurrent.futures.ThreadPoolExecutor` 并行化。

**模板**（以 SkillMCP 脚本为例）：

```python
from concurrent.futures import ThreadPoolExecutor

def main():
    # 并行执行 3 个不相互依赖的子任务
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_skill = ex.submit(check_skills_update)
        f_mcp = ex.submit(test_mcp_servers)
        f_curator = ex.submit(run_curator)
        skill_status = f_skill.result()
        mcp_status = f_mcp.result()
        curator_status = f_curator.result()
    # 串行执行依赖顺序的任务
    update_status = check_official_update()
```

**MCP 测试并行化**（最耗时环节）：
```python
# 前: for name in servers: run("hermes mcp test", timeout=30)  # 8×30=240s
# 后:
with ThreadPoolExecutor(max_workers=4) as ex:
    futures = {ex.submit(_test_one, s): s for s in servers}
    for f in as_completed(futures):
        results.append(f.result())
# 8台服务器 4线程并行 = ~30s（减少 8×）
```

## Orion API 参数要求

Orion Terminal API (`https://screener.orionterminal.com/api/screener`) 必须显式指定 `?exchange=binance` 或 `?exchange=hl`。

```python
# ❌ 错误 — 返回空数组（API 行为变更）
tickers = fetch_orion("")

# ✅ 正确
tickers = fetch_orion("binance")
```

## 审计 cron 输出乱码

```bash
# 检查最近 cron 输出是否有 UTF-8 乱码
ls -t ~/AppData/Local/hermes/cron/output/ef4cf5f7cd24/ | head -3 | while read f; do
    echo "--- $f ---"
    grep -a "鏁版嵁\|鍙栧け\|鈿" "~/AppData/Local/hermes/cron/output/ef4cf5f7cd24/$f" 2>/dev/null
done
# 如果匹配 → 脚本缺 UTF-8 编码修复
```

## 检查清单

在每个 no_agent 脚本创建/修改后运行：
- [ ] `grep "TextIOWrapper" <script>` → 有编码修复
- [ ] `grep '"hermes"' <script>` → 无 bare hermes 调用
- [ ] 耗时子任务用 ThreadPoolExecutor 并行化
- [ ] 外部 API 调用有显式参数（不依赖默认值）
