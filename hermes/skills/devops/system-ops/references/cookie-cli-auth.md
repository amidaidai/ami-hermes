# Cookie-based CLI 认证配置（会话案例）

本文件记录 Agent-Reach 安装和配置过程中涉及的 cookie-based CLI 工具认证方式。

## 案例：Agent-Reach 渠道配置

### 雪球 (Xueqiu) — Cookie 提取与配置

**配置方式**：利用 browser cookie（xq_a_token）通过 API 访问行情/热帖。

**自动化提取**：
```bash
agent-reach configure --from-browser chrome
```
自动化提取成功时，config.yaml 中会增加 `xueqiu_cookie` 字段。

**自动化提取失败时**（Chrome 127+ App-Bound 加密）：
1. 在 Chrome 中登录 `xueqiu.com`
2. 安装 Cookie-Editor 扩展（https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm）
3. 点 Cookie-Editor → Export → 复制 Header String
4. 将 Cookie 写入配置：
```python
from agent_reach.config import Config
cfg = Config()
cfg.set("xueqiu_cookie", "xq_a_token=xxx; ...完整 cookie 字符串...")
```

**验证**：
```bash
python -c "
import urllib.request, json
r = urllib.request.Request(
    'https://stock.xueqiu.com/v5/stock/batch/quote.json?symbol=SH000001',
    headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://xueqiu.com/'})
data = json.loads(urllib.request.urlopen(r).read())
print(data['data']['items'][0]['quote']['name'])
"
```
返回 `上证指数` 即配置成功。

### GitHub (gh CLI)

**安装方式**：portable zip（MSI 在 Git-Bash 静默失败）
- 版本：v2.69.0
- 路径：`~/.local/bin/gh.exe`
- 认证：`gh auth login` → 设备授权码 → 用户访问 https://github.com/login/device 输入 code
- 验证：`gh auth status` → scope 含 `repo`、`read:org`、`gist`

### Reddit (rdt-cli)

**安装**：
```bash
pip install 'git+https://github.com/public-clis/rdt-cli.git'
```

**Cookie 配置**：
用户从 Cookie-Editor 导出 Header String，包含 12 个 cookies。关键 cookie 是 `reddit_session`（JWT token）。

credential.json 格式（`~/.config/rdt-cli/credential.json`）：
```json
{
  "cookies": {
    "token_v2": "eyJ...JWT...XQ",
    "reddit_session": "eyJ...JWT...Eg",
    "csv": "2",
    "session_tracker": "...",
    "g_state": "{...}",
    "edgebucket": "...",
    "ads_cookie": "1",
    "csrf_token": "...",
    "eu_cookie": "{...}",
    "loid": "...",
    "reddit_chat_view": "closed",
    "reddit_supported_media_codecs": "video/avc,video/vp9"
  },
  "source": "manual:cookie-editor",
  "saved_at": 1234567890
}
```

**JWT 长度参考**：
- token_v2: 1309 字符（3 段：header.payload.signature）
- reddit_session: 729 字符（3 段）

**解析陷阱**：当用户在消息中粘贴超长 JWT，且消息中包含 `...` 截断时，`http.cookies.SimpleCookie` 可能只解析到截断前的少数 cookie。手动 `split(';')` 更可靠。

**验证**：
- `rdt status` → authenticated: true, username: "Appropriate-Swim4554"
- `rdt sub python --limit 3` → 返回 r/Python 帖子数据

### Twitter/X (twitter-cli)

**安装**：
```bash
pip install twitter-cli  # v0.8.5
```

**认证方式**：auth_token + ct0

两种配置方式：
1. `agent-reach configure twitter-cookies "auth_token=xxx; ct0=xxx"`（推荐）
2. 环境变量 `TWITTER_AUTH_TOKEN` + `TWITTER_CT0`

**注意**：Twitter 在中国大陆被墙，必须走代理。且有些工具只读小写 `http_proxy`（不读大写的 `HTTP_PROXY`），两者都要设置。

**验证**：
- `twitter status` → authenticated: true, user.id, username, screenName
- `twitter feed -n 3` → 返回时间线推文
- `twitter search "query" -n 2` → 返回搜索结果

### 全网语义搜索 (Exa via mcporter)

**安装**：
```bash
npm install -g mcporter
mcporter config add exa https://mcp.exa.ai/mcp
```

**配置路径陷阱**：`mcporter config add` 默认写入当前工作目录（如 `D:/Hermes agent/config/mcporter.json`），但 Agent-Reach doctor 检测的是 `~/.mcporter/mcporter.json`。需手动复制：
```bash
mkdir -p ~/.mcporter
cp /path/to/current/config/mcporter.json ~/.mcporter/mcporter.json
```

### YouTube (yt-dlp)

**JS runtime 配置**（Windows）：
```bash
YT_CONFIG="$HOME/AppData/Roaming/yt-dlp/config"
mkdir -p "$(dirname "$YT_CONFIG")"
echo "--js-runtimes node" >> "$YT_CONFIG"
```

## 代理配置

本环境中代理地址 `http://127.0.0.1:7897`，需同时设置：
```bash
export HTTP_PROXY="http://127.0.0.1:7897"
export HTTPS_PROXY="http://127.0.0.1:7897"
export http_proxy="http://127.0.0.1:7897"
export https_proxy="http://127.0.0.1:7897"
```

## Agent-Reach 渠道状态变更记录

| 步骤 | 操作 | 可用渠道数 | 新增 |
|------|------|:---------:|------|
| 初始安装 | `pip install https://github.com/Panniantong/agent-reach/archive/main.zip` | 4/13 | Web/V2EX/RSS/B站 |
| yt-dlp 配置 | JS runtime = node | 5/13 | YouTube |
| mcporter + Exa | npm + config add + 复制到 ~/.mcporter | 6/13 | 语义搜索 |
| gh CLI | portable zip 安装 | 6/13 | GitHub（待认证） |
| GitHub 认证 | 设备授权码 | 7/13 | GitHub |
| rdt-cli | pip install + cookie 写入 credential.json | 8/13 | Reddit |
| twitter-cli | pip install + agent-reach configure | 9/13 | Twitter |
