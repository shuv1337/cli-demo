"""Central configuration for the demo engine."""

from __future__ import annotations

import os
import random
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Resolve project root relative to this file
PROJECT_ROOT = Path(__file__).resolve().parent.parent
THEMES_DIR = PROJECT_ROOT / "themes"
SCENES_DIR = PROJECT_ROOT / "scenes"
ASSETS_DIR = PROJECT_ROOT / "assets"
DEFAULT_OUTDIR = PROJECT_ROOT


@dataclass
class RenderConfig:
    """Full render configuration assembled from CLI flags, env, and defaults."""

    # Core
    theme: str = "synthwave"
    preset: str = "standard"
    scenario: Optional[str] = None
    seed: Optional[int] = None

    # Display
    aspect: str = "16:9"
    font_profile: str = "nerd-safe"
    font_strict: bool = False

    # Export
    export: str = "gif"  # gif | mp4 | webm | all
    outdir: Path = field(default_factory=lambda: DEFAULT_OUTDIR)
    cover: str = "auto"  # auto | frame:<idx> | none
    cut: Optional[str] = None  # 8s | 15s | 30s | 45s

    # Timing
    speed: float = 1.0

    # Audio
    audio: bool = False

    # Workspace
    keep_workspace: bool = False
    workspace: Optional[Path] = None

    # Internals (set during init)
    rng: random.Random = field(default_factory=random.Random, repr=False)

    def __post_init__(self) -> None:
        self.outdir = Path(self.outdir)
        if self.seed is not None:
            self.rng = random.Random(self.seed)
        if self.workspace is None:
            self.workspace = Path(
                tempfile.mkdtemp(prefix=f"demo-{self.theme}-")
            )

    @property
    def fps(self) -> int:
        """Frames per second based on preset."""
        from demo_engine.presets import get_preset

        return get_preset(self.preset).fps

    @property
    def resolution(self) -> tuple[int, int]:
        """Canvas resolution based on aspect ratio."""
        aspect_map = {
            "16:9": (1920, 1080),
            "1:1": (1080, 1080),
            "9:16": (1080, 1920),
        }
        return aspect_map.get(self.aspect, (1920, 1080))

    def cleanup(self) -> None:
        """Remove workspace if not keeping."""
        import shutil

        if not self.keep_workspace and self.workspace and self.workspace.exists():
            shutil.rmtree(self.workspace, ignore_errors=True)
