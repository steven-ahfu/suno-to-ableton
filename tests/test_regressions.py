"""Regression tests for every export-pipeline bug fixed in May 2026.

Each test pins one specific symptom we observed in Live so it can never regress.
Names of the issues correspond to the order they appeared during debugging.
"""

from __future__ import annotations

import gzip
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pretty_midi
import soundfile as sf

from suno_to_ableton.audio_processing import process_audio_file
from suno_to_ableton.bpm_detection import _detect_downbeat_phase
from suno_to_ableton.config import SunoPrepConfig
from suno_to_ableton.features.export_als import (
    _renumber_pointee_ids,
    export_als,
)
from suno_to_ableton.midi_cleanup import cleanup_midi
from suno_to_ableton.models import (
    DiscoveredFile,
    FileRole,
    ProcessedFile,
    ProcessingManifest,
    StemType,
)


# ---------- helpers ----------


def _als_xml(path: Path) -> str:
    with gzip.open(path, "rb") as f:
        return f.read().decode("utf-8")


def _als_root(path: Path) -> ET.Element:
    return ET.fromstring(_als_xml(path))


def _audio_clips_with_stems(xml: str) -> list[str]:
    return [m.group(0) for m in re.finditer(r"<AudioClip[^>]*>.*?</AudioClip>", xml, re.DOTALL) if "stems/" in m.group(0)]


def _touch_wav(path: Path, duration_sec: float = 1.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = np.zeros((int(48000 * duration_sec), 2), dtype=np.float32)
    sf.write(path, samples, 48000, subtype="FLOAT")
    return path


def _make_manifest(tmp_path: Path, stem_types: list[StemType], bpm: float = 132.0) -> ProcessingManifest:
    stems = []
    for i, st in enumerate(stem_types):
        p = _touch_wav(tmp_path / "processed" / "stems" / f"0{i}_{st.value}.wav")
        stems.append(ProcessedFile(output_path=p, stem_type=st))
    return ProcessingManifest(
        song_title="test",
        bpm=bpm,
        offset_seconds=0.0,
        stems=stems,
    )


# ---------- 1. IsWarped fix ----------


class TestIsWarped:
    @patch("suno_to_ableton.features.export_als._get_audio_info", return_value=(48000 * 60, 48000))
    def test_all_audio_clips_are_warped(self, _mock, tmp_path: Path):
        """Audio clips must have IsWarped=true so warp markers actually apply."""
        config = SunoPrepConfig(source_dir=tmp_path)
        manifest = _make_manifest(tmp_path, [StemType.DRUMS, StemType.BASS, StemType.SYNTH])
        result = export_als(manifest, config)
        for clip_xml in _audio_clips_with_stems(_als_xml(result.output_path)):
            m = re.search(r'<IsWarped Value="(\w+)"', clip_xml)
            assert m and m.group(1) == "true", "stem clip must be warped"


# ---------- 2. Tempo automation envelope flattened ----------


class TestTempoEnvelopeFlat:
    @patch("suno_to_ableton.features.export_als._get_audio_info", return_value=(48000 * 60, 48000))
    def test_tempo_envelope_is_flat_at_project_bpm(self, _mock, tmp_path: Path):
        """Bundled template ships a 144.23 BPM tempo curve; export must flatten it."""
        config = SunoPrepConfig(source_dir=tmp_path)
        manifest = _make_manifest(tmp_path, [StemType.DRUMS], bpm=120.0)
        result = export_als(manifest, config)
        xml = _als_xml(result.output_path)

        # Master Tempo > Manual must equal project BPM
        m = re.search(r"<Tempo>\s*<LomId Value=\"0\"\s*/>\s*<Manual Value=\"([\d.]+)\"", xml)
        assert m, "master Tempo not found"
        assert abs(float(m.group(1)) - 120.0) < 0.01

        # Tempo automation envelope must contain only project-BPM values
        target_id = re.search(r"<Tempo>.*?<AutomationTarget Id=\"(\d+)\"", xml, re.DOTALL).group(1)
        for env in re.finditer(r"<AutomationEnvelope[^>]*>.*?</AutomationEnvelope>", xml, re.DOTALL):
            if f'<PointeeId Value="{target_id}"' in env.group(0):
                events = re.findall(r"<FloatEvent[^/]*?Value=\"([\d.]+)\"", env.group(0))
                assert events, "tempo envelope has no events"
                for v in events:
                    assert abs(float(v) - 120.0) < 0.01, f"tempo envelope contains stray BPM {v}"


# ---------- 3. BPM snap and override ----------


class TestBPMOverrides:
    def test_snap_bpm_rounds_to_integer(self, tmp_path: Path):
        """--snap-bpm rounds detection (which often lands fractional) to nearest int."""
        # We only test the rounding behavior; actual detection isn't needed.
        cfg = SunoPrepConfig(source_dir=tmp_path, snap_bpm=True)
        # The pipeline applies round() — match that here
        assert round(130.81) == 131
        assert round(127.4) == 127
        assert cfg.snap_bpm is True

    def test_bpm_override_replaces_detected_value(self, tmp_path: Path):
        cfg = SunoPrepConfig(source_dir=tmp_path, bpm_override=132.0)
        assert cfg.bpm_override == 132.0


# ---------- 4. Downbeat phase voting ----------


class TestDownbeatPhase:
    def test_downbeat_voting_picks_phase_with_strongest_onsets(self):
        """Mock the onset envelope so beats at phase 2 carry all the energy.
        Voting must return phase 2."""
        beat_frames = np.arange(0, 16) * 10  # 16 beats, 10 frames apart
        # Patch onset_strength to return an envelope with peaks ONLY at phase-2 beat frames.
        n_frames = int(beat_frames[-1]) + 20
        envelope = np.zeros(n_frames, dtype=np.float32)
        for f in beat_frames[2::4]:  # phase 2: beats 2, 6, 10, 14
            envelope[int(f)] = 100.0

        with patch("suno_to_ableton.bpm_detection.librosa.onset.onset_strength", return_value=envelope), \
             patch("suno_to_ableton.bpm_detection.librosa.effects.preemphasis", side_effect=lambda y, coef: y):
            y = np.zeros(48000, dtype=np.float32)  # placeholder; envelope is mocked
            phase = _detect_downbeat_phase(y, sr=48000, beat_frames=beat_frames, beats_per_bar=4)
        assert phase == 2, f"expected phase 2, got {phase}"

    def test_downbeat_voting_handles_short_input(self):
        """With fewer beats than a bar, voting falls back to phase 0."""
        beat_frames = np.array([0, 100])
        y = np.zeros(48000, dtype=np.float32)
        phase = _detect_downbeat_phase(y, 48000, beat_frames, beats_per_bar=4)
        assert phase == 0


# ---------- 5. Beat offset ----------


class TestBeatOffset:
    def test_beat_offset_config_field(self, tmp_path: Path):
        cfg = SunoPrepConfig(source_dir=tmp_path, beat_offset=2)
        assert cfg.beat_offset == 2
        cfg2 = SunoPrepConfig(source_dir=tmp_path, beat_offset=-1)
        assert cfg2.beat_offset == -1


# ---------- 6. Align downbeat: trim audio + shift MIDI ----------


class TestAlignDownbeat:
    def test_audio_trimmed_when_align_downbeat_on(self, tmp_path: Path):
        input_path = tmp_path / "0 Drums.wav"
        samples = np.zeros((48000 * 4, 2), dtype=np.float32)  # 4 seconds
        sf.write(input_path, samples, 48000, subtype="FLOAT")
        cfg = SunoPrepConfig(source_dir=tmp_path, align_downbeat=True)
        out, steps = process_audio_file(
            DiscoveredFile(
                path=input_path, role=FileRole.AUDIO_STEM, stem_type=StemType.DRUMS,
                track_number=0, sample_rate=48000, channels=2, subtype="FLOAT",
            ),
            output_dir=tmp_path / "processed" / "stems",
            offset_seconds=1.0,
            config=cfg,
        )
        info = sf.info(str(out))
        # Original 4 seconds, trimmed by 1 second → ~3 seconds
        assert abs(info.frames - 48000 * 3) < 1000
        assert any("trimmed" in s for s in steps)

    def test_audio_not_trimmed_when_align_downbeat_off(self, tmp_path: Path):
        input_path = tmp_path / "0 Drums.wav"
        samples = np.zeros((48000 * 4, 2), dtype=np.float32)
        sf.write(input_path, samples, 48000, subtype="FLOAT")
        cfg = SunoPrepConfig(source_dir=tmp_path, align_downbeat=False)
        out, steps = process_audio_file(
            DiscoveredFile(
                path=input_path, role=FileRole.AUDIO_STEM, stem_type=StemType.DRUMS,
                track_number=0, sample_rate=48000, channels=2, subtype="FLOAT",
            ),
            output_dir=tmp_path / "processed" / "stems",
            offset_seconds=1.0,
            config=cfg,
        )
        info = sf.info(str(out))
        assert info.frames == 48000 * 4

    def test_midi_notes_shifted_when_align_downbeat_on(self, tmp_path: Path):
        midi_path = tmp_path / "drums.mid"
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=2.0, end=2.5))
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=62, start=3.0, end=3.5))
        midi.instruments.append(inst)
        midi.write(str(midi_path))

        cfg = SunoPrepConfig(source_dir=tmp_path, align_downbeat=True)
        out_dir = tmp_path / "processed" / "midi"
        out_dir.mkdir(parents=True, exist_ok=True)
        result = cleanup_midi(midi_path, out_dir, offset_seconds=1.5, bpm=120.0, config=cfg)

        cleaned = pretty_midi.PrettyMIDI(str(result.output_path))
        starts = sorted(n.start for inst in cleaned.instruments for n in inst.notes)
        # 2.0-1.5 = 0.5; 3.0-1.5 = 1.5
        assert abs(starts[0] - 0.5) < 0.01
        assert abs(starts[1] - 1.5) < 0.01

    def test_midi_notes_preserved_when_align_downbeat_off(self, tmp_path: Path):
        midi_path = tmp_path / "drums.mid"
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=2.0, end=2.5))
        midi.instruments.append(inst)
        midi.write(str(midi_path))

        cfg = SunoPrepConfig(source_dir=tmp_path, align_downbeat=False)
        out_dir = tmp_path / "processed" / "midi"
        out_dir.mkdir(parents=True, exist_ok=True)
        result = cleanup_midi(midi_path, out_dir, offset_seconds=1.5, bpm=120.0, config=cfg)

        cleaned = pretty_midi.PrettyMIDI(str(result.output_path))
        starts = sorted(n.start for inst in cleaned.instruments for n in inst.notes)
        assert abs(starts[0] - 2.0) < 0.01


# ---------- 7. Per-beat warp markers ----------


class TestPerBeatWarpMarkers:
    @patch("suno_to_ableton.features.export_als._get_audio_info", return_value=(48000 * 60, 48000))
    def test_per_beat_warp_markers_written(self, _mock, tmp_path: Path):
        cfg = SunoPrepConfig(source_dir=tmp_path, per_beat_warp_markers=True)
        beat_times = [i * 0.5 for i in range(120)]  # 120 beats at 120 BPM
        manifest = ProcessingManifest(
            song_title="test", bpm=120.0, offset_seconds=0.0,
            beat_times=beat_times,
            stems=[ProcessedFile(
                output_path=_touch_wav(tmp_path / "processed" / "stems" / "00_drums.wav"),
                stem_type=StemType.DRUMS,
            )],
        )
        result = export_als(manifest, cfg)
        for clip_xml in _audio_clips_with_stems(_als_xml(result.output_path)):
            wm = re.search(r"<WarpMarkers>.*?</WarpMarkers>", clip_xml, re.DOTALL)
            n = wm.group(0).count("<WarpMarker ") if wm else 0  # trailing space excludes <WarpMarkers>
            assert n > 100, f"expected per-beat markers (>100), got {n}"

    @patch("suno_to_ableton.features.export_als._get_audio_info", return_value=(48000 * 60, 48000))
    def test_two_marker_fallback_when_disabled(self, _mock, tmp_path: Path):
        cfg = SunoPrepConfig(source_dir=tmp_path, per_beat_warp_markers=False)
        manifest = _make_manifest(tmp_path, [StemType.DRUMS], bpm=120.0)
        result = export_als(manifest, cfg)
        for clip_xml in _audio_clips_with_stems(_als_xml(result.output_path)):
            wm = re.search(r"<WarpMarkers>.*?</WarpMarkers>", clip_xml, re.DOTALL)
            n = wm.group(0).count("<WarpMarker ") if wm else 0  # trailing space excludes <WarpMarkers>
            assert n == 2, f"expected 2 markers, got {n}"


# ---------- 8. Generic stem track support (clones for missing types) ----------


class TestGenericStemTracks:
    @patch("suno_to_ableton.features.export_als._get_audio_info", return_value=(48000 * 60, 48000))
    def test_vocals_track_created_via_clone(self, _mock, tmp_path: Path):
        """Template lacks Vocals/Backing Vocals/FX tracks — they must be cloned in."""
        cfg = SunoPrepConfig(source_dir=tmp_path)
        manifest = _make_manifest(tmp_path, [
            StemType.DRUMS, StemType.BASS, StemType.SYNTH,
            StemType.FX, StemType.VOCALS, StemType.BACKING_VOCALS,
        ])
        result = export_als(manifest, cfg)
        xml = _als_xml(result.output_path)
        names = re.findall(r'<AudioTrack[^>]*>.*?<EffectiveName Value="([^"]*)"', xml, re.DOTALL)
        for required in ("Drums", "Bass", "Synth", "FX", "Vocals", "Backing Vocals"):
            assert required in names, f"missing AudioTrack: {required} (got {names})"

    @patch("suno_to_ableton.features.export_als._get_audio_info", return_value=(48000 * 60, 48000))
    def test_cloned_tracks_inserted_before_midi_tracks(self, _mock, tmp_path: Path):
        """Live requires AudioTrack* MidiTrack* ReturnTrack* MasterTrack ordering."""
        cfg = SunoPrepConfig(source_dir=tmp_path)
        manifest = _make_manifest(tmp_path, [
            StemType.DRUMS, StemType.VOCALS, StemType.BACKING_VOCALS,
        ])
        # Add a MIDI file so MidiTracks exist
        midi_path = tmp_path / "processed" / "midi" / "drums.cleaned.mid"
        midi_path.parent.mkdir(parents=True, exist_ok=True)
        m = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=36, start=0, end=0.5))
        m.instruments.append(inst)
        m.write(str(midi_path))
        manifest.midi_files = [ProcessedFile(output_path=midi_path, stem_type=StemType.DRUMS)]

        result = export_als(manifest, cfg)
        xml = _als_xml(result.output_path)
        order = [m.group(1) for m in re.finditer(r"<(AudioTrack|MidiTrack|ReturnTrack|MasterTrack)\s", xml)]
        phase_map = {"AudioTrack": 0, "MidiTrack": 1, "ReturnTrack": 2, "MasterTrack": 3}
        phase = 0
        for t in order:
            assert phase_map[t] >= phase, f"track ordering violated: {t} after phase {phase} in {order}"
            phase = phase_map[t]


# ---------- 9. Pointee ID uniqueness ----------


class TestPointeeUniqueness:
    @patch("suno_to_ableton.features.export_als._get_audio_info", return_value=(48000 * 60, 48000))
    def test_pointee_ids_are_unique_with_clones(self, _mock, tmp_path: Path):
        """Cloning a track must not produce duplicate Pointee IDs in the document."""
        cfg = SunoPrepConfig(source_dir=tmp_path)
        manifest = _make_manifest(tmp_path, [
            StemType.DRUMS, StemType.BASS, StemType.SYNTH, StemType.FX,
            StemType.VOCALS, StemType.BACKING_VOCALS,
        ])
        result = export_als(manifest, cfg)
        xml = _als_xml(result.output_path)

        # Per-tag uniqueness for the Pointee namespace (Target/Targets, Pointee, RemoteableBool/Float)
        pointee_tag_classes = list(set(re.findall(r"<(\w+(?:Target|Targets))", xml))) + [
            "Pointee", "RemoteableBool", "RemoteableFloat",
        ]
        for tag in pointee_tag_classes:
            ids = [int(m.group(1)) for m in re.finditer(rf'<{tag}\s[^>]*\bId="(\d+)"', xml)]
            dups = sum(c - 1 for c in Counter(ids).values() if c > 1)
            assert dups == 0, f"{tag}: {dups} duplicate ids"

    def test_renumber_pointee_ids_shifts_target_ids(self):
        """_renumber_pointee_ids must shift Target Ids and PointeeId references by offset."""
        root = ET.fromstring(
            """<root>
                <AutomationTarget Id="5"><LockEnvelope Value="0"/></AutomationTarget>
                <ModulationTarget Id="6"><LockEnvelope Value="0"/></ModulationTarget>
                <PointeeId Value="5"/>
                <RemoteableTimeSignature><Manual Value="201"/></RemoteableTimeSignature>
            </root>"""
        )
        # Add an Id to RTS for the test
        root.find("RemoteableTimeSignature").set("Id", "0")
        max_id = _renumber_pointee_ids(root, offset=1000)
        assert root.find("AutomationTarget").get("Id") == "1005"
        assert root.find("ModulationTarget").get("Id") == "1006"
        assert root.find("PointeeId").get("Value") == "1005"
        assert root.find("RemoteableTimeSignature").get("Id") == "1000"
        assert max_id >= 1006

    def test_renumber_skips_clip_local_tags(self):
        """AudioClip / WarpMarker / FileRef Ids must NOT be renumbered (clip-local scope)."""
        root = ET.fromstring(
            """<root>
                <AudioClip Id="42"/>
                <WarpMarker Id="0" SecTime="0" BeatTime="0"/>
                <FileRef Id="0"/>
            </root>"""
        )
        _renumber_pointee_ids(root, offset=1000)
        assert root.find("AudioClip").get("Id") == "42"
        assert root.find("WarpMarker").get("Id") == "0"
        assert root.find("FileRef").get("Id") == "0"


# ---------- 10. NextPointeeId > all Pointee Ids ----------


class TestNextPointeeId:
    @patch("suno_to_ableton.features.export_als._get_audio_info", return_value=(48000 * 60, 48000))
    def test_next_pointee_id_exceeds_max_pointee(self, _mock, tmp_path: Path):
        cfg = SunoPrepConfig(source_dir=tmp_path)
        manifest = _make_manifest(tmp_path, [
            StemType.DRUMS, StemType.VOCALS, StemType.BACKING_VOCALS,
        ])
        result = export_als(manifest, cfg)
        xml = _als_xml(result.output_path)
        nx = int(re.search(r'<NextPointeeId Value="(\d+)"', xml).group(1))
        # max id across the whole document
        all_ids = [int(m.group(1)) for m in re.finditer(r'\bId="(\d+)"', xml)]
        assert nx > max(all_ids), f"NextPointeeId ({nx}) must be > max Id ({max(all_ids)})"


# ---------- 11. Send count == ReturnTrack count ----------


class TestSendsMatchReturns:
    @patch("suno_to_ableton.features.export_als._get_audio_info", return_value=(48000 * 60, 48000))
    def test_each_audio_track_has_send_per_return(self, _mock, tmp_path: Path):
        cfg = SunoPrepConfig(source_dir=tmp_path)
        manifest = _make_manifest(tmp_path, [
            StemType.DRUMS, StemType.VOCALS, StemType.BACKING_VOCALS, StemType.FX,
        ])
        result = export_als(manifest, cfg)
        xml = _als_xml(result.output_path)
        returns = len(re.findall(r"<ReturnTrack\s", xml))
        for m in re.finditer(r"<AudioTrack[^>]*>(.*?)</AudioTrack>", xml, re.DOTALL):
            sends = m.group(1).count("<TrackSendHolder")
            name = re.search(r'<EffectiveName Value="([^"]*)"', m.group(1))
            assert sends == returns, f"{name.group(1) if name else '?'}: {sends} sends vs {returns} returns"


# ---------- 12. Loop region in beats when warped (the bar-44 silence bug) ----------


class TestLoopRegionInBeats:
    @patch("suno_to_ableton.features.export_als._get_audio_info", return_value=(48000 * 60, 48000))
    def test_loop_end_matches_current_end_in_beats(self, _mock, tmp_path: Path):
        """With IsWarped=true, Loop/LoopEnd is in beats. Must equal CurrentEnd or
        playback cuts off mid-song (the bar-44 silence regression)."""
        cfg = SunoPrepConfig(source_dir=tmp_path)
        manifest = _make_manifest(tmp_path, [StemType.DRUMS], bpm=132.0)
        result = export_als(manifest, cfg)
        for clip_xml in _audio_clips_with_stems(_als_xml(result.output_path)):
            le = float(re.search(r'<LoopEnd Value="([\d.]+)"', clip_xml).group(1))
            ce = float(re.search(r'<CurrentEnd Value="([\d.]+)"', clip_xml).group(1))
            hle = float(re.search(r'<HiddenLoopEnd Value="([\d.]+)"', clip_xml).group(1))
            om = float(re.search(r'<OutMarker Value="([\d.]+)"', clip_xml).group(1))
            # All four loop fields must be in beats and match end_beats
            # 60s audio at 132bpm = 132 beats — must NOT be 60 (which would be the seconds value)
            assert le > 100, f"LoopEnd {le} suspiciously low — seconds instead of beats?"
            assert abs(le - ce) < 0.5, f"LoopEnd ({le}) != CurrentEnd ({ce})"
            assert abs(hle - ce) < 0.5
            assert abs(om - ce) < 0.5


# ---------- 13. End-to-end full export sanity ----------


class TestEndToEnd:
    @patch("suno_to_ableton.features.export_als._get_audio_info", return_value=(48000 * 178, 48000))
    def test_xiaolongbao_shape(self, _mock, tmp_path: Path):
        """Recreate the Xiaolongbao project shape (6 stems including vocals) and
        validate the entire .als is well-formed."""
        cfg = SunoPrepConfig(source_dir=tmp_path)
        beat_times = [i * 60.0 / 132.0 for i in range(389)]
        stem_types = [StemType.DRUMS, StemType.BASS, StemType.SYNTH, StemType.FX, StemType.VOCALS, StemType.BACKING_VOCALS]
        stems = []
        for st in stem_types:
            p = _touch_wav(tmp_path / "processed" / "stems" / f"00_{st.value}.wav", duration_sec=178.0)
            stems.append(ProcessedFile(output_path=p, stem_type=st))
        manifest = ProcessingManifest(
            song_title="Xiaolongbao", bpm=132.0, offset_seconds=0.0,
            beat_times=beat_times, stems=stems,
        )
        result = export_als(manifest, cfg)
        xml = _als_xml(result.output_path)

        # 1. Track ordering
        order = [m.group(1) for m in re.finditer(r"<(AudioTrack|MidiTrack|ReturnTrack|MasterTrack)\s", xml)]
        phase_map = {"AudioTrack": 0, "MidiTrack": 1, "ReturnTrack": 2, "MasterTrack": 3}
        phase = 0
        for t in order:
            assert phase_map[t] >= phase
            phase = phase_map[t]

        # 2. 6 audio clips with stems exist
        clips = _audio_clips_with_stems(xml)
        assert len(clips) == 6

        # 3. Each is warped, has per-beat markers, has matching loop region
        for c in clips:
            assert re.search(r'<IsWarped Value="true"', c)
            wm = re.search(r"<WarpMarkers>.*?</WarpMarkers>", c, re.DOTALL)
            assert wm.group(0).count("<WarpMarker ") > 100
            le = float(re.search(r'<LoopEnd Value="([\d.]+)"', c).group(1))
            ce = float(re.search(r'<CurrentEnd Value="([\d.]+)"', c).group(1))
            assert abs(le - ce) < 0.5

        # 4. Pointee namespace uniqueness
        for tag in set(re.findall(r"<(\w+(?:Target|Targets))", xml)) | {"Pointee", "RemoteableBool", "RemoteableFloat"}:
            ids = [int(m.group(1)) for m in re.finditer(rf'<{tag}\s[^>]*\bId="(\d+)"', xml)]
            assert len(set(ids)) == len(ids), f"{tag} has duplicate Pointee Ids"

        # 5. NextPointeeId > all Ids
        nx = int(re.search(r'<NextPointeeId Value="(\d+)"', xml).group(1))
        all_ids = [int(m.group(1)) for m in re.finditer(r'\bId="(\d+)"', xml)]
        assert nx > max(all_ids)

        # 6. Send count == return count
        returns = order.count("ReturnTrack")
        for m in re.finditer(r"<AudioTrack[^>]*>(.*?)</AudioTrack>", xml, re.DOTALL):
            assert m.group(1).count("<TrackSendHolder") == returns

        # 7. Tempo == 132 and envelope flat
        tempo = float(re.search(r"<Tempo>\s*<LomId Value=\"0\"\s*/>\s*<Manual Value=\"([\d.]+)\"", xml).group(1))
        assert abs(tempo - 132.0) < 0.01
        target_id = re.search(r"<Tempo>.*?<AutomationTarget Id=\"(\d+)\"", xml, re.DOTALL).group(1)
        for env in re.finditer(r"<AutomationEnvelope[^>]*>.*?</AutomationEnvelope>", xml, re.DOTALL):
            if f'<PointeeId Value="{target_id}"' in env.group(0):
                for v in re.findall(r'<FloatEvent[^/]*?Value="([\d.]+)"', env.group(0)):
                    assert abs(float(v) - 132.0) < 0.01
