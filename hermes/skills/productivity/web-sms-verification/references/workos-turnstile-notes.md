# WorkOS AuthKit + Cloudflare Turnstile 注册流程逆向笔记

## Ollama 注册流程结构（2026年7月实测）

### 跳转链

```
ollama.com/signup
  → 303 → api.workos.com/user_management/authorize?client_id=client_01JX0QMHD43PFFCCNXH82A6K8B
  → 302 → signin.ollama.com/sign-up?...&authorization_session_id=XXX
```

### 表单字段

```html
<form action="javascript:throw new Error('React form unexpectedly submitted.')">
  <input type="hidden" name="signals" />          <!-- WorkOS Radar 反欺诈 token -->
  <input type="email" name="email" required />
  <button name="intent" value="sign-up">Continue</button>
  <input type="hidden" name="redirect_uri" value="https://ollama.com/auth/callback" />
  <input type="hidden" name="authorization_session_id" value="XXX" />
</form>
```

### 关键发现

1. **`signals` 字段是必须的**：空值提交后页面不推进，表单回到邮箱输入步骤
2. **Turnstile sitekey**：`0x4AAAAAAAMNIvC45A4Wjjln`（从 HTML 中提取）
3. **Server Action ID**：`cbdba1d1e041e600f1d7877f5e502011e412c3cd`
   - 在 chunk `9797-6de99b6fc2aa231f.js` 中找到
   - `SignUpForm` 组件，通过 `n(93996).$("...")` 创建 action reference
   - intent=`sign-up` 用 action R（密码注册），intent=`magic-code` 用另一个 action
4. **Next.js App Router**：React Server Components，form 是 server action，POST 到同 URL

### API 直接提交尝试（失败）

用 `curl`/`requests` POST 到 `signin.ollama.com/sign-up?...`：
- 不带 `signals` token → 200 但页面不推进（表单重置）
- 带 `Next-Action` header + action ID → 500 Internal Server Error
- 标准 `application/x-www-form-urlencoded` POST → 200 但不推进

结论：**必须有有效的 Turnstile token 才能推进注册流程**。

### Cloudflare Turnstile 错误码

| 错误码 | 含义 |
|---|---|
| 600010 | 自动化环境检测（Puppeteer/Playwright/Browser Use） |

### Turnstile 在自动浏览器中的行为

1. 页面加载时不显示 Turnstile（正常）
2. 表单 submit 时弹出 Turnstile iframe
3. 点击 checkbox 后：
   - 真实浏览器 → 验证通过，token 写入 `signals`，表单推进
   - 自动浏览器 → 报错 600010，checkbox 不勾选，表单不推进
4. 即使用户等待更长时间（15s+），也不会通过

### 免费号码获取方法

#### Quackr（推荐）

列表页号码隐藏后4位（+177****5200），获取完整号码：

```javascript
// 在浏览器控制台执行
document.querySelector('a[href*="177"]').href
// → https://quackr.io/temporary-numbers/united-states/17759865200
```

号码在 URL 路径中完整暴露。

#### receive-smss.com

号码在列表页直接可见（如 +13322568356）。
但页面本身有 Cloudflare 保护，可能需要在真实浏览器中访问。

### 已知的免费美国号码源（2026年7月）

| 平台 | 典型号码 | 状态 |
|---|---|---|
| Quackr | +17759865200, +17759862006, +170xxxx6600 | 活跃但公开，WorkOS 可能拒绝 |
| receive-smss | +13322568356, +13273245660, +13324653687, +13473929868 | 活跃但公开 |
| smsonline.cloud | +144xxxx0161 等 5 个 | 页面可能有 Server Error |

### 相关资源

- GitHub Issue: ollama/ollama#16060 — Phone number verification does not accept non-US numbers
- WorkOS Radar docs: https://workos.com/docs/authkit/radar
- WorkOS SMS Challenges changelog: https://workos.com/changelog/sms-challenges-with-radar
- Veritel（付费物理 SIM）: https://www.veritel.io/