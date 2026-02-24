"""Multi-format export pipeline.

Exports rendered frames to:
  - GIF (Pillow + optional palette optimization)
  - MP4 (H.264 via ffmpeg)
  - WebM (VP9 via ffmpeg)
  - Cover PNG (best frame or specific index)

Supports aspect ratio variants and social cuts.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image

from demo_engine.config import RenderConfig


@dataclass
class ExportResult:
    """Result of an export operation."""

    format: str
    path: Path
    size_bytes: int = 0
    duration_s: float = 0.0
    resolution: tuple[int, int] = (0, 0)

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)

    def __str__(self) -> str:
        return (
            f"{self.format.upper()}: {self.path.name} "
            f"({self.size_mb:.1f}MB, {self.resolution[0]}x{self.resolution[1]}, "
            f"{self.duration_s:.1f}s)"
        )


@dataclass
class ExportManifest:
    """Complete export output manifest."""

    results: list[ExportResult] = field(default_factory=list)

    def add(self, result: ExportResult) -> None:
        self.results.append(result)

    def summary(self) -> str:
        lines = ["Export Summary:"]
        for r in self.results:
            lines.append(f"  {r}")
        return "\n".join(lines)


# ── GIF export ────────────────────────────────────────────────────────────

def export_gif(
    frames: list[Image.Image],
    output_path: Path,
    fps: int = 30,
    optimize: bool = True,
    loop: int = 0,
) -> ExportResult:
    """Export frames as an optimized GIF.

    Args:
        frames: List of PIL Image frames.
        output_path: Output .gif path.
        fps: Frames per second.
        optimize: Apply palette optimization.
        loop: Loop count (0 = infinite).
    """
    if not frames:
        raise ValueError("No frames to export")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    duration_ms = int(1000 / fps)

    # Convert to palette mode for GIF
    quantized = []
    for frame in frames:
        q = frame.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        quantized.append(q)

    quantized[0].save(
        str(output_path),
        save_all=True,
        append_images=quantized[1:],
        duration=duration_ms,
        loop=loop,
        optimize=optimize,
    )

    stat = output_path.stat()
    return ExportResult(
        format="gif",
        path=output_path,
        size_bytes=stat.st_size,
        duration_s=len(frames) / fps,
        resolution=frames[0].size,
    )


# ── Video export (ffmpeg) ─────────────────────────────────────────────────

def _check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    return shutil.which("ffmpeg") is not None


def export_mp4(
    frames: list[Image.Image],
    output_path: Path,
    fps: int = 30,
    crf: int = 18,
    audio_path: Optional[Path] = None,
) -> ExportResult:
    """Export frames as H.264 MP4 via ffmpeg.

    Args:
        frames: List of PIL Image frames.
        output_path: Output .mp4 path.
        fps: Frames per second.
        crf: Constant Rate Factor (lower = higher quality).
        audio_path: Optional audio file to mux in.
    """
    if not _check_ffmpeg():
        raise RuntimeError("ffmpeg not found — required for MP4 export")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="demo-export-") as tmpdir:
        tmpdir = Path(tmpdir)

        # Write frames as PNGs
        for i, frame in enumerate(frames):
            frame.save(tmpdir / f"{i:06d}.png")

        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(tmpdir / "%06d.png"),
        ]

        if audio_path and audio_path.exists():
            cmd.extend(["-i", str(audio_path), "-shortest"])

        cmd.extend([
            "-c:v", "libx264",
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path),
        ])

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr[:500]}")

    stat = output_path.stat()
    return ExportResult(
        format="mp4",
        path=output_path,
        size_bytes=stat.st_size,
        duration_s=len(frames) / fps,
        resolution=frames[0].size,
    )


def export_webm(
    frames: list[Image.Image],
    output_path: Path,
    fps: int = 30,
    crf: int = 30,
    audio_path: Optional[Path] = None,
) -> ExportResult:
    """Export frames as VP9 WebM via ffmpeg."""
    if not _check_ffmpeg():
        raise RuntimeError("ffmpeg not found — required for WebM export")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="demo-export-") as tmpdir:
        tmpdir = Path(tmpdir)

        for i, frame in enumerate(frames):
            frame.save(tmpdir / f"{i:06d}.png")

        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(tmpdir / "%06d.png"),
        ]

        if audio_path and audio_path.exists():
            cmd.extend(["-i", str(audio_path), "-shortest"])

        cmd.extend([
            "-c:v", "libvpx-vp9",
            "-crf", str(crf),
            "-b:v", "0",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ])

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr[:500]}")

    stat = output_path.stat()
    return ExportResult(
        format="webm",
        path=output_path,
        size_bytes=stat.st_size,
        duration_s=len(frames) / fps,
        resolution=frames[0].size,
    )


# ── Cover image ───────────────────────────────────────────────────────────

def export_cover(
    frames: list[Image.Image],
    output_path: Path,
    mode: str = "auto",
    frame_idx: Optional[int] = None,
) -> ExportResult:
    """Export a cover image from the frame sequence.

    Args:
        mode: "auto" (pick highest-info frame) or "frame:<idx>".
        frame_idx: Explicit frame index override.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if frame_idx is not None:
        idx = min(frame_idx, len(frames) - 1)
    elif mode.startswith("frame:"):
        idx = int(mode.split(":")[1])
        idx = min(idx, len(frames) - 1)
    else:
        # Auto: pick frame at ~60% through (usually has good content)
        idx = int(len(frames) * 0.6)

    cover = frames[idx]
    cover.save(str(output_path), quality=95)

    stat = output_path.stat()
    return ExportResult(
        format="png",
        path=output_path,
        size_bytes=stat.st_size,
        resolution=cover.size,
    )


# ── Social cuts ───────────────────────────────────────────────────────────

def cut_frames(
    frames: list[Image.Image],
    fps: int,
    cut_duration: str,
) -> list[Image.Image]:
    """Extract a subset of frames for a social media cut.

    Args:
        cut_duration: Duration string like "8s", "15s", "30s", "45s".
    """
    seconds = int(cut_duration.rstrip("s"))
    max_frames = seconds * fps

    if len(frames) <= max_frames:
        return frames

    # Take from the most interesting part (~20% in to capture content)
    start = int(len(frames) * 0.15)
    end = min(start + max_frames, len(frames))

    if end - start < max_frames:
        start = max(0, end - max_frames)

    return frames[start:end]


# ── Output naming ─────────────────────────────────────────────────────────

def generate_output_name(
    config: RenderConfig,
    scene_id: str = "demo",
    ext: str = "gif",
) -> str:
    """Generate standardized output filename.

    Format: <scene>-<theme>-<aspect>-<preset>.<ext>
    """
    aspect = config.aspect.replace(":", "x")
    return f"{scene_id}-{config.theme}-{aspect}-{config.preset}.{ext}"


# ── Master export orchestrator ────────────────────────────────────────────

def export_all(
    frames: list[Image.Image],
    config: RenderConfig,
    scene_id: str = "demo",
    audio_path: Optional[Path] = None,
) -> ExportManifest:
    """Run the full export pipeline based on config.

    Args:
        frames: Rendered frame sequence.
        config: Render configuration.
        scene_id: Scene identifier for naming.
        audio_path: Optional audio file.

    Returns:
        ExportManifest with all results.
    """
    manifest = ExportManifest()
    fps = config.fps
    outdir = config.outdir

    # Determine which formats to export
    formats = set()
    if config.export == "all":
        formats = {"gif", "mp4", "webm"}
    else:
        formats = {f.strip() for f in config.export.split(",")}

    # Apply social cuts if specified
    export_frames = frames
    if config.cut:
        export_frames = cut_frames(frames, fps, config.cut)

    # GIF
    if "gif" in formats:
        name = generate_output_name(config, scene_id, "gif")
        result = export_gif(export_frames, outdir / name, fps=fps)
        manifest.add(result)

    # MP4
    if "mp4" in formats:
        name = generate_output_name(config, scene_id, "mp4")
        result = export_mp4(
            export_frames, outdir / name, fps=fps, audio_path=audio_path
        )
        manifest.add(result)

    # WebM
    if "webm" in formats:
        name = generate_output_name(config, scene_id, "webm")
        result = export_webm(
            export_frames, outdir / name, fps=fps, audio_path=audio_path
        )
        manifest.add(result)

    # Cover PNG (always generated)
    cover_name = generate_output_name(config, scene_id, "png")
    cover_idx = None
    if config.cover.startswith("frame:"):
        cover_idx = int(config.cover.split(":")[1])
    cover_result = export_cover(
        frames, outdir / cover_name,
        mode=config.cover,
        frame_idx=cover_idx,
    )
    manifest.add(cover_result)

    return manifest
