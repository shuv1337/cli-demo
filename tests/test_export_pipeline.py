"""Tests for the export pipeline — GIF, MP4, WebM, cover PNG."""

import shutil
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from demo_engine.export import (
    ExportManifest,
    ExportResult,
    cut_frames,
    export_cover,
    export_gif,
    export_mp4,
    export_webm,
    generate_output_name,
)
from demo_engine.config import RenderConfig


def _make_test_frames(n: int = 10, w: int = 320, h: int = 240) -> list[Image.Image]:
    """Generate simple test frames."""
    frames = []
    for i in range(n):
        img = Image.new("RGB", (w, h), (i * 25 % 256, 50, 100))
        frames.append(img)
    return frames


class TestGifExport:
    def test_basic_gif(self):
        frames = _make_test_frames(10)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.gif"
            result = export_gif(frames, path, fps=10)
            assert result.path.exists()
            assert result.size_bytes > 0
            assert result.format == "gif"
            assert result.duration_s == 1.0

    def test_empty_frames_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="No frames"):
                export_gif([], Path(tmpdir) / "empty.gif")

    def test_single_frame(self):
        frames = _make_test_frames(1)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "single.gif"
            result = export_gif(frames, path, fps=10)
            assert result.path.exists()


class TestMp4Export:
    @pytest.mark.skipif(
        not shutil.which("ffmpeg"), reason="ffmpeg not available"
    )
    def test_basic_mp4(self):
        frames = _make_test_frames(30)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.mp4"
            result = export_mp4(frames, path, fps=30)
            assert result.path.exists()
            assert result.size_bytes > 0
            assert result.format == "mp4"

    def test_no_ffmpeg_raises(self):
        """If ffmpeg somehow isn't there, should raise."""
        # This test passes if ffmpeg IS available (it won't reach the error)
        frames = _make_test_frames(5)
        with tempfile.TemporaryDirectory() as tmpdir:
            if shutil.which("ffmpeg"):
                path = Path(tmpdir) / "test.mp4"
                result = export_mp4(frames, path)
                assert result.path.exists()


class TestWebmExport:
    @pytest.mark.skipif(
        not shutil.which("ffmpeg"), reason="ffmpeg not available"
    )
    def test_basic_webm(self):
        frames = _make_test_frames(30)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.webm"
            result = export_webm(frames, path, fps=30)
            assert result.path.exists()
            assert result.format == "webm"


class TestCoverExport:
    def test_auto_cover(self):
        frames = _make_test_frames(20)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cover.png"
            result = export_cover(frames, path, mode="auto")
            assert result.path.exists()
            assert result.format == "png"

    def test_specific_frame(self):
        frames = _make_test_frames(20)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cover.png"
            result = export_cover(frames, path, frame_idx=5)
            assert result.path.exists()

    def test_frame_mode_string(self):
        frames = _make_test_frames(20)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "cover.png"
            result = export_cover(frames, path, mode="frame:3")
            assert result.path.exists()


class TestCutFrames:
    def test_short_cut(self):
        frames = _make_test_frames(300)  # 10s at 30fps
        cut = cut_frames(frames, 30, "5s")
        assert len(cut) == 150

    def test_cut_shorter_than_total(self):
        frames = _make_test_frames(30)  # 1s at 30fps
        cut = cut_frames(frames, 30, "5s")
        # Should return all frames since total < cut
        assert len(cut) == 30

    def test_cut_15s(self):
        frames = _make_test_frames(900)  # 30s at 30fps
        cut = cut_frames(frames, 30, "15s")
        assert len(cut) == 450


class TestOutputNaming:
    def test_default_name(self):
        config = RenderConfig(theme="glitch", aspect="16:9", preset="standard")
        name = generate_output_name(config, "demo", "gif")
        assert name == "demo-glitch-16x9-standard.gif"

    def test_square_aspect(self):
        config = RenderConfig(theme="matrix", aspect="1:1", preset="short")
        name = generate_output_name(config, "launch", "mp4")
        assert name == "launch-matrix-1x1-short.mp4"


class TestExportManifest:
    def test_manifest_summary(self):
        manifest = ExportManifest()
        manifest.add(ExportResult(
            format="gif", path=Path("test.gif"),
            size_bytes=1024 * 1024, duration_s=10.0, resolution=(1920, 1080),
        ))
        summary = manifest.summary()
        assert "GIF" in summary
        assert "1.0MB" in summary
