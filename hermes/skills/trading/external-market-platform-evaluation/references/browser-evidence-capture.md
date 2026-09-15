# 浏览器取证 / 取数手法（外部平台评估与接入）

无头浏览器在这类评估里同时是证据来源和数据通道。下面四条按使用顺序排列。

## 1. 判登录墙：只看最终落点 URL

无 cookie 打开目标链接，然后读 `location.href`：

```python
new_tab(url); wait_for_load()
print(js("location.href"))   # 跳到 /login?act=xxx 或 /signin 就是登录墙
```

- 登录墙 ≠ 链接失效、≠ 平台不可用。写结论时区分「打不开」与「要凭据」。
- `web_extract` 抓回登录页内容，是同一信号的旁证，但以最终 URL 为准。
- 交付物：留一张落点页面截图当证据（见第 4 条）。

## 2. 无头 UA 被边缘拦截 → 伪装正常 Chrome UA

症状：同一 URL 用 `curl`（正常 UA）返回 200，在无头浏览器里却是 nginx 404 或**空 200**（`size_download=0`）。

判定三分法（一次跑完，别猜）：

```bash
u="<目标URL>"
curl -s -o /dev/null -w "direct:%{http_code} len=%{size_download}\n" --max-time 10 "$u"
curl -s -o /dev/null -w "proxy:%{http_code} len=%{size_download}\n" --max-time 15 -x http://127.0.0.1:7897 "$u"
curl -s -o out.html -w "UA-headless:%{http_code} len=%{size_download}\n" -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/152.0.0.0 Safari/537.36" --compressed "$u"
curl -s -o out.html -w "UA-chrome:%{http_code} len=%{size_download}\n"   -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36" --compressed "$u"
```

- 直连与代理都对、只有 headless UA 404 → UA 拦截，不是网络问题（本机境外源需代理 `127.0.0.1:7897`）。
- 修法：导航**之前**下发 UA 覆写，后续所有请求都带上：

```python
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
cdp('Network.setUserAgentOverride', userAgent=UA, acceptLanguage="zh-CN,zh;q=0.9", platform="Win32")
goto_url(url)
```

## 2b. 域名解析到 127.0.0.1 ≠ 平台自建/不可用

本机代理（fake-ip / 系统代理）会把境外域名解析成 `127.0.0.1`，`nslookup` 的结果与 curl 的 `%{remote_ip}` 都只是**代理地址**，不是站点地址。

- 判据：`www.` 子域解析到真实公网 IP、且 `curl -x http://127.0.0.1:7897` 能取到内容 → 是代理直通，站点正常。
- 本机脚本取数必须**显式建代理 opener**：`urllib.request.build_opener(ProxyHandler({'http':'http://127.0.0.1:7897','https':…}))`；用 `ProxyHandler({})` 关代理会得到 `WinError 10061 目标计算机积极拒绝`，别把这个当成「站点不可访问」。
- curl 走代理时 `remote_ip` 恒为 `127.0.0.1`，因此**不能用它判 CDN/边缘**。

## 3. 抓 SPA 的 XHR JSON（含首屏请求）

首屏请求在页面脚本之前发出，**先 hook 再加载**才抓得到：

```python
hook = r"""
(() => {
  if (window.__capInstalled) return; window.__capInstalled = true; window.__cap = [];
  const of = window.fetch;
  window.fetch = async function(...a) {
    const res = await of.apply(this, a);
    try { const u = (typeof a[0]==='string') ? a[0] : (a[0] && a[0].url);
      if (u && u.includes('<目标域名>')) { const c = res.clone(); c.text().then(t => window.__cap.push({u, s: res.status, t: t.slice(0, 50000)})); }
    } catch(e) {}
    return res;
  };
  const oOpen = XMLHttpRequest.prototype.open, oSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(m, u, ...r) { this.__u = u; return oOpen.call(this, m, u, ...r); };
  XMLHttpRequest.prototype.send = function(...a) {
    this.addEventListener('load', () => { try { if (this.__u && this.__u.includes('<目标域名>')) window.__cap.push({u:this.__u, s:this.status, t:String(this.responseText).slice(0,50000)}); } catch(e){} });
    return oSend.apply(this, a);
  };
})()
"""
cdp('Page.addScriptToEvaluateOnNewDocument', source=hook)
goto_url(url); wait_for_load(); time.sleep(15)      # 让首屏请求跑完
print(js("(() => JSON.stringify((window.__cap||[]).map(c=>[c.s, c.u.slice(0,150), c.t.length])))()"))
```

从 `performance.getEntriesByType('resource')` 里过滤 `initiatorType in ('xmlhttprequest','fetch')` 可以快速列出候选端点，但拿不到响应体 —— 要体必须用上面的 hook。

**大多数情况下不必装 hook**（更省事、更抗重置）：

```python
ensure_real_tab()
goto_url(url); wait_for_load(); time.sleep(12)      # 让首屏请求跑完
print(js("JSON.stringify(performance.getEntriesByType('resource')"
         ".map(e=>e.name).filter(n=>!n.match(r'\\.(js|css|png|svg|woff2?|jpg|webp|ico)(\\?|$)')))"))
```

- hook 装完再 `location.reload()` 会被清掉；会话标签也可能被重置成 `about:blank`。重载后先 `ensure_real_tab()` 再 `goto_url()`，不要指望 hook 跨重载存活。
- 端点清单（含查询串与筛选参数）足够在 Python 侧重放；拿到清单后立刻做第 4 条的脱离浏览器实测。

**端点在 minified bundle 里搜不到时**：`search_files` 对单行大 bundle 常返回 0 —— 改用 Python 正则扫 `re.findall(r"/api/[\w/.-]+", src)`。路由与参数名常由模板串拼装，所以还要抓 **分块文件名**（形如 `execcostApi-<hash>.js`，从首屏 HTML 的 `modulepreload` / 资源清单里找），读其中的 `${base}/xxx`、`URLSearchParams({...})` 与 `?${e}` 调用，才能还原端点与参数名（如 `asset=` / `days=` / `sizes=`）。

## 4. 判断「抓到的接口能否脱离浏览器用」——必须实测

把捕获到的**完整 URL**（含签名参数）拿到 Python 侧重放，再测去掉签名参数/换成 dummy 两种：

- 正常结构化 JSON → 可以做成脚本数据源，记录鉴权头与限频。
- 只有 `{"code":"0","success":true}` 之类空壳、或 `40001` 签名错 → 服务端要一次性签名/会话，**不要承诺脚本可取**；只能浏览器内取数（读页面已解密的数值/图表）。
- 响应里出现明显不可读的长 base64 字段（`data`）＝ 载荷加密，同理。

这一步是「接入可行性」的唯一判据：没重放成功前，一律按「只能人眼看」写结论。

## 5. 免登录 JSON 数据站的批量取数配方（多标的）

- 每个标的一两个端点，**串行会撞工具超时**（>5 分钟就白跑）→ `ThreadPoolExecutor(max_workers=8)` 预取进内存缓存，分析函数只读缓存；一个标的的耗时端点（成本、全场所报价）只取一次。
- 取数封装：浏览器 UA + `Referer` 指向平台对应页面 + 显式代理 opener；失败重试 3-5 次（退避 2/4/6…秒），境外源 TLS 抖动是常态。
- **取不到就标 `?` / `unavailable`，绝不当 0**；成本缺失时不要输出回本天数这类派生结论（宁缺勿假）。
- 落档 `json` + `csv`（`encoding='utf-8-sig'`，Excel 直接可读）双份，附 `generated_at` 与本次过滤条件，便于下轮对比而不是重新猜口径。
- 参考实现：`scripts/perp_dex_arb_scan.py`（同目录技能的 scripts/）。

## 6. 证据截图归档

```python
print(capture_screenshot())          # 返回 png 路径
```

- 拿去当证据前先用 `vision_analyze` 确认图里到底是什么页面（路径/图里没有地址栏）。
- 归档到 `D:/Hermes agent/outputs/diag/<平台>_<事项>_<日期>.png`，回复里用 Markdown 引用本地绝对路径。
