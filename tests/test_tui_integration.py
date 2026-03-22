"""Integration test: walk through the TUI with mock project data end-to-end."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from suno_to_ableton.config import SunoPrepConfig
from suno_to_ableton.models import (
    ProcessedFile,
    ProcessingManifest,
    StemType,
)
from suno_to_ableton.tui import SunoPrepTUI


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    """Create a fake Suno export directory with numbered stems and MIDI."""
    project = tmp_path / "test_song"
    project.mkdir()
    (project / "0 Test Song.wav").touch()
    (project / "1 Drums.wav").touch()
    (project / "2 Bass.wav").touch()
    (project / "3 Vocals.wav").touch()
    (project / "Test Song.mid").touch()

    # Create output dirs so pipeline can "write" to them
    out = project / "processed"
    (out / "stems").mkdir(parents=True)
    (out / "midi").mkdir(parents=True)
    (out / "reports").mkdir(parents=True)

    return project


def _make_manifest(project_dir: Path) -> ProcessingManifest:
    """Build a realistic ProcessingManifest for test assertions."""
    out = project_dir / "processed"
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
                processing_steps=["resample 48000", "trim 0.05s"],
            ),
            ProcessedFile(
                output_path=out / "stems" / "01_drums.wav",
                stem_type=StemType.DRUMS,
                processing_steps=["resample 48000", "trim 0.05s"],
            ),
            ProcessedFile(
                output_path=out / "stems" / "02_bass.wav",
                stem_type=StemType.BASS,
                processing_steps=["resample 48000"],
            ),
            ProcessedFile(
                output_path=out / "stems" / "03_vocals.wav",
                stem_type=StemType.VOCALS,
                processing_steps=["resample 48000"],
            ),
        ],
        midi_files=[
            ProcessedFile(
                output_path=out / "midi" / "Test Song.mid",
                stem_type=StemType.OTHER,
                processing_steps=[
                    "tracks kept: 1",
                    "tracks removed: 0",
                    "short notes removed: 2",
                    "notes quantized: 45",
                    "tempo set: 120.0",
                    "offset applied: 0.0500s",
                ],
            ),
        ],
        warnings=[],
    )


AUDIO_META = {
    "sample_rate": 44100,
    "channels": 2,
    "frames": 441000,
    "duration_seconds": 10.0,
    "subtype": "PCM_16",
}


@pytest.mark.asyncio
async def test_tui_full_walkthrough(project_dir: Path):
    """Scan a project, hit Process, and verify we reach completion."""

    manifest = _make_manifest(project_dir)

    def mock_run_pipeline(config: SunoPrepConfig, on_progress=None):
        """Simulate pipeline execution with progress callbacks."""
        from suno_to_ableton.progress import StepStatus

        steps = [
            ("discovery", StepStatus.DONE, "4 audio, 1 MIDI"),
            ("output_dirs", StepStatus.DONE, ""),
            ("bpm", StepStatus.DONE, "120.0 BPM"),
            ("alignment", StepStatus.DONE, "offset 0.05s"),
            ("audio", StepStatus.DONE, "4 files"),
            ("midi", StepStatus.DONE, "1 file"),
            ("separation", StepStatus.SKIPPED, "Not requested"),
            ("advanced", StepStatus.DONE, ""),
            ("reports", StepStatus.DONE, ""),
        ]
        if on_progress:
            for key, status, detail in steps:
                on_progress(key, status, detail)
        return manifest

    with (
        patch(
            "suno_to_ableton.discovery._probe_audio",
            return_value=AUDIO_META,
        ),
        patch(
            "suno_to_ableton.pipeline.run_pipeline",
            side_effect=mock_run_pipeline,
        ),
        patch(
            "suno_to_ableton.pipeline.write_manifest",
            return_value=project_dir / "processed" / "reports" / "manifest.json",
        ),
    ):
        app = SunoPrepTUI()

        async with app.run_test(size=(120, 40)) as pilot:
            # Step 1: Set the source directory
            source_input = app.query_one("#source-dir")
            source_input.value = str(project_dir)

            # Step 2: Scan the project (click the Scan button)
            await pilot.click("#scan")
            await pilot.pause(0.5)

            # Verify inventory populated
            inventory_table = app.query_one("#inventory")
            assert inventory_table.row_count > 0, "Inventory table should have rows after scan"

            # Verify Process button is now enabled
            process_btn = app.query_one("#process")
            assert not process_btn.disabled, "Process button should be enabled after scan"

            # Step 3: Click Process to start the pipeline
            await pilot.click("#process")
            await pilot.pause(1.0)

            # We should now be on the ProcessingScreen
            from suno_to_ableton.tui import ProcessingScreen
            proc_screen = app.screen
            assert isinstance(proc_screen, ProcessingScreen), (
                f"Expected ProcessingScreen, got {type(proc_screen).__name__}"
            )

            # Wait for the pipeline worker to complete
            await pilot.pause(1.0)

            # Verify step table has rows
            step_table = proc_screen.query_one("#step-table")
            assert step_table.row_count > 0, "Step table should have rows"

            # Verify pipeline finished
            assert proc_screen._finished, "Pipeline should have finished"

            # Verify output dir was captured by the screen
            assert proc_screen._output_dir is not None, (
                "ProcessingScreen should have captured the output directory"
            )

            # Step 4: Dismiss the processing screen (press Enter)
            await pilot.press("enter")
            await pilot.pause(0.5)


@pytest.mark.asyncio
async def test_tui_scan_populates_inventory(project_dir: Path):
    """Verify that scanning a project populates the inventory table correctly."""

    with patch(
        "suno_to_ableton.discovery._probe_audio",
        return_value=AUDIO_META,
    ):
        app = SunoPrepTUI()

        async with app.run_test(size=(120, 40)) as pilot:
            source_input = app.query_one("#source-dir")
            source_input.value = str(project_dir)

            await pilot.click("#scan")
            await pilot.pause(0.5)

            inventory_table = app.query_one("#inventory")
            # full mix + 3 stems + 1 MIDI = 5 rows
            assert inventory_table.row_count == 5

            # Process button should be enabled
            assert not app.query_one("#process").disabled

            # Log should show scan results
            log = app.query_one("#pipeline-log")
            log_text = log.lines
            assert any("audio" in str(line).lower() for line in log_text)


@pytest.mark.asyncio
async def test_tui_scan_empty_dir_finds_no_files(tmp_path: Path):
    """Scanning an empty directory should warn and not enable Process."""

    app = SunoPrepTUI()

    async with app.run_test(size=(120, 40)) as pilot:
        source_input = app.query_one("#source-dir")
        source_input.value = str(tmp_path)

        await pilot.click("#scan")
        await pilot.pause(0.5)

        # Process button should stay disabled
        assert app.query_one("#process").disabled


@pytest.mark.asyncio
async def test_tui_find_projects(project_dir: Path):
    """Find Projects should discover the test project in a parent directory."""

    with patch(
        "suno_to_ableton.discovery._probe_audio",
        return_value=AUDIO_META,
    ):
        app = SunoPrepTUI()

        async with app.run_test(size=(120, 40)) as pilot:
            # Point to the parent of our project dir
            source_input = app.query_one("#source-dir")
            source_input.value = str(project_dir.parent)

            await pilot.click("#find-projects")
            await pilot.pause(1.0)

            # Projects table should be visible with our test project
            projects_table = app.query_one("#projects-table")
            assert projects_table.row_count >= 1


@pytest.mark.asyncio
async def test_tui_keyboard_shortcuts(project_dir: Path):
    """F5 should trigger scan, same as clicking the Scan button."""

    with patch(
        "suno_to_ableton.discovery._probe_audio",
        return_value=AUDIO_META,
    ):
        app = SunoPrepTUI()

        async with app.run_test(size=(120, 40)) as pilot:
            source_input = app.query_one("#source-dir")
            source_input.value = str(project_dir)

            # Use F5 keyboard shortcut instead of clicking
            await pilot.press("f5")
            await pilot.pause(0.5)

            inventory_table = app.query_one("#inventory")
            assert inventory_table.row_count > 0


@pytest.mark.asyncio
async def test_tui_config_builds_correctly(project_dir: Path):
    """Verify _build_config gathers all widget values into SunoPrepConfig."""

    with patch(
        "suno_to_ableton.discovery._probe_audio",
        return_value=AUDIO_META,
    ):
        app = SunoPrepTUI()

        async with app.run_test(size=(120, 40)) as pilot:
            source_input = app.query_one("#source-dir")
            source_input.value = str(project_dir)

            # Toggle some options
            from textual.widgets import Checkbox

            dry_run_cb = app.query_one("#dry-run", Checkbox)
            dry_run_cb.value = True

            verbose_cb = app.query_one("#verbose", Checkbox)
            verbose_cb.value = True

            config = app._build_config()

            assert config.source_dir == project_dir
            assert config.dry_run is True
            assert config.verbose is True
            assert config.target_sr == 48000
            assert config.quantize_grid == "1/16"
            assert config.min_note_ms == 40.0


@pytest.mark.asyncio
async def test_processing_screen_handles_error(project_dir: Path):
    """Pipeline errors should be caught and displayed, not crash the TUI."""

    def mock_run_pipeline_error(config, on_progress=None):
        from suno_to_ableton.progress import StepStatus

        if on_progress:
            on_progress("discovery", StepStatus.RUNNING, "")
        raise RuntimeError("Simulated pipeline failure")

    with (
        patch(
            "suno_to_ableton.discovery._probe_audio",
            return_value=AUDIO_META,
        ),
        patch(
            "suno_to_ableton.pipeline.run_pipeline",
            side_effect=mock_run_pipeline_error,
        ),
    ):
        app = SunoPrepTUI()

        async with app.run_test(size=(120, 40)) as pilot:
            source_input = app.query_one("#source-dir")
            source_input.value = str(project_dir)

            await pilot.click("#scan")
            await pilot.pause(0.5)

            await pilot.click("#process")
            await pilot.pause(1.5)

            # Should still be on ProcessingScreen (not crashed)
            from suno_to_ableton.tui import ProcessingScreen

            proc_screen = app.screen
            assert isinstance(proc_screen, ProcessingScreen)

            # Pipeline should have finished (error path sets _finished)
            assert proc_screen._finished

            # Escape to dismiss
            await pilot.press("escape")
            await pilot.pause(0.3)


@pytest.mark.asyncio
async def test_processing_screen_updates_step_rows(project_dir: Path):
    """Progress callback should update the step table cells."""

    manifest = _make_manifest(project_dir)

    def mock_run_pipeline(config: SunoPrepConfig, on_progress=None):
        from suno_to_ableton.progress import StepStatus

        if on_progress:
            on_progress("discovery", StepStatus.RUNNING, "Scanning")
            on_progress("discovery", StepStatus.DONE, "4 audio, 1 MIDI")
        return manifest

    with (
        patch(
            "suno_to_ableton.discovery._probe_audio",
            return_value=AUDIO_META,
        ),
        patch(
            "suno_to_ableton.pipeline.run_pipeline",
            side_effect=mock_run_pipeline,
        ),
    ):
        app = SunoPrepTUI()

        async with app.run_test(size=(120, 40)) as pilot:
            source_input = app.query_one("#source-dir")
            source_input.value = str(project_dir)

            await pilot.click("#scan")
            await pilot.pause(0.2)
            await pilot.click("#process")
            await pilot.pause(0.8)

            from suno_to_ableton.tui import ProcessingScreen

            proc_screen = app.screen
            assert isinstance(proc_screen, ProcessingScreen)

            table = proc_screen.query_one("#step-table")
            row_key = proc_screen._step_row_keys["discovery"]

            assert str(table.get_cell(row_key, proc_screen._step_column_keys["status"])) == "[ok]"
            assert str(table.get_cell(row_key, proc_screen._step_column_keys["detail"])) == "4 audio, 1 MIDI"
