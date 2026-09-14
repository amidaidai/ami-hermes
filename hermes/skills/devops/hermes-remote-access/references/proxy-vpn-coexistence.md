# 代理 / VPN 环境下访问自托管 Hermes

适用：电脑跑 Clash（TUN 或系统代理），手机跑代理 App 或商业 VPN，同时要用手机访问自托管 Web UI。

## 分层：两个性质完全不同的冲突

| 层 | 性质 | 能否配置解决 |
|---|---|---|
| 电脑（Clash / 代理软件） | TUN 模式接管路由，把 Tailscale 的流量也劫走 | **能**，加分流规则 |
| 手机（代理 App / 商业 VPN） | Android/iOS 系统层只允许一个 VPN 同时激活 | **不能**，只能换思路绕 |

手机那条是系统限制，不是配置问题：手机上的 Clash、Shadowrocket、Stash、一键加速类 App 全都占用同一个 VPN 槽位。回答用户前先判断他遇到的是哪一层。

## 判断顺序（从最省事开始）

1. **手机和电脑同一个 WiFi？** → 不需要 Tailscale，也不存在冲突。Web UI 绑到局域网可达地址，手机开 `http://<电脑内网IP>:<端口>`。唯一小坑：Clash 的 TUN 偶尔拦内网访问，加 `IP-CIDR,192.168.0.0/16,DIRECT` 或临时关 TUN。
2. **只在家里用、偶尔出门？** → Tailscale + 手动切换代理（见下「路线二」）。
3. **经常在外面用？** → Tailscale + 电脑当 exit node（见下「路线一」）。
4. **手机不想装任何 VPN？** → Cloudflare Tunnel（见文末）。

## 电脑端：Clash 放行 Tailscale（TUN 模式必做）

```yaml
rules:
  - IP-CIDR,100.64.0.0/10,DIRECT,no-resolve      # Tailscale 自身 IP 段（CGNAT）
  - IP-CIDR6,fd7a:115c:a1e0::/48,DIRECT,no-resolve
  - DOMAIN-SUFFIX,ts.net,DIRECT                  # MagicDNS 域名
  - DOMAIN-SUFFIX,tailscale.com,DIRECT

dns:
  fake-ip-filter:                                # 伪 IP 模式必须加
    - "*.ts.net"
    - "*.tailscale.com"
```

要点与坑：

- 漏掉 `100.64.0.0/10` 的典型症状是「Tailscale 显示已连接但打不开页面」。
- **CGNAT 段冲突**：部分运营商光猫 / 内网地址池本身就发 `100.64.0.0/10`，会和 Tailscale 撞车。此时要给 Tailscale 换一个 IP 池，而不是继续调 Clash。
- 登录 / 控制面连不上时，可把 `tailscale.com` **临时**改成 `PROXY` 走 Clash 完成登录；数据面（UDP 直连 / DERP）不受这条影响，登录后再改回 DIRECT。
- v2rayN 这类缺 `route_exclude_address` 的客户端无法排除该段，只能改用支持排除项的实现。

## 手机端三条路

### 路线一：电脑当 exit node（免 root，首选）

手机只开 Tailscale，科学上网的流量交给电脑上的 Clash。**Windows 官方支持 advertise exit node**：

1. 电脑 Tailscale 客户端 → **Exit Node** → **Run as exit node**。
2. 管理后台 Machines 页找到该设备（会出现 **Exit Node** 徽章）→ 菜单 **Edit route settings** → 勾 **Use as exit node** → Save。
3. 手机 Tailscale 里选用该设备作为 exit node。

注意：

- **exit node 模式下官方那套 split-tunnel DNS 办法失效**——Tailscale 此时会像传统 VPN 一样设置激进防火墙规则，官方明确「exit nodes only support one VPN at a time」。
- 但 **Android 客户端 v1.70+ 支持分应用代理**，可以把抖音/银行等国内 App 排除出去，避免它们也绕回家。排除列表在客户端设置里直接配；「只让指定 App 走 tailnet」的白名单模式需要 MDM。
- 依赖电脑常开，且手机全量流量经电脑中转（P2P 打洞失败时受 DERP 带宽限制）。

### 路线二：手动切换（零配置）

关键判断：**连自己电脑上的 Hermes 走内网，根本不需要代理**。代理是手机自己上外网用的，和访问 Hermes 是两件事——两个需求本不必同时满足。需要翻墙时切过去、用完切回来。iOS 基本就是这个答案。

### 路线三：root 后共存（最彻底，最麻烦）

tailscaled 以 `userspace-networking` 模式跑（不建 TUN、不改防火墙），在本地开 SOCKS5，再让 Clash 把 Tailscale 网段交给它：

```bash
tailscaled --tun=userspace-networking --statedir=.cache -socks5-server=localhost:5432
tailscale up
```

```yaml
proxies:
  - name: tailscale
    type: socks5
    server: 127.0.0.1
    port: 5432
rules:
  - IP-CIDR,100.64.0.0/10,tailscale,no-resolve
```

代价：**没有 MagicDNS**，只能用 Tailscale IP 访问，不能用机器名；userspace 模式下标准 `ping` 不通，要用 `tailscale ping`。

## 用户在中国大陆时的额外现实

- Tailscale 官方 DERP 中继**没有大陆节点**，一旦打洞失败会绕道境外，慢到不可用。
- 好消息：手机（4G/5G）与电脑（家宽）都在国内时，NAT 打洞通常成功，走国内链路，速度正常。**先按能打洞成功来配，别一上来就吓用户说会慢。**
- 确实打不通再考虑自建 DERP：国内 1核1G 云主机 + Docker，延迟可压到 20ms 级。

## 备选：完全避开 VPN 槽位 —— Cloudflare Tunnel

电脑跑 `cloudflared` 把 Web UI 发布成 HTTPS 域名，**手机什么都不用装**，浏览器直接开，手机上的代理 App 照常用。代价：要用 Cloudflare Access（免费档够）做访问鉴权，且手机访问该域名可能得走代理。适合「手机不想动 VPN 设置」的用户。

## 结论式回答模板

1. 一句结论：「会互相抢占，但分两层，电脑端可配、手机端是系统硬限制」。
2. 给决策表（同 WiFi / 偶尔出门 / 经常出门 / 不想装 VPN）各对应一条路。
3. 诚实列代价：原生 Windows 限制、exit node 带宽与依赖、打洞失败备用路径。
