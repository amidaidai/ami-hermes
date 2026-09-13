# -*- coding: utf-8 -*-
"""scripts/maintenance/mcp_proxy_check.py 的回归测试。

锁死一条实测教训（2026-09-13）：境外源 MCP（financekit / Yahoo）必须在该 server 的
`env:` 块显式带代理，否则子进程直连被 429。同时要能识别「配置改了但运行进程没带代理」
这种假修复状态。
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.maintenance import mcp_proxy_check as m  # noqa: E402


PROXY = "http://127.0.0.1:7897"
NEEDS = {"financekit": "境外源"}


class TestConfigLayer:
    def test_env_with_proxy_passes(self):
        servers = {"financekit": {"command": "uvx", "enabled": True,
                                  "env": {"HTTP_PROXY": PROXY, "HTTPS_PROXY": PROXY}}}
        assert m.check_config_env(servers, NEEDS) == []

    def test_env_missing_proxy_is_flagged(self):
        servers = {"financekit": {"command": "uvx", "enabled": True, "env": {}}}
        problems = m.check_config_env(servers, NEEDS)
        assert len(problems) == 1
        assert problems[0]["code"] == "missing_proxy_env"
        assert problems[0]["layer"] == "config"
        # 修复提示必须带上可直接执行的命令
        assert "hermes config set mcp_servers.financekit.env.HTTP_PROXY" in problems[0]["detail"]

    def test_blank_proxy_string_counts_as_missing(self):
        servers = {"financekit": {"enabled": True, "env": {"HTTP_PROXY": "   ",
                                                           "HTTPS_PROXY": ""}}}
        problems = m.check_config_env(servers, NEEDS)
        assert [p["code"] for p in problems] == ["missing_proxy_env"]

    def test_env_block_absent_is_flagged(self):
        servers = {"financekit": {"command": "uvx", "enabled": True}}
        assert m.check_config_env(servers, NEEDS)[0]["code"] == "missing_proxy_env"

    def test_missing_server_is_flagged(self):
        problems = m.check_config_env({}, NEEDS)
        assert problems[0]["code"] == "missing_server"

    def test_disabled_server_is_flagged(self):
        servers = {"financekit": {"enabled": False, "env": {"HTTP_PROXY": PROXY}}}
        assert m.check_config_env(servers, NEEDS)[0]["code"] == "disabled"


class TestRuntimeLayer:
    def test_live_process_without_proxy_is_flagged(self):
        procs = [{"server": "financekit", "pid": 1, "env": {}}]
        problems = m.check_runtime_env(procs, NEEDS)
        assert len(problems) == 1
        assert problems[0]["code"] == "live_process_without_proxy"
        assert "/reload-mcp" in problems[0]["detail"]

    def test_live_process_with_proxy_passes(self):
        procs = [{"server": "financekit", "pid": 1, "env": {"HTTP_PROXY": PROXY}}]
        assert m.check_runtime_env(procs, NEEDS) == []

    def test_no_live_process_is_not_a_failure(self):
        # 没跑就无从验证；不能因为「没进程」而报错
        assert m.check_runtime_env([], NEEDS) == []

    def test_multiple_processes_all_checked(self):
        procs = [{"server": "financekit", "pid": 1, "env": {"HTTP_PROXY": PROXY}},
                 {"server": "financekit", "pid": 2, "env": {}}]
        problems = m.check_runtime_env(procs, NEEDS)
        assert len(problems) == 1 and "pid=2" in problems[0]["detail"]


class TestMain:
    def _write_cfg(self, tmp_path: Path, body: str) -> Path:
        cfg = tmp_path / "config.yaml"
        cfg.write_text(body, encoding="utf-8")
        return cfg

    def test_main_exit_0_when_config_ok(self, tmp_path, monkeypatch, capsys):
        cfg = self._write_cfg(tmp_path, f"""
mcp_servers:
  financekit:
    command: "uvx"
    enabled: true
    env:
      HTTP_PROXY: "{PROXY}"
      HTTPS_PROXY: "{PROXY}"
""")
        monkeypatch.setenv("HERMES_CONFIG", str(cfg))
        monkeypatch.setattr(m, "collect_runtime", lambda *a, **k: [])
        monkeypatch.chdir(tmp_path)
        rc = m.main([])
        assert rc == 0
        assert "✅" in capsys.readouterr().out
        # 报告落盘且文件名稳定
        assert (tmp_path / "data" / "maintenance" / "mcp_proxy_check.json").is_file()

    def test_main_exit_2_and_hints_reload(self, tmp_path, monkeypatch, capsys):
        cfg = self._write_cfg(tmp_path, """
mcp_servers:
  financekit:
    command: "uvx"
    enabled: true
""")
        monkeypatch.setenv("HERMES_CONFIG", str(cfg))
        monkeypatch.setattr(
            m, "collect_runtime",
            lambda *a, **k: [{"server": "financekit", "pid": 42, "env": {}}],
        )
        monkeypatch.chdir(tmp_path)
        rc = m.main(["--no-write"])
        out = capsys.readouterr().out
        assert rc == 2
        assert "missing_proxy_env" not in out  # 输出的是 detail 文本，不是 code
        assert "hermes config set" in out
        assert "/reload-mcp" in out
        assert not (tmp_path / "data").exists()

    def test_missing_config_exit_2(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HERMES_CONFIG", str(tmp_path / "nope.yaml"))
        monkeypatch.setattr(m, "config_candidates", lambda: [tmp_path / "nope.yaml"])
        assert m.main(["--no-write"]) == 2
        assert "找不到 config.yaml" in capsys.readouterr().out


class TestRealRepoConfig:
    """对本机真实 config.yaml 的软检查：只在文件存在时跑，不写盘。"""

    def test_real_config_has_proxy_for_financekit(self):
        cfg = m.find_config()
        if cfg is None:
            pytest.skip("本机找不到 config.yaml")
        servers = m.load_mcp_servers(cfg)
        if "financekit" not in servers:
            pytest.skip("本机未配置 financekit")
        problems = m.check_config_env(servers)
        assert problems == [], f"financekit 代理配置有回归：{problems}"
