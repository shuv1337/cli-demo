#!/usr/bin/env python3
"""Generate overlay assets for the effects pipeline.

Creates:
  - CRT scanline overlay PNG
  - Vignette overlay PNG
  - Noise texture PNG
  - Logo text file

Usage:
    python3 scripts/build-demo-assets.py [--width 1920] [--height 1080]
"""

import argparse
import math
import random
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from PIL import Image, ImageDraw


def build_scanline(width: int, height: int, output: Path) -> None:
    """Generate a CRT scanline overlay."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for y in range(0, height, 3):
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, 30))

    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output))
    print(f"  ✓ scanline: {output}")


def build_vignette(width: int, height: int, output: Path) -> None:
    """Generate a vignette overlay."""
    img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(img)

    cx, cy = width // 2, height // 2
    steps = 50
    for i in range(steps, 0, -1):
        frac = i / steps
        brightness = int(255 * frac)
        rx = int(cx * frac * 1.4)
        ry = int(cy * frac * 1.4)
        draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=brightness)

    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output))
    print(f"  ✓ vignette: {output}")


def build_noise(width: int, height: int, output: Path) -> None:
    """Generate a noise texture."""
    rng = random.Random(42)
    data = bytes(rng.randint(100, 156) for _ in range(width * height))
    img = Image.frombytes("L", (width, height), data)

    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output))
    print(f"  ✓ noise: {output}")


def build_branding(output: Path) -> None:
    """Generate the ASCII logo text file."""
    logo = """\
╔══════════════════════════════════════╗
║       TERMINAL DEMO ENGINE           ║
║     high-polish trailer generator    ║
╚══════════════════════════════════════╝
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(logo)
    print(f"  ✓ logo: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build demo overlay assets")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    args = parser.parse_args()

    assets_dir = project_root / "assets"

    print(f"Building assets at {args.width}x{args.height}")

    build_scanline(args.width, args.height, assets_dir / "overlays" / "crt_scanline.png")
    build_vignette(args.width, args.height, assets_dir / "overlays" / "vignette.png")
    build_noise(args.width, args.height, assets_dir / "overlays" / "noise.png")
    build_branding(assets_dir / "branding" / "logo.txt")

    print("\n✓ All assets built")
    return 0


if __name__ == "__main__":
    sys.exit(main())
