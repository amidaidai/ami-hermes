"""精确复核：每个候选键有没有**代码**消费者（排除 .md 文档与我的审计笔记）。

上一篇盘点把「只出现在我的文档里」也算成了「我方引用」，会误判为有消费者。
本脚本只扫代码类文件（.py/.js/.ts/.mjs/.yaml/.yml/.json/.sh/.cmd），
排除 .md，给出每个键的真实消费者清单，用于决定能否从 .env 移除。
绝不读取或打印任何密钥值。
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(os.environ["LOCALAPPDATA"]) / "hermes" / ".env"
HERMES = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "hermes-agent"
REPO = Path("D:/Hermes agent")
SKILLS = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "skills"

CODE_SUFFIX = {".py", ".js", ".mjs", ".cjs", ".ts", ".yaml", ".yml", ".json", ".sh", ".cmd", ".ps1"}
SCAN_ROOTS = [HERMES / "plugins", HERMES / "agent", HERMES / "tools", HERMES / "hermes_cli",
              HERMES / "hermes-agent-main" / "plugins", HERMES / "venv" / "Lib" / "site-packages" / "litellm",
              REPO / "scripts", REPO / "hermes" / "scripts", SKILLS / "trading"]

CANDIDATES = [
    "ANYSEARCH_API_KEY", "BAI_API_KEY", "FELO_API_KEY", "METASO_API_KEY",
    "POLYMARKET_RELAYER_API_KEY", "POLYMARKET_RELAYER_API_KEY_ADDRESS",
    "RELAYER_API_KEY", "RELAYER_API_KEY_ADDRESS",
    "CG_API_KEY", "COINGECKO_DEMO_API_KEY",
    "BINANCE_API_KEY", "BINANCE_SECRET_KEY", "BRAVE_API_KEY",
]


def find_consumers(key: str) -> list[str]:
    hits: list[str] = []
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in CODE_SUFFIX:
                continue
            if "node_modules" in p.parts or "__pycache__" in p.parts:
                continue
            # 排除自指：审计脚本自身含这些键名，会被误当成消费者；
            # 也排除 data/ 下的 JSON 缓存（那是产物，不是代码）
            if p.name.startswith(("env_key_consumer_audit", "env_reader_inventory",
                                  "api_source_health_probe", "scrub_terminal_snapshots")):
                continue
            if "data" in p.parts:
                continue
            try:
                if key in p.read_text(encoding="utf-8", errors="replace"):
                    rel = str(p).replace(str(HERMES), "<hermes>").replace(str(REPO), "<repo>")
                    hits.append(rel)
            except OSError:
                continue
    return hits


env_names = {
    ln.split("=", 1)[0].strip()
    for ln in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    if "=" in ln and not ln.strip().startswith("#")
}

print(f"{'变量':<34}{'.env 中存在':<12}代码消费者（前3条）")
print("-" * 100)
removable, keep = [], []
for key in CANDIDATES:
    hits = find_consumers(key)
    in_env = "是" if key in env_names else "否"
    mark = "← 零消费者，可移除" if not hits else ""
    shown = "; ".join(h.split("/")[-1] for h in hits[:3])
    print(f"{key:<34}{in_env:<12}{shown[:58]} {mark}")
    if key in env_names:
        (removable if not hits else keep).append(key)

print(f"\n可安全移除（零代码消费者）: {removable or '无'}")
print(f"必须保留（有代码消费者）  : {keep or '无'}")
print(f"\n依赖文件兜底的键（需另判）：BINANCE_* 走 binance.json；CG_API_KEY/COINGECKO_DEMO_API_KEY 走 coingecko_api_key.txt")
