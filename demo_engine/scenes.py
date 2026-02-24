"""Scene DSL engine — load YAML scene definitions and compile to timelines.

Scene files define the narrative flow of a demo:
  - Banner displays
  - Simulated commands (fake or real output)
  - Spinner/progress animations
  - Transition effects
  - Timing overrides

Template variables:
  {{workspace}} — resolved to the temp demo workspace path
  {{theme}}     — current theme name
  {{date}}      — current date string
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from demo_engine.config import SCENES_DIR, RenderConfig
from demo_engine.presets import Preset, get_preset
from demo_engine.timeline import EventType, LineStyle, Timeline, TimelineEvent


TEMPLATE_RE = re.compile(r"\{\{(\w+)\}\}")

# Default spinner frames
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# Banner fonts (box-drawing safe)
BANNERS: dict[str, str] = {
    "glitch": (
        " ██████╗ ██╗     ██╗████████╗ ██████╗██╗  ██╗\n"
        "██╔════╝ ██║     ██║╚══██╔══╝██╔════╝██║  ██║\n"
        "██║  ███╗██║     ██║   ██║   ██║     ███████║\n"
        "██║   ██║██║     ██║   ██║   ██║     ██╔══██║\n"
        "╚██████╔╝███████╗██║   ██║   ╚██████╗██║  ██║\n"
        " ╚═════╝ ╚══════╝╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝"
    ),
    "neon": (
        "███╗   ██╗███████╗ ██████╗ ███╗   ██╗\n"
        "████╗  ██║██╔════╝██╔═══██╗████╗  ██║\n"
        "██╔██╗ ██║█████╗  ██║   ██║██╔██╗ ██║\n"
        "██║╚██╗██║██╔══╝  ██║   ██║██║╚██╗██║\n"
        "██║ ╚████║███████╗╚██████╔╝██║ ╚████║\n"
        "╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝"
    ),
    "demo": (
        "██████╗ ███████╗███╗   ███╗ ██████╗ \n"
        "██╔══██╗██╔════╝████╗ ████║██╔═══██╗\n"
        "██║  ██║█████╗  ██╔████╔██║██║   ██║\n"
        "██║  ██║██╔══╝  ██║╚██╔╝██║██║   ██║\n"
        "██████╔╝███████╗██║ ╚═╝ ██║╚██████╔╝\n"
        "╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝ "
    ),
}


@dataclass
class SceneStep:
    """A single step in a scene definition."""

    step_type: str  # banner, command, spinner, progress, line, transition, pause
    text: str = ""
    label: str = ""
    mode: str = "fake"  # fake | real
    output: list[str] = field(default_factory=list)
    style: str = "default"
    cycles: int = 0  # For spinners
    width: int = 26  # For progress bars
    duration_ms: float = 0.0  # For pauses/transitions
    transition: str = "cut"  # For transitions: cut, fade, wipe, glitch
    banner_name: str = ""  # Named banner from BANNERS dict


@dataclass
class Scene:
    """A complete scene definition."""

    id: str
    title: str = ""
    theme: str = ""  # Optional theme override
    steps: list[SceneStep] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


# ── Template expansion ────────────────────────────────────────────────────

def expand_templates(text: str, config: RenderConfig) -> str:
    """Expand {{var}} templates in text."""
    def replacer(match: re.Match) -> str:
        key = match.group(1)
        mapping = {
            "workspace": str(config.workspace),
            "theme": config.theme,
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        }
        return mapping.get(key, match.group(0))

    return TEMPLATE_RE.sub(replacer, text)


# ── YAML loader ───────────────────────────────────────────────────────────

def _parse_step(data: dict) -> SceneStep:
    """Parse a single step dict from YAML."""
    step_type = data.get("type", "line")
    return SceneStep(
        step_type=step_type,
        text=data.get("text", ""),
        label=data.get("label", ""),
        mode=data.get("mode", "fake"),
        output=data.get("output", []),
        style=data.get("style", "default"),
        cycles=data.get("cycles", 0),
        width=data.get("width", 26),
        duration_ms=data.get("duration_ms", 0),
        transition=data.get("transition", "cut"),
        banner_name=data.get("banner", ""),
    )


def load_scene(name_or_path: str, scenes_dir: Optional[Path] = None) -> Scene:
    """Load a scene from YAML file.

    Args:
        name_or_path: Scene name (looked up in scenes_dir) or direct file path.
        scenes_dir: Directory to search for scene files.
    """
    scenes_dir = scenes_dir or SCENES_DIR
    path = Path(name_or_path)

    if not path.exists():
        path = scenes_dir / f"{name_or_path}.yaml"

    if not path.exists():
        available = list_scenes(scenes_dir)
        raise FileNotFoundError(
            f"Scene '{name_or_path}' not found. "
            f"Available: {', '.join(available) or 'none'}"
        )

    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Scene file must be a YAML mapping: {path}")

    steps = [_parse_step(s) for s in data.get("steps", [])]

    return Scene(
        id=data.get("id", path.stem),
        title=data.get("title", ""),
        theme=data.get("theme", ""),
        steps=steps,
        meta=data.get("meta", {}),
    )


def list_scenes(scenes_dir: Optional[Path] = None) -> list[str]:
    """List available scene names."""
    scenes_dir = scenes_dir or SCENES_DIR
    if not scenes_dir.exists():
        return []
    return sorted(p.stem for p in scenes_dir.glob("*.yaml"))


# ── Scene → Timeline compilation ─────────────────────────────────────────

STYLE_MAP: dict[str, LineStyle] = {
    "default": LineStyle.DEFAULT,
    "command": LineStyle.COMMAND,
    "success": LineStyle.SUCCESS,
    "warn": LineStyle.WARN,
    "error": LineStyle.ERROR,
    "dim": LineStyle.DIM,
    "accent": LineStyle.ACCENT,
}


def compile_scene(
    scene: Scene,
    config: RenderConfig,
    preset: Optional[Preset] = None,
) -> Timeline:
    """Compile a scene definition into a timeline.

    Resolves all templates, applies preset timing, and generates
    the full event sequence.
    """
    preset = preset or get_preset(config.preset)
    timeline = Timeline()
    cursor_ms = float(preset.intro_hold_ms)

    for step in scene.steps:
        if step.step_type == "banner":
            text = step.text
            if step.banner_name and step.banner_name in BANNERS:
                text = BANNERS[step.banner_name]
            elif not text and scene.title:
                text = scene.title

            text = expand_templates(text, config)
            timeline.add_banner(cursor_ms, text, scene=scene.id)
            cursor_ms += preset.banner_hold_ms

        elif step.step_type == "command":
            cmd_text = expand_templates(step.text, config)
            timeline.add_command(cursor_ms, f"❯ {cmd_text}", scene=scene.id)
            cursor_ms += preset.command_hold_ms

            # Output lines
            for out_line in step.output:
                out_line = expand_templates(out_line, config)
                style = STYLE_MAP.get(step.style, LineStyle.DEFAULT)
                timeline.add_line(cursor_ms, out_line, style=style, scene=scene.id)
                cursor_ms += preset.command_output_ms

            cursor_ms += preset.line_hold_ms

        elif step.step_type == "spinner":
            label = expand_templates(step.label or step.text, config)
            cycles = step.cycles if step.cycles > 0 else preset.spinner_cycles
            cursor_ms = timeline.add_spinner(
                cursor_ms,
                label,
                frames=SPINNER_FRAMES,
                cycle_ms=preset.spinner_cycle_ms,
                cycles=cycles,
            )
            cursor_ms += preset.line_hold_ms

        elif step.step_type == "progress":
            label = expand_templates(step.label or step.text, config)
            width = step.width if step.width > 0 else 26
            cursor_ms = timeline.add_progress(
                cursor_ms,
                label,
                width=width,
                step_ms=preset.progress_step_ms,
            )
            cursor_ms += preset.line_hold_ms

        elif step.step_type == "line":
            text = expand_templates(step.text, config)
            style = STYLE_MAP.get(step.style, LineStyle.DEFAULT)
            timeline.add_line(cursor_ms, text, style=style, scene=scene.id)
            cursor_ms += preset.line_hold_ms

        elif step.step_type == "transition":
            duration = step.duration_ms or preset.transition_ms
            cursor_ms = timeline.add_transition(
                cursor_ms, style=step.transition, duration_ms=duration
            )

        elif step.step_type == "pause":
            duration = step.duration_ms or preset.pause_ms
            cursor_ms = timeline.add_pause(cursor_ms, duration)

    # Outro hold
    cursor_ms = timeline.add_pause(cursor_ms, preset.outro_hold_ms)

    # Apply global speed multiplier
    if config.speed != 1.0:
        timeline.apply_speed(config.speed)

    timeline.sort()
    return timeline


# ── Built-in default scene generator ──────────────────────────────────────

def generate_default_scene(config: RenderConfig) -> Scene:
    """Generate a default demo scene matching the original record-demo.sh behavior."""
    theme = config.theme

    if theme == "glitch":
        title = "Glitch Grid Demo // high-voltage terminal sequence"
        profile = "glitch"
        ship_style = "glitchcore"
        endpoint = "https://staging.glitch-grid.demo"
        spinner_label = "Resynchronizing packet ghosts"
        progress_label = "Rebuilding fractured pipeline"
        banner_name = "glitch"
    else:
        title = "Neon Shell Demo // cinematic terminal sequence"
        profile = "cinematic"
        ship_style = "synthwave"
        endpoint = "https://staging.neon-shell.demo"
        spinner_label = "Priming spectral cache"
        progress_label = "Compiling visual pipeline"
        banner_name = "neon"

    steps = [
        SceneStep(step_type="banner", banner_name=banner_name),
        SceneStep(step_type="line", text=title, style="accent"),
        SceneStep(step_type="line", text=f"theme: {theme}", style="dim"),
        SceneStep(step_type="line", text="workspace: {{workspace}}", style="dim"),
        SceneStep(step_type="line", text="━" * 60, style="dim"),
        SceneStep(step_type="pause", duration_ms=200),
        # File listing
        SceneStep(
            step_type="command",
            text='ls -1 "{{workspace}}/src"',
            mode="fake",
            output=["orchestrator.ts", "render.ts"],
        ),
        # Grep TODOs
        SceneStep(
            step_type="command",
            text='grep -R "TODO" -n "{{workspace}}/src"',
            mode="fake",
            output=[
                "src/orchestrator.ts:3:  // TODO: retry policy tuning",
                "src/render.ts:3:  // TODO: dark mode spectrum gradients",
            ],
        ),
        # Config display
        SceneStep(
            step_type="command",
            text='awk \'NR <= 8 {print}\' "{{workspace}}/config/pipeline.json"',
            mode="fake",
            output=[
                "{",
                '  "project": "neon-shell",',
                '  "steps": ["scan", "optimize", "ship"],',
                '  "target": "staging"',
                "}",
            ],
        ),
        # Spinner
        SceneStep(step_type="spinner", label=spinner_label, cycles=20),
        # Progress
        SceneStep(step_type="progress", label=progress_label, width=26),
        # Scan command
        SceneStep(
            step_type="command",
            text=f'neon scan --project "{{{{workspace}}}}" --profile {profile}',
            mode="fake",
            style="success",
            output=[
                "✓ src/orchestrator.ts    deprecated APIs: 0   perf hints: 2",
                "✓ src/render.ts          deprecated APIs: 0   perf hints: 1",
                "✓ config/pipeline.json   schema: valid         target: staging",
                "",
                "Scan summary:",
                "  files analyzed : 3",
                "  warnings       : 0",
                "  opportunities  : 3",
            ],
        ),
        # Telemetry
        SceneStep(
            step_type="command",
            text='tail -n 5 "{{workspace}}/logs/telemetry.log"',
            mode="fake",
            output=[
                "10:21:01 ingest packets=148 latency=4.2ms",
                "10:21:02 render frames=920 dropped=0",
                "10:21:03 cache hit_rate=97.4%",
                "10:21:04 queue depth=3 status=stable",
                "10:21:05 release candidate=rc.42 verdict=green",
            ],
        ),
        # Ship command
        SceneStep(
            step_type="command",
            text=f"neon ship --target staging --style {ship_style}",
            mode="fake",
            style="success",
            output=[
                "[link] handshake with edge gateway.............ok",
                "[push] uploading release bundle................ok",
                "[verify] health checks (latency p95 < 20ms)....ok",
                "[done] deployment id: neon-rc42-a9f",
                "",
                f"endpoint: {endpoint}",
                "status:   LIVE",
            ],
        ),
        # Outro
        SceneStep(step_type="line", text="━" * 60, style="dim"),
        SceneStep(step_type="line", text=">> Demo complete.", style="success"),
        SceneStep(
            step_type="line",
            text="Tip: --theme glitch for alt style, --speed 0.35 for smoother recording.",
            style="dim",
        ),
    ]

    return Scene(id=f"default_{theme}", title=title, theme=theme, steps=steps)
