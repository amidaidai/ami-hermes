---
name: web-sms-verification
description: >
  Web 服务注册时的 SMS/手机号验证绕过 — 当用户没有手机号或不想暴露真实号码时，
  用免费虚拟美国号码完成注册。覆盖免费接码平台选型(Quackr/receive-smss/smsonline)、
  验证系统识别(WorkOS Radar/Twilio)、免费号被拒时的付费 fallback(Veritel)、
  Cloudflare Turnstile 在自动浏览器中的限制、以及全自动 vs 手动操作的分界线。
  适用于：注册 Ollama/OpenAI/交易所/API 服务等需要手机验证的平台。
tags:
  - sms-verification
  - phone-verification
  - virtual-number
  - account-registration
  - cloudflare-turnstile
  - workos
---

# Web SMS 验证绕过

## 触发条件

- 用户要注册某服务但"没有手机号"
- 用户不想用真实号码注册
- 用户要求"帮我自动注册"一个需要 SMS 验证的账号
- 注册流程卡在手机号验证步骤

## 核心判断：验证系统类型

注册前先搞清楚目标服务用什么验证系统，决定免费号能不能用：

| 系统 | 特征 | 免费虚拟号可用性 |
|---|---|---|
| **WorkOS Radar** | signin.xxx.com 域名、只接受美国号码、Radar SMS challenge | 低 — 主动屏蔽已知虚拟/一次性号码 |
| **Twilio Verify** | 支持 E.164 国际号码 | 中 — 部分虚拟号可过 |
| **自建 SMS** | 直接用短信网关 | 高 — 多数虚拟号可过 |

### 如何识别 WorkOS Radar

1. 注册页 URL 跳转到 `signin.<domain>.com`（WorkOS AuthKit 托管）
2. 页面有 Cloudflare Turnstile 验证框
3. 表单含 hidden input `name="signals"`（Radar 反欺诈信号）
4. 只接受 +1 美国号码格式
5. 错误提示 "This phone number can't be verified. Please try a different number."

## 免费接码平台

### 平台对比

| 平台 | URL | 注册需求 | 号码隐藏 | 可靠性 |
|---|---|---|---|---|
| **Quackr** | quackr.io/temporary-numbers/united-states | 无需注册 | 页面隐藏后4位，需 JS 获取 | 中高 |
| **receive-smss.com** | receive-smss.com | 无需注册 | 号码直接可见 | 中（Cloudflare 保护页） |
| **smsonline.cloud** | smsonline.cloud/zh/country/United%20States | 无需注册 | 号码隐藏后4位 | 中 |

### 操作流程

1. 打开接码平台，选美国（+1）号码
2. 号码在列表页可能部分隐藏（+177****5200），需点进详情页或用 JS 提取完整号码
3. 在目标注册页填入号码（格式：+1XXXXXXXXXX）
4. 回接码平台等 SMS，通常 8 秒~10 分钟到达
5. 填回验证码完成注册

### 免费号被拒的处理

WorkOS Radar 会屏蔽公开虚拟号。如果提示 "This phone number can't be verified"：
1. 换同一平台的另一个号码重试
2. 换另一个接码平台
3. 如果 3~4 个号都被拒，基本说明该服务屏蔽了所有公开虚拟号 → 走付费方案

## 付费 Fallback：Veritel.io

当免费号被拒时推荐。特点：

- **物理 SIM 卡**（非虚拟号），通过率高
- 明确支持 Ollama 等 350+ 服务
- $0.84/次（Ollama），支持加密货币+信用卡
- 95% 送达率，不成功自动退款
- 一次性使用，隐私保护
- URL：https://www.veritel.io/register

### Veritel 操作流程

1. 注册 Veritel 账号
2. 充值（卡或加密货币）
3. 选 USA（+1）→ 服务选目标平台名
4. 付款拿号码 → 填入注册页
5. Veritel 面板等 SMS（15分钟窗口）
6. 填入验证码

## Cloudflare Turnstile 限制

### 关键事实

Cloudflare Turnstile 在自动浏览器（Browser Use / Puppeteer / Playwright）中会被检测：
- **错误码 600010** = 自动化环境检测
- 每次 form submit 都会弹出 Turnstile 验证
- 在自动浏览器中点击验证框后，验证不会通过
- Turnstile token 是 Cloudflare 服务端签发，无法通过 API/curl 模拟

### 应对策略

- **Turnstile 在真实浏览器中通常会静默通过**（无感验证）
- 自动浏览器无法绕过 → 需要用户在自己的真实浏览器中操作
- 可以帮用户准备号码 + 收码页面链接，但最后提交须手动

### 判断是否卡在 Turnstile

1. 浏览器控制台出现 `[Cloudflare Turnstile] Error: 600010`
2. 表单提交后页面不推进（停在邮箱输入步骤）
3. `signals` hidden input 值为空

## 全自动 vs 手动的分界线

| 步骤 | 能否自动 | 原因 |
|---|---|---|
| 查找免费号码 | ✅ 自动 | 接码平台无需登录 |
| 提取完整号码 | ✅ 自动 | JS 或详情页可获取 |
| 在注册页填邮箱 | ✅ 自动 | 无验证 |
| 提交邮箱表单 | ❌ 手动 | Turnstile 验证 |
| 填密码 | ❌ 手动 | 需 Turnstile 通过后 |
| 填手机号 | ❌ 手动 | 需在上一步之后 |
| 接收验证码 | ✅ 自动 | 接码平台公开可见 |
| 填验证码 | ❌ 手动 | 需在真实浏览器中 |

**结论**：如果目标服务有 Turnstile，帮用户准备好号码和收码链接，让用户在真实浏览器里手动完成注册。不要在自动浏览器里反复尝试点 Turnstile——浪费时间且不会成功。

## 已知服务验证情况

| 服务 | 验证系统 | 免费号可用 | 备注 |
|---|---|---|---|
| **Ollama** | WorkOS Radar + Turnstile | 低 | 只接受 +1，屏蔽虚拟号，GitHub Issue #16060 全球用户投诉 |
| **OpenAI** | 自建 + Twilio | 低 | 需要真实号码 |
| **Binance** | 自建 | 不适用 | 用户已有账号 |

## 给用户的交付格式

当需要手动操作时，给用户：
1. **准备好的免费号码**（完整 +1XXXXXXXXXX 格式）
2. **收码页面直链**（点击即可看 SMS）
3. **注册页面直链**
4. **简短步骤**（不超过 6 步）
5. **备选号码**（如果第一个被拒）