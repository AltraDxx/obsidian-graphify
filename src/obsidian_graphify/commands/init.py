"""Initialize a Vault using versioned resources shipped with the package."""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def scaffold_files():
    def walk(resource, relative=Path()):
        for child in sorted(resource.iterdir(), key=lambda item: item.name):
            path = relative / child.name
            if child.is_dir():
                yield from walk(child, path)
            else:
                yield path, child

    packaged = files("obsidian_graphify").joinpath("resources")
    if packaged.is_dir():
        yield from walk(packaged)
        return
    # Editable installs read canonical source assets; wheels are self-contained.
    repository = Path(__file__).resolve().parents[3]
    if not (repository / "vault-template").is_dir():
        raise RuntimeError("Missing packaged Vault resources; reinstall Graphify.")
    for source, relative in (
        ("vault-template", ""), ("schema", "schema"),
        ("templates", "templates"), (".codex/skills", ".codex/skills"),
    ):
        yield from walk(repository / source, Path(relative))


def command_init(vault_path: str, force: bool = False) -> int:
    root = Path(vault_path).expanduser().resolve()
    directories = [Path(p) for p in ("raw/inbox", "知识簇", "_graphify/sources", "_graphify/indexes", "_graphify/dashboards")]
    resources = list(scaffold_files())
    resource_paths = {path for path, _ in resources}
    # Preflight every path before writing; symlinks must not redirect scaffold writes.
    for relative in [*directories, *resource_paths]:
        target = root / relative
        if not target.resolve().is_relative_to(root):
            raise ValueError(f"Scaffold path escapes Vault: {relative}")
        for parent in target.parents:
            if parent == root.parent:
                break
            if parent.exists() and not parent.is_dir():
                raise ValueError(f"Expected directory: {parent}")
        if relative in resource_paths and target.is_dir():
            raise ValueError(f"Expected file: {target}")
        if relative in directories and target.exists() and not target.is_dir():
            raise ValueError(f"Expected directory: {target}")
    root.mkdir(parents=True, exist_ok=True)
    for relative in directories:
        target = root / relative
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {relative.as_posix()}/")
    for relative, resource in resources:
        target = root / relative
        if target.exists() and not force:
            print(f"Kept: {relative.as_posix()}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.exists()
        target.write_bytes(resource.read_bytes())
        print(f"{'Updated' if existed else 'Created'}: {relative.as_posix()}")
    print(f"Vault ready: {root}")
    return 0
