"""清理终端会话快照里的明文凭据（2026-09-13）。

问题：Hermes 的终端环境在 init_session 时执行 `export -p > hermes-snap-<sid>.sh`
（见 hermes-agent/tools/environments/base.py:373），把**整个登录 shell 环境**写盘。
Hermes 会把密钥注入终端进程环境，于是 `BINANCE_SECRET_KEY` / `TWITTER_AUTH_TOKEN`
等**明文落盘**在 ~/AppData/Local/hermes/cache/terminal/ 下。

`HERMES_REDACT_SECRETS=true` 只覆盖文本脱敏（agent/redact.py 的 redact_sensitive_text），
**不覆盖这条 shell 快照路径** —— 属于上游缺口，不能靠配置关掉。

本脚本的处置（可反复运行）：
  · 把快照里疑似凭据的变量值清空：`declare -x NAME="值"` → `declare -x NAME=""`
  · 保留变量名与文件结构，快照仍可被 bash source（不会打断会话）
  · 绝不打印任何值，只报键名与计数

用法：
    python scripts/maintenance/scrub_terminal_snapshots.py            # 预演
    python scripts/maintenance/scrub_terminal_snapshots.py --apply    # 落盘
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SNAP_DIR = (Path(os.environ["LOCALAPPDATA"]) / "hermes" / "cache" / "terminal")

# 疑似凭据的变量名（保守：宁可多清，也不放过明文密钥）
SUSPECT = re.compile(
    r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|APIKEY|API_BASE|AUTH)", re.IGNORECASE)
# 明确不动的（不是凭据，清掉还会引发副作用）
ALLOW = {
    "PATHEXT", "SSH_AUTH_SOCK", "GPG_AGENT_INFO", "KEYBOARD", "MONKEYTYPE",
    # Hermes 自身的开关/配置：清空 HERMES_REDACT_SECRETS 等于**关掉脱敏**，会更糟
    "HERMES_REDACT_SECRETS",
}
# 名字里带这些后缀的是端点/地址，不是凭据
NOT_SECRET_SUFFIX = ("_BASE", "_BASE_URL", "_API_BASE", "_ENDPOINT", "_URL",
                     "_HOST", "_PORT", "_ADDRESS")
LINE = re.compile(r'^(declare -x|export)\s+([A-Za-z_][A-Za-z0-9_]*)=("?)(.*)$')


def main() -> int:
    apply = "--apply" in sys.argv
    if not SNAP_DIR.is_dir():
        print(f"快照目录不存在：{SNAP_DIR}")
        return 0

    files = sorted(SNAP_DIR.glob("hermes-snap-*.sh"))
    if not files:
        print("没有快照文件。")
        return 0

    total_redacted = 0
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except OSError as exc:
            print(f"  {path.name}: 读取失败 {exc}")
            continue
        hits: list[str] = []
        out: list[str] = []
        for raw in lines:
            line = raw.rstrip("\n")
            m = LINE.match(line)
            if not m:
                out.append(raw)
                continue
            name, value = m.group(2), m.group(4).rstrip('"')
            is_not_secret = (name.upper().endswith(NOT_SECRET_SUFFIX)
                             or name.upper().startswith("HERMES_"))
            if (not value or name in ALLOW or not SUSPECT.search(name)
                    or is_not_secret):
                out.append(raw)
                continue
            # 保留变量名，值清空 —— 既除秘又保持可 source
            out.append(f'{m.group(1)} {name}=""\n')
            hits.append(name)
        if hits:
            total_redacted += len(hits)
            if apply:
                path.write_text("".join(out), encoding="utf-8")
            verb = "已清空" if apply else "将清空"
            print(f"  {path.name}: {verb} {len(hits)} 个凭据变量 → {', '.join(sorted(set(hits)))}")
        else:
            print(f"  {path.name}: 无凭据变量")

    verb = "已清理" if apply else "将清理"
    print(f"\n{verb} {len(files)} 个快照，共 {total_redacted} 处凭据值。")
    if not apply:
        print("（预演模式，未改盘；确认后加 --apply）")
    else:
        print("注意：Hermes 每条新会话都会重建快照，这是**一次性清理**；"
              "根治需上游在 base.py 的 `export -p` 路径上加脱敏。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
