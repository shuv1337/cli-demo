"""Audio layer — soundtrack and SFX hooks.

Manages:
  - Soundtrack selection and looping
  - SFX event triggers (click, success, error)
  - Beat-sync markers for timeline alignment
  - Audio muxing into video exports
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from demo_engine.config import ASSETS_DIR


@dataclass
class AudioTrack:
    """An audio track reference."""

    path: Path
    label: str = ""
    duration_s: float = 0.0
    loop: bool = False

    @property
    def exists(self) -> bool:
        return self.path.exists()


@dataclass
class SFXEvent:
    """A sound effect event at a specific timestamp."""

    t_ms: float
    sfx_name: str
    volume: float = 1.0


@dataclass
class AudioMix:
    """Complete audio mix for a render."""

    soundtrack: Optional[AudioTrack] = None
    sfx_events: list[SFXEvent] = field(default_factory=list)
    output_path: Optional[Path] = None
    enabled: bool = False

    def add_sfx(self, t_ms: float, sfx_name: str, volume: float = 1.0) -> None:
        self.sfx_events.append(SFXEvent(t_ms=t_ms, sfx_name=sfx_name, volume=volume))


# ── Audio asset discovery ─────────────────────────────────────────────────

SOUNDTRACK_DIR = ASSETS_DIR / "audio"
SFX_MAP = {
    "click": "ui_click.wav",
    "success": "success_chime.wav",
}


def find_soundtrack(name: str) -> Optional[AudioTrack]:
    """Find a soundtrack by name in the assets directory."""
    # Try exact match
    for ext in (".mp3", ".wav", ".ogg"):
        path = SOUNDTRACK_DIR / f"{name}{ext}"
        if path.exists():
            return AudioTrack(path=path, label=name, loop=True)

    # Try partial match
    if SOUNDTRACK_DIR.exists():
        for f in SOUNDTRACK_DIR.iterdir():
            if name.lower() in f.stem.lower():
                return AudioTrack(path=f, label=f.stem, loop=True)

    return None


def find_sfx(name: str) -> Optional[Path]:
    """Find a sound effect file by name."""
    if name in SFX_MAP:
        path = SOUNDTRACK_DIR / SFX_MAP[name]
        if path.exists():
            return path

    # Direct file check
    path = SOUNDTRACK_DIR / name
    if path.exists():
        return path

    return None


# ── Audio mixing ──────────────────────────────────────────────────────────

def _check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def mix_audio(
    audio_mix: AudioMix,
    duration_s: float,
    output_path: Path,
) -> Optional[Path]:
    """Mix soundtrack and SFX into a single audio file.

    This is a simplified mixer — for complex mixes, consider
    using a dedicated audio library.

    Returns output path or None if mixing isn't possible.
    """
    if not audio_mix.enabled or not audio_mix.soundtrack:
        return None

    if not _check_ffmpeg():
        return None

    if not audio_mix.soundtrack.exists:
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Simple approach: trim/loop soundtrack to duration
    cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_mix.soundtrack.path),
        "-t", str(duration_s),
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and output_path.exists():
            audio_mix.output_path = output_path
            return output_path
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


def prepare_audio(
    config_audio: bool,
    theme_name: str,
    duration_s: float,
    outdir: Path,
) -> Optional[Path]:
    """Prepare audio for a render if enabled.

    Returns path to mixed audio file, or None.
    """
    if not config_audio:
        return None

    # Try to find a theme-matching soundtrack
    soundtrack = find_soundtrack(theme_name)
    if not soundtrack:
        soundtrack = find_soundtrack("synthwave_loop")

    if not soundtrack:
        return None

    mix = AudioMix(soundtrack=soundtrack, enabled=True)
    output = outdir / "audio_mix.aac"
    return mix_audio(mix, duration_s, output)
