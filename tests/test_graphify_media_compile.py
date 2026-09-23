from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
GRAPHIFY_PATH = ROOT / "scripts" / "graphify.py"


def load_graphify():
    spec = importlib.util.spec_from_file_location("graphify_media_compile", GRAPHIFY_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def patched_roots(graphify, root: Path):
    with graphify.use_vault(graphify.VaultContext(root)):
        yield


class FakeVisualBackend:
    def __init__(self, graphify):
        self.graphify = graphify
        self.extracted_timestamps: list[float] = []
        self.ocr_targets: list[Path] = []
        self.frame_signatures: dict[str, str] = {}

    def probe(self, video_path: Path):
        return self.graphify.MediaProbe(
            duration_seconds=98.433,
            width=592,
            height=1280,
            has_audio=True,
            has_video=True,
        )

    def select_timestamps(self, video_path: Path, probe):
        return [0.0, 12.5]

    def extract_frame(self, video_path: Path, timestamp_seconds: float, output_path: Path) -> None:
        self.extracted_timestamps.append(timestamp_seconds)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-png")
        self.frame_signatures[output_path.name] = f"frame-{timestamp_seconds:.3f}"

    def frame_fingerprint(self, image_path: Path) -> str:
        return self.frame_signatures[image_path.name]

    def ocr_image(self, image_path: Path) -> list[dict[str, object]]:
        self.ocr_targets.append(image_path)
        if "0001" in image_path.name:
            return [
                {"text": "11:11", "bbox": [0.10, 0.02, 0.20, 0.05], "score": 0.99},
                {"text": "强化学习到底在学什么？", "bbox": [0.08, 0.20, 0.78, 0.28], "score": 0.98},
                {"text": "action a", "bbox": [0.10, 0.32, 0.24, 0.36], "score": 0.41},
                {"text": "合集·大模型全景", "bbox": [0.02, 0.92, 0.24, 0.96], "score": 0.98},
            ]
        return [
            {"text": "SFT→RewardModel→PPO", "bbox": [0.22, 0.34, 0.69, 0.39], "score": 0.99},
            {"text": "Step1", "bbox": [0.15, 0.42, 0.24, 0.46], "score": 0.99},
            {"text": "Step2", "bbox": [0.42, 0.42, 0.51, 0.46], "score": 0.99},
            {"text": "下一集>", "bbox": [0.82, 0.95, 0.95, 0.98], "score": 0.99},
        ]


class FakeVisualDedupeBackend(FakeVisualBackend):
    def select_timestamps(self, video_path: Path, probe):
        return [0.0, 1.0, 12.5]

    def extract_frame(self, video_path: Path, timestamp_seconds: float, output_path: Path) -> None:
        super().extract_frame(video_path, timestamp_seconds, output_path)
        if timestamp_seconds in {0.0, 1.0}:
            self.frame_signatures[output_path.name] = "same-frame"
        else:
            self.frame_signatures[output_path.name] = "other-frame"


class GraphifyMediaCompileTest(unittest.TestCase):
    def test_main_routes_compile_media_without_loading_vault(self) -> None:
        graphify = load_graphify()
        argv = [str(GRAPHIFY_PATH), "compile-media", "raw/inbox/video-visual/demo.mp4"]

        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch("obsidian_graphify.cli.load_vault", side_effect=AssertionError("load_vault should not run")),
            mock.patch("obsidian_graphify.media.transfer_platform.command_compile_media", return_value=0) as compile_media,
        ):
            exit_code = graphify.main()

        self.assertEqual(exit_code, 0)
        compile_media.assert_called_once()
        self.assertEqual(compile_media.call_args.kwargs["target_path"], "raw/inbox/video-visual/demo.mp4")

    def test_infer_media_compile_mode_detects_expected_directories(self) -> None:
        graphify = load_graphify()

        self.assertEqual(
            graphify.infer_media_compile_mode(ROOT / "raw" / "inbox" / "video-visual" / "demo.mp4"),
            "video-visual",
        )
        self.assertEqual(
            graphify.infer_media_compile_mode(ROOT / "raw" / "inbox" / "video-audio" / "demo.mp4"),
            "video-audio",
        )
        self.assertEqual(
            graphify.infer_media_compile_mode(ROOT / "raw" / "inbox" / "audio" / "demo.m4a"),
            "audio",
        )
        self.assertIsNone(graphify.infer_media_compile_mode(ROOT / "raw" / "inbox" / "demo.mp4"))

    def test_visual_output_paths_preserve_subdirectories(self) -> None:
        graphify = load_graphify()
        video_path = ROOT / "raw" / "inbox" / "video-visual" / "专题" / "demo.mp4"

        self.assertEqual(
            graphify.compiled_visual_note_path(video_path).relative_to(ROOT).as_posix(),
            "raw/compiled/visual/专题/demo（视觉编译）.md",
        )
        self.assertEqual(
            graphify.compiled_visual_asset_dir(video_path).relative_to(ROOT).as_posix(),
            "raw/assets/video-visual/专题/demo",
        )
        self.assertEqual(
            graphify.compiled_visual_ocr_regions_path(video_path).relative_to(ROOT).as_posix(),
            "raw/assets/video-visual/专题/demo/ocr_regions.json",
        )

    def test_collect_raw_items_skips_raw_assets_files(self) -> None:
        graphify = load_graphify()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "raw" / "inbox" / "video-visual").mkdir(parents=True)
            (root / "raw" / "assets" / "video-visual" / "demo").mkdir(parents=True)
            (root / "raw" / "inbox" / "video-visual" / "demo.mp4").write_bytes(b"video")
            (root / "raw" / "assets" / "video-visual" / "demo" / "frame-0001.png").write_bytes(b"png")

            with patched_roots(graphify, root):
                items = graphify.collect_raw_items()

        rel_paths = {item.rel_path for item in items}
        self.assertIn("raw/inbox/video-visual/demo.mp4", rel_paths)
        self.assertNotIn("raw/assets/video-visual/demo/frame-0001.png", rel_paths)

    def test_compile_video_visual_raw_item_writes_canonical_note_and_sidecar(self) -> None:
        graphify = load_graphify()
        backend = FakeVisualBackend(graphify)
        generated_at = datetime(2026, 5, 31, 10, 30, tzinfo=UTC)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_path = root / "raw" / "inbox" / "video-visual" / "demo.mp4"
            video_path.parent.mkdir(parents=True, exist_ok=True)
            video_path.write_bytes(b"video")

            with patched_roots(graphify, root):
                artifact = graphify.compile_video_visual_raw_item(
                    video_path,
                    force=False,
                    backend=backend,
                    generated_at=generated_at,
                )

                note_path = artifact.note_path
                asset_dir = artifact.asset_dir
                sidecar_path = artifact.sidecar_path
                content = note_path.read_text(encoding="utf-8")
                payload = json.loads(sidecar_path.read_text(encoding="utf-8"))

        self.assertEqual(artifact.frame_count, 2)
        self.assertEqual(note_path.relative_to(root).as_posix(), "raw/compiled/visual/demo（视觉编译）.md")
        self.assertEqual(asset_dir.relative_to(root).as_posix(), "raw/assets/video-visual/demo")
        self.assertEqual(sidecar_path.relative_to(root).as_posix(), "raw/assets/video-visual/demo/ocr_regions.json")
        self.assertIn("type: source", content)
        self.assertIn("status: draft", content)
        self.assertIn("source_kind: extracted", content)
        self.assertIn("traceability_level: anchor", content)
        self.assertIn("source_refs:", content)
        self.assertIn("- raw/inbox/video-visual/demo.mp4", content)
        self.assertIn("## 内容记录", content)
        self.assertIn("## 锚点附录", content)
        self.assertIn("### E01 |", content)
        self.assertIn("Time: 00:00:00.000", content)
        self.assertIn("### Frame 01", content)
        self.assertIn("Covers: 00:00:00.000", content)
        self.assertIn("Image: `raw/assets/video-visual/demo/frame-0001-00-00-00-000.png`", content)
        self.assertIn("![Frame 01](", content)
        self.assertIn("- [A01] 强化学习到底在学什么？", content)
        self.assertIn("强化学习到底在学什么？", content)
        self.assertIn("Review: ocr_unclear", content)
        self.assertNotIn("全屏观看", content)
        self.assertNotIn("合集", content)
        self.assertNotIn("下一集", content)
        self.assertEqual(backend.extracted_timestamps, [0.0, 12.5])
        self.assertEqual(len(backend.ocr_targets), 2)
        self.assertEqual(payload["schema_version"], "1")
        self.assertEqual(payload["media"]["source_path"], "raw/inbox/video-visual/demo.mp4")
        self.assertEqual(payload["media"]["mode"], "video_visual")
        self.assertEqual(payload["media"]["title"], "demo")
        self.assertEqual(len(payload["frames"]), 2)
        self.assertEqual(payload["frames"][0]["cover_start"], "00:00:00.000")
        self.assertEqual(payload["frames"][0]["cover_end"], "00:00:00.000")
        self.assertEqual(payload["frames"][0]["regions"][0]["text"], "强化学习到底在学什么？")
        self.assertEqual(payload["frames"][0]["regions"][1]["review"], "ocr_unclear")
        self.assertEqual(payload["frames"][1]["regions"][0]["text"], "SFT→RewardModel→PPO")

    def test_compile_video_visual_raw_item_dedupes_static_frames_and_extends_cover_range(self) -> None:
        graphify = load_graphify()
        backend = FakeVisualDedupeBackend(graphify)
        generated_at = datetime(2026, 5, 31, 10, 30, tzinfo=UTC)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_path = root / "raw" / "inbox" / "video-visual" / "demo.mp4"
            video_path.parent.mkdir(parents=True, exist_ok=True)
            video_path.write_bytes(b"video")

            with patched_roots(graphify, root):
                artifact = graphify.compile_video_visual_raw_item(
                    video_path,
                    force=False,
                    backend=backend,
                    generated_at=generated_at,
                )
                content = artifact.note_path.read_text(encoding="utf-8")
                payload = json.loads(artifact.sidecar_path.read_text(encoding="utf-8"))

        self.assertEqual(artifact.frame_count, 2)
        self.assertEqual(backend.extracted_timestamps, [0.0, 1.0, 12.5])
        self.assertEqual(len(backend.ocr_targets), 2)
        self.assertEqual(payload["frames"][0]["cover_start"], "00:00:00.000")
        self.assertEqual(payload["frames"][0]["cover_end"], "00:00:01.000")
        self.assertIn("Time: 00:00:00.000-00:00:01.000", content)
        self.assertIn("Covers: 00:00:00.000-00:00:01.000", content)
        self.assertEqual(content.count("![Frame 01]("), 1)

    def test_filter_visual_ocr_noise_removes_short_video_ui_text(self) -> None:
        graphify = load_graphify()

        filtered = graphify.filter_visual_ocr_lines(
            [
                "11:11",
                "5G88",
                "全屏观看",
                "1天前",
                "合集·大模型全景",
                "下一集>",
                "第17集IRLHF、PPO、DPO、GRPO：大模.展开",
                "9个人观点，仅供参考",
                "第17集 | RLHF、PPO、DPO、GRPO：大模型对齐算法盘点",
                "Reward Model",
                "善语结善缘，恶言伤人心",
            ]
        )

        self.assertEqual(
            filtered,
            [
                "第17集 | RLHF、PPO、DPO、GRPO：大模型对齐算法盘点",
                "Reward Model",
            ],
        )

    def test_command_compile_media_shells_out_to_transfer_platform_for_visual_mode(self) -> None:
        graphify = load_graphify()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_path = root / "raw" / "inbox" / "video-visual" / "专题" / "demo.mp4"
            video_path.parent.mkdir(parents=True, exist_ok=True)
            video_path.write_bytes(b"video")

            with (
                patched_roots(graphify, root),
                mock.patch("obsidian_graphify.media.transfer_platform.resolve_transfer_platform_executable", return_value="/tmp/transfer-platform"),
                mock.patch.object(
                    subprocess,
                    "run",
                    return_value=mock.Mock(returncode=0, stdout="compiled\n", stderr=""),
                ) as run_mock,
                mock.patch.object(sys, "stdout", new_callable=io.StringIO) as stdout,
            ):
                exit_code = graphify.command_compile_media("raw/inbox/video-visual/专题/demo.mp4", force=True)

        self.assertEqual(exit_code, 0)
        run_mock.assert_called_once()
        command = run_mock.call_args.args[0]
        self.assertEqual(command[:4], ["/tmp/transfer-platform", "compile", "visual", str(video_path)])
        self.assertIn("--markdown-path", command)
        self.assertIn(str(root / "raw" / "compiled" / "visual" / "专题" / "demo（视觉编译）.md"), command)
        self.assertIn("--sidecar-path", command)
        self.assertIn(str(root / "raw" / "assets" / "video-visual" / "专题" / "demo" / "ocr_regions.json"), command)
        self.assertIn("--assets-dir", command)
        self.assertIn(str(root / "raw" / "assets" / "video-visual" / "专题" / "demo"), command)
        self.assertIn("--force", command)
        self.assertIn("Wrote raw/compiled/visual/专题/demo（视觉编译）.md", stdout.getvalue())

    def test_command_compile_media_reports_transfer_platform_failure(self) -> None:
        graphify = load_graphify()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_path = root / "raw" / "inbox" / "video-visual" / "demo.mp4"
            video_path.parent.mkdir(parents=True, exist_ok=True)
            video_path.write_bytes(b"video")

            with (
                patched_roots(graphify, root),
                mock.patch("obsidian_graphify.media.transfer_platform.resolve_transfer_platform_executable", return_value="/tmp/transfer-platform"),
                mock.patch.object(
                    subprocess,
                    "run",
                    return_value=mock.Mock(returncode=1, stdout="", stderr="compile failed\n"),
                ),
                mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr,
            ):
                exit_code = graphify.command_compile_media("raw/inbox/video-visual/demo.mp4")

        self.assertEqual(exit_code, 1)
        self.assertIn("compile failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
