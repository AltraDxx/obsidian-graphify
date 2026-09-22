from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from obsidian_graphify.cli import main
from obsidian_graphify.config import VaultContext, current_vault, resolve_vault, use_vault
from obsidian_graphify.refs import resolve_reference
from obsidian_graphify.vault import load_vault


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.vault = self.root / "独立 Vault"
        shutil.copytree(ROOT / "tests/fixtures/sample-vault", self.vault,
                        ignore=shutil.ignore_patterns("_logs", "exports"))

    def cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(list(args))
        self.assertEqual(code, 0, stdout.getvalue() + stderr.getvalue())
        return stdout.getvalue()

    def test_resolution_priority_and_relative_paths(self):
        nested = self.vault / "nested/deep"
        nested.mkdir(parents=True)
        explicit = self.root / "explicit"
        env = {"GRAPHIFY_VAULT": str(self.root / "environment")}
        self.assertEqual(resolve_vault(explicit, cwd=nested, environ=env).root, explicit)
        self.assertEqual(resolve_vault(cwd=nested, environ=env).root, self.root / "environment")
        self.assertEqual(resolve_vault(cwd=nested, environ={}).root, self.vault)
        self.assertEqual(resolve_vault(cwd=self.root, environ={}).root, self.root)
        self.assertEqual(resolve_vault("..", cwd=nested, environ=env).root, nested.parent)
        self.assertEqual(resolve_vault(cwd=nested, environ={"GRAPHIFY_VAULT": ".."}).root, nested.parent)
        (nested.parent / "graphify.toml").write_text("", encoding="utf-8")
        self.assertEqual(resolve_vault(cwd=nested, environ={}).root, nested.parent)

    def test_context_restored_on_exception(self):
        with use_vault(VaultContext(self.vault)):
            with self.assertRaises(RuntimeError):
                with use_vault(VaultContext(self.root)):
                    raise RuntimeError("test")
            self.assertEqual(current_vault().root, self.vault)

    def test_cli_explicit_overrides_environment(self):
        with patch.dict(os.environ, {"GRAPHIFY_VAULT": str(self.root / "missing")}):
            output = self.cli("--vault", str(self.vault), "status")
        self.assertIn(str(self.vault), output)
        self.assertIn("claim: 3", output)

    def test_environment_and_upward_discovery_in_subprocess(self):
        nested = self.vault / "nested/deep"
        nested.mkdir(parents=True)
        env = {**os.environ, "PYTHONUTF8": "1"}
        env.pop("GRAPHIFY_VAULT", None)
        for cwd, extra in ((nested, {}), (self.root, {"GRAPHIFY_VAULT": str(self.vault)})):
            result = subprocess.run([sys.executable, str(ROOT / "scripts/graphify.py"), "status"],
                                    cwd=cwd, env={**env, **extra}, capture_output=True,
                                    text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(str(self.vault), result.stdout)
            self.assertIn("total: 9", result.stdout)

    def test_missing_vault_does_not_create_directory(self):
        target = self.root / "missing"
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["--vault", str(target), "export"])
        self.assertEqual(code, 1)
        self.assertFalse(target.exists())

    def test_fixture_commands_and_export_graph(self):
        self.assertIn("Lint passed", self.cli("--vault", str(self.vault), "lint"))
        self.assertIn("source: 2", self.cli("--vault", str(self.vault), "status"))
        lookup = self.cli("--vault", str(self.vault), "lookup", "光照实验")
        self.assertIn("光照实验.md", lookup)
        self.assertIn("section=", lookup)
        impact = self.cli("--vault", str(self.vault), "impact", "_graphify/sources/温室记录甲.md")
        for expected in ("应控制浇水量.md", "实验设计.md", "光照实验.md", "_索引.md"):
            self.assertIn(expected, impact)
        self.cli("--vault", str(self.vault), "export")
        graph = json.loads((self.vault / "exports/graph.json").read_text(encoding="utf-8"))
        self.assertEqual(len(graph["nodes"]), 10)
        conflicts = [e for e in graph["edges"] if e["kind"] == "conflict_ref"]
        self.assertEqual(len(conflicts), 2)
        self.assertEqual(conflicts[0]["source"], conflicts[1]["target"])
        self.assertEqual(conflicts[0]["target"], conflicts[1]["source"])
        self.assertTrue(any(e["kind"] == "see_also" for e in graph["edges"]))
        ET.parse(self.vault / "exports/graph.graphml")
        self.assertIn("No lint findings", self.cli("--vault", str(self.vault), "lint"))

    def test_scope_changes_and_protected_links(self):
        self.cli("--vault", str(self.vault), "export")
        scope = self.cli("--vault", str(self.vault), "scope", "处理清单.md")
        self.assertIn("温室记录甲.md", scope)
        self.assertIn("应控制浇水量.md", scope)
        self.cli("--vault", str(self.vault), "scan", "--scope", "处理清单.md")
        self.assertTrue((self.vault / "_logs/pending.md").is_file())
        note = self.vault / "知识簇/温室/实验设计.md"
        note.write_text(note.read_text(encoding="utf-8").replace("[[蓝灯促进生长]]", "蓝灯促进生长"), encoding="utf-8")
        changes = self.cli("--vault", str(self.vault), "changes")
        self.assertIn("modified: 1", changes)
        self.assertIn("实验设计.md", changes)
        self.assertIn("protected wikilinks missing", self.cli("--vault", str(self.vault), "lint"))
        self.cli("--vault", str(self.vault), "changes", "--save")
        self.assertIn("No tracked", self.cli("--vault", str(self.vault), "changes"))

    def test_ordinary_load_does_not_hash_media(self):
        with use_vault(VaultContext(self.vault)), patch(
            "obsidian_graphify.vault.hashlib.file_digest", side_effect=AssertionError("unexpected hash")
        ):
            load_vault()

    def test_hash_changes_detect_same_size_edit_with_preserved_timestamp(self):
        self.cli("--vault", str(self.vault), "changes", "--save")
        path = self.vault / "raw/inbox/虚构温室实验.md"
        stat = path.stat()
        content = path.read_bytes()
        replacement = content.replace("甲组".encode(), "丙组".encode())
        self.assertEqual(len(content), len(replacement))
        path.write_bytes(replacement)
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertIn("modified: 1", self.cli("--vault", str(self.vault), "changes"))

    def test_hash_changes_ignore_timestamp_only_edits(self):
        self.cli("--vault", str(self.vault), "changes", "--save")
        path = self.vault / "raw/inbox/虚构温室实验.md"
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000_000))
        self.assertIn("No tracked", self.cli("--vault", str(self.vault), "changes"))

    def test_legacy_snapshot_remains_readable_and_upgrades_on_save(self):
        self.cli("--vault", str(self.vault), "changes", "--save")
        state_path = self.vault / "_logs/vault-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        for metadata in state["files"].values():
            metadata.pop("sha256")
        state_path.write_text(json.dumps(state), encoding="utf-8")
        self.assertIn("No tracked", self.cli("--vault", str(self.vault), "changes"))
        self.cli("--vault", str(self.vault), "changes", "--save")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(all(len(meta["sha256"]) == 64 for meta in state["files"].values()))

    def test_reference_alias_heading_and_ambiguity(self):
        with use_vault(VaultContext(self.vault)):
            data = load_vault()
        path = "知识簇/温室/实验设计.md"
        aliases = {**data["alias_map"], "ambiguous": None}
        for ref in (path, "实验设计#主线解释|显示名", "./" + path):
            self.assertEqual(resolve_reference(ref, aliases, data["node_specs"]), path)
        self.assertIsNone(resolve_reference("ambiguous", aliases, data["node_specs"]))

    def test_init_idempotency_force_and_resources(self):
        target = self.root / "new vault"
        self.cli("init", str(target))
        expected = ("graphify.toml", "AGENTS.md", ".gitignore", "处理清单.md",
                    "schema/note-spec.md", "templates/wiki.md", ".codex/skills/graphify-ingest/SKILL.md")
        for name in expected:
            self.assertTrue((target / name).is_file(), name)
        for name in ("raw/inbox", "知识簇", "_graphify/sources", "_graphify/indexes", "_graphify/dashboards"):
            self.assertTrue((target / name).is_dir())
        custom = target / "AGENTS.md"
        custom.write_text("用户定制", encoding="utf-8")
        before = {p.relative_to(target): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in target.rglob("*") if p.is_file()}
        self.cli("init", str(target))
        after = {p.relative_to(target): (p.read_bytes(), p.stat().st_mtime_ns)
                 for p in target.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.cli("--vault", str(target), "status")
        self.cli("--vault", str(target), "lint")
        self.cli("init", str(target), "--force")
        self.assertNotEqual(custom.read_text(encoding="utf-8"), "用户定制")

    def test_init_dot_ignores_environment_target(self):
        env = {**os.environ, "GRAPHIFY_VAULT": str(self.vault), "PYTHONUTF8": "1"}
        result = subprocess.run([sys.executable, str(ROOT / "scripts/graphify.py"), "init", "."],
                                cwd=self.root, env=env, capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "AGENTS.md").is_file())
        self.assertFalse((self.vault / "AGENTS.md").exists())

    def test_init_preflight_prevents_partial_writes_on_collision(self):
        target = self.root / "collision"
        target.mkdir()
        (target / "schema").write_text("keep", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["init", str(target)])
        self.assertEqual(code, 1)
        self.assertEqual(list(target.iterdir()), [target / "schema"])

    def test_commands_do_not_leak_vault_context(self):
        empty = self.root / "empty"
        empty.mkdir()
        self.cli("--vault", str(self.vault), "status")
        self.cli("--vault", str(empty), "export")
        graph = json.loads((empty / "exports/graph.json").read_text(encoding="utf-8"))
        self.assertEqual(graph["nodes"], [])
        self.assertFalse((self.vault / "exports").exists())

    def test_core_does_not_import_optional_media(self):
        code = """import sys
sys.path.insert(0, sys.argv[1])
class BlockMedia:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('rapidocr', 'scenedetect', 'onnxruntime', 'obsidian_graphify.media')):
            raise AssertionError(fullname)
sys.meta_path.insert(0, BlockMedia())
from obsidian_graphify.cli import main
assert main(['--vault', sys.argv[2], 'status']) == 0
"""
        result = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT / "src"), str(self.vault)],
                                cwd=self.root, capture_output=True, encoding="utf-8",
                                env={**os.environ, "PYTHONUTF8": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
