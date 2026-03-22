"""Tests for data models."""

from pathlib import Path

from suno_to_ableton.models import (
    AlignmentResult,
    BPMResult,
    DiscoveredFile,
    FeatureInvocation,
    FileRole,
    MIDICleanupResult,
    ProcessedFile,
    ProcessingManifest,
    ProjectInventory,
    StemType,
    STEM_NAME_MAP,
)


class TestStemType:
    def test_all_stem_types_have_values(self):
        expected = {
            "drums", "bass", "vocals", "backing_vocals", "synth",
            "fx", "percussion", "sample", "full_mix", "other",
        }
        assert {s.value for s in StemType} == expected

    def test_stem_name_map_covers_key_types(self):
        assert STEM_NAME_MAP["drums"] == StemType.DRUMS
        assert STEM_NAME_MAP["bass"] == StemType.BASS
        assert STEM_NAME_MAP["vocals"] == StemType.VOCALS
        assert STEM_NAME_MAP["backing_vocals"] == StemType.BACKING_VOCALS
        assert STEM_NAME_MAP["synth"] == StemType.SYNTH
        assert STEM_NAME_MAP["fx"] == StemType.FX


class TestDiscoveredFile:
    def test_minimal_construction(self):
        f = DiscoveredFile(path=Path("/tmp/test.wav"), role=FileRole.AUDIO_STEM)
        assert f.path == Path("/tmp/test.wav")
        assert f.role == FileRole.AUDIO_STEM
        assert f.stem_type == StemType.OTHER
        assert f.track_number is None
        assert f.sample_rate is None

    def test_full_construction(self):
        f = DiscoveredFile(
            path=Path("/tmp/1 Drums.wav"),
            role=FileRole.AUDIO_STEM,
            stem_type=StemType.DRUMS,
            track_number=1,
            stem_name="Drums",
            sample_rate=44100,
            channels=2,
            frames=100000,
            duration_seconds=2.27,
        )
        assert f.track_number == 1
        assert f.stem_type == StemType.DRUMS
        assert f.duration_seconds == 2.27


class TestProjectInventory:
    def test_empty_inventory(self):
        inv = ProjectInventory(source_dir=Path("/tmp"))
        assert inv.full_mix is None
        assert inv.stems == []
        assert inv.midi_files == []
        assert inv.song_title == ""
        assert inv.warnings == []

    def test_inventory_with_stems(self):
        stem = DiscoveredFile(
            path=Path("/tmp/1 Drums.wav"),
            role=FileRole.AUDIO_STEM,
            stem_type=StemType.DRUMS,
        )
        inv = ProjectInventory(source_dir=Path("/tmp"), stems=[stem])
        assert len(inv.stems) == 1
        assert inv.stems[0].stem_type == StemType.DRUMS


class TestBPMResult:
    def test_defaults(self):
        r = BPMResult(bpm=120.0)
        assert r.bpm == 120.0
        assert r.confidence == 0.0
        assert r.beat_times == []
        assert r.downbeat_time == 0.0

    def test_full_construction(self):
        r = BPMResult(
            bpm=128.5,
            confidence=0.92,
            beat_times=[0.0, 0.468, 0.937],
            downbeat_time=0.05,
            onset_times=[0.01, 0.47],
            leading_silence=0.03,
        )
        assert r.bpm == 128.5
        assert len(r.beat_times) == 3
        assert r.leading_silence == 0.03


class TestAlignmentResult:
    def test_construction(self):
        r = AlignmentResult(
            offset_seconds=0.05,
            offset_samples=2400,
            bpm=120.0,
            samples_per_beat=24000.0,
        )
        assert r.offset_seconds == 0.05
        assert r.offset_samples == 2400


class TestProcessingManifest:
    def test_defaults(self):
        m = ProcessingManifest()
        assert m.song_title == ""
        assert m.bpm is None
        assert m.target_sr == 48000
        assert m.stems == []
        assert m.midi_files == []
        assert m.generated_stems == []
        assert m.warnings == []
        assert m.features_invoked == []

    def test_with_processed_files(self):
        pf = ProcessedFile(
            output_path=Path("/out/drums.wav"),
            stem_type=StemType.DRUMS,
            processing_steps=["resample", "trim"],
        )
        m = ProcessingManifest(stems=[pf])
        assert len(m.stems) == 1
        assert m.stems[0].processing_steps == ["resample", "trim"]

    def test_feature_invocation(self):
        fi = FeatureInvocation(
            feature="detect-sections",
            mode="report",
            confidence=0.85,
            recommendation="4 sections detected",
        )
        m = ProcessingManifest(features_invoked=[fi])
        assert m.features_invoked[0].feature == "detect-sections"
        assert m.features_invoked[0].confidence == 0.85


class TestMIDICleanupResult:
    def test_defaults(self):
        r = MIDICleanupResult(
            input_path=Path("/in/song.mid"),
            output_path=Path("/out/song.mid"),
        )
        assert r.tracks_removed == 0
        assert r.notes_quantized == 0
        assert r.tempo_set == 0.0
        assert r.warnings == []
