"""Terminal stream parser with CR/LF awareness and ANSI handling.

Handles:
  - \\r (carriage return): resets cursor to column 0 on current line
  - \\n (line feed): commits current line and moves to next
  - ANSI escape sequences: preserve or strip modes
  - Cursor position tracking
  - Screen snapshot emission for frame rendering
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AnsiMode(Enum):
    """How to handle ANSI escape sequences."""

    PRESERVE = "preserve"
    STRIP = "strip"


# Regex to match ANSI escape sequences
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\].*?\x07|\x1b[()][AB012]")


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape sequences from text."""
    return ANSI_RE.sub("", text)


def visible_len(text: str) -> int:
    """Length of text excluding ANSI escape codes."""
    return len(strip_ansi(text))


@dataclass
class StyledChar:
    """A single character with style information."""

    char: str = " "
    fg: Optional[str] = None
    bg: Optional[str] = None
    bold: bool = False
    dim: bool = False
    underline: bool = False

    def __str__(self) -> str:
        return self.char


@dataclass
class TerminalLine:
    """A single terminal line as a list of styled characters."""

    cells: list[StyledChar] = field(default_factory=list)
    width: int = 120

    def __post_init__(self) -> None:
        if not self.cells:
            self.cells = [StyledChar() for _ in range(self.width)]

    def set_char(self, col: int, char: str, style: Optional[dict] = None) -> None:
        """Set character at column with optional style."""
        if 0 <= col < self.width:
            sc = StyledChar(char=char)
            if style:
                sc.fg = style.get("fg")
                sc.bg = style.get("bg")
                sc.bold = style.get("bold", False)
                sc.dim = style.get("dim", False)
            self.cells[col] = sc

    def to_plain(self) -> str:
        """Return plain text content, right-stripped."""
        return "".join(c.char for c in self.cells).rstrip()

    def clear(self) -> None:
        """Clear the line."""
        self.cells = [StyledChar() for _ in range(self.width)]


@dataclass
class ScreenSnapshot:
    """A frozen snapshot of the terminal screen at a point in time."""

    lines: list[str]
    styled_lines: list[TerminalLine]
    cursor_row: int
    cursor_col: int
    t_ms: float = 0.0

    def to_text(self) -> str:
        """Render as plain text."""
        return "\n".join(self.lines)


# ── ANSI SGR (Select Graphic Rendition) parser ────────────────────────────

SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")

_BASIC_FG = {
    30: "#000000", 31: "#cc0000", 32: "#00cc00", 33: "#cccc00",
    34: "#0000cc", 35: "#cc00cc", 36: "#00cccc", 37: "#cccccc",
    90: "#555555", 91: "#ff5555", 92: "#55ff55", 93: "#ffff55",
    94: "#5555ff", 95: "#ff55ff", 96: "#55ffff", 97: "#ffffff",
}


def _parse_sgr_params(params_str: str) -> dict:
    """Parse SGR parameters into a style dict delta."""
    style: dict = {}
    if not params_str:
        return {"reset": True}

    codes = [int(c) if c else 0 for c in params_str.split(";")]
    i = 0
    while i < len(codes):
        c = codes[i]
        if c == 0:
            style["reset"] = True
        elif c == 1:
            style["bold"] = True
        elif c == 2:
            style["dim"] = True
        elif c == 4:
            style["underline"] = True
        elif c == 22:
            style["bold"] = False
            style["dim"] = False
        elif c == 24:
            style["underline"] = False
        elif c in _BASIC_FG:
            style["fg"] = _BASIC_FG[c]
        elif c == 39:
            style["fg"] = None
        elif c == 49:
            style["bg"] = None
        elif c == 38 and i + 1 < len(codes):
            # Extended foreground
            if codes[i + 1] == 5 and i + 2 < len(codes):
                style["fg"] = f"256:{codes[i + 2]}"
                i += 2
            elif codes[i + 1] == 2 and i + 4 < len(codes):
                r, g, b = codes[i + 2], codes[i + 3], codes[i + 4]
                style["fg"] = f"#{r:02x}{g:02x}{b:02x}"
                i += 4
        elif c == 48 and i + 1 < len(codes):
            # Extended background
            if codes[i + 1] == 5 and i + 2 < len(codes):
                style["bg"] = f"256:{codes[i + 2]}"
                i += 2
            elif codes[i + 1] == 2 and i + 4 < len(codes):
                r, g, b = codes[i + 2], codes[i + 3], codes[i + 4]
                style["bg"] = f"#{r:02x}{g:02x}{b:02x}"
                i += 4
        i += 1
    return style


class TerminalParser:
    """Stateful terminal stream parser.

    Processes raw terminal output character-by-character, tracking:
    - Cursor position (row, col)
    - Screen buffer (rows x cols)
    - ANSI style state
    - CR/LF semantics for spinner/progress overwrites

    Usage:
        parser = TerminalParser(rows=40, cols=120)
        parser.feed("Hello\\r\\n")
        parser.feed("\\rOverwritten line")
        snapshot = parser.snapshot()
    """

    def __init__(
        self,
        rows: int = 40,
        cols: int = 120,
        ansi_mode: AnsiMode = AnsiMode.PRESERVE,
    ) -> None:
        self.rows = rows
        self.cols = cols
        self.ansi_mode = ansi_mode

        # Screen buffer
        self.screen: list[TerminalLine] = [
            TerminalLine(width=cols) for _ in range(rows)
        ]

        # Cursor position
        self.cursor_row = 0
        self.cursor_col = 0

        # Current style state
        self._style: dict = {}

        # Scroll offset (for tracking total lines scrolled)
        self._scroll_count = 0

    def feed(self, data: str) -> None:
        """Process a chunk of terminal output."""
        i = 0
        while i < len(data):
            ch = data[i]

            # Check for ANSI escape sequence
            if ch == "\x1b" and i + 1 < len(data) and data[i + 1] == "[":
                # Find end of sequence
                j = i + 2
                while j < len(data) and data[j] not in "ABCDEFGHJKSTfmnsu":
                    j += 1
                if j < len(data):
                    seq = data[i : j + 1]
                    self._handle_escape(seq)
                    i = j + 1
                    continue
                else:
                    i += 1
                    continue

            # Regular character handling
            if ch == "\r":
                self.cursor_col = 0
            elif ch == "\n":
                self._line_feed()
            elif ch == "\b":
                if self.cursor_col > 0:
                    self.cursor_col -= 1
            elif ch == "\t":
                # Tab to next 8-column stop
                next_stop = ((self.cursor_col // 8) + 1) * 8
                self.cursor_col = min(next_stop, self.cols - 1)
            elif ord(ch) >= 32:  # Printable character
                self._put_char(ch)
            i += 1

    def _put_char(self, ch: str) -> None:
        """Place a character at the current cursor position."""
        if self.cursor_col >= self.cols:
            self._line_feed()
            self.cursor_col = 0

        self.screen[self.cursor_row].set_char(
            self.cursor_col, ch, self._style if self._style else None
        )
        self.cursor_col += 1

    def _line_feed(self) -> None:
        """Move cursor down, scrolling if at bottom."""
        if self.cursor_row < self.rows - 1:
            self.cursor_row += 1
        else:
            # Scroll: remove top line, add blank at bottom
            self.screen.pop(0)
            self.screen.append(TerminalLine(width=self.cols))
            self._scroll_count += 1
        self.cursor_col = 0

    def _handle_escape(self, seq: str) -> None:
        """Handle an ANSI escape sequence."""
        # SGR (Select Graphic Rendition) - color/style
        m = SGR_RE.match(seq)
        if m:
            params = _parse_sgr_params(m.group(1))
            if params.get("reset"):
                self._style = {}
            else:
                self._style.update(params)
            return

        # Cursor movement sequences
        body = seq[2:]
        if not body:
            return

        cmd = body[-1]
        param_str = body[:-1]

        try:
            n = int(param_str) if param_str else 1
        except ValueError:
            n = 1

        if cmd == "A":  # Cursor up
            self.cursor_row = max(0, self.cursor_row - n)
        elif cmd == "B":  # Cursor down
            self.cursor_row = min(self.rows - 1, self.cursor_row + n)
        elif cmd == "C":  # Cursor forward
            self.cursor_col = min(self.cols - 1, self.cursor_col + n)
        elif cmd == "D":  # Cursor back
            self.cursor_col = max(0, self.cursor_col - n)
        elif cmd == "K":  # Erase in line
            mode = n if param_str else 0
            if mode == 0:
                # Clear from cursor to end of line
                for c in range(self.cursor_col, self.cols):
                    self.screen[self.cursor_row].set_char(c, " ")
            elif mode == 1:
                # Clear from start to cursor
                for c in range(self.cursor_col + 1):
                    self.screen[self.cursor_row].set_char(c, " ")
            elif mode == 2:
                # Clear entire line
                self.screen[self.cursor_row].clear()
        elif cmd == "J":  # Erase in display
            mode = n if param_str else 0
            if mode == 0:
                # Clear from cursor to end
                for c in range(self.cursor_col, self.cols):
                    self.screen[self.cursor_row].set_char(c, " ")
                for r in range(self.cursor_row + 1, self.rows):
                    self.screen[r].clear()
            elif mode == 2:
                # Clear entire screen
                for r in range(self.rows):
                    self.screen[r].clear()
                self.cursor_row = 0
                self.cursor_col = 0

    def snapshot(self, t_ms: float = 0.0) -> ScreenSnapshot:
        """Capture the current screen state as a frozen snapshot."""
        lines = [line.to_plain() for line in self.screen]
        styled = [
            TerminalLine(
                cells=[
                    StyledChar(
                        char=c.char, fg=c.fg, bg=c.bg, bold=c.bold, dim=c.dim
                    )
                    for c in line.cells
                ],
                width=line.width,
            )
            for line in self.screen
        ]
        return ScreenSnapshot(
            lines=lines,
            styled_lines=styled,
            cursor_row=self.cursor_row,
            cursor_col=self.cursor_col,
            t_ms=t_ms,
        )

    def reset(self) -> None:
        """Reset the terminal to blank state."""
        self.screen = [TerminalLine(width=self.cols) for _ in range(self.rows)]
        self.cursor_row = 0
        self.cursor_col = 0
        self._style = {}
        self._scroll_count = 0
