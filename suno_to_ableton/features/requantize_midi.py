"""Musical feel-based MIDI quantization beyond the automatic pipeline's conservative cleanup."""

from __future__ import annotations

from pathlib import Path

import pretty_midi

from ..config import SunoPrepConfig
from ..models import FeatureInvocation, RequantizeResult
from ..reporting import write_json_report


def _grid_size(bpm: float, mode: str) -> float:
    """Compute grid size in seconds based on mode."""
    beat_duration = 60.0 / bpm

    if mode == "triplet":
        # 1/12 of a whole note = 1/3 of a beat
        return beat_duration / 3.0
    else:
        # 1/16 of a whole note = 1/4 of a beat
        return beat_duration / 4.0


def _snap_time(t: float, grid: float, mode: str) -> float:
    """Snap a time value to the grid based on mode."""
    if mode == "swing":
        # Swing: alternate 16th notes are pushed later
        # Standard swing ratio: 2:1 (66%)
        beat_pos = t / grid
        beat_idx = int(beat_pos)
        frac = beat_pos - beat_idx

        if beat_idx % 2 == 1:
            # Odd subdivisions get swing offset (push later by 33%)
            return (beat_idx + 0.33) * grid
        else:
            return beat_idx * grid
    else:
        # Standard snap
        return round(t / grid) * grid


def requantize_midi(
    midi_path: Path,
    output_dir: Path,
    bpm: float,
    mode: str,
    config: SunoPrepConfig,
    apply: bool = False,
) -> RequantizeResult:
    """Apply feel-based quantization to MIDI."""
    result = RequantizeResult(input_path=midi_path, mode=mode)

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    grid = _grid_size(bpm, mode)

    # Tolerance for "light" mode
    light_threshold_ms = 20.0  # only snap notes >20ms off-grid
    light_threshold_s = light_threshold_ms / 1000.0

    notes_moved = 0
    max_shift = 0.0
    total_shift = 0.0

    for inst in midi.instruments:
        for note in inst.notes:
            new_start = _snap_time(note.start, grid, mode)
            new_end = _snap_time(note.end, grid, mode)

            # Ensure minimum duration
            if new_end <= new_start:
                new_end = new_start + grid

            start_shift = abs(new_start - note.start)
            end_shift = abs(new_end - note.end)
            shift = max(start_shift, end_shift)

            if mode == "light" and shift < light_threshold_s:
                # Skip notes that are already close to grid
                continue

            if mode == "strict" or mode == "swing" or mode == "triplet" or shift >= light_threshold_s:
                if apply:
                    note.start = new_start
                    note.end = new_end

                notes_moved += 1
                shift_ms = shift * 1000.0
                max_shift = max(max_shift, shift_ms)
                total_shift += shift_ms

    result.notes_moved = notes_moved
    result.max_shift_ms = round(max_shift, 2)
    result.avg_shift_ms = round(total_shift / max(1, notes_moved), 2)

    # Write output
    if apply and not config.dry_run:
        output_name = midi_path.stem + ".requantized.mid"
        output_path = output_dir / output_name
        output_dir.mkdir(parents=True, exist_ok=True)
        midi.write(str(output_path))
        result.output_path = output_path

    return result


def run_requantize_midi(
    midi_path: Path,
    bpm: float,
    config: SunoPrepConfig,
    apply: bool = False,
) -> tuple[RequantizeResult, FeatureInvocation]:
    """Entry point for requantize-midi feature."""
    mode = config.requantize_mode
    invocation = FeatureInvocation(
        feature="requantize_midi",
        mode="apply" if apply else "report",
    )

    try:
        result = requantize_midi(
            midi_path, config.midi_dir, bpm, mode, config, apply=apply
        )

        if not config.dry_run:
            import json
            report_data = json.loads(result.model_dump_json())
            write_json_report(report_data, "requantize.json", config)
            invocation.output_files.append(config.reports_dir / "requantize.json")
            if result.output_path:
                invocation.output_files.append(result.output_path)

        invocation.recommendation = (
            f"Mode: {mode}, {result.notes_moved} notes would move, "
            f"max shift: {result.max_shift_ms:.1f}ms, "
            f"avg shift: {result.avg_shift_ms:.1f}ms"
        )

    except Exception as e:
        invocation.warnings.append(f"requantize-midi failed: {e}")
        result = RequantizeResult(mode=mode)

    return result, invocation
