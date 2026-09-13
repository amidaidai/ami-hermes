"""`.env` 读取方盘点（只读）—— 决定哪些密钥能从 .env 移走以收窄泄露面。

背景：终端快照泄露的根因是「密钥进了 Hermes 进程环境」。而进环境的是 `~/.hermes/.env`。
若某个密钥**没有任何消费者**，或只有我们自己的脚本读它（那些脚本走 `hermes/secrets/*.txt`），
就可以从 `.env` 移走 → 不再进进程环境 → 从源头缩小暴露面。

分类：
  PLUGIN  被 Hermes 插件/provider 读取 → 必须留在 .env（或需插件级替代），风险最高、优先单独处理
  OURS    只被本仓库脚本/技能读 → 可迁到 hermes/secrets/
  UNUSED  无消费者 → 可直接删
  PLATFORM 平台 token（Telegram/Discord/Feishu…）→ gateway 必须读，留在 .env

绝不打印任何密钥值。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ENV_FILE = Path(os.environ["LOCALAPPDATA"]) / "hermes" / ".env"
HERMES = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "hermes-agent"
REPO = Path("D:/Hermes agent")

SUSPECT = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.IGNORECASE)
PLATFORM_HINT = re.compile(r"^(TELEGRAM|DISCORD|SLACK|WHATSAPP|FEISHU|MATTERMOST|WEIXIN|SIGNAL)")

# 只扫这些子树，避免全盘 grep 太慢
PLUGIN_DIRS = [HERMES / "plugins", HERMES / "agent", HERMES / "tools", HERMES / "hermes_cli"]
OUR_DIRS = [REPO / "scripts", REPO / "hermes" / "scripts",
            Path(os.environ["LOCALAPPDATA"]) / "hermes" / "skills" / "trading"]


def keys_from_env() -> list[str]:
    out = []
    for line in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name = line.split("=", 1)[0].strip()
        if SUSPECT.search(name) and not name.startswith("HERMES_"):
            out.append(name)
    return sorted(set(out))


def grep_count(name: str, roots: list[Path]) -> int:
    """粗粒度计数：在给定子树里出现该键名的文件数（不读值）。"""
    hits = 0
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix not in (".py", ".js", ".ts", ".mjs", ".yaml", ".yml", ".json", ".md", ".sh", ".cmd"):
                continue
            try:
                if name in p.read_text(encoding="utf-8", errors="replace"):
                    hits += 1
            except OSError:
                continue
    return hits


def main() -> int:
    keys = keys_from_env()
    print(f"`{ENV_FILE}` 里的凭据类变量: {len(keys)} 个（只列名，不读值）\n")

    rows = []
    for k in keys:
        plug = grep_count(k, PLUGIN_DIRS)
        ours = grep_count(k, OUR_DIRS)
        if PLATFORM_HINT.match(k):
            cat = "PLATFORM"
        elif plug:
            cat = "PLUGIN"
        elif ours:
            cat = "OURS"
        else:
            cat = "UNUSED"
        rows.append((cat, k, plug, ours))

    order = {"PLUGIN": 0, "PLATFORM": 1, "OURS": 2, "UNUSED": 3}
    rows.sort(key=lambda r: (order[r[0]], r[1]))
    print(f"{'分类':<10}{'变量':<34}{'插件侧引用':<10}{'我方引用'}")
    print("-" * 78)
    for cat, k, plug, ours in rows:
        print(f"{cat:<10}{k:<34}{plug:<10}{ours}")

    print("\n说明：")
    print("  PLUGIN  —— Hermes 插件/provider 从 env 读，移走会破坏功能 → 风险最高，需单独方案")
    print("  PLATFORM—— 平台 token，gateway 必须读 → 只能留在 .env")
    print("  OURS    —— 似乎只被我方脚本引用（我方脚本本就走 hermes/secrets/）→ 可评估迁出")
    print("  UNUSED  —— 没找到消费者 → 可考虑删除")

    out = Path("D:/Hermes agent/data/maintenance/env_reader_inventory.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"env_file": str(ENV_FILE),
         "counts": {c: sum(1 for r in rows if r[0] == c) for c in order},
         "rows": [{"category": c, "name": k, "plugin_refs": p, "our_refs": o}
                  for c, k, p, o in rows]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
