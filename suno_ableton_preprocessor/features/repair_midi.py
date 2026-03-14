"""Conservative harmonic MIDI cleanup beyond the automatic pipeline's technical cleanup."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pretty_midi

from ..config import SunoPrepConfig
from ..models import FeatureInvocation, MIDIRepairResult
from ..reporting import write_json_report

# Major and minor scale intervals from root
_SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
}
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _detect_key(midi: pretty_midi.PrettyMIDI) -> tuple[int, str, float]:
    """Detect key via duration-weighted pitch class histogram.

    Returns (root_pitch_class, scale_type, confidence).
    """
    # Build pitch class histogram weighted by note duration
    histogram = np.zeros(12)
    for inst in midi.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            pc = note.pitch % 12
            duration = note.end - note.start
            histogram[pc] += duration

    if histogram.sum() == 0:
        return 0, "major", 0.0

    histogram = histogram / histogram.sum()

    best_root = 0
    best_scale = "major"
    best_score = 0.0

    for root in range(12):
        for scale_name, intervals in _SCALES.items():
            # Rotate histogram so root is at index 0
            rotated = np.roll(histogram, -root)
            # Score = sum of weights on scale degrees
            score = sum(rotated[i] for i in intervals)
            if score > best_score:
                best_score = score
                best_root = root
                best_scale = scale_name

    confidence = min(1.0, best_score / 0.85)  # normalize against typical threshold
    return best_root, best_scale, confidence


def _get_scale_pitches(root: int, scale_type: str) -> set[int]:
    """Get all pitch classes in a scale."""
    intervals = _SCALES.get(scale_type, _SCALES["major"])
    return {(root + i) % 12 for i in intervals}


def _snap_to_scale(pitch: int, scale_pcs: set[int]) -> int:
    """Snap a pitch to the nearest scale degree (minimizes interval)."""
    pc = pitch % 12
    if pc in scale_pcs:
        return pitch

    # Find nearest scale degree in both directions, pick closest
    for offset in range(1, 7):
        up = (pc + offset) % 12 in scale_pcs
        down = (pc - offset) % 12 in scale_pcs
        if up and down:
            return pitch - offset  # prefer downward to preserve melodic contour
        if up:
            return pitch + offset
        if down:
            return pitch - offset
    return pitch


def repair_midi(
    midi_path: Path,
    output_dir: Path,
    config: SunoPrepConfig,
    apply: bool = False,
) -> MIDIRepairResult:
    """Analyze and optionally repair MIDI harmonics."""
    result = MIDIRepairResult(input_path=midi_path)

    midi = pretty_midi.PrettyMIDI(str(midi_path))

    # Detect key
    root, scale_type, key_confidence = _detect_key(midi)
    root_name = _NOTE_NAMES[root]
    result.key_detected = f"{root_name} {scale_type}"

    scale_pcs = _get_scale_pitches(root, scale_type)

    # Analyze notes
    notes_flagged = 0
    notes_repaired = 0
    stacked_fixed = 0
    details = []

    for inst in midi.instruments:
        if inst.is_drum:
            continue

        # Check for out-of-key notes
        for note in inst.notes:
            pc = note.pitch % 12
            if pc not in scale_pcs:
                notes_flagged += 1
                detail = {
                    "instrument": inst.name,
                    "pitch": note.pitch,
                    "note_name": pretty_midi.note_number_to_name(note.pitch),
                    "time": round(note.start, 3),
                    "issue": "out_of_key",
                }
                if apply:
                    new_pitch = _snap_to_scale(note.pitch, scale_pcs)
                    detail["repaired_to"] = pretty_midi.note_number_to_name(new_pitch)
                    note.pitch = new_pitch
                    notes_repaired += 1
                details.append(detail)

        # Check for stacked notes (same pitch, overlapping)
        notes_by_pitch: dict[int, list] = {}
        for note in inst.notes:
            notes_by_pitch.setdefault(note.pitch, []).append(note)

        for pitch, pitch_notes in notes_by_pitch.items():
            if len(pitch_notes) <= 1:
                continue
            pitch_notes.sort(key=lambda n: n.start)
            to_remove = []
            for i in range(len(pitch_notes) - 1):
                a = pitch_notes[i]
                b = pitch_notes[i + 1]
                # Overlapping if a.end > b.start
                if a.end > b.start + 0.001:
                    details.append({
                        "instrument": inst.name,
                        "pitch": pitch,
                        "note_name": pretty_midi.note_number_to_name(pitch),
                        "time": round(b.start, 3),
                        "issue": "stacked_overlap",
                    })
                    if apply:
                        # Truncate first note to end at second note's start
                        a.end = b.start
                        stacked_fixed += 1

    result.notes_flagged = notes_flagged
    result.notes_repaired = notes_repaired
    result.stacked_chords_fixed = stacked_fixed
    result.details = details

    # Write output
    if apply and not config.dry_run:
        output_name = midi_path.stem + ".repaired.mid"
        output_path = output_dir / output_name
        output_dir.mkdir(parents=True, exist_ok=True)
        midi.write(str(output_path))
        result.output_path = output_path

    return result


def run_repair_midi(
    midi_path: Path,
    config: SunoPrepConfig,
    apply: bool = False,
) -> tuple[MIDIRepairResult, FeatureInvocation]:
    """Entry point for repair-midi feature."""
    invocation = FeatureInvocation(
        feature="repair_midi",
        mode="apply" if apply else "report",
    )

    try:
        result = repair_midi(midi_path, config.midi_dir, config, apply=apply)

        if not config.dry_run:
            import json
            report_data = json.loads(result.model_dump_json())
            write_json_report(report_data, "midi_repair.json", config)
            invocation.output_files.append(config.reports_dir / "midi_repair.json")
            if result.output_path:
                invocation.output_files.append(result.output_path)

        invocation.recommendation = (
            f"Key: {result.key_detected}, "
            f"{result.notes_flagged} flagged, "
            f"{result.notes_repaired} repaired, "
            f"{result.stacked_chords_fixed} stacked fixed"
        )

    except Exception as e:
        invocation.warnings.append(f"repair-midi failed: {e}")
        result = MIDIRepairResult()

    return result, invocation
