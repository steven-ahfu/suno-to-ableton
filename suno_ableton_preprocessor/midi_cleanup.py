"""MIDI cleanup pipeline using pretty_midi."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pretty_midi

from .config import SunoPrepConfig
from .models import MIDICleanupResult


def _remove_empty_instruments(midi: pretty_midi.PrettyMIDI) -> int:
    """Remove instruments with no notes. Returns count removed."""
    original_count = len(midi.instruments)
    midi.instruments = [inst for inst in midi.instruments if len(inst.notes) > 0]
    return original_count - len(midi.instruments)


def _remove_short_notes(midi: pretty_midi.PrettyMIDI, min_duration_s: float) -> int:
    """Remove notes shorter than min_duration. Returns count removed."""
    removed = 0
    for inst in midi.instruments:
        original = inst.notes[:]
        inst.notes = [n for n in inst.notes if (n.end - n.start) >= min_duration_s]
        removed += len(original) - len(inst.notes)
    return removed


def _remove_duplicate_notes(midi: pretty_midi.PrettyMIDI, tolerance: float = 0.0001) -> int:
    """Remove duplicate notes (same pitch, start, end within tolerance). Returns count removed."""
    removed = 0
    for inst in midi.instruments:
        unique = []
        seen: set[tuple[int, float, float]] = set()
        for note in inst.notes:
            # Round to tolerance
            key = (
                note.pitch,
                round(note.start / tolerance) * tolerance,
                round(note.end / tolerance) * tolerance,
            )
            if key not in seen:
                seen.add(key)
                unique.append(note)
            else:
                removed += 1
        inst.notes = unique
    return removed


def _apply_offset(midi: pretty_midi.PrettyMIDI, offset_seconds: float) -> int:
    """Shift all notes by -offset_seconds. Remove notes ending before t=0.

    Returns count of notes removed.
    """
    if offset_seconds <= 0:
        return 0

    removed = 0
    for inst in midi.instruments:
        surviving = []
        for note in inst.notes:
            note.start -= offset_seconds
            note.end -= offset_seconds
            if note.end > 0:
                note.start = max(0.0, note.start)
                surviving.append(note)
            else:
                removed += 1
        inst.notes = surviving

        # Also shift control changes
        for cc in inst.control_changes:
            cc.time -= offset_seconds
        inst.control_changes = [cc for cc in inst.control_changes if cc.time >= 0]

        # Shift pitch bends
        for pb in inst.pitch_bends:
            pb.time -= offset_seconds
        inst.pitch_bends = [pb for pb in inst.pitch_bends if pb.time >= 0]

    return removed


def _quantize_notes(
    midi: pretty_midi.PrettyMIDI, grid_fraction: Fraction, bpm: float
) -> int:
    """Snap note start/end to nearest grid point. Returns count of notes quantized."""
    # Grid size in seconds
    beat_duration = 60.0 / bpm
    # grid_fraction is fraction of a whole note (e.g. 1/16)
    # whole note = 4 beats, so grid in seconds = 4 * beat_duration * fraction
    grid_seconds = 4.0 * beat_duration * float(grid_fraction)

    if grid_seconds <= 0:
        return 0

    quantized = 0
    for inst in midi.instruments:
        for note in inst.notes:
            new_start = round(note.start / grid_seconds) * grid_seconds
            new_end = round(note.end / grid_seconds) * grid_seconds

            # Ensure minimum duration of one grid unit
            if new_end <= new_start:
                new_end = new_start + grid_seconds

            if new_start != note.start or new_end != note.end:
                note.start = new_start
                note.end = new_end
                quantized += 1

    return quantized


def _sanitize_midi_filename(name: str) -> str:
    """Create a clean filename from a MIDI stem name."""
    # Replace spaces and special chars
    clean = name.lower()
    for char in "()[]{}!@#$%^&*+=|\\/<>?\"':;,":
        clean = clean.replace(char, "")
    clean = clean.replace(" ", "_").replace("-", "_")
    # Collapse multiple underscores
    while "__" in clean:
        clean = clean.replace("__", "_")
    return clean.strip("_")


def cleanup_midi(
    input_path: Path,
    output_dir: Path,
    offset_seconds: float,
    bpm: float,
    config: SunoPrepConfig,
) -> MIDICleanupResult:
    """Full MIDI cleanup pipeline.

    1. Remove empty instruments
    2. Remove short notes
    3. Remove duplicate notes
    4. Apply global offset
    5. Set correct tempo
    6. Quantize to grid
    7. Write output
    """
    result = MIDICleanupResult(
        input_path=input_path,
        output_path=output_dir / "placeholder.mid",
    )

    # Generate output filename
    clean_name = _sanitize_midi_filename(input_path.stem)
    output_path = output_dir / f"{clean_name}.cleaned.mid"
    result.output_path = output_path

    if config.skip_existing and output_path.exists() and not config.force:
        return result

    # Load
    midi = pretty_midi.PrettyMIDI(str(input_path))

    # Step 1: Remove empty instruments
    result.tracks_removed = _remove_empty_instruments(midi)
    result.tracks_kept = len(midi.instruments)

    # Step 2: Remove short notes
    min_duration_s = config.min_note_ms / 1000.0
    result.notes_removed_short = _remove_short_notes(midi, min_duration_s)

    # Step 3: Remove duplicates
    result.notes_removed_duplicate = _remove_duplicate_notes(midi)

    # Step 4: Apply offset
    result.offset_applied = offset_seconds
    result.notes_removed_pre_offset = _apply_offset(midi, offset_seconds)

    # Step 5: Set correct tempo — create new PrettyMIDI with correct tempo
    # and copy instruments over
    result.tempo_set = bpm
    new_midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    for inst in midi.instruments:
        new_midi.instruments.append(inst)

    # Step 6: Quantize
    result.notes_quantized = _quantize_notes(
        new_midi, config.quantize_fraction, bpm
    )

    # Step 7: Write
    if not config.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        new_midi.write(str(output_path))

    return result
