"""Asciicast v2 capture parser.

Converts asciinema recordings (.cast files) into timeline events,
allowing real terminal recordings to be themed and re-rendered
through the demo engine pipeline.

Asciicast v2 format:
  Line 1: JSON header {"version": 2, "width": W, "height": H, ...}
  Lines 2+: [timestamp, "o", "data"]  (output events)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from demo_engine.terminal_parser import TerminalParser, AnsiMode
from demo_engine.timeline import (
    EventType,
    LineStyle,
    Timeline,
    TimelineEvent,
)


def parse_asciicast(path: str | Path) -> tuple[dict, list[tuple[float, str, str]]]:
    """Parse an asciicast v2 file.

    Returns:
        (header_dict, list of (timestamp_s, event_type, data))
    """
    path = Path(path)
    lines = path.read_text().strip().split("\n")

    if not lines:
        raise ValueError(f"Empty asciicast file: {path}")

    header = json.loads(lines[0])
    if header.get("version") != 2:
        raise ValueError(
            f"Unsupported asciicast version: {header.get('version')} (expected 2)"
        )

    events = []
    for line in lines[1:]:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if isinstance(entry, list) and len(entry) >= 3:
                ts, etype, data = entry[0], entry[1], entry[2]
                events.append((float(ts), str(etype), str(data)))
        except (json.JSONDecodeError, ValueError):
            continue

    return header, events


def asciicast_to_timeline(
    path: str | Path,
    speed: float = 1.0,
    max_idle_ms: float = 2000.0,
) -> Timeline:
    """Convert an asciicast recording to a timeline.

    Args:
        path: Path to .cast file.
        speed: Playback speed multiplier.
        max_idle_ms: Cap idle gaps to prevent long pauses.

    Returns:
        Timeline with events from the recording.
    """
    header, events = parse_asciicast(path)
    width = header.get("width", 120)
    height = header.get("height", 40)

    timeline = Timeline()
    parser = TerminalParser(rows=height, cols=width, ansi_mode=AnsiMode.PRESERVE)

    prev_ts = 0.0
    cursor_ms = 0.0

    for ts, etype, data in events:
        if etype != "o":  # Only process output events
            continue

        # Calculate delta, cap idle time
        delta_s = ts - prev_ts
        delta_ms = delta_s * 1000.0 / speed
        if delta_ms > max_idle_ms:
            delta_ms = max_idle_ms
        cursor_ms += delta_ms
        prev_ts = ts

        # Feed data to terminal parser
        parser.feed(data)

        # Snapshot the terminal state after this output
        snapshot = parser.snapshot(t_ms=cursor_ms)

        # Create a line event for each non-empty visible line
        # We emit the full screen state as a single snapshot event
        visible_text = "\n".join(
            line for line in snapshot.lines if line.strip()
        )
        if visible_text.strip():
            timeline.add(
                TimelineEvent(
                    t_ms=cursor_ms,
                    event_type=EventType.LINE,
                    text=visible_text,
                    style=LineStyle.DEFAULT,
                    meta={
                        "source": "asciicast",
                        "cursor": (snapshot.cursor_row, snapshot.cursor_col),
                    },
                )
            )

    timeline.sort()
    return timeline
