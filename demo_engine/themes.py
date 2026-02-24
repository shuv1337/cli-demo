"""Theme loader, validator, and registry.

Themes are JSON files in the themes/ directory that define:
  - Color palette (bg, text, cmd, success, warn, accent, etc.)
  - Effect toggles and intensity (CRT, scanlines, noise, vignette, glitch)
  - Glyph substitution map for font-safety
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from demo_engine.config import THEMES_DIR


# ── Schema for validation ─────────────────────────────────────────────────

REQUIRED_COLORS = {"bg", "text", "cmd", "success", "warn", "accent"}
OPTIONAL_COLORS = {"panel", "header", "error", "dim", "cursor", "border"}
ALL_COLORS = REQUIRED_COLORS | OPTIONAL_COLORS

EFFECT_KEYS = {
    "crt": bool,
    "scanlines": (int, float),
    "noise": (int, float),
    "vignette": (int, float),
    "glitch_cuts": bool,
    "glow": (int, float),
    "chromatic_aberration": (int, float),
}


class ThemeError(Exception):
    """Raised when a theme is invalid."""

    pass


@dataclass
class ThemeColors:
    """Theme color palette."""

    bg: str = "#0a0a0a"
    panel: str = "#141414"
    header: str = "#1e1e1e"
    text: str = "#e0e0e0"
    cmd: str = "#67e8f9"
    success: str = "#86efac"
    warn: str = "#fbbf24"
    accent: str = "#c084fc"
    error: str = "#f87171"
    dim: str = "#666666"
    cursor: str = "#ffffff"
    border: str = "#333333"


@dataclass
class ThemeEffects:
    """Theme effect configuration."""

    crt: bool = False
    scanlines: float = 0.0
    noise: float = 0.0
    vignette: float = 0.0
    glitch_cuts: bool = False
    glow: float = 0.0
    chromatic_aberration: float = 0.0


@dataclass
class Theme:
    """A fully resolved theme."""

    id: str
    name: str = ""
    colors: ThemeColors = field(default_factory=ThemeColors)
    effects: ThemeEffects = field(default_factory=ThemeEffects)
    glyph_map: dict[str, str] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.id.title()


# ── Loader ────────────────────────────────────────────────────────────────

def validate_theme_data(data: dict, source: str = "<unknown>") -> list[str]:
    """Validate theme JSON data. Returns list of error messages (empty = valid)."""
    errors = []

    if "id" not in data:
        errors.append(f"{source}: missing required field 'id'")

    colors = data.get("colors", {})
    for key in REQUIRED_COLORS:
        if key not in colors:
            errors.append(f"{source}: missing required color '{key}'")

    for key, val in colors.items():
        if key not in ALL_COLORS:
            errors.append(f"{source}: unknown color key '{key}'")
        if not isinstance(val, str) or not val.startswith("#"):
            errors.append(f"{source}: color '{key}' must be a hex string (got {val!r})")

    effects = data.get("effects", {})
    for key, val in effects.items():
        if key not in EFFECT_KEYS:
            errors.append(f"{source}: unknown effect key '{key}'")
        else:
            expected = EFFECT_KEYS[key]
            if not isinstance(val, expected):
                errors.append(
                    f"{source}: effect '{key}' should be {expected}, got {type(val).__name__}"
                )

    return errors


def load_theme_from_dict(data: dict) -> Theme:
    """Load a Theme from a validated dict."""
    colors_data = data.get("colors", {})
    effects_data = data.get("effects", {})

    colors = ThemeColors(**{k: v for k, v in colors_data.items() if k in ALL_COLORS})
    effects = ThemeEffects(
        **{k: v for k, v in effects_data.items() if k in EFFECT_KEYS}
    )

    return Theme(
        id=data["id"],
        name=data.get("name", data["id"].title()),
        colors=colors,
        effects=effects,
        glyph_map=data.get("glyph_map", {}),
        meta=data.get("meta", {}),
    )


def load_theme(name: str, themes_dir: Optional[Path] = None) -> Theme:
    """Load a theme by name from the themes directory."""
    themes_dir = themes_dir or THEMES_DIR
    path = themes_dir / f"{name}.json"

    if not path.exists():
        available = list_themes(themes_dir)
        raise ThemeError(
            f"Theme '{name}' not found at {path}. "
            f"Available: {', '.join(available) or 'none'}"
        )

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ThemeError(f"Invalid JSON in {path}: {e}") from e

    errors = validate_theme_data(data, source=str(path))
    if errors:
        raise ThemeError("Theme validation failed:\n  " + "\n  ".join(errors))

    return load_theme_from_dict(data)


def list_themes(themes_dir: Optional[Path] = None) -> list[str]:
    """List available theme names."""
    themes_dir = themes_dir or THEMES_DIR
    if not themes_dir.exists():
        return []
    return sorted(p.stem for p in themes_dir.glob("*.json"))
