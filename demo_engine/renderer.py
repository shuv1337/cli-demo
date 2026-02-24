"""Frame renderer — converts timeline events to PNG frames.

Renders themed terminal frames using Pillow with:
  - Terminal window chrome (title bar, padding, rounded corners)
  - Font-aware text rendering with per-character fallback
  - Theme color mapping
  - Cursor rendering
  - Integration with the effects pipeline
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from demo_engine.config import RenderConfig
from demo_engine.effects import apply_effects, EffectsConfig
from demo_engine.fonts import FontStack, apply_glyph_map, resolve_font_stack
from demo_engine.presets import Preset, get_preset
from demo_engine.themes import Theme
from demo_engine.timeline import (
    EventType,
    LineStyle,
    Timeline,
    TimelineEvent,
)


# ── Layout constants ──────────────────────────────────────────────────────

@dataclass
class TerminalLayout:
    """Layout dimensions for the terminal frame."""

    # Canvas
    canvas_w: int = 1920
    canvas_h: int = 1080

    # Terminal window
    margin_x: int = 60
    margin_y: int = 40
    title_bar_h: int = 40
    padding_x: int = 24
    padding_y: int = 16
    corner_radius: int = 12

    # Text
    line_height: int = 24
    char_width: int = 10  # Will be measured from font

    # Traffic light dots
    dot_radius: int = 7
    dot_spacing: int = 24
    dot_y_offset: int = 20

    @property
    def terminal_x(self) -> int:
        return self.margin_x

    @property
    def terminal_y(self) -> int:
        return self.margin_y

    @property
    def terminal_w(self) -> int:
        return self.canvas_w - 2 * self.margin_x

    @property
    def terminal_h(self) -> int:
        return self.canvas_h - 2 * self.margin_y

    @property
    def content_x(self) -> int:
        return self.terminal_x + self.padding_x

    @property
    def content_y(self) -> int:
        return self.terminal_y + self.title_bar_h + self.padding_y

    @property
    def max_visible_lines(self) -> int:
        available = self.terminal_h - self.title_bar_h - 2 * self.padding_y
        return max(1, available // self.line_height)


def compute_layout(width: int, height: int, font_size: int) -> TerminalLayout:
    """Compute layout dimensions for given canvas size."""
    scale = min(width / 1920, height / 1080)
    return TerminalLayout(
        canvas_w=width,
        canvas_h=height,
        margin_x=int(60 * scale),
        margin_y=int(40 * scale),
        title_bar_h=int(40 * scale),
        padding_x=int(24 * scale),
        padding_y=int(16 * scale),
        corner_radius=int(12 * scale),
        line_height=int(font_size * 1.5),
        char_width=int(font_size * 0.6),
        dot_radius=int(7 * scale),
        dot_spacing=int(24 * scale),
        dot_y_offset=int(20 * scale),
    )


# ── Color resolution ─────────────────────────────────────────────────────

def resolve_color(style: LineStyle, theme: Theme) -> str:
    """Map a LineStyle to a theme color hex string."""
    color_map = {
        LineStyle.DEFAULT: theme.colors.text,
        LineStyle.COMMAND: theme.colors.cmd,
        LineStyle.SUCCESS: theme.colors.success,
        LineStyle.WARN: theme.colors.warn,
        LineStyle.ERROR: theme.colors.error,
        LineStyle.DIM: theme.colors.dim,
        LineStyle.ACCENT: theme.colors.accent,
        LineStyle.BANNER: theme.colors.accent,
    }
    return color_map.get(style, theme.colors.text)


# ── Terminal chrome rendering ─────────────────────────────────────────────

def draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: str,
) -> None:
    """Draw a rounded rectangle."""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def draw_title_bar(
    draw: ImageDraw.ImageDraw,
    layout: TerminalLayout,
    theme: Theme,
    title: str = "demo-engine",
    font: Optional[ImageFont.FreeTypeFont] = None,
) -> None:
    """Draw the terminal title bar with traffic light dots."""
    # Title bar background
    tx, ty = layout.terminal_x, layout.terminal_y
    tw = layout.terminal_w
    tbh = layout.title_bar_h

    draw.rounded_rectangle(
        (tx, ty, tx + tw, ty + tbh),
        radius=layout.corner_radius,
        fill=theme.colors.header,
    )
    # Square off the bottom corners
    draw.rectangle(
        (tx, ty + tbh // 2, tx + tw, ty + tbh),
        fill=theme.colors.header,
    )

    # Traffic light dots
    dot_colors = ["#ff5f56", "#ffbd2e", "#27c93f"]
    dot_x = tx + layout.padding_x + layout.dot_radius
    dot_y = ty + layout.dot_y_offset
    for color in dot_colors:
        draw.ellipse(
            (
                dot_x - layout.dot_radius,
                dot_y - layout.dot_radius,
                dot_x + layout.dot_radius,
                dot_y + layout.dot_radius,
            ),
            fill=color,
        )
        dot_x += layout.dot_spacing

    # Title text (centered)
    if font:
        bbox = font.getbbox(title)
        tw_text = bbox[2] - bbox[0]
        title_x = tx + (tw - tw_text) // 2
        title_y = ty + (tbh - (bbox[3] - bbox[1])) // 2
        draw.text((title_x, title_y), title, fill=theme.colors.dim, font=font)


# ── Frame state tracking ─────────────────────────────────────────────────

@dataclass
class FrameState:
    """Tracks the visible state of the terminal across frames."""

    lines: list[tuple[str, LineStyle]] = field(default_factory=list)
    overwrite_row: Optional[int] = None  # Row being overwritten (spinner/progress)
    cursor_visible: bool = True
    cursor_row: int = 0
    cursor_col: int = 0


class FrameRenderer:
    """Renders timeline events into image frames.

    Usage:
        renderer = FrameRenderer(config, theme)
        frames = renderer.render_all(timeline)
        renderer.save_frames(frames, output_dir)
    """

    def __init__(
        self,
        config: RenderConfig,
        theme: Theme,
        font_stack: Optional[FontStack] = None,
    ) -> None:
        self.config = config
        self.theme = theme
        self.preset = get_preset(config.preset)

        # Determine font size based on resolution
        w, h = config.resolution
        self.font_size = max(14, int(16 * min(w / 1920, h / 1080)))
        self.font_stack = font_stack or resolve_font_stack(
            config.font_profile, self.font_size
        )

        self.layout = compute_layout(w, h, self.font_size)

        # Effects config from theme
        self.effects_config = EffectsConfig(
            crt=theme.effects.crt,
            scanline_alpha=theme.effects.scanlines,
            noise_alpha=theme.effects.noise,
            vignette_strength=theme.effects.vignette,
            glow_strength=theme.effects.glow,
            glitch_cuts=theme.effects.glitch_cuts,
            effect_scale=self.preset.effect_scale,
        )

    def render_all(self, timeline: Timeline) -> list[Image.Image]:
        """Render the entire timeline into a list of PIL Image frames."""
        if not timeline.events:
            return []

        fps = self.preset.fps
        frame_ms = 1000.0 / fps
        total_ms = timeline.duration_ms + 500  # Small buffer
        num_frames = int(math.ceil(total_ms / frame_ms))

        state = FrameState()
        frames: list[Image.Image] = []
        event_idx = 0
        events = timeline.events

        for frame_num in range(num_frames):
            t_ms = frame_num * frame_ms

            # Apply all events up to this timestamp
            while event_idx < len(events) and events[event_idx].t_ms <= t_ms:
                event = events[event_idx]
                self._apply_event(state, event)
                event_idx += 1

            # Render frame
            img = self._render_frame(state, t_ms, frame_num)
            frames.append(img)

        return frames

    def _apply_event(self, state: FrameState, event: TimelineEvent) -> None:
        """Update frame state based on a timeline event."""
        if event.event_type in (EventType.LINE, EventType.COMMAND, EventType.BANNER):
            # New line(s) appended
            for line in event.text.split("\n"):
                state.lines.append((line, event.style))
            state.overwrite_row = None

            # Keep only visible lines
            max_lines = self.layout.max_visible_lines
            if len(state.lines) > max_lines:
                state.lines = state.lines[-max_lines:]

        elif event.event_type == EventType.SPINNER_FRAME:
            # Overwrite the last line (or specific row)
            if event.row is not None and event.row < len(state.lines):
                state.lines[event.row] = (event.text, event.style)
            elif state.overwrite_row is not None and state.overwrite_row < len(state.lines):
                state.lines[state.overwrite_row] = (event.text, event.style)
            elif state.lines:
                # First spinner frame: append, then track for overwrite
                if state.overwrite_row is None:
                    state.lines.append((event.text, event.style))
                    state.overwrite_row = len(state.lines) - 1
                else:
                    state.lines[-1] = (event.text, event.style)
            else:
                state.lines.append((event.text, event.style))
                state.overwrite_row = 0

        elif event.event_type == EventType.PROGRESS_FRAME:
            # Same overwrite behavior as spinner
            if event.row is not None and event.row < len(state.lines):
                state.lines[event.row] = (event.text, event.style)
            elif state.overwrite_row is not None and state.overwrite_row < len(state.lines):
                state.lines[state.overwrite_row] = (event.text, event.style)
            elif state.lines:
                if state.overwrite_row is None:
                    state.lines.append((event.text, event.style))
                    state.overwrite_row = len(state.lines) - 1
                else:
                    state.lines[-1] = (event.text, event.style)
            else:
                state.lines.append((event.text, event.style))
                state.overwrite_row = 0

        elif event.event_type == EventType.CLEAR:
            state.lines.clear()
            state.overwrite_row = None

        elif event.event_type == EventType.TRANSITION:
            # Reset overwrite tracking on transitions
            state.overwrite_row = None

        # Update cursor position
        if state.lines:
            state.cursor_row = len(state.lines) - 1
            last_text = state.lines[-1][0]
            state.cursor_col = len(last_text)

    def _render_frame(
        self,
        state: FrameState,
        t_ms: float,
        frame_num: int,
    ) -> Image.Image:
        """Render a single frame image."""
        w, h = self.config.resolution
        img = Image.new("RGB", (w, h), self.theme.colors.bg)
        draw = ImageDraw.Draw(img)

        layout = self.layout
        theme = self.theme

        # Terminal panel background
        draw_rounded_rect(
            draw,
            (layout.terminal_x, layout.terminal_y,
             layout.terminal_x + layout.terminal_w,
             layout.terminal_y + layout.terminal_h),
            layout.corner_radius,
            theme.colors.panel,
        )

        # Title bar
        title_font = None
        try:
            title_font = self.font_stack.primary.font_variant(size=max(10, self.font_size - 2))
        except Exception:
            title_font = self.font_stack.primary
        draw_title_bar(draw, layout, theme, title="demo-engine", font=title_font)

        # Text content
        x = layout.content_x
        y = layout.content_y
        font = self.font_stack.primary

        for i, (text, style) in enumerate(state.lines):
            if y + layout.line_height > layout.terminal_y + layout.terminal_h - layout.padding_y:
                break

            color = resolve_color(style, theme)

            # Apply glyph map
            text = apply_glyph_map(text, theme.glyph_map)

            # Render text with per-character font fallback
            self._draw_text_with_fallback(draw, x, y, text, color, font)

            y += layout.line_height

        # Cursor blink (visible every other ~500ms)
        if state.cursor_visible and state.lines:
            cursor_phase = int(t_ms / 500) % 2
            if cursor_phase == 0:
                cursor_x = x + state.cursor_col * layout.char_width
                cursor_y_pos = layout.content_y + state.cursor_row * layout.line_height
                if cursor_y_pos + layout.line_height < layout.terminal_y + layout.terminal_h:
                    draw.rectangle(
                        (cursor_x, cursor_y_pos,
                         cursor_x + layout.char_width,
                         cursor_y_pos + layout.line_height),
                        fill=theme.colors.cursor,
                    )

        # Apply visual effects
        img = apply_effects(img, self.effects_config, t_ms=t_ms, frame_num=frame_num)

        return img

    def _draw_text_with_fallback(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        text: str,
        color: str,
        default_font: ImageFont.FreeTypeFont,
    ) -> None:
        """Render text with per-character font fallback for missing glyphs."""
        cursor_x = x
        for char in text:
            if char == " ":
                cursor_x += self.layout.char_width
                continue

            font = self.font_stack.get_font_for_char(char)
            try:
                draw.text((cursor_x, y), char, fill=color, font=font)
                bbox = font.getbbox(char)
                char_w = bbox[2] - bbox[0] if bbox else self.layout.char_width
                cursor_x += max(char_w, self.layout.char_width)
            except Exception:
                cursor_x += self.layout.char_width

    def save_frames(
        self,
        frames: list[Image.Image],
        output_dir: Path,
        prefix: str = "frame",
    ) -> list[Path]:
        """Save frames as numbered PNGs."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        paths = []
        for i, frame in enumerate(frames):
            path = output_dir / f"{prefix}_{i:06d}.png"
            frame.save(path)
            paths.append(path)

        return paths
