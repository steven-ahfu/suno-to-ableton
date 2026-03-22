"""MIDI cleanup pipeline with source timing preserved."""

from __future__ import annotations

import tempfile
from fractions import Fraction
from pathlib import Path

import pretty_midi

from .config import SunoPrepConfig
from .models import MIDICleanupResult, StemType

_TRACK_CHUNK_TYPE = b"MTrk"
_HEADER_CHUNK_TYPE = b"MThd"


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


def _canonical_midi_output_stem(stem_type: StemType) -> str:
    """Return a canonical processed MIDI basename for a stem type."""
    if stem_type in (StemType.OTHER, StemType.FULL_MIX):
        return "midi_song"
    return f"midi_{stem_type.value}"


def _read_varlen(data: bytes, index: int) -> tuple[int, int]:
    """Read a MIDI variable-length integer from data[index:]."""
    value = 0
    while True:
        byte = data[index]
        index += 1
        value = (value << 7) | (byte & 0x7F)
        if byte < 0x80:
            return value, index


def _write_varlen(value: int) -> bytes:
    """Encode a MIDI variable-length integer."""
    buffer = [value & 0x7F]
    value >>= 7
    while value:
        buffer.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(buffer))


def _channel_message_data_length(status: int) -> int:
    """Return the number of data bytes for a channel-message status."""
    message_type = status & 0xF0
    if message_type in (0xC0, 0xD0):
        return 1
    return 2


def _sanitize_track_chunk(track_data: bytes) -> tuple[bytes, int]:
    """Strip invalid key-signature meta events from a raw MIDI track chunk."""
    index = 0
    running_status: int | None = None
    pending_delta = 0
    output = bytearray()
    removed = 0

    while index < len(track_data):
        delta, index = _read_varlen(track_data, index)
        delta += pending_delta
        pending_delta = 0

        status = track_data[index]
        event_start = index

        if status == 0xFF:
            meta_type = track_data[index + 1]
            length, data_start = _read_varlen(track_data, index + 2)
            data_end = data_start + length
            event_bytes = track_data[event_start:data_end]
            index = data_end
            running_status = None

            if meta_type == 0x59 and length == 2:
                sharps_flats = int.from_bytes(bytes([track_data[data_start]]), "big", signed=True)
                mode = track_data[data_start + 1]
                if sharps_flats < -7 or sharps_flats > 7 or mode not in (0, 1):
                    removed += 1
                    pending_delta = delta
                    continue

            output.extend(_write_varlen(delta))
            output.extend(event_bytes)
            continue

        if status in (0xF0, 0xF7):
            length, data_start = _read_varlen(track_data, index + 1)
            data_end = data_start + length
            event_bytes = track_data[event_start:data_end]
            index = data_end
            running_status = None
            output.extend(_write_varlen(delta))
            output.extend(event_bytes)
            continue

        if status & 0x80:
            running_status = status
            index += 1
            data_len = _channel_message_data_length(status)
            event_bytes = bytes([status]) + track_data[index:index + data_len]
            index += data_len
        else:
            if running_status is None:
                raise ValueError("Malformed MIDI: running status used before status byte")
            data_len = _channel_message_data_length(running_status)
            event_bytes = track_data[event_start:event_start + data_len]
            index = event_start + data_len

        output.extend(_write_varlen(delta))
        output.extend(event_bytes)

    return bytes(output), removed


def _sanitize_key_signatures_for_pretty_midi(input_path: Path) -> tuple[Path, list[str]]:
    """Drop invalid key-signature meta events that pretty_midi can't decode."""
    raw = input_path.read_bytes()
    if not raw.startswith(_HEADER_CHUNK_TYPE):
        return input_path, []

    removed_warnings: list[str] = []
    changed = False
    index = 0
    sanitized = bytearray()
    track_index = 0

    while index + 8 <= len(raw):
        chunk_type = raw[index:index + 4]
        chunk_length = int.from_bytes(raw[index + 4:index + 8], "big")
        chunk_data_start = index + 8
        chunk_data_end = chunk_data_start + chunk_length
        chunk_data = raw[chunk_data_start:chunk_data_end]

        if chunk_type == _TRACK_CHUNK_TYPE:
            track_index += 1
            sanitized_track, removed = _sanitize_track_chunk(chunk_data)
            if removed:
                changed = True
                removed_warnings.append(
                    f"Removed {removed} invalid key_signature meta event(s) from track {track_index}"
                )
            chunk_data = sanitized_track
            chunk_length = len(chunk_data)

        sanitized.extend(chunk_type)
        sanitized.extend(chunk_length.to_bytes(4, "big"))
        sanitized.extend(chunk_data)
        index = chunk_data_end

    if not changed:
        return input_path, removed_warnings

    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(bytes(sanitized))
    return temp_path, removed_warnings


def _load_midi_resilient(input_path: Path) -> tuple[pretty_midi.PrettyMIDI, list[str]]:
    """Load MIDI, retrying after stripping malformed key-signature metadata."""
    try:
        return pretty_midi.PrettyMIDI(str(input_path)), []
    except Exception as exc:
        if "Could not decode key with" not in str(exc):
            raise
        original_exc = exc

    sanitized_path, warnings = _sanitize_key_signatures_for_pretty_midi(input_path)
    if sanitized_path == input_path:
        raise original_exc

    try:
        friendly_warnings = [
            (
                f"Sanitized malformed key-signature metadata in {input_path.name}; "
                "note timing was preserved"
            )
        ] if warnings else []
        return pretty_midi.PrettyMIDI(str(sanitized_path)), friendly_warnings
    finally:
        sanitized_path.unlink(missing_ok=True)


def cleanup_midi(
    input_path: Path,
    output_dir: Path,
    offset_seconds: float,
    bpm: float,
    config: SunoPrepConfig,
    stem_type: StemType = StemType.OTHER,
) -> MIDICleanupResult:
    """Full MIDI cleanup pipeline.

    1. Remove empty instruments
    2. Remove short notes
    3. Remove duplicate notes
    4. Preserve original note timing
    5. Write output
    """
    result = MIDICleanupResult(
        input_path=input_path,
        output_path=output_dir / "placeholder.mid",
    )

    # Generate output filename
    clean_name = _canonical_midi_output_stem(stem_type)
    output_path = output_dir / f"{clean_name}.cleaned.mid"
    result.output_path = output_path

    if config.skip_existing and output_path.exists() and not config.force:
        return result

    # Load
    midi, load_warnings = _load_midi_resilient(input_path)
    result.warnings.extend(load_warnings)

    # Step 1: Remove empty instruments
    result.tracks_removed = _remove_empty_instruments(midi)
    result.tracks_kept = len(midi.instruments)

    # Step 2: Remove short notes
    min_duration_s = config.min_note_ms / 1000.0
    result.notes_removed_short = _remove_short_notes(midi, min_duration_s)

    # Step 3: Remove duplicates
    result.notes_removed_duplicate = _remove_duplicate_notes(midi)

    # Preserve source timing. The detected alignment offset is still reported in
    # pipeline reports, but cleanup no longer shifts or quantizes note data.
    result.offset_applied = 0.0
    result.notes_removed_pre_offset = 0
    result.tempo_set = bpm
    result.notes_quantized = 0

    # Step 5: Write
    if not config.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        midi.write(str(output_path))

    return result
