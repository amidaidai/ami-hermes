#!/usr/bin/env python3
"""
检查 pydantic-core / pydantic 版本兼容性。
任何 TradingView MCP 故障排查前必跑。

Usage: python check_pydantic_compat.py
"""
import sys

def main():
    try:
        import pydantic
    except Exception as e:
        print(f"[FATAL] pydantic 导入失败: {e}")
        print("  原因：pydantic_core 二进制扩展与 pydantic 版本不匹配")
        print("  修复：pip install pydantic-core==2.46.4 --force-reinstall")
        sys.exit(1)

    try:
        import pydantic_core
    except Exception as e:
        print(f"[FATAL] pydantic_core 导入失败: {e}")
        print("  修复：pip install pydantic-core==2.46.4 --force-reinstall")
        sys.exit(1)

    # 检查版本兼容性
    pyd_ver = pydantic.__version__
    core_ver = pydantic_core.__version__
    print(f"pydantic:       {pyd_ver}")
    print(f"pydantic-core:  {core_ver}")

    # pydantic 2.13.x 需要 pydantic-core == 2.46.4
    # pydantic 2.12.x 需要 pydantic-core == 2.41.x
    # pydantic 2.10.x 需要 pydantic-core == 2.27.x
    if pyd_ver.startswith("2.13"):
        expected = "2.46.4"
    elif pyd_ver.startswith("2.12"):
        expected = "2.41"
    elif pyd_ver.startswith("2.11"):
        expected = "2.33"
    elif pyd_ver.startswith("2.10"):
        expected = "2.27"
    else:
        print(f"[WARN] 未知 pydantic {pyd_ver}，请参考 pydantic 官方版本表")
        return

    if not core_ver.startswith(expected):
        print(f"\n[FATAL] 版本不兼容！pydantic {pyd_ver} 要求 pydantic-core ~={expected}，但当前是 {core_ver}")
        print(f"  修复：pip install 'pydantic-core=={expected}' --force-reinstall")
        sys.exit(1)
    else:
        print(f"\n[OK] 版本兼容（pydantic {pyd_ver} ↔ pydantic-core {core_ver}）")
        # 额外检查 fetch_tv_mcp.py 的 sys.path 注入
        fetch_tv_mcp = r"D:\Hermes agent\scripts\fetch_tv_mcp.py"
        try:
            content = open(fetch_tv_mcp, 'r', encoding='utf-8').read()
            if "sys.path.insert(0, str(hermes_venv))" in content and "TANGXI-FIX" not in content[:2000]:
                print("\n[WARN] fetch_tv_mcp.py 仍有未注释的 sys.path 注入")
                print(f"  修复：注释掉 fetch_tv_mcp.py 开头 3 行（hermes_venv / sys.path.insert）")
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
