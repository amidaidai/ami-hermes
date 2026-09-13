"""从 `~/.hermes/.env` 移除「零代码消费者」的凭据键（收窄终端环境泄露面）。

依据 `env_key_consumer_audit.py` 的只读复核：
  零消费者            : ANYSEARCH / BAI / FELO / METASO /
                        POLYMARKET_RELAYER_API_KEY(+_ADDRESS) / RELAYER_API_KEY(+_ADDRESS)
  有文件兜底（可移）  : CG_API_KEY / COINGECKO_DEMO_API_KEY → coingecko_api_key.txt
                        BINANCE_API_KEY / BINANCE_SECRET_KEY → binance.json
  必须保留            : BRAVE_API_KEY（litellm 读）、BRAVE_SEARCH/DEEPSEEK/EXA/FIRECRAWL/
                        GITHUB/OPENROUTER/TAVILY（插件读）、
                        TELEGRAM/DISCORD/FEISHU（gateway 读）

价值：这些键原本随 .env 进入 Hermes 进程环境 → 被终端快照 export -p 明文落盘。
移出后可把「每个快照 13 个明文凭据」压到个位数。

用法：
    python scripts/maintenance/env_trim_unused_keys.py            # 预演
    python scripts/maintenance/env_trim_unused_keys.py --apply    # 落盘
绝不打印任何密钥值。
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ENV_FILE = Path(os.environ["LOCALAPPDATA"]) / "hermes" / ".env"

REMOVE = {
    # 零消费者
    "ANYSEARCH_API_KEY", "BAI_API_KEY", "FELO_API_KEY", "METASO_API_KEY",
    "POLYMARKET_RELAYER_API_KEY", "POLYMARKET_RELAYER_API_KEY_ADDRESS",
    "RELAYER_API_KEY", "RELAYER_API_KEY_ADDRESS",
    # 有文件兜底（coingecko_api_key.txt / binance.json）
    "CG_API_KEY", "COINGECKO_DEMO_API_KEY",
    "BINANCE_API_KEY", "BINANCE_SECRET_KEY",
}


def main() -> int:
    apply = "--apply" in sys.argv
    if not ENV_FILE.is_file():
        print(f"未找到 {ENV_FILE}")
        return 1

    lines = ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    kept, removed = [], []
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#") or "=" not in s:
            kept.append(raw)
            continue
        name = s.split("=", 1)[0].strip()
        if name in REMOVE:
            removed.append(name)
        else:
            kept.append(raw)

    print(f"`{ENV_FILE}`")
    print(f"  总行数 {len(lines)} → 保留 {len(kept)}")
    print(f"  将移除 {len(removed)} 个键：{', '.join(sorted(removed)) or '(无)'}")
    if len(removed) != len(REMOVE & set(removed)):
        pass

    if not removed:
        print("\n没有需要移除的键（可能已处理过）。")
        return 0

    if not apply:
        print("\n（预演模式，未改盘；确认后加 --apply）")
        return 0

    # 记录（只记键名，不留值）
    log = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "maintenance-logs"
    log.mkdir(parents=True, exist_ok=True)
    (log / "env-trim-20260913.txt").write_text(
        "2026-09-13 按用户指示从 .env 移除零消费者/有文件兜底的凭据键\n"
        "移除: " + ", ".join(sorted(removed)) + "\n"
        "理由: 终端快照 export -p 会把 .env 里的密钥明文落盘；这些键无代码消费者或已有文件兜底。\n"
        "原值不保留。\n", encoding="utf-8")

    ENV_FILE.write_text("".join(kept), encoding="utf-8")
    print(f"\n✅ 已移除 {len(removed)} 个键；记录见 {log / 'env-trim-20260913.txt'}")
    print("注意：已在运行的进程仍持有旧环境 —— 下次启动/新会话才生效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
