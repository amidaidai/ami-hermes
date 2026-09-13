"""Isolated watchdog tests; no real delivery module is ever loaded."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["HANGQING_NO_SEND"] = "1"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts/data_freshness_watchdog.py"
spec = importlib.util.spec_from_file_location("watchdog_local_test", SCRIPT)
assert spec is not None and spec.loader is not None
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


class WatchdogTests(unittest.TestCase):
    def test_missing_active_file_is_an_issue(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "active.json"
            with patch.object(watch, "WATCH_FILES", {path.name: {"threshold": 1, "paths": [path]}}):
                self.assertTrue(callable(getattr(watch, "check", None)), "safe check API missing")
                report = watch.check()
            self.assertFalse(report["healthy"])
            self.assertEqual(report["items"][0]["status"], "missing")
            self.assertEqual(report["issue_count"], 1)

    def test_retired_sources_are_explicitly_excluded(self):
        with patch.object(watch, "WATCH_FILES", {}), patch.object(watch, "PAUSED_SOURCES", {"old.json": "retired"}):
            result = watch.check()
        self.assertEqual(result.get("paused_sources"), {"old.json": "retired"})
        self.assertTrue(result["healthy"])
        self.assertEqual(result["active_count"], 0)

    def test_default_and_check_report_archive_locally_without_delivery(self):
        import contextlib
        import io
        import types
        blocked = types.ModuleType("telegram_reliable")
        setattr(blocked, "push_tg_rich", lambda *a, **k: self.fail("real sender reached"))
        with tempfile.TemporaryDirectory() as root, patch.object(watch, "WATCH_FILES", {}), patch.dict("sys.modules", {"telegram_reliable": blocked, "alert_dedup": blocked}), patch.object(watch.importlib, "import_module", side_effect=AssertionError("delivery import forbidden")):
            for mode in ([], ["check"], ["report"]):
                out = Path(root) / "report.json"
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    rc = watch.main(mode + ["--output", str(out)])
                self.assertEqual(rc, 0)
                report = json.loads(out.read_text(encoding="utf-8"))
                self.assertEqual(report["delivery"], "local_only")
                self.assertEqual(stdout.getvalue(), "")

    def test_stale_payload_with_new_mtime_remains_unhealthy(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "active.json"
            path.write_text(json.dumps({"timestamp": "2000-01-01T00:00:00Z"}), encoding="utf-8")
            with patch.object(watch, "WATCH_FILES", {path.name: {"threshold": 1, "paths": [path]}}):
                result = watch.check()
            self.assertFalse(result["healthy"])
            self.assertEqual(result["items"][0]["status"], "stale_cache")

    def test_missing_default_is_quiet_even_without_kill_switch(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "absent.json"
            out = Path(root) / "result.json"
            with patch.object(watch, "WATCH_FILES", {path.name: {"threshold": 1, "paths": [path]}}), patch.dict(os.environ, {"HANGQING_NO_SEND": "0"}), patch.object(watch.importlib, "import_module", side_effect=AssertionError("sender loaded")), contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(watch.main(["--output", str(out)]), 0)
            self.assertEqual(stdout.getvalue(), "")
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["issue_count"], 1)
            self.assertEqual(result["delivery"], "local_only")

    def test_explicit_send_is_blocked_by_kill_switch(self):
        with tempfile.TemporaryDirectory() as root, patch.object(watch.importlib, "import_module", side_effect=AssertionError("sender loaded")):
            out = Path(root) / "result.json"
            self.assertEqual(watch.main(["report", "--send", "--output", str(out)]), 0)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["delivery"], "blocked_by_no_send")


    def test_nested_timestamp_key_is_watched_not_the_result_file(self):
        """keylevels_structure_review.json 无时间戳；真信号在 config 的嵌套键里。"""
        with tempfile.TemporaryDirectory() as root:
            config = Path(root) / "keylevels_config.json"
            config.write_text(json.dumps({"auto_approval_policy": {
                "structure_reviewed_at": "2000-01-01T00:00:00+08:00"}}), encoding="utf-8")
            cfg = {"threshold": 6, "payload_path": ("auto_approval_policy", "structure_reviewed_at"),
                   "paths": [config]}
            with patch.object(watch, "WATCH_FILES", {"structure_reviewed_at": cfg}):
                stale = watch.check()
            self.assertFalse(stale["healthy"])
            self.assertEqual(stale["items"][0]["status"], "stale_cache")
            from datetime import datetime, timedelta, timezone
            fresh_at = datetime.now(timezone(timedelta(hours=8))).isoformat()
            config.write_text(json.dumps({"auto_approval_policy": {
                "structure_reviewed_at": fresh_at}}), encoding="utf-8")
            with patch.object(watch, "WATCH_FILES", {"structure_reviewed_at": cfg}):
                fresh = watch.check()
            self.assertTrue(fresh["healthy"])
            self.assertEqual(fresh["items"][0]["status"], "live")

    def test_timestampless_result_file_is_not_watched(self):
        self.assertNotIn("keylevels_structure_review.json", watch.WATCH_FILES)
        self.assertIn("structure_reviewed_at", watch.WATCH_FILES)


if __name__ == "__main__":
    unittest.main()
