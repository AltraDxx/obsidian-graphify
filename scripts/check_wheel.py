"""Verify a wheel in a clean environment outside the source checkout."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import venv


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    wheels = list((root / "dist").glob(f"obsidian_graphify-{version}-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("Build exactly one wheel for the current version with python -m build.")
    env = {**os.environ, "PYTHONUTF8": "1"}
    for key in ("PYTHONPATH", "GRAPHIFY_VAULT", "VIRTUAL_ENV"):
        env.pop(key, None)
    with tempfile.TemporaryDirectory(prefix="graphify-wheel-") as directory:
        temp = Path(directory).resolve()
        environment = temp / "environment"
        venv.EnvBuilder(with_pip=True).create(environment)
        bindir = environment / ("Scripts" if os.name == "nt" else "bin")
        python = bindir / ("python.exe" if os.name == "nt" else "python")
        cli = bindir / ("graphify.exe" if os.name == "nt" else "graphify")

        def run(*args):
            result = subprocess.run([str(arg) for arg in args], cwd=temp, env=env,
                                    capture_output=True, text=True, encoding="utf-8")
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            return result.stdout

        run(python, "-m", "pip", "install", "--no-index", "--no-deps", wheels[0])
        installed = run(python, "-I", "-c", "import obsidian_graphify; print(obsidian_graphify.__file__)")
        assert str(environment) in installed, installed
        run(cli, "--help")
        fresh = temp / "新 Vault"
        run(cli, "init", fresh)
        for source, destination in (("vault-template", ""), ("schema", "schema"),
                                    ("templates", "templates"), (".codex/skills", ".codex/skills")):
            for path in (root / source).rglob("*"):
                if path.is_file():
                    target = fresh / destination / path.relative_to(root / source)
                    assert target.read_bytes() == path.read_bytes(), target
        for path in [fresh / "AGENTS.md", *(fresh / ".codex/skills").rglob("SKILL.md")]:
            for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if "://" not in link:
                    assert (path.parent / link.split("#")[0]).is_file(), (path, link)
        (fresh / "AGENTS.md").write_text("用户定制", encoding="utf-8")
        run(cli, "init", fresh)
        assert (fresh / "AGENTS.md").read_text(encoding="utf-8") == "用户定制"
        run(cli, "--vault", fresh, "status")
        run(cli, "--vault", fresh, "lint")
        fixture = temp / "sample-vault"
        shutil.copytree(root / "tests/fixtures/sample-vault", fixture,
                        ignore=shutil.ignore_patterns("exports", "_logs"))
        for command in ("lint", "status", "export"):
            run(cli, "--vault", fixture, command)
        assert "光照实验.md" in run(cli, "--vault", fixture, "lookup", "光照实验")
        assert "实验设计.md" in run(cli, "--vault", fixture, "impact", "_graphify/sources/温室记录甲.md")
        graph = json.loads((fixture / "exports/graph.json").read_text(encoding="utf-8"))
        assert len(graph["nodes"]) == 10
        assert "No lint findings" in run(cli, "--vault", fixture, "lint")
        print(f"Wheel {wheels[0].name}: isolated install, resources, init, lint/status/export/lookup/impact passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
