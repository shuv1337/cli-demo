"""Tests for timing presets."""

import pytest

from demo_engine.presets import Preset, get_preset, list_presets, PRESETS


class TestPresetDefinitions:
    def test_all_presets_exist(self):
        assert "short" in PRESETS
        assert "standard" in PRESETS
        assert "cinematic" in PRESETS

    def test_list_presets(self):
        names = list_presets()
        assert len(names) == 3
        assert "short" in names

    def test_get_preset(self):
        p = get_preset("short")
        assert isinstance(p, Preset)
        assert p.name == "short"

    def test_get_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown preset"):
            get_preset("nonexistent")


class TestPresetTiming:
    def test_short_is_fastest(self):
        short = get_preset("short")
        standard = get_preset("standard")
        cinematic = get_preset("cinematic")

        assert short.line_hold_ms < standard.line_hold_ms
        assert standard.line_hold_ms < cinematic.line_hold_ms

    def test_short_target_range(self):
        p = get_preset("short")
        assert p.target_min_s == 8.0
        assert p.target_max_s == 15.0
        assert p.target_min_ms == 8000.0

    def test_standard_target_range(self):
        p = get_preset("standard")
        assert p.target_min_s == 20.0
        assert p.target_max_s == 30.0

    def test_cinematic_target_range(self):
        p = get_preset("cinematic")
        assert p.target_min_s == 35.0
        assert p.target_max_s == 60.0

    def test_fps_reasonable(self):
        for name in list_presets():
            p = get_preset(name)
            assert 20 <= p.fps <= 60

    def test_effect_scale_ordering(self):
        short = get_preset("short")
        standard = get_preset("standard")
        cinematic = get_preset("cinematic")

        assert short.effect_scale <= standard.effect_scale
        assert standard.effect_scale <= cinematic.effect_scale


class TestPresetConsistency:
    def test_all_fields_positive(self):
        """All timing values should be positive."""
        for name in list_presets():
            p = get_preset(name)
            assert p.line_hold_ms > 0
            assert p.command_hold_ms > 0
            assert p.spinner_cycle_ms > 0
            assert p.progress_step_ms > 0
            assert p.intro_hold_ms > 0
            assert p.outro_hold_ms > 0

    def test_intro_shorter_than_outro(self):
        """Outro should generally hold longer than intro."""
        for name in list_presets():
            p = get_preset(name)
            assert p.outro_hold_ms >= p.intro_hold_ms

    def test_spinner_cycles_reasonable(self):
        for name in list_presets():
            p = get_preset(name)
            assert 5 <= p.spinner_cycles <= 50
