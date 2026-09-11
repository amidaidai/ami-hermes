# Windows 便携式 CLI 工具安装指南

在 Windows Git-Bash (MSYS) 环境中，winget/scoop/choco 通常不可用。便携式 zip 安装是最可靠的路径。

## 通用安装模式

```bash
# 1. 下载 portable zip
cd /tmp
curl -L -o tool.zip "https://github.com/org/repo/releases/download/vX.Y.Z/tool_windows_amd64.zip"

# 2. 解压
unzip -o tool.zip -d tool_extract

# 3. 安装到 ~/.local/bin
mkdir -p ~/.local/bin
cp tool_extract/bin/tool.exe ~/.local/bin/

# 4. 添加 PATH（如果尚未存在）
grep -q 'local/bin' ~/.bashrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# 5. 验证
export PATH="$HOME/.local/bin:$PATH"
tool --version
```

## 针对特定工具的 Linux 静默安装

对于以 deb/rpm 分发的工具（如 Codex CLI），如果本地有 `docker`:

```bash
# 方法: 在 Docker 容器中下载并解压 deb，再提取二进制
# 不依赖本地 apt/dpkg（可能缺失或受限）
```

## 本次会话案例: gh CLI

```bash
# 下载
curl -L -o /tmp/gh.zip "https://github.com/cli/cli/releases/download/v2.69.0/gh_2.69.0_windows_amd64.zip"

# 解压
unzip -o /tmp/gh.zip -d /tmp/gh_extract

# 安装
mkdir -p ~/.local/bin
cp /tmp/gh_extract/bin/gh.exe ~/.local/bin/

# PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# 验证
export PATH="$HOME/.local/bin:$PATH"
gh --version
# → gh version 2.69.0
```

**注意**：MSI 安装（`msiexec /i ... /quiet`）在 Git-Bash 中可能静默失败（exit code 103），原因可能是缺管理员权限。便携式 zip 不需要管理员。

## 本次会话案例: mcporter + Exa MCP

```bash
npm install -g mcporter
mcporter config add exa https://mcp.exa.ai/mcp
```

**配置路径陷阱**：`mcporter config add` 默认写入当前工作目录（如 `D:/Hermes agent/config/mcporter.json`），但 `agent-reach doctor` 检查的是 `~/.mcporter/mcporter.json`。解决方法：

```bash
mkdir -p ~/.mcporter
cp /d/Hermes\ agent/config/mcporter.json ~/.mcporter/mcporter.json
```

## 本次会话案例: yt-dlp JS runtime (Windows)

```bash
YT_CONFIG="$HOME/AppData/Roaming/yt-dlp/config"
mkdir -p "$(dirname "$YT_CONFIG")"
echo "--js-runtimes node" >> "$YT_CONFIG"
```

## 安装非 PyPI Python 包

当 `pip install <name>` 返回 "No matching distribution" 时，从 GitHub 源码安装：

```bash
pip install https://github.com/org/repo/archive/main.zip
# 或指定分支
pip install https://github.com/org/repo/archive/<branch>.zip
```

## Pitfalls

- **MSI 静默安装在 Git-Bash 中不可靠** — exit code 103 表示权限不足，不会报错。优先便携式 zip。
- **`which` vs `where`** — Git-Bash 中 `which` 有时找不到刚刚安装的 exe（PATH 缓存），用绝对路径验证：`~/.local/bin/tool.exe --version`
- **解压后目录名不固定** — 解压前先 `ls` 确认，或解压到独立目录再检查。
- **`~/.local/bin` 路径优先级** — 要确保该目录在 PATH 中出现在系统目录之前，否则可能调用到旧版本。
- **PATH 变更不自动传播** — 当前 bash 会话需要 `export PATH="$HOME/.local/bin:$PATH"` 才生效；新终端窗口或 `bash -l` 才读到 `.bashrc`。
- **Python pip 包安装后要运行其 CLI** — 如果 Python 包安装到 venv 中（如 Hermes 的 venv），其中的 CLI 工具只在激活该 venv 时可用。
