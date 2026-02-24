<div align="center">

# 🎬 Terminal Demo Engine

**High-polish terminal trailer engine — generate themed, effect-rich demo GIFs, MP4s, and WebMs from authored scene scripts or real terminal recordings.**

*One command. Five themes. Infinite drama.*

<br>

![Synthwave Demo](demos/default_synthwave-synthwave-16x9-short.gif)

<sub>▲ Synthwave theme — neon retrowave with CRT scanlines, glow, and vignette</sub>

</div>

<br>

## ✨ Features

- 🎨 **5 built-in themes** — synthwave, glitch, matrix, minimal, ops
- 🎬 **Scene DSL** — author demos in YAML with banners, spinners, progress bars, fake commands
- 📐 **Multi-aspect** — 16:9 widescreen, 9:16 stories/reels, 1:1 square
- 🔥 **Effect pipeline** — CRT scanlines, glow, noise, vignette, glitch cuts
- 📦 **Multi-format export** — GIF, MP4, WebM, or all at once
- 🎯 **Deterministic** — seed-based rendering for reproducible output
- 🔤 **Glyph-safe** — font fallback chain with per-theme glyph maps

---

## 🎭 Theme Gallery

<table>
<tr>
<td align="center" width="50%">

### Glitch

![Glitch Demo](demos/default_glitch-glitch-16x9-short.gif)

<sub>Cyber-tech aesthetic · CRT + medium glow · glitch cuts</sub>

</td>
<td align="center" width="50%">

### Matrix

![Matrix Demo](demos/incident_recovery-matrix-16x9-short.gif)

<sub>Green-on-black terminal · CRT + high glow · incident recovery scene</sub>

</td>
</tr>
<tr>
<td align="center" width="50%">

### Ops

![Ops Demo](demos/launch_day-ops-16x9-short.gif)

<sub>GitHub dark palette · clean + subtle glow · launch day scene</sub>

</td>
<td align="center" width="50%">

### Minimal

![Minimal Demo](demos/migration_story-minimal-1x1-short.gif)

<sub>VS Code-inspired · no effects · 1:1 square · migration story scene</sub>

</td>
</tr>
</table>

<div align="center">

### 📱 Vertical / Stories Format (9:16)

<img src="demos/launch_day-synthwave-9x16-short.gif" width="320" alt="Synthwave 9:16 Demo">

<sub>Synthwave theme · 9:16 aspect · perfect for Instagram Stories & TikTok</sub>

</div>

---

## 🚀 Quickstart

```bash
# Install
pip install -e .

# Render default demo with the glitch theme
./record-demo.sh --theme glitch --preset short --export gif

# Use the Python CLI directly
python3 -m demo_engine --theme synthwave --preset cinematic --export all

# Render a named scenario
python3 -m demo_engine --scenario launch_day --theme ops --export mp4

# Social media vertical cut (9:16 for stories/reels)
./record-demo.sh --theme glitch --preset short --aspect 9:16 --export all --cut 15s

# Deterministic output
python3 -m demo_engine --theme matrix --preset standard --seed 42 --export gif
```

### Requirements

- Python ≥ 3.11
- [Pillow](https://pillow.readthedocs.io/) ≥ 10.0, [PyYAML](https://pyyaml.org/) ≥ 6.0, [fonttools](https://github.com/fonttools/fonttools) ≥ 4.40
- [ffmpeg](https://ffmpeg.org/) (for MP4/WebM export)
- [Nerd Fonts](https://www.nerdfonts.com/) recommended (JetBrainsMono or CaskaydiaMono)

---

## 🎨 Themes

| Theme | Vibe | CRT | Glow | Best For |
|-------|------|:---:|:----:|----------|
| **`synthwave`** | Purple/pink neon retrowave | ✓ | High | Hero demos, launch trailers |
| **`glitch`** | Dark blue cyber-tech | ✓ | Medium | DevOps, infra tooling |
| **`matrix`** | Green-on-black terminal | ✓ | High | Security, monitoring |
| **`minimal`** | Clean dark, VS Code-like | — | — | Documentation, tutorials |
| **`ops`** | GitHub dark palette | — | Low | SaaS dashboards, CI/CD |

Themes are plain JSON files in `themes/` — add your own without touching code:

```json
{
  "id": "mytheme",
  "colors": {
    "bg": "#0a0a0a",
    "text": "#e0e0e0",
    "cmd": "#67e8f9",
    "success": "#86efac",
    "warn": "#fbbf24",
    "accent": "#c084fc"
  },
  "effects": {
    "crt": true,
    "scanlines": 0.12,
    "glow": 0.4,
    "noise": 0.04,
    "vignette": 0.2
  }
}
```

---

## ⏱ Presets

| Preset | Duration | FPS | Use Case |
|--------|----------|-----|----------|
| **`short`** | 8–15s | 24 | Social media, tweets, quick demos |
| **`standard`** | 20–30s | 30 | README embeds, docs |
| **`cinematic`** | 35–60s | 30 | Launch trailers, full walkthroughs |

---

## 📝 Scene DSL

Scenes define the narrative flow. Create a `.yaml` file in `scenes/`:

```yaml
id: my_demo
title: "My Cool Demo"

steps:
  - type: banner
    banner: demo

  - type: command
    text: 'ls -la'
    mode: fake
    output:
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
```

### Step Types

| Type | Description | Key Fields |
|------|-------------|------------|
| `banner` | ASCII art header | `text`, `banner` (named) |
| `line` | Single text line | `text`, `style` |
| `command` | Simulated terminal command | `text`, `output[]`, `mode` |
| `spinner` | Animated spinner | `label`, `cycles` |
| `progress` | Progress bar animation | `label`, `width` |
| `transition` | Visual transition effect | `transition`, `duration_ms` |
| `pause` | Hold/delay | `duration_ms` |

### Built-in Scenes

| Scene | Description |
|-------|-------------|
| `default_glitch` | Cyber-tech pipeline rebuild |
| `launch_day` | Product launch deploy sequence |
| `incident_recovery` | Alert → triage → recovery story |
| `migration_story` | Database migration walkthrough |

---

## 🖥 CLI Reference

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

---

## 🔤 Font Fallback & Glyph Safety

The engine uses a prioritized font stack with per-character font selection (Pillow doesn't do automatic fallback):

1. **JetBrainsMono Nerd Font Mono** (primary)
2. **CaskaydiaMono Nerd Font Mono** (fallback)
3. **Noto Sans Symbols2** (symbol fallback)

Each theme defines a `glyph_map` for safe substitutions:
```json
{ "🚀": ">>", "✔": "✓" }
```

Run the audit to catch missing glyphs:
```bash
python3 scripts/glyph-audit.py          # Full audit
python3 scripts/glyph-audit.py --strict  # Fail on any missing glyph
```

---

## 🏗 Architecture

```
record-demo.sh              ← Shell wrapper
scripts/
  render-demo.py            ← Python CLI entrypoint
  glyph-audit.py            ← Font/glyph coverage tool
  build-demo-assets.py      ← Generate overlay assets

demo_engine/
  cli.py                    ← Argument parsing & orchestration
  config.py                 ← Central configuration
  terminal_parser.py        ← CR/LF-aware terminal stream parser
  timeline.py               ← Timeline event model
  scenes.py                 ← YAML scene DSL loader & compiler
  themes.py                 ← Theme JSON loader & validator
  presets.py                ← Timing preset profiles
  fonts.py                  ← Font discovery & glyph auditing
  renderer.py               ← Pillow-based frame renderer
  effects.py                ← CRT, glow, noise, vignette, glitch
  export.py                 ← Multi-format export (GIF/MP4/WebM)
  capture.py                ← Asciicast v2 parser
  audio.py                  ← Soundtrack & SFX management

themes/*.json               ← Theme definitions
scenes/*.yaml               ← Scene narratives
assets/                     ← Overlay textures, audio, branding
tests/                      ← Test suite
```

---

## 🛠 Troubleshooting

<details>
<summary><b>Missing fonts</b></summary>

```bash
# Arch Linux
yay -S ttf-jetbrains-mono-nerd

# Ubuntu/Debian
wget -P ~/.local/share/fonts https://github.com/ryanoasis/nerd-fonts/releases/download/v3.0.2/JetBrainsMono.zip
unzip ~/.local/share/fonts/JetBrainsMono.zip -d ~/.local/share/fonts
fc-cache -fv
```
</details>

<details>
<summary><b>ffmpeg not found</b></summary>

MP4/WebM export requires ffmpeg:
```bash
sudo pacman -S ffmpeg    # Arch
sudo apt install ffmpeg  # Ubuntu
```
</details>

<details>
<summary><b>GIF too large</b></summary>

- Use `--preset short` for smaller output
- Use `--cut 15s` for social media clips
- Lower resolution with `--aspect 1:1` (1080×1080 vs 1920×1080)
</details>

<details>
<summary><b>Tofu characters (□□□)</b></summary>

Run the glyph audit:
```bash
python3 scripts/glyph-audit.py --strict
```
Add substitutions to your theme's `glyph_map` for problematic characters.
</details>

---

<div align="center">

**[Themes](#-themes) · [Scenes](#-scene-dsl) · [CLI](#%EF%B8%8F-cli-reference) · [Architecture](#-architecture)**

MIT License

</div>
