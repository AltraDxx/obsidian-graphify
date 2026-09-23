from __future__ import annotations

from pathlib import Path
import re
from obsidian_graphify.config import current_vault
from obsidian_graphify.media.protocol import MEDIA_COMPILE_MODES, VISUAL_MODE


def infer_media_compile_mode(path: Path) -> str | None:
    try:
        relative = path.relative_to(current_vault().root)
    except ValueError:
        return None
    if len(relative.parts) < 3 or relative.parts[0] != "raw" or relative.parts[1] != "inbox":
        return None
    mode = relative.parts[2]
    return mode if mode in MEDIA_COMPILE_MODES else None


def compiled_visual_note_path(video_path: Path) -> Path:
    mode_root = current_vault().raw_root / "inbox" / VISUAL_MODE
    relative = video_path.relative_to(mode_root).with_suffix("")
    note_dir = current_vault().raw_root / "compiled" / "visual"
    for part in relative.parts[:-1]:
        note_dir /= sanitize_filename(part)
    return note_dir / f"{sanitize_filename(relative.name)}（视觉编译）.md"


def compiled_visual_asset_dir(video_path: Path) -> Path:
    mode_root = current_vault().raw_root / "inbox" / VISUAL_MODE
    relative = video_path.relative_to(mode_root).with_suffix("")
    asset_dir = current_vault().raw_root / "assets" / VISUAL_MODE
    for part in relative.parts[:-1]:
        asset_dir /= sanitize_filename(part)
    return asset_dir / sanitize_filename(relative.name)


def compiled_visual_ocr_regions_path(video_path: Path) -> Path:
    return compiled_visual_asset_dir(video_path) / "ocr_regions.json"


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[\\\\/:*?\"<>|]+", "-", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    return cleaned[:120]
