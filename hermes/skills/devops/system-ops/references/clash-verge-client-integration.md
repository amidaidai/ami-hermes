# Clash Verge 客户端导入与外部控制联动

适用场景：用户安装 Clash 配置检测/生成工具后，要求“像推文那样在 Clash 客户端显示”。这通常意味着检测结果要真正进入 Clash Verge 配置列表，而不是只在 Web 页面里展示。

## 目标闭环

1. 本地工具 Web UI 可访问，例如 `http://127.0.0.1:8080`。
2. Clash Verge External Controller 可访问，例如 `http://127.0.0.1:9097/version`。
3. 工具能通过 Controller 切换节点并检测 IP。
4. 生成/导出的 YAML 由本地 HTTP 服务提供。
5. 通过 `clash://install-config?...` deep link 导入 Clash Verge。
6. 在 Clash Verge 的配置列表里看到新配置，节点名带检测标签。

## 文件位置

```text
%APPDATA%/io.github.clash-verge-rev.clash-verge-rev/verge.yaml          # Verge UI 配置
%APPDATA%/io.github.clash-verge-rev.clash-verge-rev/clash-verge.yaml    # mihomo 运行配置
%APPDATA%/io.github.clash-verge-rev.clash-verge-rev/profiles.yaml       # 配置列表索引
%APPDATA%/io.github.clash-verge-rev.clash-verge-rev/profiles/           # 导入配置文件
```

## 操作步骤

### 1. 先备份

```bash
APP='/c/Users/Administrator/AppData/Roaming/io.github.clash-verge-rev.clash-verge-rev'
TS=$(date '+%Y%m%d-%H%M%S')
mkdir -p "$APP/backups/hermes-$TS"
cp "$APP/verge.yaml" "$APP/backups/hermes-$TS/verge.yaml.bak"
cp "$APP/clash-verge.yaml" "$APP/backups/hermes-$TS/clash-verge.yaml.bak"
cp "$APP/profiles.yaml" "$APP/backups/hermes-$TS/profiles.yaml.bak"
```

### 2. 开启 External Controller

用 YAML 工具修改：

```yaml
# verge.yaml
enable_external_controller: true

# clash-verge.yaml
external-controller: 127.0.0.1:9097
secret: set-your-secret
allow-lan: false
```

`allow-lan: false` 是安全默认：只给本机工具调用，不暴露到局域网。

### 3. 重启 Clash Verge 与 mihomo

```bash
taskkill //F //IM clash-verge.exe 2>/dev/null || true
taskkill //F //IM verge-mihomo.exe 2>/dev/null || true
sleep 2
powershell.exe -NoProfile -Command "Start-Process 'C:\Program Files\Clash Verge\clash-verge.exe'" | cat
sleep 8
```

### 4. 验证 Controller

```bash
curl -sS --max-time 5 \
  -H 'Authorization: Bearer set-your-secret' \
  http://127.0.0.1:9097/version
```

成功示例：

```json
{"meta":true,"version":"v1.19.25"}
```

同时检查端口：

```bash
netstat -ano | grep -E ':(9097|7897) '
```

### 5. 导出 YAML 并生成 deep link

如果检测工具把结果导出到本地 `exports/foo_checked.yaml`，先确认 HTTP 能访问：

```bash
curl -sS -I http://127.0.0.1:8080/exports/foo_checked.yaml
```

生成导入链接：

```python
from urllib.parse import quote
url = 'http://127.0.0.1:8080/exports/foo_checked.yaml'
name = 'Clash-IP-Checker-checked'
print(f"clash://install-config?url={quote(url, safe='')}&name={quote(name, safe='')}")
```

打开链接：

```bash
powershell.exe -NoProfile -Command "Start-Process 'clash://install-config?url=...&name=...'" | cat
```

### 6. 验证导入成功

读 `profiles.yaml`，应出现新 `remote` 条目：

```yaml
- uid: <new_uid>
  type: remote
  name: foo_checked.yaml
  file: <new_uid>.yaml
  url: http://127.0.0.1:8080/exports/foo_checked.yaml
```

也可以列出新文件：

```bash
ls -lt "$APP/profiles" | head
```

## 常见坑

| 现象 | 原因 | 修复 |
|---|---|---|
| Web UI 能打开，但检测无法切换节点 | External Controller 没开 | 改 `verge.yaml` + `clash-verge.yaml`，重启 Clash Verge |
| `curl :9097/version` 失败 | 只开了 mixed-port 7897，没有控制端口 | 设置 `external-controller: 127.0.0.1:9097` |
| 返回 401 | secret 不匹配 | 工具配置里的 `clash_api_secret` 与 `clash-verge.yaml secret` 对齐 |
| deep link 打开后客户端没新增 | YAML URL 不能被 Clash Verge 访问 | 先 `curl -I` 验证本地 HTTP 200 |
| 客户端新增了配置但节点没标签 | 导入的是原始 YAML，不是检测后的 `_checked.yaml` | 先跑检测并导入生成结果 |
| 修改配置后无效 | mihomo 进程还在用旧配置 | 同时杀 `clash-verge.exe` 和 `verge-mihomo.exe` 再启动 |

## 安全边界

- Controller 绑定 `127.0.0.1`，不要绑定 `0.0.0.0`。
- 不要把订阅 token、secret 写进回复正文；报告时只说已对齐或 present。
- 修改 Clash Verge 配置前先备份 `verge.yaml`、`clash-verge.yaml`、`profiles.yaml`。
