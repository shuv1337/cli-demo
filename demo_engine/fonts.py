"""Font discovery, fallback chain, and glyph coverage auditing.

Handles:
  - System font discovery via fontconfig (fc-list)
  - Nerd Font detection and preference ordering
  - Glyph coverage checking via fonttools
  - Per-character font selection for missing glyphs (Pillow workaround)
  - Theme-level glyph map substitutions
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

from PIL import ImageFont

# ── Font profiles ─────────────────────────────────────────────────────────

FONT_PROFILES: dict[str, list[str]] = {
    "nerd-safe": [
        "JetBrainsMono Nerd Font Mono",
        "JetBrainsMonoNL Nerd Font Mono",
        "CaskaydiaMono Nerd Font Mono",
        "MesloLGS Nerd Font Mono",
    ],
    "classic": [
        "JetBrains Mono",
        "Cascadia Mono",
        "Fira Code",
        "Source Code Pro",
        "DejaVu Sans Mono",
    ],
}

# Symbol fallback fonts (tried after primary stack)
SYMBOL_FALLBACKS = [
    "Noto Sans Symbols2",
    "Noto Sans Symbols",
    "Symbola",
]

DEFAULT_FONT_SIZE = 16


@dataclass
class FontStack:
    """Resolved font stack with loaded Pillow font objects."""

    primary: ImageFont.FreeTypeFont
    primary_path: str
    fallbacks: list[ImageFont.FreeTypeFont] = field(default_factory=list)
    fallback_paths: list[str] = field(default_factory=list)
    size: int = DEFAULT_FONT_SIZE
    bold: Optional[ImageFont.FreeTypeFont] = None
    bold_path: Optional[str] = None

    def get_font_for_char(self, char: str) -> ImageFont.FreeTypeFont:
        """Return the best font for rendering a specific character.

        Pillow doesn't do automatic font fallback, so we manually check
        glyph availability and select the appropriate font.
        """
        if _font_has_glyph(self.primary, char):
            return self.primary
        for fb in self.fallbacks:
            if _font_has_glyph(fb, char):
                return fb
        # Fall back to primary even if glyph is missing
        return self.primary


def _font_has_glyph(font: ImageFont.FreeTypeFont, char: str) -> bool:
    """Check if a font can render a specific character (non-tofu)."""
    try:
        # Use getmask to check — returns None-width for missing glyphs
        mask = font.getmask(char)
        return mask.size[0] > 0 and mask.size[1] > 0
    except Exception:
        return False


# ── System font discovery ─────────────────────────────────────────────────

@lru_cache(maxsize=1)
def discover_system_fonts() -> dict[str, str]:
    """Discover monospace fonts available on the system via fc-list.

    Returns dict mapping family name → file path.
    """
    fonts: dict[str, str] = {}
    try:
        result = subprocess.run(
            ["fc-list", ":spacing=100", "family", "file"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.strip().split("\n"):
            if ":" not in line:
                continue
            file_part, family_part = line.split(":", 1)
            file_path = file_part.strip()
            # fc-list can return comma-separated family names
            families = [f.strip() for f in family_part.strip().split(",")]
            for fam in families:
                if fam and file_path:
                    fonts[fam] = file_path
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return fonts


def find_font_path(family: str) -> Optional[str]:
    """Find a specific font family's file path on the system."""
    system_fonts = discover_system_fonts()

    # Exact match
    if family in system_fonts:
        return system_fonts[family]

    # Partial match
    family_lower = family.lower()
    for name, path in system_fonts.items():
        if family_lower in name.lower():
            return path

    return None


def resolve_font_stack(
    profile: str = "nerd-safe",
    size: int = DEFAULT_FONT_SIZE,
) -> FontStack:
    """Resolve a full font stack from the given profile.

    Tries each font in the profile until one is found on the system.
    Adds symbol fallback fonts afterward.
    """
    families = FONT_PROFILES.get(profile, FONT_PROFILES["nerd-safe"])

    primary_path = None
    primary_family = None

    for fam in families:
        path = find_font_path(fam)
        if path:
            primary_path = path
            primary_family = fam
            break

    if not primary_path:
        # Ultimate fallback: Pillow default
        return FontStack(
            primary=ImageFont.load_default(),
            primary_path="<default>",
            size=size,
        )

    primary_font = ImageFont.truetype(primary_path, size)

    # Find bold variant
    bold_font = None
    bold_path = None
    if primary_path:
        bold_candidate = primary_path.replace("Regular", "Bold")
        if Path(bold_candidate).exists() and bold_candidate != primary_path:
            bold_font = ImageFont.truetype(bold_candidate, size)
            bold_path = bold_candidate

    # Build fallback chain
    fallbacks = []
    fallback_paths = []
    for fam in families:
        if fam == primary_family:
            continue
        path = find_font_path(fam)
        if path:
            try:
                fallbacks.append(ImageFont.truetype(path, size))
                fallback_paths.append(path)
            except Exception:
                pass

    # Add symbol fallbacks
    for fam in SYMBOL_FALLBACKS:
        path = find_font_path(fam)
        if path:
            try:
                fallbacks.append(ImageFont.truetype(path, size))
                fallback_paths.append(path)
            except Exception:
                pass

    return FontStack(
        primary=primary_font,
        primary_path=primary_path,
        fallbacks=fallbacks,
        fallback_paths=fallback_paths,
        size=size,
        bold=bold_font,
        bold_path=bold_path,
    )


# ── Glyph audit ──────────────────────────────────────────────────────────

@dataclass
class GlyphAuditResult:
    """Result of auditing glyph coverage for a text corpus."""

    total_chars: int = 0
    covered: int = 0
    missing: list[str] = field(default_factory=list)
    substitutions: dict[str, str] = field(default_factory=dict)

    @property
    def coverage_pct(self) -> float:
        return (self.covered / self.total_chars * 100) if self.total_chars else 100.0

    @property
    def is_clean(self) -> bool:
        return len(self.missing) == 0

    def report(self) -> str:
        lines = [
            f"Glyph Audit Report",
            f"  Total unique chars: {self.total_chars}",
            f"  Covered:            {self.covered} ({self.coverage_pct:.1f}%)",
            f"  Missing:            {len(self.missing)}",
        ]
        if self.missing:
            chars = ", ".join(
                f"U+{ord(c):04X} ({c})" for c in self.missing[:20]
            )
            lines.append(f"  Missing chars:      {chars}")
        if self.substitutions:
            subs = ", ".join(
                f"{k}→{v}" for k, v in list(self.substitutions.items())[:10]
            )
            lines.append(f"  Substitutions:      {subs}")
        return "\n".join(lines)


def audit_glyphs(
    text_corpus: str,
    font_stack: FontStack,
    glyph_map: Optional[dict[str, str]] = None,
) -> GlyphAuditResult:
    """Audit glyph coverage for a text corpus against the font stack.

    Args:
        text_corpus: All text that will be rendered.
        font_stack: The resolved font stack.
        glyph_map: Theme-level character substitution map.

    Returns:
        GlyphAuditResult with coverage info.
    """
    glyph_map = glyph_map or {}
    unique_chars = set(text_corpus) - {"\n", "\r", "\t", " "}
    result = GlyphAuditResult(total_chars=len(unique_chars))

    for char in sorted(unique_chars):
        # Check if theme has a substitution
        if char in glyph_map:
            result.substitutions[char] = glyph_map[char]
            sub_char = glyph_map[char]
            if _font_has_glyph(font_stack.primary, sub_char):
                result.covered += 1
                continue
            # Check fallbacks for substituted char
            found = False
            for fb in font_stack.fallbacks:
                if _font_has_glyph(fb, sub_char):
                    result.covered += 1
                    found = True
                    break
            if not found:
                result.missing.append(char)
            continue

        # Check primary font
        if _font_has_glyph(font_stack.primary, char):
            result.covered += 1
            continue

        # Check fallbacks
        found = False
        for fb in font_stack.fallbacks:
            if _font_has_glyph(fb, char):
                result.covered += 1
                found = True
                break

        if not found:
            result.missing.append(char)

    return result


def apply_glyph_map(text: str, glyph_map: dict[str, str]) -> str:
    """Apply theme glyph substitutions to text."""
    for src, dst in glyph_map.items():
        text = text.replace(src, dst)
    return text
