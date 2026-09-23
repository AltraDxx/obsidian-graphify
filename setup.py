"""Bundle canonical Vault resources without maintaining duplicate source copies."""
from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        root = Path(__file__).parent
        destination = Path(self.build_lib) / "obsidian_graphify" / "resources"
        for source, relative in (
            ("vault-template", ""),
            ("schema", "schema"),
            ("templates", "templates"),
            (".codex/skills", ".codex/skills"),
        ):
            shutil.copytree(root / source, destination / relative, dirs_exist_ok=True)


setup(cmdclass={"build_py": BuildPy})
