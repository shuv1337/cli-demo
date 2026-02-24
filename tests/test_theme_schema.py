"""Tests for theme loading, validation, and schema compliance."""

import json
import pytest
import tempfile
from pathlib import Path

from demo_engine.themes import (
    Theme,
    ThemeError,
    list_themes,
    load_theme,
    load_theme_from_dict,
    validate_theme_data,
)


class TestThemeValidation:
    def test_valid_theme(self):
        data = {
            "id": "test",
            "colors": {
                "bg": "#000000",
                "text": "#ffffff",
                "cmd": "#00ff00",
                "success": "#00ff00",
                "warn": "#ffff00",
                "accent": "#ff00ff",
            },
        }
        errors = validate_theme_data(data)
        assert errors == []

    def test_missing_id(self):
        data = {"colors": {"bg": "#000", "text": "#fff", "cmd": "#0f0",
                           "success": "#0f0", "warn": "#ff0", "accent": "#f0f"}}
        errors = validate_theme_data(data)
        assert any("id" in e for e in errors)

    def test_missing_required_color(self):
        data = {
            "id": "test",
            "colors": {"bg": "#000", "text": "#fff"},  # Missing cmd, success, etc.
        }
        errors = validate_theme_data(data)
        assert len(errors) > 0
        assert any("cmd" in e for e in errors)

    def test_invalid_color_format(self):
        data = {
            "id": "test",
            "colors": {
                "bg": "not-a-hex",  # Invalid
                "text": "#fff", "cmd": "#0f0",
                "success": "#0f0", "warn": "#ff0", "accent": "#f0f",
            },
        }
        errors = validate_theme_data(data)
        assert any("hex" in e.lower() for e in errors)

    def test_unknown_effect_key(self):
        data = {
            "id": "test",
            "colors": {"bg": "#000", "text": "#fff", "cmd": "#0f0",
                       "success": "#0f0", "warn": "#ff0", "accent": "#f0f"},
            "effects": {"unknown_effect": True},
        }
        errors = validate_theme_data(data)
        assert any("unknown" in e for e in errors)

    def test_wrong_effect_type(self):
        data = {
            "id": "test",
            "colors": {"bg": "#000", "text": "#fff", "cmd": "#0f0",
                       "success": "#0f0", "warn": "#ff0", "accent": "#f0f"},
            "effects": {"crt": "yes"},  # Should be bool
        }
        errors = validate_theme_data(data)
        assert any("crt" in e for e in errors)


class TestThemeLoading:
    def test_load_builtin_themes(self):
        """All built-in themes should load without errors."""
        for name in list_themes():
            theme = load_theme(name)
            assert theme.id == name
            assert theme.colors.bg.startswith("#")
            assert theme.colors.text.startswith("#")

    def test_theme_not_found(self):
        with pytest.raises(ThemeError, match="not found"):
            load_theme("nonexistent_theme_xyz")

    def test_load_from_dict(self):
        data = {
            "id": "custom",
            "name": "Custom Theme",
            "colors": {
                "bg": "#111111",
                "text": "#eeeeee",
                "cmd": "#aabbcc",
                "success": "#00ff00",
                "warn": "#ffff00",
                "accent": "#ff00ff",
            },
            "effects": {"crt": True, "scanlines": 0.1},
            "glyph_map": {"🚀": ">>"},
        }
        theme = load_theme_from_dict(data)
        assert theme.id == "custom"
        assert theme.name == "Custom Theme"
        assert theme.effects.crt is True
        assert theme.effects.scanlines == 0.1
        assert theme.glyph_map["🚀"] == ">>"


class TestThemeRegistry:
    def test_list_themes_returns_names(self):
        themes = list_themes()
        assert len(themes) >= 5  # synthwave, glitch, matrix, minimal, ops
        assert "synthwave" in themes
        assert "glitch" in themes

    def test_theme_swap_produces_different_colors(self):
        t1 = load_theme("synthwave")
        t2 = load_theme("glitch")
        assert t1.colors.bg != t2.colors.bg

    def test_each_theme_has_glyph_map(self):
        for name in list_themes():
            theme = load_theme(name)
            assert isinstance(theme.glyph_map, dict)


class TestThemeFile:
    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.json"
            path.write_text("not json at all {{{")
            with pytest.raises(ThemeError, match="Invalid JSON"):
                load_theme("bad", themes_dir=Path(tmpdir))

    def test_validation_failure_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "incomplete.json"
            path.write_text(json.dumps({"colors": {}}))
            with pytest.raises(ThemeError, match="validation failed"):
                load_theme("incomplete", themes_dir=Path(tmpdir))
