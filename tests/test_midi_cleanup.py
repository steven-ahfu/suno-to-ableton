"""Tests for MIDI cleanup edge cases."""

from __future__ import annotations

import io
from pathlib import Path

import mido
import pretty_midi
from mido.midifiles.midifiles import write_track

from suno_to_ableton.config import SunoPrepConfig
from suno_to_ableton.models import StemType
from suno_to_ableton.midi_cleanup import cleanup_midi


def _write_invalid_key_signature_midi(path: Path) -> None:
    midi = mido.MidiFile()
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0))
    track.append(mido.Message("note_on", note=60, velocity=96, time=0))
    track.append(mido.Message("note_off", note=60, velocity=0, time=480))

    # Inject a malformed key-signature meta event directly into the track data.
    raw_buffer = io.BytesIO()
    write_track(raw_buffer, track)
    raw = raw_buffer.getvalue()
    malformed = b"\x00\xff\x59\x02\x12\x01"  # delta 0 + 18 sharps, minor mode
    end_of_track = b"\x00\xff\x2f\x00"
    assert raw.endswith(end_of_track)
    track_body = raw[8:-4] + malformed + end_of_track
    track_chunk = raw[:4] + len(track_body).to_bytes(4, "big") + track_body
    with path.open("wb") as handle:
        handle.write(b"MThd\x00\x00\x00\x06\x00\x01\x00\x01\x01\xe0")
        handle.write(track_chunk)


def test_cleanup_midi_recovers_from_invalid_key_signature(tmp_path: Path):
    input_path = tmp_path / "broken.mid"
    output_dir = tmp_path / "out"
    _write_invalid_key_signature_midi(input_path)

    result = cleanup_midi(
        input_path=input_path,
        output_dir=output_dir,
        offset_seconds=0.0,
        bpm=120.0,
        config=SunoPrepConfig(source_dir=tmp_path),
        stem_type=StemType.DRUMS,
    )

    assert result.output_path.exists()
    assert result.output_path.name == "midi_drums.cleaned.mid"
    assert result.tracks_kept >= 1
    assert any("Sanitized malformed key-signature metadata" in warning for warning in result.warnings)


def test_cleanup_midi_preserves_note_timing(tmp_path: Path):
    input_path = tmp_path / "timing.mid"
    output_dir = tmp_path / "out"

    midi = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=1.0, end=1.5))
    midi.instruments.append(inst)
    midi.write(str(input_path))

    result = cleanup_midi(
        input_path=input_path,
        output_dir=output_dir,
        offset_seconds=0.75,
        bpm=144.0,
        config=SunoPrepConfig(source_dir=tmp_path),
        stem_type=StemType.BASS,
    )

    cleaned = pretty_midi.PrettyMIDI(str(result.output_path))
    note = cleaned.instruments[0].notes[0]
    assert note.start == 1.0
    assert note.end == 1.5
    assert result.output_path.name == "midi_bass.cleaned.mid"
    assert result.offset_applied == 0.0
    assert result.notes_quantized == 0
