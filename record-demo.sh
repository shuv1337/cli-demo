#!/usr/bin/env bash
set -euo pipefail

export TERM="${TERM:-xterm-256color}"

# ── Demo Engine wrapper ───────────────────────────────────────────────────
# If Python demo engine is available, delegate to it.
# Falls back to legacy bash implementation for backward compatibility.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DEMO_SPEED="${DEMO_SPEED:-1}"     # 0 = no animation, 1 = default, <1 faster, >1 slower
KEEP_DEMO="${KEEP_DEMO:-0}"       # 1 = keep temp workspace
THEME="${THEME:-synthwave}"       # synthwave | glitch

usage() {
  cat <<'EOF'
Usage: ./record-demo.sh [--theme synthwave|glitch|matrix|minimal|ops] [--speed N] [--keep]
       ./record-demo.sh [--theme T] [--preset short|standard|cinematic] [--aspect 16:9|1:1|9:16]
                        [--export gif|mp4|webm|all] [--scenario NAME] [--seed N]

Options:
  --theme <name>     Visual theme (synthwave, glitch, matrix, minimal, ops)
  --preset <name>    Timing preset (short, standard, cinematic)
  --speed <number>   Animation speed multiplier
  --aspect <ratio>   Output aspect ratio (16:9, 1:1, 9:16)
  --export <fmt>     Export format (gif, mp4, webm, all)
  --scenario <name>  Scene scenario (default_glitch, launch_day, etc.)
  --seed <int>       Deterministic seed
  --keep             Keep temporary demo workspace
  --legacy           Force legacy bash mode
  -h, --help         Show this help message

Env overrides:
  THEME, DEMO_SPEED, KEEP_DEMO, NO_COLOR
EOF
}

USE_LEGACY=0
ENGINE_ARGS=()

while (($#)); do
  case "$1" in
    --theme)
      THEME="${2:-}"
      ENGINE_ARGS+=(--theme "$THEME")
      shift 2
      ;;
    --theme=*)
      THEME="${1#*=}"
      ENGINE_ARGS+=(--theme "$THEME")
      shift
      ;;
    --speed)
      DEMO_SPEED="${2:-}"
      ENGINE_ARGS+=(--speed "$DEMO_SPEED")
      shift 2
      ;;
    --speed=*)
      DEMO_SPEED="${1#*=}"
      ENGINE_ARGS+=(--speed "$DEMO_SPEED")
      shift
      ;;
    --keep)
      KEEP_DEMO="1"
      ENGINE_ARGS+=(--keep-workspace)
      shift
      ;;
    --legacy)
      USE_LEGACY=1
      shift
      ;;
    --preset|--aspect|--export|--scenario|--seed|--cut|--cover|--outdir|--font-profile|--audio)
      ENGINE_ARGS+=("$1" "${2:-}")
      shift 2
      ;;
    --font-strict|--glyph-audit|--dry-run|--list-themes|--list-scenes)
      ENGINE_ARGS+=("$1")
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

# ── Try Python engine first (unless --legacy) ────────────────────────────
if [[ "$USE_LEGACY" == "0" ]] && command -v python3 &>/dev/null; then
  if python3 -c "import demo_engine" 2>/dev/null || [[ -d "$SCRIPT_DIR/demo_engine" ]]; then
    export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH:-}"
    exec python3 "$SCRIPT_DIR/scripts/render-demo.py" "${ENGINE_ARGS[@]}"
  fi
fi

# ── Legacy bash fallback ─────────────────────────────────────────────────
echo "ℹ Using legacy bash mode (Python engine not available)"

case "$THEME" in
  synthwave|glitch) ;;
  *)
    printf 'Unsupported theme in legacy mode: %s (use synthwave or glitch)\n' "$THEME" >&2
    exit 1
    ;;
esac

DEMO_DIR="$(mktemp -d "/tmp/${THEME}-shell-demo.XXXXXX")"

supports_color() {
  [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]]
}

# default (no color)
C_RESET=''
C_BOLD=''
C_DIM=''
C_PRIMARY=''
C_ACCENT=''
C_SUCCESS=''
C_WARN=''

if supports_color; then
  C_RESET=$'\033[0m'
  C_BOLD=$'\033[1m'
  C_DIM=$'\033[2m'

  case "$THEME" in
    synthwave)
      C_PRIMARY=$'\033[35m'
      C_ACCENT=$'\033[36m'
      C_SUCCESS=$'\033[32m'
      C_WARN=$'\033[33m'
      ;;
    glitch)
      C_PRIMARY=$'\033[95m'
      C_ACCENT=$'\033[92m'
      C_SUCCESS=$'\033[96m'
      C_WARN=$'\033[93m'
      ;;
  esac
fi

if [[ "$THEME" == "glitch" ]]; then
  DEMO_TITLE="Glitch Grid Demo // high-voltage terminal sequence"
  PROFILE="glitch"
  SHIP_STYLE="glitchcore"
  ENDPOINT="https://staging.glitch-grid.demo"
  SPINNER_LABEL="Resynchronizing packet ghosts"
  PROGRESS_LABEL="Rebuilding fractured pipeline"
else
  DEMO_TITLE="Neon Shell Demo // cinematic terminal sequence"
  PROFILE="cinematic"
  SHIP_STYLE="synthwave"
  ENDPOINT="https://staging.neon-shell.demo"
  SPINNER_LABEL="Priming spectral cache"
  PROGRESS_LABEL="Compiling visual pipeline"
fi

cleanup() {
  if [[ "$KEEP_DEMO" == "1" ]]; then
    printf "\n%sworkspace kept:%s %s\n" "$C_DIM" "$C_RESET" "$DEMO_DIR"
  else
    rm -rf "$DEMO_DIR"
  fi
}
trap cleanup EXIT

pause() {
  local base="${1:-0.05}"
  [[ "$DEMO_SPEED" == "0" ]] && return
  local scaled
  scaled="$(awk -v b="$base" -v s="$DEMO_SPEED" 'BEGIN { printf "%.3f", (b * s) }')"
  sleep "$scaled"
}

type_line() {
  local text="$1"
  if [[ "$DEMO_SPEED" == "0" ]]; then
    printf "%s\n" "$text"
    return
  fi

  local i ch
  for ((i = 0; i < ${#text}; i++)); do
    ch="${text:i:1}"
    printf "%s" "$ch"
    pause 0.01
  done
  printf "\n"
}

rule() {
  printf "%b%s%b\n" "$C_DIM" "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" "$C_RESET"
}

cmd() {
  local statement="$1"
  printf "\n%b❯%b %s\n" "$C_ACCENT" "$C_RESET" "$statement"
  pause 0.12
}

run_real() {
  local statement="$1"
  cmd "$statement"
  bash -lc "$statement"
}

run_fake() {
  local statement="$1"
  cmd "$statement"
  while IFS= read -r line; do
    printf "%s\n" "$line"
    pause 0.03
  done
}

spinner() {
  local label="$1"
  local cycles="${2:-20}"
  local frames=("⠋" "⠙" "⠹" "⠸" "⠼" "⠴" "⠦" "⠧" "⠇" "⠏")
  local i frame

  for ((i = 0; i < cycles; i++)); do
    frame="${frames[i % ${#frames[@]}]}"
    printf "\r%b%s%b %s" "$C_WARN" "$frame" "$C_RESET" "$label"
    pause 0.06
  done
  printf "\r%b✔%b %s\n" "$C_SUCCESS" "$C_RESET" "$label"
}

progress() {
  local label="$1"
  local width="${2:-26}"
  local i pct
  local full empty

  printf "%s\n" "$label"
  for ((i = 0; i <= width; i++)); do
    pct=$((i * 100 / width))
    printf -v full "%${i}s" ""
    printf -v empty "%$((width - i))s" ""
    full="${full// /█}"
    empty="${empty// /░}"
    printf "\r%b[%s%s] %3d%%%b" "$C_PRIMARY" "$full" "$empty" "$pct" "$C_RESET"
    pause 0.02
  done
  printf "\n"
}

print_banner() {
  printf "%b" "$C_BOLD$C_PRIMARY"
  if [[ "$THEME" == "glitch" ]]; then
    cat <<'BANNER'
 ██████╗ ██╗     ██╗████████╗ ██████╗██╗  ██╗
██╔════╝ ██║     ██║╚══██╔══╝██╔════╝██║  ██║
██║  ███╗██║     ██║   ██║   ██║     ███████║
██║   ██║██║     ██║   ██║   ██║     ██╔══██║
╚██████╔╝███████╗██║   ██║   ╚██████╗██║  ██║
 ╚═════╝ ╚══════╝╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝
BANNER
  else
    cat <<'BANNER'
███╗   ██╗███████╗ ██████╗ ███╗   ██╗
████╗  ██║██╔════╝██╔═══██╗████╗  ██║
██╔██╗ ██║█████╗  ██║   ██║██╔██╗ ██║
██║╚██╗██║██╔══╝  ██║   ██║██║╚██╗██║
██║ ╚████║███████╗╚██████╔╝██║ ╚████║
╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝
BANNER
  fi
  printf "%b\n" "$C_RESET"
}

mkdir -p "$DEMO_DIR/src" "$DEMO_DIR/logs" "$DEMO_DIR/config"

cat > "$DEMO_DIR/src/orchestrator.ts" <<'TS'
export const orchestrate = async () => {
  // TODO: retry policy tuning
  return { stage: "hyperdrive", status: "ready" }
}
TS

cat > "$DEMO_DIR/src/render.ts" <<'TS'
export const render = (name: string) => {
  // TODO: dark mode spectrum gradients
  return `rendered:${name}`
}
TS

cat > "$DEMO_DIR/config/pipeline.json" <<'JSON'
{
  "project": "neon-shell",
  "steps": ["scan", "optimize", "ship"],
  "target": "staging"
}
JSON

cat > "$DEMO_DIR/logs/telemetry.log" <<'LOG'
10:21:01 ingest packets=148 latency=4.2ms
10:21:02 render frames=920 dropped=0
10:21:03 cache hit_rate=97.4%
10:21:04 queue depth=3 status=stable
10:21:05 release candidate=rc.42 verdict=green
LOG

print_banner
type_line "$DEMO_TITLE"
printf "%btheme:%b %s\n" "$C_DIM" "$C_RESET" "$THEME"
printf "%bworkspace:%b %s\n" "$C_DIM" "$C_RESET" "$DEMO_DIR"
rule
pause 0.2

run_real "ls -1 \"$DEMO_DIR/src\""
run_real "grep -R \"TODO\" -n \"$DEMO_DIR/src\""
run_real "awk 'NR <= 8 {print}' \"$DEMO_DIR/config/pipeline.json\""

spinner "$SPINNER_LABEL"
progress "$PROGRESS_LABEL"

run_fake "neon scan --project \"$DEMO_DIR\" --profile $PROFILE" <<EOF
${C_SUCCESS}✔${C_RESET} src/orchestrator.ts    deprecated APIs: 0   perf hints: 2
${C_SUCCESS}✔${C_RESET} src/render.ts          deprecated APIs: 0   perf hints: 1
${C_SUCCESS}✔${C_RESET} config/pipeline.json   schema: valid         target: staging

Scan summary:
  files analyzed : 3
  warnings       : 0
  opportunities  : 3
EOF

run_real "tail -n 5 \"$DEMO_DIR/logs/telemetry.log\""

run_fake "neon ship --target staging --style $SHIP_STYLE" <<EOF
[link] handshake with edge gateway.............ok
[push] uploading release bundle................ok
[verify] health checks (latency p95 < 20ms)....ok
[done] deployment id: neon-rc42-a9f

endpoint: $ENDPOINT
status:   ${C_SUCCESS}LIVE${C_RESET}
EOF

rule
printf "%b🚀 Demo complete.%b\n" "$C_BOLD$C_SUCCESS" "$C_RESET"
printf "%bTip:%b --theme glitch for alt style, DEMO_SPEED=0.35 for smoother recording.\n" "$C_DIM" "$C_RESET"
