# Clash Verge 节点盘点与外部工具清理

适用场景：用户要求删除临时 Clash 工具/本地 Web UI，并判断 Clash Verge 里多个订阅/节点哪个更好。

## 1. 清理本地临时工具

1. 先查并杀掉引用项目路径的进程，避免 Windows 目录 `Device or resource busy`：

```bash
powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*clash-ip-checker*' } | Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Depth 3" | cat
for pid in $(powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*clash-ip-checker*' } | Select-Object -ExpandProperty ProcessId" 2>/dev/null | tr -d '\r'); do
  taskkill //F //PID "$pid" || true
done
```

2. 再删除项目与导出物：

```bash
rm -rf '/d/Hermes agent/projects/clash-ip-checker'
rm -f '/d/Hermes agent/outputs/clash-ip-checker-installed.png'
```

3. 验证 8080 不再监听：

```bash
netstat -ano | grep ':8080 ' || true
```

Pitfall：如果清理命令本身的 `CommandLine` 包含 `clash-ip-checker`，不要让循环 kill 当前 shell/terminal 子进程；优先只 kill `python.exe web.py`，或在脚本结束后用新一轮独立验证。若目录内容已空但目录仍 `Device or resource busy`，说明仍有进程 cwd/句柄占用；报告“内容已清空，空目录待进程释放后删除”，不要反复自杀式重试。

## 2. 清理 Clash Verge 中误导入的检测配置

检查 `profiles.yaml`，删除名称/URL/文件中包含临时检测配置的 remote 项：

```python
from pathlib import Path
from ruamel.yaml import YAML
app = Path(r'C:/Users/Administrator/AppData/Roaming/io.github.clash-verge-rev.clash-verge-rev')
p = app / 'profiles.yaml'
y = YAML(); y.preserve_quotes = True
data = y.load(p.read_text(encoding='utf-8'))
keep, removed = [], []
markers = ['clash-ip-checker', 'clash-verge_checked', 'current-clash-verge', 'Clash-IP-Checked', 'Clash-IP-Checker']
for item in data.get('items', []) or []:
    s = ' '.join(str(item.get(k, '')) for k in ['uid', 'type', 'name', 'file', 'url'])
    (removed if any(x in s for x in markers) else keep).append(item)
if removed:
    data['items'] = keep
    with p.open('w', encoding='utf-8') as f:
        y.dump(data, f)
print('removed_profile_entries', len(removed))
```

## 3. 盘点 Clash Verge 订阅

读 `profiles.yaml`，只比较 `type: remote`：
- 当前启用：`current` UID
- 流量：`extra.upload + extra.download`、`extra.total`
- 到期：`extra.expire`
- 节点数量：读取 `profiles/<file>` 的 `proxies` 数量
- 组选中：`selected`
- 更新频率：`option.update_interval`

推荐判断：
1. 当前启用且实时延迟低 → 主用优先。
2. 剩余流量大且未过期 → 备用优先。
3. 有 ChatGPT/特殊分组且历史可用 → 特殊用途备用。
4. 已过期/临期/无实测优势 → 不优先。

## 4. 实时节点延迟采集

如果 external-controller 可用：

```python
import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:9097/proxies', headers={'Authorization': 'Bearer set-your-secret'})
with urllib.request.urlopen(req, timeout=8) as r:
    data = json.loads(r.read().decode('utf-8'))
ps = data.get('proxies', {})
leaves = []
for name, v in ps.items():
    if v.get('all'):
        continue
    hist = v.get('history') or []
    delay = hist[-1].get('delay') if hist else None
    if isinstance(delay, (int, float)) and delay > 0:
        leaves.append((delay, name, v.get('type')))
for delay, name, typ in sorted(leaves)[:20]:
    print(delay, name, typ)
```

输出建议：先给明确推荐，再给三张窄表：订阅对比、当前低延迟节点、用途推荐。不要把检测结果重新导入 Clash，除非用户明确要“节点名带风险标签”。