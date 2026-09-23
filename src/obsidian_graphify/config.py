"""Vault discovery and command-local paths, independent of the installation."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterator, Mapping


@dataclass(frozen=True)
class VaultContext:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.expanduser().resolve())

    @property
    def raw_root(self) -> Path:
        return self.root / "raw"

    @property
    def cluster_root(self) -> Path:
        return self.root / "知识簇"

    @property
    def graphify_root(self) -> Path:
        return self.root / "_graphify"

    @property
    def source_root(self) -> Path:
        return self.graphify_root / "sources"

    @property
    def index_root(self) -> Path:
        return self.graphify_root / "indexes"

    @property
    def log_root(self) -> Path:
        return self.root / "_logs"

    @property
    def export_root(self) -> Path:
        return self.root / "exports"

    @property
    def link_manifest_path(self) -> Path:
        return self.log_root / "link-manifest.json"

    @property
    def pending_path(self) -> Path:
        return self.log_root / "pending.md"

    @property
    def state_path(self) -> Path:
        return self.log_root / "vault-state.json"

    @property
    def default_scope_path(self) -> Path:
        return self.root / "处理清单.md"


def resolve_vault(
    vault: str | Path | None = None,
    *,
    cwd: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> VaultContext:
    cwd = (cwd or Path.cwd()).resolve()
    environ = os.environ if environ is None else environ
    selected = vault if vault is not None else environ.get("GRAPHIFY_VAULT")
    if selected is not None and str(selected).strip():
        path = Path(selected).expanduser()
        return VaultContext(path if path.is_absolute() else cwd / path)
    for candidate in (cwd, *cwd.parents):
        if (candidate / "graphify.toml").is_file():
            return VaultContext(candidate)
    return VaultContext(cwd)


_active_vault: ContextVar[VaultContext | None] = ContextVar("graphify_vault", default=None)


def current_vault() -> VaultContext:
    return _active_vault.get() or resolve_vault()


@contextmanager
def use_vault(context: VaultContext) -> Iterator[VaultContext]:
    token = _active_vault.set(context)
    try:
        yield context
    finally:
        _active_vault.reset(token)
