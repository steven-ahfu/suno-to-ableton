"""Tests for ALS export behavior with dynamic stem/MIDI sets."""

from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pretty_midi

from suno_to_ableton.config import SunoPrepConfig
from suno_to_ableton.features.export_als import export_als
from suno_to_ableton.models import ProcessedFile, ProcessingManifest, StemType


def _track_names(als_path: Path) -> list[str]:
    with gzip.open(als_path, "rb") as f:
        root = ET.fromstring(f.read().decode("utf-8"))
    tracks_el = root.find("LiveSet/Tracks")
    names: list[str] = []
    for track in tracks_el:
        name_el = track.find(".//Name/EffectiveName")
        if name_el is not None:
            value = name_el.get("Value", "")
            if value:
                names.append(value)
    return names


def _als_text(als_path: Path) -> str:
    with gzip.open(als_path, "rb") as f:
        return f.read().decode("utf-8")


def _als_root(als_path: Path) -> ET.Element:
    with gzip.open(als_path, "rb") as f:
        return ET.fromstring(f.read().decode("utf-8"))


def _track_summary(als_path: Path) -> list[tuple[str, str]]:
    root = _als_root(als_path)
    tracks_el = root.find("LiveSet/Tracks")
    summary: list[tuple[str, str]] = []
    for track in tracks_el:
        name_el = track.find(".//Name/EffectiveName")
        name = name_el.get("Value", "") if name_el is not None else ""
        if name:
            summary.append((track.tag, name))
    return summary


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def _write_midi(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    midi = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=0.5))
    midi.instruments.append(inst)
    midi.write(str(path))
    return path


class TestExportALS:
    @patch("suno_to_ableton.features.export_als._get_audio_info", return_value=(480000, 48000))
    def test_prunes_unused_audio_tracks_for_multi_midi_project(self, _mock_audio, tmp_path: Path):
        config = SunoPrepConfig(source_dir=tmp_path, output_dir=Path("processed"))
        manifest = ProcessingManifest(
            song_title="untitled again",
            bpm=120.0,
            stems=[
                ProcessedFile(output_path=_touch(tmp_path / "processed" / "stems" / "01_drums.wav"), stem_type=StemType.DRUMS),
                ProcessedFile(output_path=_touch(tmp_path / "processed" / "stems" / "02_bass.wav"), stem_type=StemType.BASS),
                ProcessedFile(output_path=_touch(tmp_path / "processed" / "stems" / "03_synth.wav"), stem_type=StemType.SYNTH),
            ],
            midi_files=[
                ProcessedFile(output_path=_write_midi(tmp_path / "processed" / "midi" / "drums.cleaned.mid"), stem_type=StemType.DRUMS),
                ProcessedFile(output_path=_write_midi(tmp_path / "processed" / "midi" / "bass.cleaned.mid"), stem_type=StemType.BASS),
                ProcessedFile(output_path=_write_midi(tmp_path / "processed" / "midi" / "synth.cleaned.mid"), stem_type=StemType.SYNTH),
                ProcessedFile(output_path=_write_midi(tmp_path / "processed" / "midi" / "fx.cleaned.mid"), stem_type=StemType.FX),
            ],
        )

        result = export_als(manifest, config)
        names = _track_names(result.output_path)

        assert "Drums" in names
        assert "Bass" in names
        assert "Synth" in names
        assert "Vocals" not in names
        assert "Backing Vocals" not in names
        assert "FX" not in names
        assert "MIDI Drums" in names
        assert "MIDI Bass" in names
        assert "MIDI Synth" in names
        assert "MIDI FX" in names
        summary = _track_summary(result.output_path)
        assert ("AudioTrack", "Drums") in summary
        assert ("AudioTrack", "Bass") in summary
        assert ("AudioTrack", "Synth") in summary
        assert ("MidiTrack", "MIDI Drums") in summary
        assert ("MidiTrack", "MIDI Bass") in summary
        assert ("MidiTrack", "MIDI Synth") in summary
        assert ("MidiTrack", "MIDI FX") in summary
        root = _als_root(result.output_path)
        assert root.find(".//Tempo/Manual").get("Value") == "120.000000"
        text = _als_text(result.output_path)
        assert "<SampleRef>" in text
        assert "<FileRef>" in text
        assert "<MidiClip " in text

    @patch("suno_to_ableton.features.export_als._get_audio_info", return_value=(480000, 48000))
    def test_single_midi_project_shape_still_works(self, _mock_audio, tmp_path: Path):
        config = SunoPrepConfig(source_dir=tmp_path, output_dir=Path("processed"))
        manifest = ProcessingManifest(
            song_title="in my bag",
            bpm=128.0,
            stems=[
                ProcessedFile(output_path=_touch(tmp_path / "processed" / "stems" / "01_fx.wav"), stem_type=StemType.FX),
                ProcessedFile(output_path=_touch(tmp_path / "processed" / "stems" / "02_synth.wav"), stem_type=StemType.SYNTH),
                ProcessedFile(output_path=_touch(tmp_path / "processed" / "stems" / "03_percussion.wav"), stem_type=StemType.PERCUSSION),
                ProcessedFile(output_path=_touch(tmp_path / "processed" / "stems" / "04_bass.wav"), stem_type=StemType.BASS),
                ProcessedFile(output_path=_touch(tmp_path / "processed" / "stems" / "05_drums.wav"), stem_type=StemType.DRUMS),
                ProcessedFile(output_path=_touch(tmp_path / "processed" / "stems" / "06_backing_vocals.wav"), stem_type=StemType.BACKING_VOCALS),
                ProcessedFile(output_path=_touch(tmp_path / "processed" / "stems" / "07_vocals.wav"), stem_type=StemType.VOCALS),
            ],
            midi_files=[
                ProcessedFile(output_path=_write_midi(tmp_path / "processed" / "midi" / "song.cleaned.mid"), stem_type=StemType.OTHER),
            ],
        )

        result = export_als(manifest, config)
        names = _track_names(result.output_path)

        assert "Drums" in names
        assert "Bass" in names
        assert "Synth" in names
        assert "MIDI (Song)" in names
        assert "MIDI Drums" not in names
        assert "MIDI Bass" not in names
        assert "MIDI Synth" not in names
        assert "MIDI FX" not in names
        summary = _track_summary(result.output_path)
        assert ("AudioTrack", "Drums") in summary
        assert ("AudioTrack", "Bass") in summary
        assert ("AudioTrack", "Synth") in summary
        assert ("MidiTrack", "MIDI (Song)") in summary
        root = _als_root(result.output_path)
        assert root.find(".//Tempo/Manual").get("Value") == "128.000000"
        text = _als_text(result.output_path)
        assert "<SampleRef>" in text
        assert "<FileRef>" in text
        assert "<MidiClip " in text
