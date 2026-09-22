from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any
import hashlib
import json
import re
import shutil
import subprocess
from obsidian_graphify.config import current_vault
from obsidian_graphify.media.paths import compiled_visual_asset_dir, compiled_visual_note_path, compiled_visual_ocr_regions_path, infer_media_compile_mode
from obsidian_graphify.media.protocol import DEFAULT_VISUAL_MAX_FRAMES, DEFAULT_VISUAL_MAX_INTERVAL_SECONDS, MediaProbe, VIDEO_EXTENSIONS, VISUAL_MODE, VISUAL_OCR_NOISE_PATTERNS, VisualAnchorRecord, VisualCompileArtifact, VisualFrameRecord, VisualRegionRecord
from obsidian_graphify.refs import dedupe_preserve_order
from obsidian_graphify.utils import as_string, to_float, write_text


class LocalVisualCompileBackend:
    def __init__(self, max_interval_seconds: float = DEFAULT_VISUAL_MAX_INTERVAL_SECONDS) -> None:
        self.max_interval_seconds = max_interval_seconds
        self._ocr_engine: Any = None

    def probe(self, video_path: Path) -> MediaProbe:
        return probe_media_with_ffprobe(video_path)

    def select_timestamps(self, video_path: Path, probe: MediaProbe) -> list[float]:
        return detect_visual_timestamps(
            video_path,
            duration_seconds=probe.duration_seconds,
            max_interval_seconds=self.max_interval_seconds,
            max_frames=DEFAULT_VISUAL_MAX_FRAMES,
        )

    def extract_frame(self, video_path: Path, timestamp_seconds: float, output_path: Path) -> None:
        extract_frame_with_ffmpeg(video_path, timestamp_seconds, output_path)

    def ocr_image(self, image_path: Path) -> Any:
        if self._ocr_engine is None:
            try:
                from rapidocr import RapidOCR
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "Missing Python dependency for OCR. Install rapidocr and onnxruntime inside .venv."
                ) from exc
            self._ocr_engine = RapidOCR()
        return self._ocr_engine(str(image_path))

    def frame_fingerprint(self, image_path: Path) -> str:
        return default_visual_frame_fingerprint(image_path)


def compile_video_visual_raw_item(
    video_path: Path,
    *,
    force: bool = False,
    backend: Any | None = None,
    generated_at: datetime | None = None,
) -> VisualCompileArtifact:
    backend = backend or LocalVisualCompileBackend()
    if infer_media_compile_mode(video_path) != VISUAL_MODE:
        raise ValueError(
            f"video-visual compilation expects a file under raw/inbox/{VISUAL_MODE}/, got {video_path.relative_to(current_vault().root).as_posix()}"
        )
    if video_path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError(f"Unsupported video extension: {video_path.suffix or '(none)'}")

    note_path = compiled_visual_note_path(video_path)
    asset_dir = compiled_visual_asset_dir(video_path)
    sidecar_path = compiled_visual_ocr_regions_path(video_path)
    if note_path.exists() and not force:
        raise FileExistsError(
            f"Generated markdown already exists: {note_path.relative_to(current_vault().root).as_posix()} (rerun with --force to overwrite)"
        )

    probe = backend.probe(video_path)
    if not probe.has_video:
        raise ValueError(f"Media file has no video stream: {video_path.relative_to(current_vault().root).as_posix()}")

    timestamps = normalize_visual_timestamps(backend.select_timestamps(video_path, probe))
    if not timestamps:
        timestamps = [0.0]

    frames: list[VisualFrameRecord] = []
    anchor_counter = 1
    last_fingerprint = ""
    for candidate_index, timestamp_seconds in enumerate(timestamps, start=1):
        candidate_path = asset_dir / f".candidate-{candidate_index:04d}-{format_timestamp_token(timestamp_seconds)}.png"
        final_image_path = asset_dir / visual_frame_filename(len(frames) + 1, timestamp_seconds)
        regions: list[VisualRegionRecord] = []
        error = ""
        try:
            backend.extract_frame(video_path, timestamp_seconds, candidate_path)
        except Exception as exc:  # pragma: no cover
            error = f"Frame extraction failed: {exc}"
        else:
            fingerprint = get_visual_frame_fingerprint(backend, candidate_path)
            if frames and fingerprint == last_fingerprint:
                frames[-1].cover_end_seconds = timestamp_seconds
                if candidate_path.exists():
                    candidate_path.unlink()
                continue
            candidate_path.parent.mkdir(parents=True, exist_ok=True)
            candidate_path.replace(final_image_path)
            try:
                regions = filter_visual_ocr_regions(
                    normalize_ocr_regions(
                        backend.ocr_image(final_image_path) or [],
                        frame_width=probe.width,
                        frame_height=probe.height,
                    )
                )
            except Exception as exc:  # pragma: no cover
                error = f"OCR failed: {exc}"
            last_fingerprint = fingerprint
        anchors, anchor_counter = build_visual_anchor_records(regions, error=error, start=anchor_counter)
        frames.append(
            VisualFrameRecord(
                index=len(frames) + 1,
                cover_start_seconds=timestamp_seconds,
                cover_end_seconds=timestamp_seconds,
                rel_image_path=final_image_path.relative_to(current_vault().root).as_posix(),
                regions=regions,
                anchors=anchors,
                error=error,
            )
        )

    generated_at = generated_at or datetime.now(UTC)
    sidecar = build_visual_ocr_sidecar(video_path, frames, generated_at=generated_at)
    content = render_visual_source_markdown(video_path, probe, frames, generated_at=generated_at)
    write_text(sidecar_path, json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n")
    write_text(note_path, content)
    return VisualCompileArtifact(note_path=note_path, asset_dir=asset_dir, sidecar_path=sidecar_path, frame_count=len(frames))


def visual_frame_filename(index: int, timestamp_seconds: float) -> str:
    return f"frame-{index:04d}-{format_timestamp_token(timestamp_seconds)}.png"


def format_timestamp_token(value: float) -> str:
    total_milliseconds = max(0, int(round(value * 1000)))
    hours, rem = divmod(total_milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, milliseconds = divmod(rem, 1000)
    return f"{hours:02d}-{minutes:02d}-{seconds:02d}-{milliseconds:03d}"


def format_timestamp(value: float) -> str:
    return format_timestamp_token(value).replace("-", ":", 2).replace("-", ".", 1)


def normalize_visual_timestamps(values: list[float]) -> list[float]:
    seen: set[int] = set()
    normalized: list[float] = []
    for value in sorted(max(0.0, float(item)) for item in values):
        milliseconds = int(round(value * 1000))
        if milliseconds in seen:
            continue
        seen.add(milliseconds)
        normalized.append(milliseconds / 1000.0)
    return normalized


def probe_media_with_ffprobe(video_path: Path) -> MediaProbe:
    ffprobe_path = require_executable("ffprobe", install_hint="brew install ffmpeg")
    result = subprocess.run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {video_path.name}: {result.stderr.strip() or result.stdout.strip()}")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ffprobe returned invalid JSON for {video_path.name}") from exc

    streams = payload.get("streams", [])
    duration_seconds = to_float(payload.get("format", {}).get("duration")) or 0.0
    width: int | None = None
    height: int | None = None
    has_audio = False
    has_video = False
    for stream in streams:
        codec_type = as_string(stream.get("codec_type"))
        if codec_type == "video":
            has_video = True
            width = width or (int(stream["width"]) if stream.get("width") is not None else None)
            height = height or (int(stream["height"]) if stream.get("height") is not None else None)
        elif codec_type == "audio":
            has_audio = True
    return MediaProbe(
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        has_audio=has_audio,
        has_video=has_video,
    )


def detect_visual_timestamps(
    video_path: Path,
    *,
    duration_seconds: float,
    max_interval_seconds: float = DEFAULT_VISUAL_MAX_INTERVAL_SECONDS,
    max_frames: int = DEFAULT_VISUAL_MAX_FRAMES,
) -> list[float]:
    try:
        from scenedetect import SceneManager, open_video
        from scenedetect.detectors import ContentDetector
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Missing Python dependency for scene detection. Install scenedetect inside .venv.") from exc

    video = open_video(str(video_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector())
    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()

    timestamps: list[float] = []
    if scene_list:
        for start_time, end_time in scene_list:
            start_seconds = max(0.0, float(start_time.get_seconds()))
            end_seconds = max(start_seconds, float(end_time.get_seconds()))
            timestamps.append(start_seconds)
            cursor = start_seconds + max_interval_seconds
            while max_interval_seconds > 0 and cursor < end_seconds - 0.25:
                timestamps.append(cursor)
                cursor += max_interval_seconds
    else:
        timestamps.append(0.0)

    if duration_seconds > 0 and timestamps:
        last_timestamp = max(timestamps)
        cursor = last_timestamp + max_interval_seconds
        while max_interval_seconds > 0 and cursor < duration_seconds - 0.25:
            timestamps.append(cursor)
            cursor += max_interval_seconds

    timestamps = normalize_visual_timestamps(timestamps or [0.0])
    if len(timestamps) <= max_frames:
        return timestamps
    if max_frames <= 1:
        return [timestamps[0]]

    selected = [timestamps[0]]
    for index in range(1, max_frames - 1):
        source_index = round(index * (len(timestamps) - 1) / (max_frames - 1))
        selected.append(timestamps[source_index])
    selected.append(timestamps[-1])
    return normalize_visual_timestamps(selected)


def extract_frame_with_ffmpeg(video_path: Path, timestamp_seconds: float, output_path: Path) -> None:
    ffmpeg_path = require_executable("ffmpeg", install_hint="brew install ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{timestamp_seconds:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "ffmpeg frame extraction failed")


def normalize_ocr_lines(result: Any) -> list[str]:
    return [region["text"] for region in normalize_ocr_regions(result)]


def normalize_ocr_regions(
    result: Any,
    *,
    frame_width: int | None = None,
    frame_height: int | None = None,
) -> list[dict[str, Any]]:
    candidate = result[0] if isinstance(result, tuple) and result else result
    if candidate is None:
        return []

    parsed_items: list[dict[str, Any]] = []
    if hasattr(candidate, "txts"):
        texts = list(getattr(candidate, "txts", []) or [])
        scores = list(getattr(candidate, "scores", []) or [])
        boxes = list(getattr(candidate, "boxes", []) or [])
        for index, text in enumerate(texts):
            parsed_items.append(
                {
                    "text": text,
                    "score": scores[index] if index < len(scores) else None,
                    "bbox": boxes[index] if index < len(boxes) else None,
                }
            )
    elif isinstance(candidate, list):
        for item in candidate:
            parsed = parse_ocr_region_item(item)
            if parsed:
                parsed_items.append(parsed)
    else:
        text = as_string(candidate)
        if text:
            parsed_items.append({"text": text, "bbox": None, "score": None})

    normalized: list[dict[str, Any]] = []
    for item in parsed_items:
        text = normalize_ocr_text(as_string(item.get("text")))
        if not text:
            continue
        bbox, bbox_missing = normalize_region_bbox(
            item.get("bbox"),
            frame_width=frame_width,
            frame_height=frame_height,
        )
        normalized.append(
            {
                "text": text,
                "bbox": bbox,
                "bbox_missing": bbox_missing,
                "score": to_float(item.get("score")),
            }
        )
    return normalized


def parse_ocr_region_item(item: Any) -> dict[str, Any] | None:
    if isinstance(item, dict):
        return {
            "text": item.get("text") or item.get("txt") or item.get("content"),
            "bbox": item.get("bbox") or item.get("box") or item.get("points"),
            "score": item.get("score") or item.get("confidence"),
        }
    if isinstance(item, str):
        return {"text": item, "bbox": None, "score": None}
    if not isinstance(item, (list, tuple)) or not item:
        return None
    if len(item) >= 3 and isinstance(item[1], str):
        return {"bbox": item[0], "text": item[1], "score": item[2]}
    if isinstance(item[0], str):
        bbox = None
        score = None
        if len(item) >= 2:
            if isinstance(item[1], (list, tuple, dict)):
                bbox = item[1]
            else:
                score = to_float(item[1])
        if len(item) >= 3:
            if bbox is None and isinstance(item[2], (list, tuple, dict)):
                bbox = item[2]
            elif score is None:
                score = to_float(item[2])
        return {"text": item[0], "bbox": bbox, "score": score}
    return None


def normalize_region_bbox(
    raw_bbox: Any,
    *,
    frame_width: int | None,
    frame_height: int | None,
) -> tuple[list[float], bool]:
    coords: list[tuple[float, float]] = []
    if isinstance(raw_bbox, dict):
        if all(key in raw_bbox for key in ("x1", "y1", "x2", "y2")):
            coords = [
                (float(raw_bbox["x1"]), float(raw_bbox["y1"])),
                (float(raw_bbox["x2"]), float(raw_bbox["y2"])),
            ]
    elif isinstance(raw_bbox, (list, tuple)):
        if len(raw_bbox) == 4 and all(is_number(value) for value in raw_bbox):
            coords = [(float(raw_bbox[0]), float(raw_bbox[1])), (float(raw_bbox[2]), float(raw_bbox[3]))]
        else:
            for point in raw_bbox:
                if isinstance(point, (list, tuple)) and len(point) >= 2 and is_number(point[0]) and is_number(point[1]):
                    coords.append((float(point[0]), float(point[1])))
    if not coords:
        return [0.0, 0.0, 1.0, 1.0], True

    xs = [point[0] for point in coords]
    ys = [point[1] for point in coords]
    if max(abs(value) for value in (*xs, *ys)) > 1.5 and frame_width and frame_height:
        xs = [value / frame_width for value in xs]
        ys = [value / frame_height for value in ys]

    bbox = [
        round(min(max(min(xs), 0.0), 1.0), 4),
        round(min(max(min(ys), 0.0), 1.0), 4),
        round(min(max(max(xs), 0.0), 1.0), 4),
        round(min(max(max(ys), 0.0), 1.0), 4),
    ]
    return bbox, False


def is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def filter_visual_ocr_lines(lines: list[str]) -> list[str]:
    filtered: list[str] = []
    for line in lines:
        text = normalize_ocr_text(line)
        if not text:
            continue
        if is_visual_ocr_noise(text):
            continue
        filtered.append(text)
    return dedupe_preserve_order(filtered)


def filter_visual_ocr_regions(regions: list[dict[str, Any]]) -> list[VisualRegionRecord]:
    filtered: list[VisualRegionRecord] = []
    seen: set[tuple[str, tuple[float, ...]]] = set()
    for item in regions:
        text = normalize_ocr_text(as_string(item.get("text")))
        if not text or is_visual_ocr_noise(text):
            continue
        bbox = [round(float(value), 4) for value in list(item.get("bbox") or [0.0, 0.0, 1.0, 1.0])[:4]]
        bbox_key = tuple(bbox)
        key = (text, bbox_key)
        if key in seen:
            continue
        review = ""
        if maybe_visual_ocr_noise(text):
            review = "maybe_noise"
        score = to_float(item.get("score"))
        if not review and score is not None and score < 0.6:
            review = "ocr_unclear"
        if not review and bool(item.get("bbox_missing")):
            review = "layout_unclear"
        filtered.append(
            VisualRegionRecord(
                region_id=f"r{len(filtered) + 1:02d}",
                bbox=bbox,
                text=text,
                order=len(filtered) + 1,
                review=review,
            )
        )
        seen.add(key)
    return filtered


def normalize_ocr_text(value: str) -> str:
    text = re.sub(r"\s+", " ", as_string(value))
    text = text.strip(" \t\r\n｜|")
    return text


def is_visual_ocr_noise(text: str) -> bool:
    if len(text) <= 1:
        return True
    if any(re.match(pattern, text, flags=re.IGNORECASE) for pattern in VISUAL_OCR_NOISE_PATTERNS):
        return True
    if re.fullmatch(r"[\d\s:：.·,，%]+", text):
        return True
    if re.fullmatch(r"[♡❤★☆💬↗+\-\d\s]+", text):
        return True
    return False


def maybe_visual_ocr_noise(text: str) -> bool:
    return any(
        re.match(pattern, text, flags=re.IGNORECASE)
        for pattern in (
            r"^原声.*$",
            r"^更多.*$",
            r"^置顶.*$",
        )
    )


def default_visual_frame_fingerprint(image_path: Path) -> str:
    return hashlib.sha1(image_path.read_bytes()).hexdigest()


def get_visual_frame_fingerprint(backend: Any, image_path: Path) -> str:
    fingerprint = getattr(backend, "frame_fingerprint", None)
    if callable(fingerprint):
        return as_string(fingerprint(image_path))
    return default_visual_frame_fingerprint(image_path)


def build_visual_anchor_records(
    regions: list[VisualRegionRecord],
    *,
    error: str,
    start: int,
) -> tuple[list[VisualAnchorRecord], int]:
    anchors: list[VisualAnchorRecord] = []
    cursor = start
    for region in regions:
        anchors.append(
            VisualAnchorRecord(
                anchor_id=f"A{cursor:02d}",
                text=region.text,
                review=region.review,
                region_ids=(region.region_id,),
            )
        )
        cursor += 1
    if anchors:
        return anchors, cursor

    fallback_text = error or "未识别到明显文字"
    fallback_review = "ocr_unclear" if error else "layout_unclear"
    return [VisualAnchorRecord(anchor_id=f"A{cursor:02d}", text=fallback_text, review=fallback_review)], cursor + 1


def build_visual_ocr_sidecar(
    video_path: Path,
    frames: list[VisualFrameRecord],
    *,
    generated_at: datetime,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "compiled_at": generated_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "media": {
            "source_path": video_path.relative_to(current_vault().root).as_posix(),
            "mode": VISUAL_MODE.replace("-", "_"),
            "title": video_path.stem,
        },
        "frames": [
            {
                "frame_id": f"frame-{frame.index:04d}",
                "cover_start": format_timestamp(frame.cover_start_seconds),
                "cover_end": format_timestamp(frame.cover_end_seconds),
                "image_path": frame.rel_image_path,
                "regions": [
                    {
                        "region_id": region.region_id,
                        "bbox": region.bbox,
                        "text": region.text,
                        "order": region.order,
                        **({"review": region.review} if region.review else {}),
                    }
                    for region in frame.regions
                ],
            }
            for frame in frames
        ],
    }


def render_visual_source_markdown(
    video_path: Path,
    probe: MediaProbe,
    frames: list[VisualFrameRecord],
    *,
    generated_at: datetime,
) -> str:
    del probe
    origin = video_path.relative_to(current_vault().root).as_posix()
    doc_lang = detect_visual_doc_lang(video_path, frames)
    content_title = "内容记录" if doc_lang == "zh" else "Content Records"
    appendix_title = "锚点附录" if doc_lang == "zh" else "Anchor Appendix"
    review_after = (generated_at.date() + timedelta(days=30)).isoformat()
    lines = [
        "---",
        "type: source",
        "status: draft",
        "aliases: []",
        "source_refs:",
        f"  - {origin}",
        "tags:",
        "  - source",
        f"  - {VISUAL_MODE}",
        "  - media-compiled",
        "confidence: 0.55",
        f"updated_at: {generated_at.date().isoformat()}",
        f"review_after: {review_after}",
        "see_also: []",
        "part_of: []",
        "depends_on: []",
        "supports: []",
        "contradicts: []",
        "source_kind: extracted",
        "traceability_level: anchor",
        "---",
        "",
        f"## {content_title}",
    ]
    for frame in frames:
        lines.extend(
            [
                "",
                f"### E{frame.index:02d} | {visual_keywords_for_frame(frame, doc_lang=doc_lang)}",
                f"Time: {format_timestamp_span(frame.cover_start_seconds, frame.cover_end_seconds)}",
            ]
        )
        for anchor in frame.anchors:
            lines.append(f"- [{anchor.anchor_id}] {anchor.text}")

    lines.extend(["", f"## {appendix_title}"])
    for frame in frames:
        lines.extend(
            [
                "",
                f"### Frame {frame.index:02d}",
                f"Covers: {format_timestamp_span(frame.cover_start_seconds, frame.cover_end_seconds)}",
                f"Image: `{frame.rel_image_path}`",
                f"![Frame {frame.index:02d}]({frame.rel_image_path})",
            ]
        )
        for anchor in frame.anchors:
            lines.append(f"- [{anchor.anchor_id}] {anchor.text}")
            if anchor.review:
                lines.append(f"  Review: {anchor.review}")
    lines.append("")
    return "\n".join(lines)


def detect_visual_doc_lang(video_path: Path, frames: list[VisualFrameRecord]) -> str:
    samples = [video_path.stem]
    for frame in frames:
        samples.extend(region.text for region in frame.regions)
    return "zh" if any(has_cjk_text(sample) for sample in samples) else "en"


def has_cjk_text(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def visual_keywords_for_frame(frame: VisualFrameRecord, *, doc_lang: str) -> str:
    texts = [region.text for region in frame.regions] or [anchor.text for anchor in frame.anchors]
    if not texts:
        return "未识别文本" if doc_lang == "zh" else "No OCR text"
    keywords: list[str] = []
    for text in texts[:2]:
        compact = normalize_ocr_text(text)
        if len(compact) > 30:
            compact = compact[:27].rstrip() + "..."
        keywords.append(compact)
    return " / ".join(keywords)


def format_timestamp_span(start_seconds: float, end_seconds: float) -> str:
    start = format_timestamp(start_seconds)
    end = format_timestamp(end_seconds)
    return start if start == end else f"{start}-{end}"


def require_executable(name: str, *, install_hint: str) -> str:
    resolved = shutil.which(name)
    if resolved:
        return resolved
    raise RuntimeError(f"Missing required executable: {name}. Install it first with `{install_hint}`.")
