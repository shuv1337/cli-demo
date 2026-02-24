"""Tests for the terminal parser — CR/LF semantics, ANSI handling."""

import pytest

from demo_engine.terminal_parser import (
    AnsiMode,
    TerminalParser,
    strip_ansi,
    visible_len,
)


class TestStripAnsi:
    def test_no_ansi(self):
        assert strip_ansi("hello world") == "hello world"

    def test_basic_colors(self):
        assert strip_ansi("\033[31mred\033[0m") == "red"

    def test_multiple_codes(self):
        assert strip_ansi("\033[1;32mbold green\033[0m text") == "bold green text"

    def test_256_color(self):
        assert strip_ansi("\033[38;5;196mtext\033[0m") == "text"


class TestVisibleLen:
    def test_plain(self):
        assert visible_len("hello") == 5

    def test_with_ansi(self):
        assert visible_len("\033[31mhello\033[0m") == 5

    def test_empty(self):
        assert visible_len("") == 0


class TestTerminalParserBasic:
    def test_simple_text(self):
        p = TerminalParser(rows=10, cols=40)
        p.feed("Hello World")
        snap = p.snapshot()
        assert snap.lines[0] == "Hello World"

    def test_newline(self):
        p = TerminalParser(rows=10, cols=40)
        p.feed("line1\nline2\nline3")
        snap = p.snapshot()
        assert snap.lines[0] == "line1"
        assert snap.lines[1] == "line2"
        assert snap.lines[2] == "line3"

    def test_empty_lines(self):
        p = TerminalParser(rows=10, cols=40)
        p.feed("a\n\nb")
        snap = p.snapshot()
        assert snap.lines[0] == "a"
        assert snap.lines[1] == ""
        assert snap.lines[2] == "b"


class TestCarriageReturn:
    """CR (\r) should reset cursor to column 0, overwriting the current line."""

    def test_cr_overwrites(self):
        p = TerminalParser(rows=10, cols=40)
        p.feed("AAAAAAAAAA\rBBBBB")
        snap = p.snapshot()
        # First 5 chars overwritten, last 5 remain from A
        assert snap.lines[0] == "BBBBBAAAAA"

    def test_spinner_simulation(self):
        """Spinner frames should overwrite each other on the same line."""
        p = TerminalParser(rows=10, cols=40)
        frames = ["⠋", "⠙", "⠹", "⠸"]
        for frame in frames:
            p.feed(f"\r{frame} Loading...")

        snap = p.snapshot()
        # Should show last frame only
        assert snap.lines[0].startswith("⠸ Loading...")

    def test_progress_bar_overwrite(self):
        """Progress bar updates via \\r should overwrite cleanly."""
        p = TerminalParser(rows=10, cols=40)
        p.feed("\r[████░░░░░░] 40%")
        p.feed("\r[████████░░] 80%")
        p.feed("\r[██████████] 100%")
        snap = p.snapshot()
        assert "100%" in snap.lines[0]
        # No stacking — still on line 0
        assert snap.lines[1].strip() == ""

    def test_cr_then_lf(self):
        p = TerminalParser(rows=10, cols=40)
        p.feed("line1\r\nline2")
        snap = p.snapshot()
        assert snap.lines[0] == "line1"
        assert snap.lines[1] == "line2"


class TestScrolling:
    def test_scrolls_at_bottom(self):
        p = TerminalParser(rows=3, cols=40)
        p.feed("a\nb\nc\nd")
        snap = p.snapshot()
        # 'a' should have scrolled off
        assert snap.lines[0] == "b"
        assert snap.lines[1] == "c"
        assert snap.lines[2] == "d"

    def test_many_lines_scroll(self):
        p = TerminalParser(rows=5, cols=40)
        for i in range(20):
            p.feed(f"line {i}\n")
        snap = p.snapshot()
        # Should see the last few lines
        assert "line 19" in snap.to_text() or "line 18" in snap.to_text()


class TestAnsiHandling:
    def test_basic_color(self):
        p = TerminalParser(rows=10, cols=40)
        p.feed("\033[31mred text\033[0m")
        snap = p.snapshot()
        assert snap.lines[0] == "red text"
        # Check style is preserved
        assert snap.styled_lines[0].cells[0].fg == "#cc0000"

    def test_bold(self):
        p = TerminalParser(rows=10, cols=40)
        p.feed("\033[1mbold\033[0m")
        snap = p.snapshot()
        assert snap.styled_lines[0].cells[0].bold is True

    def test_cursor_movement(self):
        p = TerminalParser(rows=10, cols=40)
        p.feed("ABCDEF")
        p.feed("\033[3D")  # Move back 3
        p.feed("XYZ")
        snap = p.snapshot()
        assert snap.lines[0] == "ABCXYZ"

    def test_erase_line(self):
        p = TerminalParser(rows=10, cols=40)
        p.feed("Hello World")
        p.feed("\033[2K")  # Erase entire line
        snap = p.snapshot()
        assert snap.lines[0].strip() == ""


class TestSnapshot:
    def test_to_text(self):
        p = TerminalParser(rows=5, cols=20)
        p.feed("hello\nworld")
        snap = p.snapshot(t_ms=1000)
        assert "hello" in snap.to_text()
        assert "world" in snap.to_text()
        assert snap.t_ms == 1000

    def test_cursor_position(self):
        p = TerminalParser(rows=10, cols=40)
        p.feed("abc")
        snap = p.snapshot()
        assert snap.cursor_row == 0
        assert snap.cursor_col == 3


class TestReset:
    def test_reset_clears_state(self):
        p = TerminalParser(rows=10, cols=40)
        p.feed("some text\nmore text")
        p.reset()
        snap = p.snapshot()
        assert all(line.strip() == "" for line in snap.lines)
        assert snap.cursor_row == 0
        assert snap.cursor_col == 0
