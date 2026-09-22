from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import sys
from obsidian_graphify.config import current_vault
from obsidian_graphify.media.paths import compiled_visual_asset_dir, compiled_visual_note_path, compiled_visual_ocr_regions_path, infer_media_compile_mode
from obsidian_graphify.media.protocol import VIDEO_EXTENSIONS, VISUAL_MODE
from obsidian_graphify.utils import as_string


def command_compile_media(target_path: str, force: bool = False) -> int:
    path = Path(target_path)
    if not path.is_absolute():
        path = current_vault().root / path
    if not path.exists():
        print(f"Media path not found: {target_path}", file=sys.stderr)
        return 1

    mode = infer_media_compile_mode(path)
    rel_path = path.relative_to(current_vault().root).as_posix() if path.is_relative_to(current_vault().root) else str(path)
    if mode != VISUAL_MODE:
        print(
            f"Unsupported media compile path for v1: {rel_path}. Expected a file under raw/inbox/{VISUAL_MODE}/",
            file=sys.stderr,
        )
        return 1
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        print(f"Unsupported video extension: {path.suffix or '(none)'}", file=sys.stderr)
        return 1

    note_path = compiled_visual_note_path(path)
    asset_dir = compiled_visual_asset_dir(path)
    sidecar_path = compiled_visual_ocr_regions_path(path)
    command = [
        resolve_transfer_platform_executable(),
        "compile",
        "visual",
        str(path),
        "--markdown-path",
        str(note_path),
        "--sidecar-path",
        str(sidecar_path),
        "--assets-dir",
        str(asset_dir),
    ]
    if force:
        command.append("--force")

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print((result.stderr or result.stdout).strip() or "transfer-platform compile failed", file=sys.stderr)
        return 1

    if result.stdout.strip():
        print(result.stdout.strip())
    print(f"Wrote {note_path.relative_to(current_vault().root).as_posix()}")
    print(f"Assets: {asset_dir.relative_to(current_vault().root).as_posix()}")
    print(f"Sidecar: {sidecar_path.relative_to(current_vault().root).as_posix()}")
    return 0


def resolve_transfer_platform_executable() -> str:
    env_path = as_string(os.environ.get("TRANSFER_PLATFORM_BIN"))
    if env_path:
        return env_path

    env_root = as_string(os.environ.get("TRANSFER_PLATFORM_ROOT"))
    if env_root:
        candidate = Path(env_root) / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("transfer-platform.exe" if os.name == "nt" else "transfer-platform")
        if candidate.exists():
            return str(candidate)

    which_result = shutil.which("transfer-platform")
    if which_result:
        return which_result

    candidate = Path.home() / "Coding" / "transfer_platform" / ".venv" / "bin" / "transfer-platform"
    if candidate.exists():
        return str(candidate)

    raise RuntimeError(
        "Missing transfer-platform executable. Install the standalone tool or set TRANSFER_PLATFORM_BIN."
    )
