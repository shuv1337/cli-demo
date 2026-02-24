"""Timing preset profiles.

Presets control the pacing and duration of demo renders:
  - short:     8–15s, fast-paced social cuts
  - standard:  20–30s, balanced demo flow
  - cinematic: 35–60s, dramatic holds and transitions
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    """Timing preset configuration."""

    name: str
    fps: int

    # Duration targets (seconds)
    target_min_s: float
    target_max_s: float

    # Per-element timing (milliseconds)
    line_hold_ms: float       # How long a text line stays before next
    command_hold_ms: float    # Hold after a command prompt
    command_output_ms: float  # Per-line delay for command output
    spinner_cycle_ms: float   # Per-frame spinner delay
    spinner_cycles: int       # Number of spinner animation cycles
    progress_step_ms: float   # Per-step progress bar delay
    banner_hold_ms: float     # Hold time after banner display
    pause_ms: float           # Default scene pause duration

    # Intro/outro
    intro_hold_ms: float      # Hold on intro/banner
    outro_hold_ms: float      # Hold on final frame

    # Transitions
    transition_ms: float      # Default transition duration

    # Effect intensity scaling (1.0 = theme default)
    effect_scale: float = 1.0

    @property
    def target_min_ms(self) -> float:
        return self.target_min_s * 1000

    @property
    def target_max_ms(self) -> float:
        return self.target_max_s * 1000


# ── Built-in presets ──────────────────────────────────────────────────────

PRESETS: dict[str, Preset] = {
    "short": Preset(
        name="short",
        fps=24,
        target_min_s=8.0,
        target_max_s=15.0,
        line_hold_ms=60,
        command_hold_ms=200,
        command_output_ms=30,
        spinner_cycle_ms=50,
        spinner_cycles=12,
        progress_step_ms=20,
        banner_hold_ms=600,
        pause_ms=150,
        intro_hold_ms=400,
        outro_hold_ms=800,
        transition_ms=100,
        effect_scale=0.8,
    ),
    "standard": Preset(
        name="standard",
        fps=30,
        target_min_s=20.0,
        target_max_s=30.0,
        line_hold_ms=120,
        command_hold_ms=400,
        command_output_ms=60,
        spinner_cycle_ms=80,
        spinner_cycles=20,
        progress_step_ms=40,
        banner_hold_ms=1200,
        pause_ms=300,
        intro_hold_ms=800,
        outro_hold_ms=1500,
        transition_ms=200,
        effect_scale=1.0,
    ),
    "cinematic": Preset(
        name="cinematic",
        fps=30,
        target_min_s=35.0,
        target_max_s=60.0,
        line_hold_ms=200,
        command_hold_ms=700,
        command_output_ms=100,
        spinner_cycle_ms=100,
        spinner_cycles=30,
        progress_step_ms=60,
        banner_hold_ms=2000,
        pause_ms=500,
        intro_hold_ms=1500,
        outro_hold_ms=2500,
        transition_ms=400,
        effect_scale=1.2,
    ),
}


def get_preset(name: str) -> Preset:
    """Get a preset by name."""
    if name not in PRESETS:
        available = ", ".join(PRESETS.keys())
        raise ValueError(f"Unknown preset '{name}'. Available: {available}")
    return PRESETS[name]


def list_presets() -> list[str]:
    """List available preset names."""
    return list(PRESETS.keys())
