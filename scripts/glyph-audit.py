#!/usr/bin/env python3
"""Glyph coverage audit tool.

Scans all theme glyph maps and scene text to identify missing glyphs
in the current font stack.

Usage:
    python3 scripts/glyph-audit.py [--profile nerd-safe|classic] [--strict]
"""

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from demo_engine.config import SCENES_DIR, THEMES_DIR
from demo_engine.fonts import audit_glyphs, resolve_font_stack
from demo_engine.themes import load_theme, list_themes
from demo_engine.scenes import load_scene, list_scenes


def main() -> int:
    parser = argparse.ArgumentParser(description="Glyph coverage audit")
    parser.add_argument("--profile", default="nerd-safe", choices=["nerd-safe", "classic"])
    parser.add_argument("--strict", action="store_true", help="Exit 1 on missing glyphs")
    parser.add_argument("--size", type=int, default=16, help="Font size for testing")
    args = parser.parse_args()

    print(f"Glyph Audit — profile: {args.profile}, size: {args.size}")
    print("=" * 60)

    font_stack = resolve_font_stack(args.profile, args.size)
    print(f"Primary font: {font_stack.primary_path}")
    print(f"Fallbacks: {len(font_stack.fallback_paths)}")
    print()

    has_issues = False

    # Audit each theme
    print("Theme Audit:")
    print("-" * 40)
    for theme_name in list_themes():
        try:
            theme = load_theme(theme_name)
        except Exception as e:
            print(f"  ✗ {theme_name}: {e}")
            has_issues = True
            continue

        # Collect all glyph map characters
        corpus = "".join(theme.glyph_map.keys()) + "".join(theme.glyph_map.values())
        # Add common terminal characters used in demos
        corpus += "❯✓✔✗█░━╗╔╚╝║╠╣╦╩╬⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

        result = audit_glyphs(corpus, font_stack, theme.glyph_map)
        status = "✓" if result.is_clean else "⚠"
        print(f"  {status} {theme_name}: {result.coverage_pct:.1f}% "
              f"({result.covered}/{result.total_chars})")
        if result.missing:
            print(f"    missing: {', '.join(f'U+{ord(c):04X} ({c})' for c in result.missing[:10])}")
            has_issues = True
        if result.substitutions:
            print(f"    subs: {', '.join(f'{k}→{v}' for k, v in result.substitutions.items())}")
    print()

    # Audit each scene
    print("Scene Audit:")
    print("-" * 40)
    for scene_name in list_scenes():
        try:
            scene = load_scene(scene_name)
        except Exception as e:
            print(f"  ✗ {scene_name}: {e}")
            has_issues = True
            continue

        corpus = ""
        for step in scene.steps:
            corpus += step.text + step.label
            corpus += "".join(step.output)

        if not corpus.strip():
            print(f"  - {scene_name}: (no text)")
            continue

        result = audit_glyphs(corpus, font_stack)
        status = "✓" if result.is_clean else "⚠"
        print(f"  {status} {scene_name}: {result.coverage_pct:.1f}% "
              f"({result.covered}/{result.total_chars})")
        if result.missing:
            print(f"    missing: {', '.join(f'U+{ord(c):04X} ({c})' for c in result.missing[:10])}")
            has_issues = True
    print()

    if has_issues and args.strict:
        print("✗ Strict mode: missing glyphs detected")
        return 1

    if not has_issues:
        print("✓ All glyphs covered across themes and scenes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
