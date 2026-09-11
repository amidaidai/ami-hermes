# Windows Git-Bash 安装并验证 Python Web 工具

适用场景：用户给出 GitHub 上的 Python/FastAPI/Playwright 小工具，要求“安装这个”。目标不是只克隆，而是安装、启动、验证页面可访问。

## 推荐流程

1. 克隆到长期 projects 目录，例如 `D:/Hermes agent/projects/<repo>`。
2. 创建项目本地虚拟环境：
   ```bash
   cd '/d/Hermes agent/projects/<repo>'
   python -m venv .venv
   source .venv/Scripts/activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. 如果依赖 Playwright，安装浏览器运行时：
   ```bash
   python -m playwright install chromium
   ```
   下载遇到一次 `ECONNRESET` 可重试；Playwright 会自动换源/续跑，最终成功才算完成。不要把一次网络断开记录成“工具不可用”。
4. 启动 Web 服务用 Hermes background process，长期运行类服务不要 shell 级 `&`：
   ```bash
   python web.py
   ```
   使用 `background=true`，并用 `watch_patterns` 监听 `Uvicorn running on` 或 `Application startup complete`。
5. 验证至少两层：
   - `curl http://127.0.0.1:<port>/` 看 HTTP/HTML；注意 `HEAD` 可能返回 405，不等于服务坏。
   - 用 Playwright 打开页面并读 `page.title()` / `body.inner_text()`，最好保存截图到 outputs 目录。
6. 最终回复给出：安装路径、启动命令、访问地址、真实验证结果、截图路径。

## Starlette/FastAPI TemplateResponse 兼容坑

现象：服务启动成功，但访问首页返回 `Internal Server Error`，日志出现：

```text
TypeError: unhashable type: 'dict'
... starlette.templating.py ... get_template(name)
```

常见原因：项目代码仍使用旧式位置参数：

```python
return templates.TemplateResponse("index.html", {"request": request})
```

在新 Starlette/FastAPI 组合中可能被解析错。修复为显式关键字参数：

```python
return templates.TemplateResponse(request=request, name="index.html", context={})
```

或按当前 Starlette 版本签名使用 `request=...`、`name=...`、`context=...`。修复后重启服务并重新验证页面。