"""Offline tests: never execute archived Python files."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import json
import subprocess
import sys

GENERATOR = Path(__file__).resolve().parents[1] / "scripts/maintenance/archive_manifest.py"


class ArchiveManifestTests(unittest.TestCase):
    def load_generator(self):
        self.assertTrue(GENERATOR.is_file(), "archive manifest generator must exist")
        spec = importlib.util.spec_from_file_location("archive_manifest", GENERATOR)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_inventory_hashes_nested_files_and_reports_only_metadata(self):
        module = self.load_generator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "scripts/_disabled/nested"
            archive.mkdir(parents=True)
            content = b"raise RuntimeError('MUST_NOT_EXECUTE_PRIVATE_SOURCE')\n"
            (archive / "sample.py").write_bytes(content)
            (archive / "ignore.txt").write_text("not python")
            (root / "scripts/sample.py").write_bytes(content)
            result = module.build_manifest(root)
            self.assertEqual(result["archived_python_count"], 1)
            self.assertEqual(result["active_root"], "scripts")
            self.assertEqual(result["entries"], [{
                "path": "scripts/_disabled/nested/sample.py",
                "sha256": hashlib.sha256(content).hexdigest(),
                "active_root_same_name": True,
                "active_root_path": "scripts/sample.py",
                "reason": "unknown",
                "retired_date": "unknown",
            }])
            self.assertNotIn("MUST_NOT_EXECUTE_PRIVATE_SOURCE", str(result))
            self.assertEqual((archive / "sample.py").read_bytes(), content)


    def test_missing_archive_fails_but_empty_archive_is_valid(self):
        module = self.load_generator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(FileNotFoundError):
                module.build_manifest(root)
            (root / "scripts/_disabled").mkdir(parents=True)
            self.assertEqual(module.build_manifest(root)["archived_python_count"], 0)

    def test_rejects_linked_archive_files(self):
        module = self.load_generator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "scripts/_disabled"
            archive.mkdir(parents=True)
            target = root / "outside.py"
            target.write_bytes(b"not to be hashed")
            try:
                (archive / "linked.py").symlink_to(target)
            except OSError:
                self.skipTest("Symlink creation is not permitted on this host")
            with self.assertRaises(ValueError):
                module.build_manifest(root)

    def test_cli_is_repeatable_and_writes_only_documentation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "scripts/_disabled"
            archive.mkdir(parents=True)
            (archive / "z.py").write_bytes(b"raise RuntimeError('NEVER_RUN')")
            (archive / "a.py").write_bytes(b"# archive")
            before = {p: p.read_bytes() for p in archive.iterdir()}
            command = [sys.executable, str(GENERATOR), "--repo-root", str(root)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            output = root / "docs/maintenance/archive_manifest.json"
            self.assertTrue(output.is_file(), "CLI must generate manifest")
            original = output.read_bytes()
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(output.read_bytes(), original)
            manifest = json.loads(original)
            self.assertEqual([x["path"] for x in manifest["entries"]],
                             ["scripts/_disabled/a.py", "scripts/_disabled/z.py"])
            self.assertFalse(any(x["active_root_same_name"] for x in manifest["entries"]))
            self.assertEqual(before, {p: p.read_bytes() for p in archive.iterdir()})
            readme = root / "docs/maintenance/README.md"
            self.assertTrue(readme.is_file())
            self.assertNotIn("NEVER_RUN", readme.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
