from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}


MEDIA_COMPILE_MODES = {"video-visual", "video-audio", "audio"}


VISUAL_MODE = "video-visual"


DEFAULT_VISUAL_MAX_INTERVAL_SECONDS = 15.0


DEFAULT_VISUAL_MAX_FRAMES = 24


VISUAL_OCR_NOISE_PATTERNS = (
    r"^\d{1,2}:\d{2}$",
    r"^5G\d*$",
    r"^\d+\s*%$",
    r"^\d+\s*(天|小时|分钟)前$",
    r"^@\S+·\d+\s*(天|小时|分钟)前$",
    r"^第?\d+\s*(赞|评论|收藏|分享)?$",
    r"^全屏观看$",
    r"^点击推荐[>＞]?$",
    r"^下一集[>＞]?$",
    r"^第\d+集.*展开$",
    r"^合集[·:：].*$",
    r"^拍同款$",
    r"^展开$",
    r"^\d*个人观点，仅供参考$",
    r"^搜索$",
    r"^弹$",
    r"^善语结善缘，恶言伤人心$",
    r"^汽水音乐[>＞].*$",
)


@dataclass(frozen=True)
class MediaProbe:
    duration_seconds: float
    width: int | None
    height: int | None
    has_audio: bool
    has_video: bool


@dataclass(frozen=True)
class VisualRegionRecord:
    region_id: str
    bbox: list[float]
    text: str
    order: int
    review: str = ""


@dataclass(frozen=True)
class VisualAnchorRecord:
    anchor_id: str
    text: str
    review: str = ""
    region_ids: tuple[str, ...] = ()


@dataclass
class VisualFrameRecord:
    index: int
    cover_start_seconds: float
    cover_end_seconds: float
    rel_image_path: str
    regions: list[VisualRegionRecord]
    anchors: list[VisualAnchorRecord]
    error: str = ""


@dataclass(frozen=True)
class VisualCompileArtifact:
    note_path: Path
    asset_dir: Path
    sidecar_path: Path
    frame_count: int
