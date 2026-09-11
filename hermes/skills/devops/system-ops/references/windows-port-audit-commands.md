# Windows Port Security Audit — Commands Reference

All commands via `powershell -Command "..." | cat` in MSYS/Git Bash.

## Step 1: Listening Ports with Process Info

```powershell
# All listening ports with process name and path
Get-NetTCPConnection | Where-Object { $_.State -eq 'Listen' } | ForEach-Object {
  $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
  [PSCustomObject]@{Port=$_.LocalPort; PID=$_.OwningProcess; Process=$proc.ProcessName; Path=$proc.Path}
} | Sort-Object Port -Unique | Format-Table -AutoSize
```

## Step 2: Binding Addresses (Critical for Risk Assessment)

```powershell
# Shows which ports are externally reachable vs localhost-only
Get-NetTCPConnection | Where-Object { $_.State -eq 'Listen' } | ForEach-Object {
  $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
  [PSCustomObject]@{LocalAddr=$_.LocalAddress; Port=$_.LocalPort; PID=$_.OwningProcess; Process=$proc.ProcessName}
} | Sort-Object Port -Unique | Format-Table -AutoSize
```

**Binding address interpretation:**
- `0.0.0.0` or `::` → reachable from ALL interfaces (external)
- `192.168.x.x` → reachable from LAN
- `127.0.0.1` or `::1` → localhost only (safe)
- IPv6 global (`240e:...`, `2001:...`) → reachable from internet if no firewall

## Step 3: Firewall Rules per Port

```powershell
# Check specific ports for firewall rules
Get-NetFirewallRule | Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' } | ForEach-Object {
  $pf = $_ | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue
  if ($pf.LocalPort -and $pf.LocalPort -ne 'Any') {
    [PSCustomObject]@{Name=$_.DisplayName; Action=$_.Action; Port=$pf.LocalPort; Protocol=$pf.Protocol; Profile=$_.Profile}
  }
} | Format-Table -AutoSize
```

```powershell
# Check all rules for a specific process/app
Get-NetFirewallRule | Where-Object { $_.DisplayName -like '*360*' -and $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' } | ForEach-Object {
  $pf = $_ | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue
  [PSCustomObject]@{Name=$_.DisplayName; Action=$_.Action; Port=$pf.LocalPort; Protocol=$pf.Protocol; Profile=$_.Profile}
} | Format-Table -AutoSize
```

```powershell
# Find overly permissive rules (Allow Any port on Public profile)
Get-NetFirewallRule | Where-Object {
  $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow'
} | ForEach-Object {
  $pf = $_ | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue
  if ($pf.LocalPort -eq 'Any') {
    [PSCustomObject]@{Name=$_.DisplayName; Action=$_.Action; Port=$pf.LocalPort; Protocol=$pf.Protocol; Profile=$_.Profile}
  }
} | Format-Table -AutoSize
```

## Step 4: Network Category

```powershell
# Current network profile (Public = most restrictive, Domain = most permissive)
Get-NetConnectionProfile | Select-Object Name,InterfaceAlias,NetworkCategory | Format-Table -AutoSize
```

## Step 5: Firewall Profile Status

```powershell
Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction | Format-Table -AutoSize
```

## Step 6: Specific App Rules

```powershell
# Find rules for a specific app (e.g., Clash Verge, Hermes Studio)
Get-NetFirewallRule | Where-Object { $_.DisplayName -like '*verge*' -or $_.DisplayName -like '*Hermes*' } |
  Select-Object DisplayName,Enabled,Direction,Action,Profile | Format-Table -AutoSize
```

## Decision Matrix

| Binding | Firewall Rule | Network=Public | Actual Status |
|---------|--------------|----------------|---------------|
| `0.0.0.0`/`::` | No rule | Public | ✅ Blocked (default deny) |
| `0.0.0.0`/`::` | Allow specific port | Public | ⚠️ Open for that port |
| `0.0.0.0`/`::` | Allow Any port | Public | 🔴 Wide open |
| `0.0.0.0`/`::` | Block rule exists | Any | ✅ Blocked (Block wins) |
| `127.0.0.1`/`::1` | Any | Any | ✅ Safe (localhost only) |

## Common Risk Patterns

1. **Security software Allow Any rules**: 360安全卫士, 火绒, etc. often create `Allow Any TCP/UDP` on Public profile for their executables. This effectively disables the firewall for those processes.

2. **Proxy tools (Clash Verge, v2rayN)**: May create Allow Any rules exposing proxy ports to the network.

3. **UPnP port 2869**: Has explicit Allow rule in Windows defaults. UPnP has known vulnerabilities — disable if not needed.

4. **SMB 445 / RPC 135 / NetBIOS 139**: Usually listening on `::` but typically blocked by default firewall on Public profile. Verify no explicit Allow rules exist.

5. **Hermes Studio / Web UI**: May have both Allow and Block rules — Block takes precedence, but clean up the Allow rule to avoid confusion.
