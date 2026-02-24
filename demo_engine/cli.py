"""CLI entrypoint for the demo engine.

Usage:
    python -m demo_engine --theme glitch --preset cinematic --export all
    python scripts/render-demo.py --theme synthwave --preset short --aspect 9:16
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from demo_engine import __version__
from demo_engine.config import RenderConfig
from demo_engine.export import export_all, generate_output_name
from demo_engine.fonts import audit_glyphs, resolve_font_stack
from demo_engine.presets import list_presets
from demo_engine.renderer import FrameRenderer
from demo_engine.scenes import (
    Scene,
    compile_scene,
    generate_default_scene,
    list_scenes,
    load_scene,
)
from demo_engine.themes import list_themes, load_theme


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="demo-engine",
        description="Terminal Demo Engine — high-polish terminal trailer generation",
        epilog="Examples:\n"
        "  %(prog)s --theme glitch --preset short --export gif\n"
        "  %(prog)s --theme synthwave --preset cinematic --export all --aspect 16:9\n"
        "  %(prog)s --scenario launch_day --theme ops --export mp4\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    # Theme & scene
    parser.add_argument(
        "--theme",
        default="synthwave",
        help=f"Visual theme ({', '.join(list_themes())})",
    )
    parser.add_argument(
        "--scenario",
        default=None,
        help=f"Scene scenario name or YAML path ({', '.join(list_scenes())})",
    )

    # Timing
    parser.add_argument(
        "--preset",
        default="standard",
        help=f"Timing preset ({', '.join(list_presets())})",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Global speed multiplier (default: 1.0)",
    )

    # Display
    parser.add_argument(
        "--aspect",
        default="16:9",
        choices=["16:9", "1:1", "9:16"],
        help="Output aspect ratio (default: 16:9)",
    )
    parser.add_argument(
        "--font-profile",
        default="nerd-safe",
        choices=["nerd-safe", "classic", "auto"],
        help="Font selection profile (default: nerd-safe)",
    )
    parser.add_argument(
        "--font-strict",
        action="store_true",
        help="Fail on unresolved glyphs instead of substituting",
    )

    # Export
    parser.add_argument(
        "--export",
        default="gif",
        help="Export format: gif, mp4, webm, all (default: gif)",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help="Output directory (default: project root)",
    )
    parser.add_argument(
        "--cover",
        default="auto",
        help="Cover image mode: auto, frame:<idx>, none (default: auto)",
    )
    parser.add_argument(
        "--cut",
        default=None,
        help="Social media cut duration: 8s, 15s, 30s, 45s",
    )

    # Audio
    parser.add_argument(
        "--audio",
        choices=["on", "off"],
        default="off",
        help="Enable audio soundtrack (default: off)",
    )

    # Determinism
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for deterministic output",
    )

    # Workspace
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Keep temporary workspace after render",
    )

    # Debug
    parser.add_argument(
        "--glyph-audit",
        action="store_true",
        help="Run glyph audit and exit (no render)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse scene and show timeline stats without rendering",
    )
    parser.add_argument(
        "--list-themes",
        action="store_true",
        help="List available themes and exit",
    )
    parser.add_argument(
        "--list-scenes",
        action="store_true",
        help="List available scenes and exit",
    )

    return parser


def run(args: argparse.Namespace) -> int:
    """Execute the demo engine pipeline."""

    # List commands
    if args.list_themes:
        print("Available themes:")
        for t in list_themes():
            print(f"  {t}")
        return 0

    if args.list_scenes:
        print("Available scenes:")
        for s in list_scenes():
            print(f"  {s}")
        return 0

    # Build config
    from demo_engine.config import DEFAULT_OUTDIR

    config = RenderConfig(
        theme=args.theme,
        preset=args.preset,
        scenario=args.scenario,
        seed=args.seed,
        aspect=args.aspect,
        font_profile=args.font_profile,
        font_strict=args.font_strict,
        export=args.export,
        outdir=args.outdir or DEFAULT_OUTDIR,
        cover=args.cover,
        cut=args.cut,
        speed=args.speed,
        audio=args.audio == "on",
        keep_workspace=args.keep_workspace,
    )

    try:
        # Load theme
        print(f"▸ Loading theme: {config.theme}")
        theme = load_theme(config.theme)
        print(f"  colors: {theme.id} | effects: crt={theme.effects.crt}, "
              f"scanlines={theme.effects.scanlines}, glow={theme.effects.glow}")

        # Resolve font stack
        print(f"▸ Resolving fonts: {config.font_profile}")
        font_stack = resolve_font_stack(config.font_profile, size=16)
        print(f"  primary: {font_stack.primary_path}")
        if font_stack.fallback_paths:
            print(f"  fallbacks: {len(font_stack.fallback_paths)}")

        # Load or generate scene
        if config.scenario:
            print(f"▸ Loading scenario: {config.scenario}")
            scene = load_scene(config.scenario)
        else:
            print(f"▸ Generating default scene for theme: {config.theme}")
            scene = generate_default_scene(config)

        print(f"  scene: {scene.id} ({len(scene.steps)} steps)")

        # Compile timeline
        print(f"▸ Compiling timeline: preset={config.preset}, speed={config.speed}x")
        timeline = compile_scene(scene, config)
        print(f"  events: {len(timeline)}, duration: {timeline.duration_ms / 1000:.1f}s")

        # Glyph audit
        all_text = "\n".join(e.text for e in timeline.events if e.text)
        audit = audit_glyphs(all_text, font_stack, theme.glyph_map)
        print(f"▸ Glyph audit: {audit.coverage_pct:.1f}% coverage "
              f"({audit.covered}/{audit.total_chars} chars)")
        if audit.missing:
            msg = f"  ⚠ Missing glyphs: {', '.join(f'U+{ord(c):04X}' for c in audit.missing[:10])}"
            print(msg)
            if config.font_strict:
                print("  ✗ Strict mode — aborting due to missing glyphs")
                return 1

        if args.glyph_audit:
            print("\n" + audit.report())
            return 0

        if args.dry_run:
            print("\n▸ Dry run — timeline preview:")
            for event in timeline.events[:30]:
                d = event.to_dict()
                print(f"  [{d['t_ms']:8.0f}ms] {d['type']:16s} {d['text'][:60]}")
            if len(timeline) > 30:
                print(f"  ... and {len(timeline) - 30} more events")
            return 0

        # Render frames
        print(f"\n▸ Rendering {len(timeline)} events → {config.resolution[0]}x{config.resolution[1]} frames")
        t0 = time.monotonic()
        renderer = FrameRenderer(config, theme, font_stack)
        frames = renderer.render_all(timeline)
        render_time = time.monotonic() - t0
        print(f"  rendered {len(frames)} frames in {render_time:.1f}s "
              f"({len(frames) / render_time:.0f} fps)")

        # Export
        print(f"\n▸ Exporting: {config.export} → {config.outdir}")
        t0 = time.monotonic()

        # Handle audio
        audio_path = None
        if config.audio:
            from demo_engine.audio import prepare_audio

            audio_path = prepare_audio(
                True, config.theme, len(frames) / config.fps, config.outdir
            )
            if audio_path:
                print(f"  audio: {audio_path}")

        manifest = export_all(frames, config, scene.id, audio_path)
        export_time = time.monotonic() - t0

        print(f"  exported in {export_time:.1f}s")
        print(f"\n{manifest.summary()}")

        return 0

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    finally:
        config.cleanup()


def main() -> None:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
