"""Tests for SunoPrepConfig."""

from fractions import Fraction
from pathlib import Path

from suno_to_ableton.config import SunoPrepConfig


class TestSunoPrepConfig:
    def test_defaults(self):
        c = SunoPrepConfig()
        assert c.dry_run is False
        assert c.verbose is False
        assert c.target_sr == 48000
        assert c.target_channels == 2
        assert c.quantize_grid == "1/16"
        assert c.min_note_ms == 40.0
        assert c.separate_missing is False
        assert c.choose_stems is False
        assert c.export_als is False

    def test_resolved_output_dir_relative(self):
        c = SunoPrepConfig(
            source_dir=Path("/home/user/project"),
            output_dir=Path("processed"),
        )
        assert c.resolved_output_dir == Path("/home/user/project/processed")

    def test_resolved_output_dir_absolute(self):
        c = SunoPrepConfig(
            source_dir=Path("/home/user/project"),
            output_dir=Path("/tmp/output"),
        )
        assert c.resolved_output_dir == Path("/tmp/output")

    def test_stems_dir(self):
        c = SunoPrepConfig(
            source_dir=Path("/project"),
            output_dir=Path("out"),
        )
        assert c.stems_dir == Path("/project/out/stems")

    def test_midi_dir(self):
        c = SunoPrepConfig(
            source_dir=Path("/project"),
            output_dir=Path("out"),
        )
        assert c.midi_dir == Path("/project/out/midi")

    def test_reports_dir(self):
        c = SunoPrepConfig(
            source_dir=Path("/project"),
            output_dir=Path("out"),
        )
        assert c.reports_dir == Path("/project/out/reports")

    def test_generated_stems_dir(self):
        c = SunoPrepConfig(
            source_dir=Path("/project"),
            output_dir=Path("out"),
        )
        assert c.generated_stems_dir == Path("/project/out/stems_generated")

    def test_quantize_fraction(self):
        c = SunoPrepConfig(quantize_grid="1/16")
        assert c.quantize_fraction == Fraction(1, 16)

        c2 = SunoPrepConfig(quantize_grid="1/8")
        assert c2.quantize_fraction == Fraction(1, 8)

    def test_ensure_output_dirs_dry_run(self, tmp_path):
        c = SunoPrepConfig(
            source_dir=tmp_path,
            output_dir=Path("out"),
            dry_run=True,
        )
        c.ensure_output_dirs()
        # Dry run should not create directories
        assert not (tmp_path / "out" / "stems").exists()

    def test_ensure_output_dirs_creates(self, tmp_path):
        c = SunoPrepConfig(
            source_dir=tmp_path,
            output_dir=Path("out"),
            dry_run=False,
        )
        c.ensure_output_dirs()
        assert (tmp_path / "out" / "stems").is_dir()
        assert (tmp_path / "out" / "midi").is_dir()
        assert (tmp_path / "out" / "reports").is_dir()
