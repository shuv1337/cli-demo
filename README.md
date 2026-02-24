# Terminal Demo Engine

High-polish terminal trailer engine — generate themed, effect-rich demo GIFs, MP4s, and WebMs from authored scene scripts or real terminal recordings.

## Quickstart

```bash
# Render default demo with glitch theme
./record-demo.sh --theme glitch --preset short --export gif

# Use the Python CLI directly
python3 -m demo_engine --theme synthwave --preset cinematic --export all

# Render a named scenario
python3 -m demo_engine --scenario launch_day --theme ops --export mp4

# Fast social cut (9:16 for stories/reels)
./record-demo.sh --theme glitch --preset short --aspect 9:16 --export all --cut 15s

# Deterministic output
python3 -m demo_engine --theme matrix --preset standard --seed 42 --export gif
```

## Available Themes

| Theme | Vibe | CRT | Glow |
|-------|------|-----|------|
| `synthwave` | Purple/pink neon retrowave | ✓ | High |
| `glitch` | Dark blue cyber-tech | ✓ | Medium |
| `matrix` | Green-on-black terminal | ✓ | High |
| `minimal` | Clean dark, VS Code-like | — | — |
| `ops` | GitHub dark palette | — | Low |

```bash
python3 -m demo_engine --list-themes
```

## Available Presets

| Preset | Duration | FPS | Pace |
|--------|----------|-----|------|
| `short` | 8–15s | 24 | Fast, social-optimized |
| `standard` | 20–30s | 30 | Balanced demo flow |
| `cinematic` | 35–60s | 30 | Dramatic holds, transitions |

## Scene DSL (YAML)

Scenes define the narrative flow of a demo. Create a `.yaml` file in `scenes/`:

```yaml
id: my_demo
title: "My Cool Demo"

steps:
  - type: banner
    banner: demo          # Use named ASCII art banner

  - type: line
    text: "Starting demo..."
    style: accent

  - type: command
    text: 'ls -la'
    mode: fake
    output:
      - "total 42"
      - "drwxr-xr-x  5 user group  160 Jan 15 10:00 src/"
      - "-rw-r--r--  1 user group 1234 Jan 15 09:55 main.ts"

  - type: spinner
    label: "Installing dependencies"
    cycles: 20

  - type: progress
    label: "Building project"
    width: 30

  - type: transition
    transition: glitch
    duration_ms: 200

  - type: pause
    duration_ms: 500
```

### Step types

| Type | Description | Key fields |
|------|-------------|------------|
| `banner` | ASCII art banner | `text`, `banner` (named) |
| `line` | Single text line | `text`, `style` |
| `command` | Simulated command | `text`, `output[]`, `mode` |
| `spinner` | Animated spinner | `label`, `cycles` |
| `progress` | Progress bar | `label`, `width` |
| `transition` | Visual transition | `transition`, `duration_ms` |
| `pause` | Hold/delay | `duration_ms` |

### Style values

`default`, `command`, `success`, `warn`, `error`, `dim`, `accent`

### Template variables

| Variable | Expansion |
|----------|-----------|
| `{{workspace}}` | Temp demo workspace path |
| `{{theme}}` | Current theme name |
| `{{date}}` | Current date (YYYY-MM-DD) |

## Theme Schema

Themes are JSON files in `themes/`:

```json
{
  "id": "mytheme",
  "colors": {
    "bg": "#0a0a0a",
    "panel": "#141414",
    "header": "#1e1e1e",
    "text": "#e0e0e0",
    "cmd": "#67e8f9",
    "success": "#86efac",
    "warn": "#fbbf24",
    "accent": "#c084fc",
    "error": "#f87171",
    "dim": "#666666",
    "cursor": "#ffffff",
    "border": "#333333"
  },
  "effects": {
    "crt": true,
    "scanlines": 0.12,
    "noise": 0.04,
    "vignette": 0.2,
    "glitch_cuts": false,
    "glow": 0.4
  },
  "glyph_map": {
    "✔": "✓",
    "🚀": ">>"
  }
}
```

**Required colors:** `bg`, `text`, `cmd`, `success`, `warn`, `accent`
**Optional colors:** `panel`, `header`, `error`, `dim`, `cursor`, `border`

Add a new theme by creating a JSON file — no code changes needed.

## Font Fallback & Glyph Safety

The engine uses a prioritized font stack:

1. **JetBrainsMono Nerd Font Mono** (primary)
2. **CaskaydiaMono Nerd Font Mono** (fallback)
3. **Noto Sans Symbols2** (symbol fallback)

Pillow doesn't do automatic font fallback, so the engine checks each character
against the font stack and selects the best font per-character.

### Glyph map

Each theme defines a `glyph_map` for characters that may not render in all fonts:
```json
{ "🚀": ">>", "✔": "✓" }
```

### Audit

```bash
# Full audit across all themes and scenes
python3 scripts/glyph-audit.py

# Strict mode (exit 1 on any missing glyph)
python3 scripts/glyph-audit.py --strict
```

## CLI Reference

```
python3 -m demo_engine [OPTIONS]

Theme & Scene:
  --theme NAME          Visual theme (synthwave, glitch, matrix, minimal, ops)
  --scenario NAME       Scene file name or path
  --list-themes         List available themes
  --list-scenes         List available scenes

Timing:
  --preset NAME         Timing preset (short, standard, cinematic)
  --speed FLOAT         Global speed multiplier (default: 1.0)

Display:
  --aspect RATIO        Output aspect (16:9, 1:1, 9:16)
  --font-profile NAME   Font stack (nerd-safe, classic)
  --font-strict         Fail on missing glyphs

Export:
  --export FORMAT       gif, mp4, webm, all (default: gif)
  --outdir PATH         Output directory
  --cover MODE          Cover image: auto, frame:N, none
  --cut DURATION        Social cut: 8s, 15s, 30s, 45s

Audio:
  --audio on|off        Enable soundtrack (default: off)

Determinism:
  --seed INT            Random seed for reproducible output

Debug:
  --dry-run             Show timeline without rendering
  --glyph-audit         Run glyph audit and exit
  --keep-workspace      Keep temp workspace
```

## Troubleshooting

### Missing fonts
Install Nerd Fonts:
```bash
# Arch Linux
yay -S ttf-jetbrains-mono-nerd

# Ubuntu/Debian
wget -P ~/.local/share/fonts https://github.com/ryanoasis/nerd-fonts/releases/download/v3.0.2/JetBrainsMono.zip
unzip ~/.local/share/fonts/JetBrainsMono.zip -d ~/.local/share/fonts
fc-cache -fv
```

### ffmpeg not found
MP4/WebM export requires ffmpeg:
```bash
sudo pacman -S ffmpeg    # Arch
sudo apt install ffmpeg  # Ubuntu
```

### GIF too large
- Use `--preset short` for smaller output
- Use `--cut 15s` for social media clips
- Lower resolution with `--aspect 1:1` (1080x1080 vs 1920x1080)

### Tofu characters
Run the glyph audit to identify missing characters:
```bash
python3 scripts/glyph-audit.py --strict
```
Add substitutions to your theme's `glyph_map` for problematic characters.

## Architecture

```
record-demo.sh          ← Shell wrapper (delegates to Python engine)
scripts/
  render-demo.py        ← Python CLI entrypoint
  glyph-audit.py        ← Font/glyph coverage tool
  build-demo-assets.py  ← Generate overlay assets

demo_engine/
  cli.py                ← Argument parsing & pipeline orchestration
  config.py             ← Central configuration
  terminal_parser.py    ← CR/LF-aware terminal stream parser
  timeline.py           ← Timeline event model
  scenes.py             ← YAML scene DSL loader & compiler
  themes.py             ← Theme JSON loader & validator
  presets.py            ← Timing preset profiles
  fonts.py              ← Font discovery & glyph auditing
  renderer.py           ← Pillow-based frame renderer
  effects.py            ← Visual effects pipeline (CRT, glow, etc.)
  export.py             ← Multi-format export (GIF/MP4/WebM)
  capture.py            ← Asciicast v2 parser
  audio.py              ← Soundtrack & SFX management

themes/*.json           ← Theme definitions
scenes/*.yaml           ← Scene narratives
assets/                 ← Overlay textures, audio, branding
tests/                  ← Comprehensive test suite
```
