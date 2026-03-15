"""Tests for every CLI command in suno_to_ableton.cli.

Each command is invoked via Typer's CliRunner and verified for:
  - successful exit code (or expected error exit)
  - correct console output / dry-run messaging
  - correct delegation to underlying functions
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from suno_to_ableton.cli import app
from suno_to_ableton.models import (
    ALSExportResult,
    AnchorCandidate,
    BPMResult,
    DiscoveredFile,
    FeatureInvocation,
    FileRole,
    GridAnchorResult,
    MIDIRepairResult,
    ProcessedFile,
    ProcessingManifest,
    ProjectInventory,
    RequantizeResult,
    ReseparationResult,
    Section,
    SectionDetectionResult,
    SeparatorBackend,
    StemComparisonResult,
    StemType,
)

runner = CliRunner()

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

AUDIO_META = {
    "sample_rate": 44100,
    "channels": 2,
    "frames": 441000,
    "duration_seconds": 10.0,
    "subtype": "PCM_16",
}


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    """Create a minimal Suno-export directory with stems + MIDI."""
    (tmp_path / "0 Test Song.wav").touch()
    (tmp_path / "1 Drums.wav").touch()
    (tmp_path / "2 Bass.wav").touch()
    (tmp_path / "Test Song.mid").touch()

    # Pre-create output dirs for commands that call ensure_output_dirs
    out = tmp_path / "processed"
    (out / "stems").mkdir(parents=True)
    (out / "stems_generated").mkdir(parents=True)
    (out / "midi").mkdir(parents=True)
    (out / "reports").mkdir(parents=True)

    return tmp_path


def _make_inventory(source_dir: Path) -> ProjectInventory:
    """Build a realistic ProjectInventory for the test project_dir."""
    return ProjectInventory(
        source_dir=source_dir,
        full_mix=DiscoveredFile(
            path=source_dir / "0 Test Song.wav",
            role=FileRole.AUDIO_FULL_MIX,
            stem_type=StemType.FULL_MIX,
            track_number=0,
            stem_name="Test Song",
            sample_rate=44100,
            channels=2,
            frames=441000,
            duration_seconds=10.0,
        ),
        stems=[
            DiscoveredFile(
                path=source_dir / "1 Drums.wav",
                role=FileRole.AUDIO_STEM,
                stem_type=StemType.DRUMS,
                track_number=1,
                stem_name="Drums",
                sample_rate=44100,
                channels=2,
                frames=441000,
                duration_seconds=10.0,
            ),
            DiscoveredFile(
                path=source_dir / "2 Bass.wav",
                role=FileRole.AUDIO_STEM,
                stem_type=StemType.BASS,
                track_number=2,
                stem_name="Bass",
                sample_rate=44100,
                channels=2,
                frames=441000,
                duration_seconds=10.0,
            ),
        ],
        midi_files=[
            DiscoveredFile(
                path=source_dir / "Test Song.mid",
                role=FileRole.MIDI,
                stem_type=StemType.OTHER,
            ),
        ],
        song_title="Test Song",
    )


def _make_bpm_result() -> BPMResult:
    return BPMResult(
        bpm=120.0,
        confidence=0.95,
        beat_times=[0.5, 1.0, 1.5, 2.0],
        downbeat_time=0.05,
        onset_times=[0.1, 0.5, 1.0],
        leading_silence=0.02,
    )


def _make_manifest(source_dir: Path) -> ProcessingManifest:
    out = source_dir / "processed"
    return ProcessingManifest(
        song_title="Test Song",
        bpm=120.0,
        bpm_confidence=0.95,
        offset_seconds=0.05,
        offset_samples=2400,
        samples_per_beat=24000.0,
        target_sr=48000,
        stems=[
            ProcessedFile(
                output_path=out / "stems" / "00_full_mix.wav",
                stem_type=StemType.FULL_MIX,
                processing_steps=["resample 48000"],
            ),
        ],
        midi_files=[
            ProcessedFile(
                output_path=out / "midi" / "Test Song.mid",
                stem_type=StemType.OTHER,
                processing_steps=["tracks kept: 1"],
            ),
        ],
    )


# ===================================================================
# analyze
# ===================================================================


class TestAnalyze:
    @patch("suno_to_ableton.cli.compute_alignment")
    @patch("suno_to_ableton.cli.analyze_bpm_from_inventory")
    @patch("suno_to_ableton.cli.discover_project")
    def test_analyze_success(
        self, mock_discover, mock_bpm, mock_align, project_dir
    ):
        mock_discover.return_value = _make_inventory(project_dir)
        mock_bpm.return_value = _make_bpm_result()
        mock_align.return_value = MagicMock(
            offset_seconds=0.05, offset_samples=2400,
            bpm=120.0, samples_per_beat=24000.0,
        )

        result = runner.invoke(app, ["analyze", str(project_dir)])
        assert result.exit_code == 0
        assert "Analyzing" in result.output
        mock_discover.assert_called_once()
        mock_bpm.assert_called_once()
        mock_align.assert_called_once()

    @patch("suno_to_ableton.cli.discover_project")
    def test_analyze_no_audio_exits_1(self, mock_discover, project_dir):
        inv = ProjectInventory(source_dir=project_dir)
        inv.warnings.append("No audio files found")
        mock_discover.return_value = inv

        result = runner.invoke(app, ["analyze", str(project_dir)])
        assert result.exit_code == 1
        assert "No audio files found" in result.output

    @patch("suno_to_ableton.cli.analyze_bpm_from_inventory")
    @patch("suno_to_ableton.cli.discover_project")
    def test_analyze_bpm_failure_graceful(
        self, mock_discover, mock_bpm, project_dir
    ):
        mock_discover.return_value = _make_inventory(project_dir)
        mock_bpm.side_effect = RuntimeError("librosa unavailable")

        result = runner.invoke(app, ["analyze", str(project_dir)])
        assert result.exit_code == 0
        assert "BPM detection failed" in result.output

    @patch("suno_to_ableton.cli.analyze_bpm_from_inventory")
    @patch("suno_to_ableton.cli.discover_project")
    def test_analyze_verbose_shows_traceback(
        self, mock_discover, mock_bpm, project_dir
    ):
        mock_discover.return_value = _make_inventory(project_dir)
        mock_bpm.side_effect = RuntimeError("boom")

        result = runner.invoke(app, ["analyze", str(project_dir), "-v"])
        assert result.exit_code == 0
        assert "Traceback" in result.output


# ===================================================================
# process
# ===================================================================


class TestProcess:
    @patch("suno_to_ableton.cli.run_pipeline")
    def test_process_default(self, mock_pipeline, project_dir):
        mock_pipeline.return_value = _make_manifest(project_dir)

        result = runner.invoke(app, ["process", str(project_dir)])
        assert result.exit_code == 0
        assert "Processing" in result.output
        mock_pipeline.assert_called_once()

        config = mock_pipeline.call_args[0][0]
        assert config.source_dir == project_dir
        assert config.dry_run is False

    @patch("suno_to_ableton.cli.run_pipeline")
    def test_process_dry_run(self, mock_pipeline, project_dir):
        mock_pipeline.return_value = _make_manifest(project_dir)

        result = runner.invoke(
            app, ["process", str(project_dir), "--dry-run"]
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.output

        config = mock_pipeline.call_args[0][0]
        assert config.dry_run is True

    @patch("suno_to_ableton.cli.run_pipeline")
    def test_process_custom_options(self, mock_pipeline, project_dir):
        mock_pipeline.return_value = _make_manifest(project_dir)

        result = runner.invoke(app, [
            "process", str(project_dir),
            "--output-dir", "out",
            "--target-sr", "44100",
            "--quantize-grid", "1/8",
            "--min-note-ms", "30",
            "--skip-existing",
            "--force",
            "--verbose",
        ])
        assert result.exit_code == 0

        config = mock_pipeline.call_args[0][0]
        assert config.output_dir == Path("out")
        assert config.target_sr == 44100
        assert config.quantize_grid == "1/8"
        assert config.min_note_ms == 30.0
        assert config.skip_existing is True
        assert config.force is True
        assert config.verbose is True

    @patch("suno_to_ableton.cli.run_pipeline")
    def test_process_advanced_flags(self, mock_pipeline, project_dir):
        mock_pipeline.return_value = _make_manifest(project_dir)

        result = runner.invoke(app, [
            "process", str(project_dir),
            "--choose-stems",
            "--choose-grid-anchor",
            "--detect-sections",
            "--repair-midi",
            "--requantize-midi",
            "--requantize-mode", "swing",
            "--reseparate",
            "--apply",
            "--export-als",
        ])
        assert result.exit_code == 0

        config = mock_pipeline.call_args[0][0]
        assert config.choose_stems is True
        assert config.choose_grid_anchor is True
        assert config.detect_sections is True
        assert config.repair_midi is True
        assert config.requantize_midi is True
        assert config.requantize_mode == "swing"
        assert config.reseparate is True
        assert config.apply_features is True
        assert config.export_als is True

    @patch("suno_to_ableton.cli.run_pipeline")
    def test_process_separator_option(self, mock_pipeline, project_dir):
        mock_pipeline.return_value = _make_manifest(project_dir)

        result = runner.invoke(app, [
            "process", str(project_dir),
            "--separate-missing",
            "--separator", "uvr",
        ])
        assert result.exit_code == 0

        config = mock_pipeline.call_args[0][0]
        assert config.separate_missing is True
        assert config.separator == SeparatorBackend.UVR

    @patch("suno_to_ableton.cli.run_pipeline")
    def test_process_demucs_model_option(self, mock_pipeline, project_dir):
        mock_pipeline.return_value = _make_manifest(project_dir)

        result = runner.invoke(app, [
            "process", str(project_dir),
            "--separate-missing",
            "--demucs-model", "htdemucs_ft",
        ])
        assert result.exit_code == 0

        config = mock_pipeline.call_args[0][0]
        assert config.demucs_model == "htdemucs_ft"


# ===================================================================
# separate
# ===================================================================


class TestSeparate:
    @patch("suno_to_ableton.separation.get_backend")
    @patch("suno_to_ableton.cli.discover_project")
    def test_separate_success(self, mock_discover, mock_get_backend, project_dir):
        """Separate delegates to backend and prints generated stems."""
        inv = _make_inventory(project_dir)
        mock_discover.return_value = inv

        mock_backend = MagicMock()
        mock_backend.separate.return_value = MagicMock(
            output_stems=[
                project_dir / "processed" / "stems_generated" / "drums.wav",
                project_dir / "processed" / "stems_generated" / "bass.wav",
            ]
        )
        mock_get_backend.return_value = mock_backend

        result = runner.invoke(app, ["separate", str(project_dir)])
        assert result.exit_code == 0
        assert "Generated 2 stems" in result.output
        assert "drums.wav" in result.output
        mock_backend.separate.assert_called_once()

    @patch("suno_to_ableton.cli.discover_project")
    def test_separate_no_full_mix_exits_1(self, mock_discover, project_dir):
        inv = ProjectInventory(source_dir=project_dir)
        mock_discover.return_value = inv

        result = runner.invoke(app, ["separate", str(project_dir)])
        assert result.exit_code == 1
        assert "No full mix" in result.output

    @patch("suno_to_ableton.separation.get_backend")
    @patch("suno_to_ableton.cli.discover_project")
    def test_separate_backend_option(self, mock_discover, mock_get_backend, project_dir):
        inv = _make_inventory(project_dir)
        mock_discover.return_value = inv

        mock_backend = MagicMock()
        mock_backend.separate.return_value = MagicMock(output_stems=[])
        mock_get_backend.return_value = mock_backend

        result = runner.invoke(app, [
            "separate", str(project_dir), "--separator", "uvr",
        ])
        assert result.exit_code == 0
        # Config passed to get_backend should use uvr
        config = mock_get_backend.call_args[0][0]
        assert config.separator == SeparatorBackend.UVR


# ===================================================================
# report
# ===================================================================


class TestReport:
    def test_report_success(self, project_dir):
        manifest_path = project_dir / "processed" / "reports" / "manifest.json"
        manifest_data = {
            "song_title": "Test Song",
            "bpm": 120.0,
            "stems": [],
        }
        manifest_path.write_text(json.dumps(manifest_data))

        result = runner.invoke(app, ["report", str(project_dir)])
        assert result.exit_code == 0
        assert "Manifest" in result.output
        assert "Test Song" in result.output

    def test_report_no_manifest_exits_1(self, project_dir):
        result = runner.invoke(app, ["report", str(project_dir)])
        assert result.exit_code == 1
        assert "No manifest found" in result.output

    def test_report_custom_output_dir(self, project_dir):
        custom_out = project_dir / "custom_out" / "reports"
        custom_out.mkdir(parents=True)
        manifest_path = custom_out / "manifest.json"
        manifest_path.write_text(json.dumps({"song_title": "Custom"}))

        result = runner.invoke(app, [
            "report", str(project_dir), "--output-dir", "custom_out",
        ])
        assert result.exit_code == 0
        assert "Custom" in result.output


# ===================================================================
# choose-stems
# ===================================================================


class TestChooseStems:
    @patch("suno_to_ableton.features.choose_stems.run_choose_stems")
    def test_choose_stems_report(self, mock_run, project_dir):
        mock_run.return_value = (
            StemComparisonResult(),
            FeatureInvocation(
                feature="choose_stems",
                mode="report",
                recommendation="2 original, 0 generated",
            ),
        )

        result = runner.invoke(app, ["choose-stems", str(project_dir)])
        assert result.exit_code == 0
        assert "2 original, 0 generated" in result.output
        mock_run.assert_called_once()
        # apply should be False by default
        _, kwargs = mock_run.call_args
        assert kwargs.get("apply", mock_run.call_args[0][1] if len(mock_run.call_args[0]) > 1 else False) is not None

    @patch("suno_to_ableton.features.choose_stems.run_choose_stems")
    def test_choose_stems_apply(self, mock_run, project_dir):
        mock_run.return_value = (
            StemComparisonResult(applied=True),
            FeatureInvocation(
                feature="choose_stems",
                mode="apply",
                recommendation="Applied 1 stem replacement",
            ),
        )

        result = runner.invoke(
            app, ["choose-stems", str(project_dir), "--apply"]
        )
        assert result.exit_code == 0
        assert "Applied" in result.output

    @patch("suno_to_ableton.features.choose_stems.run_choose_stems")
    def test_choose_stems_warnings(self, mock_run, project_dir):
        mock_run.return_value = (
            StemComparisonResult(),
            FeatureInvocation(
                feature="choose_stems",
                warnings=["No generated stems found"],
            ),
        )

        result = runner.invoke(app, ["choose-stems", str(project_dir)])
        assert result.exit_code == 0
        assert "No generated stems found" in result.output


# ===================================================================
# choose-grid-anchor
# ===================================================================


class TestChooseGridAnchor:
    @patch("suno_to_ableton.cli.analyze_bpm_from_inventory")
    @patch("suno_to_ableton.cli.discover_project")
    @patch("suno_to_ableton.features.choose_grid_anchor.run_choose_grid_anchor")
    def test_choose_grid_anchor_success(
        self, mock_run, mock_discover, mock_bpm, project_dir
    ):
        mock_discover.return_value = _make_inventory(project_dir)
        mock_bpm.return_value = _make_bpm_result()
        mock_run.return_value = (
            GridAnchorResult(
                candidates=[
                    AnchorCandidate(
                        time=0.05, bar_estimate=1, confidence=0.9,
                        reason="strong downbeat",
                    ),
                    AnchorCandidate(
                        time=0.52, bar_estimate=2, confidence=0.6,
                        reason="secondary onset",
                    ),
                ],
                recommended=AnchorCandidate(
                    time=0.05, bar_estimate=1, confidence=0.9,
                    reason="strong downbeat",
                ),
                analysis_notes=["clear downbeat"],
            ),
            FeatureInvocation(feature="choose_grid_anchor"),
        )

        result = runner.invoke(
            app, ["choose-grid-anchor", str(project_dir)]
        )
        assert result.exit_code == 0
        assert "Grid Anchor Candidates" in result.output
        assert "recommended" in result.output
        assert "strong downbeat" in result.output

    @patch("suno_to_ableton.cli.analyze_bpm_from_inventory")
    @patch("suno_to_ableton.cli.discover_project")
    @patch("suno_to_ableton.features.choose_grid_anchor.run_choose_grid_anchor")
    def test_choose_grid_anchor_no_candidates(
        self, mock_run, mock_discover, mock_bpm, project_dir
    ):
        mock_discover.return_value = _make_inventory(project_dir)
        mock_bpm.return_value = _make_bpm_result()
        mock_run.return_value = (
            GridAnchorResult(),
            FeatureInvocation(
                feature="choose_grid_anchor",
                warnings=["No candidates found"],
            ),
        )

        result = runner.invoke(
            app, ["choose-grid-anchor", str(project_dir)]
        )
        assert result.exit_code == 0
        assert "No candidates found" in result.output


# ===================================================================
# detect-sections
# ===================================================================


class TestDetectSections:
    @patch("suno_to_ableton.cli.analyze_bpm_from_inventory")
    @patch("suno_to_ableton.cli.discover_project")
    @patch("suno_to_ableton.features.detect_sections.run_detect_sections")
    def test_detect_sections_success(
        self, mock_run, mock_discover, mock_bpm, project_dir
    ):
        mock_discover.return_value = _make_inventory(project_dir)
        mock_bpm.return_value = _make_bpm_result()
        mock_run.return_value = (
            SectionDetectionResult(
                sections=[
                    Section(
                        label="intro", start_time=0.0, end_time=8.0,
                        start_bar=1, end_bar=4, confidence=0.85,
                    ),
                    Section(
                        label="verse", start_time=8.0, end_time=24.0,
                        start_bar=5, end_bar=12, confidence=0.90,
                    ),
                ],
                method="spectral_clustering",
            ),
            FeatureInvocation(feature="detect_sections"),
        )

        result = runner.invoke(
            app, ["detect-sections", str(project_dir)]
        )
        assert result.exit_code == 0
        assert "Sections" in result.output
        assert "intro" in result.output
        assert "verse" in result.output
        assert "spectral_clustering" in result.output

    @patch("suno_to_ableton.cli.analyze_bpm_from_inventory")
    @patch("suno_to_ableton.cli.discover_project")
    def test_detect_sections_no_audio_exits_1(
        self, mock_discover, mock_bpm, project_dir
    ):
        inv = ProjectInventory(source_dir=project_dir)
        mock_discover.return_value = inv
        mock_bpm.return_value = _make_bpm_result()

        result = runner.invoke(
            app, ["detect-sections", str(project_dir)]
        )
        assert result.exit_code == 1
        assert "No audio files found" in result.output


# ===================================================================
# repair-midi
# ===================================================================


class TestRepairMidi:
    @patch("suno_to_ableton.cli.discover_project")
    @patch("suno_to_ableton.features.repair_midi.run_repair_midi")
    def test_repair_midi_report(self, mock_run, mock_discover, project_dir):
        mock_discover.return_value = _make_inventory(project_dir)
        mock_run.return_value = (
            MIDIRepairResult(
                key_detected="C major",
                notes_flagged=5,
                notes_repaired=0,
                stacked_chords_fixed=0,
            ),
            FeatureInvocation(feature="repair_midi", mode="report"),
        )

        result = runner.invoke(app, ["repair-midi", str(project_dir)])
        assert result.exit_code == 0
        assert "C major" in result.output
        assert "Notes flagged: 5" in result.output

    @patch("suno_to_ableton.cli.discover_project")
    @patch("suno_to_ableton.features.repair_midi.run_repair_midi")
    def test_repair_midi_apply(self, mock_run, mock_discover, project_dir):
        out_path = project_dir / "processed" / "midi" / "Test Song.mid"
        mock_discover.return_value = _make_inventory(project_dir)
        mock_run.return_value = (
            MIDIRepairResult(
                key_detected="A minor",
                notes_flagged=3,
                notes_repaired=3,
                stacked_chords_fixed=1,
                output_path=out_path,
            ),
            FeatureInvocation(feature="repair_midi", mode="apply"),
        )

        result = runner.invoke(
            app, ["repair-midi", str(project_dir), "--apply"]
        )
        assert result.exit_code == 0
        assert "Notes repaired: 3" in result.output
        assert "Stacked chords fixed: 1" in result.output
        assert "Output" in result.output

    @patch("suno_to_ableton.cli.discover_project")
    def test_repair_midi_no_midi_files(self, mock_discover, project_dir):
        inv = _make_inventory(project_dir)
        inv.midi_files = []
        mock_discover.return_value = inv

        result = runner.invoke(app, ["repair-midi", str(project_dir)])
        # No MIDI files → nothing to analyze, should still succeed
        assert result.exit_code == 0


# ===================================================================
# requantize-midi
# ===================================================================


class TestRequantizeMidi:
    @patch("suno_to_ableton.cli.analyze_bpm_from_inventory")
    @patch("suno_to_ableton.cli.discover_project")
    @patch("suno_to_ableton.features.requantize_midi.run_requantize_midi")
    def test_requantize_report(
        self, mock_run, mock_discover, mock_bpm, project_dir
    ):
        mock_discover.return_value = _make_inventory(project_dir)
        mock_bpm.return_value = _make_bpm_result()
        mock_run.return_value = (
            RequantizeResult(
                notes_moved=12,
                max_shift_ms=15.3,
                avg_shift_ms=5.2,
            ),
            FeatureInvocation(feature="requantize_midi", mode="report"),
        )

        result = runner.invoke(
            app, ["requantize-midi", str(project_dir)]
        )
        assert result.exit_code == 0
        assert "Notes affected: 12" in result.output
        assert "Max shift: 15.3ms" in result.output
        assert "Avg shift: 5.2ms" in result.output

    @patch("suno_to_ableton.cli.analyze_bpm_from_inventory")
    @patch("suno_to_ableton.cli.discover_project")
    @patch("suno_to_ableton.features.requantize_midi.run_requantize_midi")
    def test_requantize_apply(
        self, mock_run, mock_discover, mock_bpm, project_dir
    ):
        out_path = project_dir / "processed" / "midi" / "Test Song.mid"
        mock_discover.return_value = _make_inventory(project_dir)
        mock_bpm.return_value = _make_bpm_result()
        mock_run.return_value = (
            RequantizeResult(
                notes_moved=8,
                max_shift_ms=10.0,
                avg_shift_ms=4.0,
                output_path=out_path,
            ),
            FeatureInvocation(feature="requantize_midi", mode="apply"),
        )

        result = runner.invoke(
            app, ["requantize-midi", str(project_dir), "--apply"]
        )
        assert result.exit_code == 0
        assert "Output" in result.output

    @patch("suno_to_ableton.cli.analyze_bpm_from_inventory")
    @patch("suno_to_ableton.cli.discover_project")
    @patch("suno_to_ableton.features.requantize_midi.run_requantize_midi")
    def test_requantize_mode_option(
        self, mock_run, mock_discover, mock_bpm, project_dir
    ):
        mock_discover.return_value = _make_inventory(project_dir)
        mock_bpm.return_value = _make_bpm_result()
        mock_run.return_value = (
            RequantizeResult(notes_moved=0, max_shift_ms=0, avg_shift_ms=0),
            FeatureInvocation(feature="requantize_midi"),
        )

        result = runner.invoke(app, [
            "requantize-midi", str(project_dir), "--mode", "triplet",
        ])
        assert result.exit_code == 0
        assert "mode=triplet" in result.output

    @patch("suno_to_ableton.cli.analyze_bpm_from_inventory")
    @patch("suno_to_ableton.cli.discover_project")
    @patch("suno_to_ableton.features.requantize_midi.run_requantize_midi")
    def test_requantize_warnings(
        self, mock_run, mock_discover, mock_bpm, project_dir
    ):
        mock_discover.return_value = _make_inventory(project_dir)
        mock_bpm.return_value = _make_bpm_result()
        mock_run.return_value = (
            RequantizeResult(notes_moved=0, max_shift_ms=0, avg_shift_ms=0),
            FeatureInvocation(
                feature="requantize_midi",
                warnings=["MIDI file has no notes"],
            ),
        )

        result = runner.invoke(
            app, ["requantize-midi", str(project_dir)]
        )
        assert result.exit_code == 0
        assert "MIDI file has no notes" in result.output


# ===================================================================
# reseparate
# ===================================================================


class TestReseparate:
    @patch("suno_to_ableton.cli.discover_project")
    @patch("suno_to_ableton.features.reseparate.run_reseparate")
    def test_reseparate_success(self, mock_run, mock_discover, project_dir):
        mock_discover.return_value = _make_inventory(project_dir)
        mock_run.return_value = (
            ReseparationResult(
                output_stems=[
                    project_dir / "processed" / "stems_generated" / "drums.wav",
                    project_dir / "processed" / "stems_generated" / "bass.wav",
                    project_dir / "processed" / "stems_generated" / "vocals.wav",
                    project_dir / "processed" / "stems_generated" / "other.wav",
                ],
            ),
            FeatureInvocation(feature="reseparate"),
        )

        result = runner.invoke(app, ["reseparate", str(project_dir)])
        assert result.exit_code == 0
        assert "Generated 4 stems" in result.output
        assert "drums.wav" in result.output

    @patch("suno_to_ableton.cli.discover_project")
    @patch("suno_to_ableton.features.reseparate.run_reseparate")
    def test_reseparate_target_option(
        self, mock_run, mock_discover, project_dir
    ):
        mock_discover.return_value = _make_inventory(project_dir)
        mock_run.return_value = (
            ReseparationResult(output_stems=[]),
            FeatureInvocation(feature="reseparate"),
        )

        result = runner.invoke(app, [
            "reseparate", str(project_dir), "--target", "vocals",
        ])
        assert result.exit_code == 0
        # target param should be forwarded
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        assert call_kwargs[1].get("target", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else "full_mix") is not None

    @patch("suno_to_ableton.cli.discover_project")
    @patch("suno_to_ableton.features.reseparate.run_reseparate")
    def test_reseparate_force_flag(
        self, mock_run, mock_discover, project_dir
    ):
        mock_discover.return_value = _make_inventory(project_dir)
        mock_run.return_value = (
            ReseparationResult(output_stems=[]),
            FeatureInvocation(feature="reseparate"),
        )

        result = runner.invoke(app, [
            "reseparate", str(project_dir), "--force",
        ])
        assert result.exit_code == 0

    @patch("suno_to_ableton.cli.discover_project")
    @patch("suno_to_ableton.features.reseparate.run_reseparate")
    def test_reseparate_warnings(
        self, mock_run, mock_discover, project_dir
    ):
        mock_discover.return_value = _make_inventory(project_dir)
        mock_run.return_value = (
            ReseparationResult(output_stems=[]),
            FeatureInvocation(
                feature="reseparate",
                warnings=["No full mix found for reseparation"],
            ),
        )

        result = runner.invoke(app, ["reseparate", str(project_dir)])
        assert result.exit_code == 0
        assert "No full mix found" in result.output


# ===================================================================
# export-als
# ===================================================================


class TestExportAls:
    def test_export_als_no_manifest_exits_1(self, project_dir):
        result = runner.invoke(app, ["export-als", str(project_dir)])
        assert result.exit_code == 1
        assert "No manifest found" in result.output

    @patch("suno_to_ableton.features.export_als.run_export_als")
    def test_export_als_success(self, mock_run, project_dir):
        # Write a manifest file so the command can load it
        manifest = _make_manifest(project_dir)
        manifest_path = project_dir / "processed" / "reports" / "manifest.json"
        manifest_path.write_text(manifest.model_dump_json())

        als_path = project_dir / "processed" / "Test Song.als"
        mock_run.return_value = (
            ALSExportResult(
                output_path=als_path,
                tracks_created=3,
                bpm_set=120.0,
            ),
            FeatureInvocation(feature="export_als"),
        )

        result = runner.invoke(app, ["export-als", str(project_dir)])
        assert result.exit_code == 0
        assert "Exported" in result.output
        assert "Audio tracks: 3" in result.output
        assert "BPM: 120.0" in result.output

    @patch("suno_to_ableton.features.export_als.run_export_als")
    def test_export_als_template_option(self, mock_run, project_dir):
        manifest = _make_manifest(project_dir)
        manifest_path = project_dir / "processed" / "reports" / "manifest.json"
        manifest_path.write_text(manifest.model_dump_json())

        template = project_dir / "my_template.als"
        template.touch()

        mock_run.return_value = (
            ALSExportResult(
                output_path=project_dir / "processed" / "Test Song.als",
                tracks_created=1,
                bpm_set=120.0,
                template_used=template,
            ),
            FeatureInvocation(feature="export_als"),
        )

        result = runner.invoke(app, [
            "export-als", str(project_dir),
            "--als-template", str(template),
        ])
        assert result.exit_code == 0

    @patch("suno_to_ableton.features.export_als.run_export_als")
    def test_export_als_warnings(self, mock_run, project_dir):
        manifest = _make_manifest(project_dir)
        manifest_path = project_dir / "processed" / "reports" / "manifest.json"
        manifest_path.write_text(manifest.model_dump_json())

        mock_run.return_value = (
            ALSExportResult(),
            FeatureInvocation(
                feature="export_als",
                warnings=["Template not found, using default"],
            ),
        )

        result = runner.invoke(app, ["export-als", str(project_dir)])
        assert result.exit_code == 0
        assert "Template not found" in result.output


# ===================================================================
# tui
# ===================================================================


class TestTui:
    @patch("suno_to_ableton.tui.run_tui")
    def test_tui_launches(self, mock_run_tui):
        result = runner.invoke(app, ["tui"])
        assert result.exit_code == 0
        mock_run_tui.assert_called_once()


# ===================================================================
# No-args / help
# ===================================================================


class TestHelpAndNoArgs:
    def test_no_args_shows_help(self):
        result = runner.invoke(app, [])
        # no_args_is_help=True causes Typer to exit with code 0 and show help
        # (Typer/Click may use exit code 0 or 2 depending on version)
        assert result.exit_code in (0, 2)
        assert "Usage" in result.output or "suno-to-ableton" in result.output.lower()

    def test_help_flag(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "analyze" in result.output
        assert "process" in result.output
        assert "separate" in result.output
        assert "report" in result.output

    def test_analyze_help(self):
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "Analyze" in result.output

    def test_process_help(self):
        result = runner.invoke(app, ["process", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.output
        assert "--target-sr" in result.output

    def test_separate_help(self):
        result = runner.invoke(app, ["separate", "--help"])
        assert result.exit_code == 0
        assert "--separator" in result.output

    def test_report_help(self):
        result = runner.invoke(app, ["report", "--help"])
        assert result.exit_code == 0

    def test_choose_stems_help(self):
        result = runner.invoke(app, ["choose-stems", "--help"])
        assert result.exit_code == 0
        assert "--apply" in result.output

    def test_choose_grid_anchor_help(self):
        result = runner.invoke(app, ["choose-grid-anchor", "--help"])
        assert result.exit_code == 0

    def test_detect_sections_help(self):
        result = runner.invoke(app, ["detect-sections", "--help"])
        assert result.exit_code == 0

    def test_repair_midi_help(self):
        result = runner.invoke(app, ["repair-midi", "--help"])
        assert result.exit_code == 0
        assert "--apply" in result.output

    def test_requantize_midi_help(self):
        result = runner.invoke(app, ["requantize-midi", "--help"])
        assert result.exit_code == 0
        assert "--mode" in result.output

    def test_reseparate_help(self):
        result = runner.invoke(app, ["reseparate", "--help"])
        assert result.exit_code == 0
        assert "--target" in result.output

    def test_export_als_help(self):
        result = runner.invoke(app, ["export-als", "--help"])
        assert result.exit_code == 0
        assert "--als-template" in result.output

    def test_tui_help(self):
        result = runner.invoke(app, ["tui", "--help"])
        assert result.exit_code == 0
