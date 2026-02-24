"""Visual effects pipeline.

Render-order compositing:
  1. Base terminal frame (from renderer)
  2. Text glow (selective)
  3. Scanline overlay
  4. Vignette
  5. Noise/grain
  6. Glitch transitions (scene boundaries)
  7. Cursor pulse pass (handled in renderer)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


@dataclass
class EffectsConfig:
    """Configuration for the visual effects pipeline."""

    crt: bool = False
    scanline_alpha: float = 0.0     # 0.0–1.0
    noise_alpha: float = 0.0        # 0.0–1.0
    vignette_strength: float = 0.0  # 0.0–1.0
    glow_strength: float = 0.0      # 0.0–1.0
    glitch_cuts: bool = False
    chromatic_aberration: float = 0.0
    effect_scale: float = 1.0       # Preset-level scaling

    def scaled(self, key: str) -> float:
        """Get an effect value scaled by the preset effect_scale."""
        val = getattr(self, key, 0.0)
        if isinstance(val, (int, float)):
            return val * self.effect_scale
        return val


def apply_effects(
    img: Image.Image,
    config: EffectsConfig,
    t_ms: float = 0.0,
    frame_num: int = 0,
) -> Image.Image:
    """Apply the full effects pipeline to a frame.

    Args:
        img: Input frame (RGB PIL Image).
        config: Effects configuration.
        t_ms: Current timestamp in ms (for animated effects).
        frame_num: Current frame number.

    Returns:
        Processed frame with effects applied.
    """
    if not any([
        config.crt,
        config.scanline_alpha > 0,
        config.noise_alpha > 0,
        config.vignette_strength > 0,
        config.glow_strength > 0,
        config.glitch_cuts,
        config.chromatic_aberration > 0,
    ]):
        return img

    result = img.copy()

    # 1. Text glow (applied as a gentle bloom)
    if config.glow_strength > 0:
        result = _apply_glow(result, config.scaled("glow_strength"))

    # 2. CRT scanlines
    if config.crt or config.scanline_alpha > 0:
        alpha = config.scaled("scanline_alpha") if config.scanline_alpha > 0 else 0.1
        result = _apply_scanlines(result, alpha)

    # 3. Vignette
    if config.vignette_strength > 0:
        result = _apply_vignette(result, config.scaled("vignette_strength"))

    # 4. Noise/grain
    if config.noise_alpha > 0:
        result = _apply_noise(result, config.scaled("noise_alpha"), seed=frame_num)

    # 5. Chromatic aberration
    if config.chromatic_aberration > 0:
        result = _apply_chromatic_aberration(
            result, config.scaled("chromatic_aberration")
        )

    # 6. Glitch cuts (periodic)
    if config.glitch_cuts:
        result = _apply_glitch(result, t_ms, frame_num)

    return result


# ── Individual effect implementations ─────────────────────────────────────

def _apply_glow(img: Image.Image, strength: float) -> Image.Image:
    """Apply a soft bloom/glow effect to bright areas."""
    if strength <= 0:
        return img

    # Create a brightened, blurred version
    enhancer = ImageEnhance.Brightness(img)
    bright = enhancer.enhance(1.0 + strength * 0.3)
    blurred = bright.filter(ImageFilter.GaussianBlur(radius=int(3 + strength * 5)))

    # Blend: screen-like composite
    return Image.blend(img, blurred, alpha=min(strength * 0.3, 0.4))


def _apply_scanlines(img: Image.Image, alpha: float) -> Image.Image:
    """Apply CRT-style horizontal scanlines."""
    if alpha <= 0:
        return img

    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Draw alternating dark lines every 2 pixels
    line_alpha = int(min(alpha * 255, 80))
    for y in range(0, h, 3):
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, line_alpha))

    # Composite
    result = img.convert("RGBA")
    result = Image.alpha_composite(result, overlay)
    return result.convert("RGB")


def _apply_vignette(img: Image.Image, strength: float) -> Image.Image:
    """Apply a vignette (darkened corners) effect."""
    if strength <= 0:
        return img

    w, h = img.size
    vignette = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(vignette)

    # Radial gradient: bright center, dark edges
    cx, cy = w // 2, h // 2
    max_r = math.sqrt(cx * cx + cy * cy)

    # Use concentric ellipses for a smooth gradient
    steps = 40
    for i in range(steps, 0, -1):
        frac = i / steps
        brightness = int(255 * (1.0 - strength * (1.0 - frac) ** 1.5))
        rx = int(cx * frac * 1.4)
        ry = int(cy * frac * 1.4)
        draw.ellipse(
            (cx - rx, cy - ry, cx + rx, cy + ry),
            fill=brightness,
        )

    # Apply as a multiply
    result = img.copy()
    r, g, b = result.split()
    r = Image.composite(r, Image.new("L", (w, h), 0), vignette)
    g = Image.composite(g, Image.new("L", (w, h), 0), vignette)
    b = Image.composite(b, Image.new("L", (w, h), 0), vignette)
    return Image.merge("RGB", (r, g, b))


def _apply_noise(
    img: Image.Image, alpha: float, seed: int = 0
) -> Image.Image:
    """Apply film grain/noise effect."""
    if alpha <= 0:
        return img

    w, h = img.size
    rng = random.Random(seed)

    # Generate noise
    noise_data = bytes(
        max(0, min(255, 128 + int(rng.gauss(0, alpha * 80))))
        for _ in range(w * h)
    )
    noise = Image.frombytes("L", (w, h), noise_data)

    # Blend noise with the image
    noise_rgb = Image.merge("RGB", (noise, noise, noise))
    return Image.blend(img, noise_rgb, alpha=min(alpha * 0.15, 0.12))


def _apply_chromatic_aberration(
    img: Image.Image, strength: float
) -> Image.Image:
    """Apply chromatic aberration (RGB channel offset)."""
    if strength <= 0:
        return img

    offset = max(1, int(strength * 3))
    r, g, b = img.split()

    # Offset red and blue channels slightly
    from PIL import ImageChops

    r_shifted = ImageChops.offset(r, offset, 0)
    b_shifted = ImageChops.offset(b, -offset, 0)

    return Image.merge("RGB", (r_shifted, g, b_shifted))


def _apply_glitch(
    img: Image.Image, t_ms: float, frame_num: int
) -> Image.Image:
    """Apply periodic glitch effect (horizontal slice displacement)."""
    # Only glitch occasionally (every ~2s, for ~3 frames)
    cycle = int(t_ms / 2000) % 10
    if cycle != 0 or frame_num % 8 > 2:
        return img

    w, h = img.size
    result = img.copy()
    rng = random.Random(frame_num)

    # Displace 3–6 random horizontal slices
    num_slices = rng.randint(3, 6)
    for _ in range(num_slices):
        y = rng.randint(0, h - 20)
        slice_h = rng.randint(4, 20)
        offset_x = rng.randint(-30, 30)

        if slice_h + y > h:
            slice_h = h - y

        slice_box = (0, y, w, y + slice_h)
        sliced = result.crop(slice_box)

        # Paste with offset (wrapping)
        result.paste(sliced, (offset_x, y))

    return result


# ── Transition effects ────────────────────────────────────────────────────

def apply_transition(
    frame_a: Image.Image,
    frame_b: Image.Image,
    progress: float,
    style: str = "cut",
) -> Image.Image:
    """Apply a transition between two frames.

    Args:
        frame_a: Outgoing frame.
        frame_b: Incoming frame.
        progress: 0.0 (start, all A) to 1.0 (end, all B).
        style: Transition type (cut, fade, wipe, glitch).
    """
    if style == "cut" or progress <= 0:
        return frame_a
    if progress >= 1.0:
        return frame_b

    if style == "fade":
        return Image.blend(frame_a, frame_b, alpha=progress)

    elif style == "wipe":
        w, h = frame_a.size
        split_x = int(w * progress)
        result = frame_a.copy()
        right = frame_b.crop((split_x, 0, w, h))
        result.paste(right, (split_x, 0))
        return result

    elif style == "glitch":
        # Glitch: random slice mix of A and B
        w, h = frame_a.size
        result = frame_a.copy() if progress < 0.5 else frame_b.copy()
        source = frame_b if progress < 0.5 else frame_a
        rng = random.Random(int(progress * 1000))

        num_slices = int(3 + progress * 8)
        for _ in range(num_slices):
            y = rng.randint(0, h - 10)
            sh = rng.randint(5, 30)
            if y + sh > h:
                sh = h - y
            sliced = source.crop((0, y, w, y + sh))
            ox = rng.randint(-20, 20)
            result.paste(sliced, (ox, y))
        return result

    return frame_b


# ── Story enhancement components ──────────────────────────────────────────

def draw_telemetry_sidebar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    metrics: list[tuple[str, str, str]],
    theme_colors: dict[str, str],
    font: ImageFont.FreeTypeFont,
    line_height: int = 20,
) -> int:
    """Draw a telemetry sidebar panel.

    Args:
        metrics: List of (label, value, status) tuples.
                 status: "ok", "warn", "error"

    Returns:
        Y position after the sidebar.
    """
    # Panel background
    panel_h = len(metrics) * line_height + 30
    draw.rounded_rectangle(
        (x, y, x + width, y + panel_h),
        radius=6,
        fill=theme_colors.get("panel", "#141414"),
    )

    # Header
    draw.text((x + 10, y + 6), "TELEMETRY", fill=theme_colors.get("dim", "#666"), font=font)
    cy = y + 24

    status_colors = {
        "ok": theme_colors.get("success", "#86efac"),
        "warn": theme_colors.get("warn", "#fbbf24"),
        "error": theme_colors.get("error", "#f87171"),
    }

    for label, value, status in metrics:
        color = status_colors.get(status, theme_colors.get("text", "#ccc"))
        draw.text((x + 10, cy), f"{label}: ", fill=theme_colors.get("dim", "#666"), font=font)
        draw.text((x + 10 + len(label) * 8 + 16, cy), value, fill=color, font=font)
        cy += line_height

    return cy + 10


def draw_benchmark_card(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    height: int,
    title: str,
    rows: list[tuple[str, str, str]],
    theme_colors: dict[str, str],
    font: ImageFont.FreeTypeFont,
) -> None:
    """Draw a benchmark summary card.

    Args:
        rows: List of (label, before, after) tuples.
    """
    draw.rounded_rectangle(
        (x, y, x + width, y + height),
        radius=8,
        fill=theme_colors.get("panel", "#141414"),
    )

    draw.text(
        (x + 12, y + 10), title,
        fill=theme_colors.get("accent", "#c084fc"),
        font=font,
    )

    cy = y + 34
    for label, before, after in rows:
        draw.text((x + 12, cy), label, fill=theme_colors.get("dim", "#666"), font=font)
        draw.text((x + 12 + 140, cy), before, fill=theme_colors.get("warn", "#fbbf24"), font=font)
        draw.text((x + 12 + 220, cy), "→", fill=theme_colors.get("dim", "#666"), font=font)
        draw.text((x + 12 + 250, cy), after, fill=theme_colors.get("success", "#86efac"), font=font)
        cy += 22


def draw_outro_card(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    height: int,
    repo: str = "",
    endpoint: str = "",
    tagline: str = "",
    theme_colors: dict[str, str] = {},
    font: ImageFont.FreeTypeFont = None,
) -> None:
    """Draw an outro CTA card."""
    draw.rounded_rectangle(
        (x, y, x + width, y + height),
        radius=10,
        fill=theme_colors.get("header", "#1e1e1e"),
        outline=theme_colors.get("border", "#333"),
        width=2,
    )

    cy = y + 20
    if tagline:
        draw.text(
            (x + width // 2 - len(tagline) * 4, cy),
            tagline,
            fill=theme_colors.get("accent", "#c084fc"),
            font=font,
        )
        cy += 30

    if repo:
        draw.text(
            (x + 20, cy), f"repo: {repo}",
            fill=theme_colors.get("cmd", "#67e8f9"),
            font=font,
        )
        cy += 24

    if endpoint:
        draw.text(
            (x + 20, cy), f"live: {endpoint}",
            fill=theme_colors.get("success", "#86efac"),
            font=font,
        )
