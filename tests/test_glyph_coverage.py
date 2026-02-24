"""Tests for font discovery and glyph coverage auditing."""

import pytest

from demo_engine.fonts import (
    FontStack,
    GlyphAuditResult,
    apply_glyph_map,
    audit_glyphs,
    resolve_font_stack,
)


class TestResolveFont:
    def test_nerd_safe_finds_font(self):
        """Should find at least one nerd font on this system."""
        stack = resolve_font_stack("nerd-safe", 16)
        assert stack.primary is not None
        assert stack.primary_path != "<default>"

    def test_classic_profile(self):
        stack = resolve_font_stack("classic", 16)
        assert stack.primary is not None

    def test_fallback_to_default(self):
        """Unknown fonts should fall back gracefully."""
        from demo_engine.fonts import FONT_PROFILES
        # Temporarily inject bogus profile
        FONT_PROFILES["bogus"] = ["NonExistentFont9999"]
        stack = resolve_font_stack("bogus", 16)
        # Should still return something
        assert stack.primary is not None
        del FONT_PROFILES["bogus"]


class TestGlyphAudit:
    def test_ascii_fully_covered(self):
        stack = resolve_font_stack("nerd-safe", 16)
        result = audit_glyphs("Hello World 123", stack)
        assert result.is_clean
        assert result.coverage_pct == 100.0

    def test_common_symbols(self):
        stack = resolve_font_stack("nerd-safe", 16)
        corpus = "✓✗❯█░━╗╔╚╝║"
        result = audit_glyphs(corpus, stack)
        # Most of these should be covered by nerd fonts
        assert result.coverage_pct >= 80.0

    def test_glyph_map_substitution(self):
        stack = resolve_font_stack("nerd-safe", 16)
        glyph_map = {"🚀": ">>"}
        result = audit_glyphs("🚀", stack, glyph_map)
        assert "🚀" in result.substitutions
        assert result.substitutions["🚀"] == ">>"

    def test_empty_corpus(self):
        stack = resolve_font_stack("nerd-safe", 16)
        result = audit_glyphs("", stack)
        assert result.is_clean
        assert result.total_chars == 0

    def test_report_format(self):
        result = GlyphAuditResult(
            total_chars=10, covered=8, missing=["🎉", "🎊"]
        )
        report = result.report()
        assert "10" in report
        assert "80.0%" in report
        assert "Missing" in report


class TestApplyGlyphMap:
    def test_basic_substitution(self):
        assert apply_glyph_map("✔ done", {"✔": "✓"}) == "✓ done"

    def test_multiple_subs(self):
        gmap = {"🚀": ">>", "✔": "✓"}
        assert apply_glyph_map("🚀 ✔", gmap) == ">> ✓"

    def test_no_match(self):
        assert apply_glyph_map("hello", {"x": "y"}) == "hello"

    def test_empty_map(self):
        assert apply_glyph_map("hello", {}) == "hello"
