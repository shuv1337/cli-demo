"""Timeline event model for demo sequences.

The timeline is the normalized intermediate representation between
scenes (authored narrative) and the renderer (frame output).

All timing is in milliseconds. Events are ordered chronologically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class EventType(Enum):
    """Types of timeline events."""

    BANNER = "banner"
    LINE = "line"
    COMMAND = "command"
    CURSOR = "cursor"
    SPINNER_FRAME = "spinner_frame"
    PROGRESS_FRAME = "progress_frame"
    TRANSITION = "transition"
    SFX = "sfx"
    MARKER = "marker"
    PAUSE = "pause"
    CLEAR = "clear"


class LineStyle(Enum):
    """Visual style hint for a line of text."""

    DEFAULT = "default"
    COMMAND = "command"
    SUCCESS = "success"
    WARN = "warn"
    ERROR = "error"
    DIM = "dim"
    ACCENT = "accent"
    BANNER = "banner"


@dataclass
class TimelineEvent:
    """A single event in the demo timeline.

    Attributes:
        t_ms: Absolute timestamp in milliseconds.
        event_type: The type of event.
        text: Text content (if applicable).
        style: Visual style hint.
        row: Target row for overwrites (spinner/progress).
        meta: Arbitrary metadata (scene name, step index, etc.).
        duration_ms: Duration for events that span time (pause, transition).
    """

    t_ms: float
    event_type: EventType
    text: str = ""
    style: LineStyle = LineStyle.DEFAULT
    row: Optional[int] = None
    meta: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to dict for debugging/export."""
        return {
            "t_ms": self.t_ms,
            "type": self.event_type.value,
            "text": self.text,
            "style": self.style.value,
            "row": self.row,
            "meta": self.meta,
            "duration_ms": self.duration_ms,
        }


class Timeline:
    """Ordered sequence of timeline events.

    Provides methods for building, querying, and iterating over
    the demo event stream.
    """

    def __init__(self) -> None:
        self._events: list[TimelineEvent] = []

    def add(self, event: TimelineEvent) -> None:
        """Add an event to the timeline."""
        self._events.append(event)

    def add_line(
        self,
        t_ms: float,
        text: str,
        style: LineStyle = LineStyle.DEFAULT,
        **meta: Any,
    ) -> float:
        """Add a text line event and return the next timestamp."""
        self._events.append(
            TimelineEvent(
                t_ms=t_ms,
                event_type=EventType.LINE,
                text=text,
                style=style,
                meta=meta,
            )
        )
        return t_ms

    def add_command(self, t_ms: float, text: str, **meta: Any) -> float:
        """Add a command event."""
        self._events.append(
            TimelineEvent(
                t_ms=t_ms,
                event_type=EventType.COMMAND,
                text=text,
                style=LineStyle.COMMAND,
                meta=meta,
            )
        )
        return t_ms

    def add_banner(self, t_ms: float, text: str, **meta: Any) -> float:
        """Add a banner event."""
        for i, line in enumerate(text.split("\n")):
            self._events.append(
                TimelineEvent(
                    t_ms=t_ms,
                    event_type=EventType.BANNER,
                    text=line,
                    style=LineStyle.BANNER,
                    meta={**meta, "banner_line": i},
                )
            )
        return t_ms

    def add_spinner(
        self,
        t_ms: float,
        label: str,
        frames: list[str],
        cycle_ms: float = 80.0,
        cycles: int = 20,
        row: Optional[int] = None,
    ) -> float:
        """Add spinner animation frames."""
        cursor = t_ms
        for i in range(cycles):
            frame_char = frames[i % len(frames)]
            self._events.append(
                TimelineEvent(
                    t_ms=cursor,
                    event_type=EventType.SPINNER_FRAME,
                    text=f"{frame_char} {label}",
                    style=LineStyle.WARN,
                    row=row,
                    meta={"frame": i, "total": cycles},
                )
            )
            cursor += cycle_ms

        # Final "done" frame
        self._events.append(
            TimelineEvent(
                t_ms=cursor,
                event_type=EventType.SPINNER_FRAME,
                text=f"✓ {label}",
                style=LineStyle.SUCCESS,
                row=row,
                meta={"frame": cycles, "done": True},
            )
        )
        return cursor

    def add_progress(
        self,
        t_ms: float,
        label: str,
        width: int = 26,
        step_ms: float = 40.0,
        row: Optional[int] = None,
    ) -> float:
        """Add progress bar animation frames."""
        cursor = t_ms

        # Label line first
        self._events.append(
            TimelineEvent(
                t_ms=cursor,
                event_type=EventType.LINE,
                text=label,
                style=LineStyle.DEFAULT,
            )
        )
        cursor += step_ms

        for i in range(width + 1):
            pct = i * 100 // width
            filled = "█" * i
            empty = "░" * (width - i)
            bar_text = f"[{filled}{empty}] {pct:3d}%"
            self._events.append(
                TimelineEvent(
                    t_ms=cursor,
                    event_type=EventType.PROGRESS_FRAME,
                    text=bar_text,
                    style=LineStyle.ACCENT,
                    row=row,
                    meta={"pct": pct, "step": i, "total": width},
                )
            )
            cursor += step_ms

        return cursor

    def add_pause(self, t_ms: float, duration_ms: float) -> float:
        """Add a pause event."""
        self._events.append(
            TimelineEvent(
                t_ms=t_ms,
                event_type=EventType.PAUSE,
                duration_ms=duration_ms,
            )
        )
        return t_ms + duration_ms

    def add_transition(
        self, t_ms: float, style: str = "cut", duration_ms: float = 200.0
    ) -> float:
        """Add a transition event."""
        self._events.append(
            TimelineEvent(
                t_ms=t_ms,
                event_type=EventType.TRANSITION,
                text=style,
                duration_ms=duration_ms,
                meta={"transition": style},
            )
        )
        return t_ms + duration_ms

    def sort(self) -> None:
        """Sort events by timestamp."""
        self._events.sort(key=lambda e: e.t_ms)

    @property
    def events(self) -> list[TimelineEvent]:
        """Get all events in order."""
        return list(self._events)

    @property
    def duration_ms(self) -> float:
        """Total timeline duration."""
        if not self._events:
            return 0.0
        last = max(e.t_ms + e.duration_ms for e in self._events)
        return last

    def events_in_range(self, start_ms: float, end_ms: float) -> list[TimelineEvent]:
        """Get events within a time range."""
        return [e for e in self._events if start_ms <= e.t_ms < end_ms]

    def apply_speed(self, multiplier: float) -> None:
        """Scale all timestamps by a speed multiplier."""
        if multiplier <= 0:
            return
        factor = 1.0 / multiplier
        for event in self._events:
            event.t_ms *= factor
            event.duration_ms *= factor

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self):
        return iter(self._events)
