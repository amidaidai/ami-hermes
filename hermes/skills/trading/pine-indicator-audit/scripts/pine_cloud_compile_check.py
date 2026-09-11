#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TradingView 服务器端轻量全量编译回执 (translate_light). 只读, 不碰图表.

用法: python pine_cloud_compile_check.py a.pine b.pine [...]
输出: JSON per file + cloud_compile.json (cwd).

重要边界:
  errors2/warnings2 双空 == 服务器接受语法, **不等于** 客户端完整编译通过.
  translate_light 不返回 IL 大小, 不校验 100256 (CE10117) 上限.
  真实先例: 主指标轻量端点成功, 客户端仍报 CE10117 100488 > 100256.
  客户端验收只能在 Pine 编辑器实际"添加到图表"后读 pine_get_errors / Pine Console.

原始端点定义见 tools/tradingview-mcp/src/core/pine.js check(); pine_check MCP 工具是它的薄封装,
但 240KB 级源码内联进 MCP 参数会吃掉数万 token, 因此本脚本走 urllib 直传.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENDPOINT = ("https://pine-facade.tradingview.com/pine-facade/translate_light"
            "?user_name=Guest&pine_id=00000000-0000-0000-0000-000000000000")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


def compile_pine(path: str) -> dict:
    src = Path(path).read_text(encoding="utf-8")
    body = urllib.parse.urlencode({"source": src}).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("Referer", "https://www.tradingview.com/")
    req.add_header("Origin", "https://www.tradingview.com")
    req.add_header("User-Agent", UA)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            status = resp.status
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"file": Path(path).name, "http": e.code,
                "error": e.read().decode("utf-8", "replace")[:2000]}
    except Exception as e:  # noqa: BLE001
        return {"file": Path(path).name, "error": f"{type(e).__name__}: {e}"}
    res = payload.get("result") or {}
    return {
        "file": Path(path).name,
        "http": status,
        "success": payload.get("success"),
        "errors2": res.get("errors2", []),
        "warnings2": res.get("warnings2", []),
        "has_errors": bool(res.get("errors2")),
        "has_warnings": bool(res.get("warnings2")),
        "note": "server-side only; does NOT prove client IL < 100256",
    }


if __name__ == "__main__":
    results = []
    for p in sys.argv[1:]:
        res = compile_pine(p)
        results.append(res)
        print(json.dumps(res, ensure_ascii=False, indent=1))
    Path("cloud_compile.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
