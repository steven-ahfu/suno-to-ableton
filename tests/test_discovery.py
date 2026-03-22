"""Tests for file discovery and classification."""

from pathlib import Path
from unittest.mock import patch

from suno_to_ableton.discovery import (
    AUDIO_EXTENSIONS,
    MIDI_EXTENSIONS,
    NUMBERED_STEM_RE,
    _classify_stem_name,
    _sanitize_title,
    discover_project,
    scan_for_projects,
)
from suno_to_ableton.models import FileRole, StemType


class TestClassifyStemName:
    def test_exact_match(self):
        assert _classify_stem_name("drums") == StemType.DRUMS
        assert _classify_stem_name("bass") == StemType.BASS
        assert _classify_stem_name("vocals") == StemType.VOCALS

    def test_case_insensitive(self):
        assert _classify_stem_name("Drums") == StemType.DRUMS
        assert _classify_stem_name("BASS") == StemType.BASS
        assert _classify_stem_name("Vocals") == StemType.VOCALS

    def test_underscore_mapping(self):
        assert _classify_stem_name("backing_vocals") == StemType.BACKING_VOCALS
        assert _classify_stem_name("Backing_Vocals") == StemType.BACKING_VOCALS

    def test_space_to_underscore(self):
        assert _classify_stem_name("backing vocals") == StemType.BACKING_VOCALS

    def test_parenthetical_midi_style_name(self):
        assert _classify_stem_name("untitled again (Drums)") == StemType.DRUMS
        assert _classify_stem_name("My Song (Backing Vocals)") == StemType.BACKING_VOCALS

    def test_unknown_returns_other(self):
        assert _classify_stem_name("guitar") == StemType.OTHER
        assert _classify_stem_name("random") == StemType.OTHER

    def test_whitespace_stripped(self):
        assert _classify_stem_name("  drums  ") == StemType.DRUMS


class TestSanitizeTitle:
    def test_strips_remix_suffix(self):
        assert _sanitize_title("Cool Song - remix") == "Cool Song"
        assert _sanitize_title("Cool Song - Remix") == "Cool Song"
        assert _sanitize_title("Cool Song remix") == "Cool Song"
        assert _sanitize_title("Cool Song Remix") == "Cool Song"

    def test_no_change_needed(self):
        assert _sanitize_title("Cool Song") == "Cool Song"

    def test_strips_whitespace(self):
        assert _sanitize_title("  Cool Song  ") == "Cool Song"


class TestNumberedStemRegex:
    def test_matches_numbered_stems(self):
        assert NUMBERED_STEM_RE.match("0 Song")
        assert NUMBERED_STEM_RE.match("1 Drums")
        assert NUMBERED_STEM_RE.match("2 Bass")
        assert NUMBERED_STEM_RE.match("10 Backing Vocals")

    def test_captures_groups(self):
        m = NUMBERED_STEM_RE.match("3 Synth")
        assert m.group(1) == "3"
        assert m.group(2) == "Synth"

    def test_no_match(self):
        assert NUMBERED_STEM_RE.match("Song") is None
        assert NUMBERED_STEM_RE.match("Drums") is None


class TestExtensions:
    def test_audio_extensions(self):
        assert ".wav" in AUDIO_EXTENSIONS
        assert ".flac" in AUDIO_EXTENSIONS
        assert ".mp3" in AUDIO_EXTENSIONS

    def test_midi_extensions(self):
        assert ".mid" in MIDI_EXTENSIONS
        assert ".midi" in MIDI_EXTENSIONS


class TestDiscoverProject:
    def test_nonexistent_directory(self, tmp_path):
        inv = discover_project(tmp_path / "nonexistent")
        assert inv.full_mix is None
        assert inv.stems == []
        assert any("does not exist" in w for w in inv.warnings)

    def test_empty_directory(self, tmp_path):
        inv = discover_project(tmp_path)
        assert inv.full_mix is None
        assert inv.stems == []
        assert any("No audio files found" in w for w in inv.warnings)
        assert any("No MIDI files found" in w for w in inv.warnings)

    def test_midi_only(self, tmp_path):
        (tmp_path / "song.mid").touch()
        inv = discover_project(tmp_path)
        assert len(inv.midi_files) == 1
        assert inv.midi_files[0].role == FileRole.MIDI
        assert inv.song_title == "song"

    @patch("suno_to_ableton.discovery._probe_audio", return_value={
        "sample_rate": 44100, "channels": 2, "frames": 100000,
        "duration_seconds": 2.27, "subtype": "PCM_16",
    })
    def test_numbered_stems(self, mock_probe, tmp_path):
        (tmp_path / "0 Cool Song.wav").touch()
        (tmp_path / "1 Drums.wav").touch()
        (tmp_path / "2 Bass.wav").touch()

        inv = discover_project(tmp_path)

        assert inv.full_mix is not None
        assert inv.full_mix.stem_type == StemType.FULL_MIX
        assert inv.full_mix.track_number == 0
        assert inv.song_title == "Cool Song"

        assert len(inv.stems) == 2
        assert inv.stems[0].stem_type == StemType.DRUMS
        assert inv.stems[1].stem_type == StemType.BASS

    @patch("suno_to_ableton.discovery._probe_audio", return_value={
        "sample_rate": 44100, "channels": 2, "frames": 100000,
        "duration_seconds": 2.27, "subtype": "PCM_16",
    })
    def test_zero_indexed_stem_export_without_full_mix(self, mock_probe, tmp_path):
        (tmp_path / "0 Drums.wav").touch()
        (tmp_path / "1 Bass.wav").touch()
        (tmp_path / "Song (Drums).mid").touch()

        inv = discover_project(tmp_path)

        assert inv.full_mix is None
        assert [stem.stem_type for stem in inv.stems] == [StemType.DRUMS, StemType.BASS]
        assert [stem.track_number for stem in inv.stems] == [0, 1]
        assert inv.song_title == "Song"

    @patch("suno_to_ableton.discovery._probe_audio", return_value={})
    def test_unnumbered_audio_warns(self, mock_probe, tmp_path):
        (tmp_path / "random_audio.wav").touch()

        inv = discover_project(tmp_path)
        assert len(inv.stems) == 1
        assert any("without track number" in w for w in inv.warnings)

    @patch("suno_to_ableton.discovery._probe_audio", return_value={
        "sample_rate": 44100, "channels": 2, "frames": 100000,
        "duration_seconds": 2.27, "subtype": "PCM_16",
    })
    def test_stems_sorted_by_track_number(self, mock_probe, tmp_path):
        (tmp_path / "3 Synth.wav").touch()
        (tmp_path / "1 Drums.wav").touch()
        (tmp_path / "2 Bass.wav").touch()

        inv = discover_project(tmp_path)
        track_nums = [s.track_number for s in inv.stems]
        assert track_nums == [1, 2, 3]

    def test_ignores_non_audio_files(self, tmp_path):
        (tmp_path / "readme.txt").touch()
        (tmp_path / "image.png").touch()
        inv = discover_project(tmp_path)
        assert inv.stems == []

    @patch("suno_to_ableton.discovery._probe_audio")
    def test_inconsistent_sample_rates_warns(self, mock_probe, tmp_path):
        call_count = {"n": 0}

        def varying_probe(path):
            call_count["n"] += 1
            sr = 44100 if call_count["n"] == 1 else 48000
            return {
                "sample_rate": sr, "channels": 2, "frames": 100000,
                "duration_seconds": 2.27, "subtype": "PCM_16",
            }

        mock_probe.side_effect = varying_probe
        (tmp_path / "1 Drums.wav").touch()
        (tmp_path / "2 Bass.wav").touch()

        inv = discover_project(tmp_path)
        assert any("Inconsistent sample rates" in w for w in inv.warnings)

    def test_midi_title_sanitized(self, tmp_path):
        (tmp_path / "Cool Song - Remix.mid").touch()
        inv = discover_project(tmp_path)
        assert inv.song_title == "Cool Song"

    def test_midi_stem_type_inferred_from_parenthetical_name(self, tmp_path):
        (tmp_path / "Cool Song (Bass).mid").touch()
        inv = discover_project(tmp_path)
        assert len(inv.midi_files) == 1
        assert inv.midi_files[0].stem_type == StemType.BASS


class TestScanForProjects:
    def test_empty_directory(self, tmp_path):
        results = scan_for_projects(tmp_path)
        assert results == []

    def test_nonexistent_directory(self, tmp_path):
        results = scan_for_projects(tmp_path / "nope")
        assert results == []

    def test_finds_project_with_numbered_audio(self, tmp_path):
        project = tmp_path / "my_song"
        project.mkdir()
        (project / "0 Song.wav").touch()
        (project / "1 Drums.wav").touch()

        results = scan_for_projects(tmp_path)
        assert len(results) == 1
        assert results[0][0] == project
        assert results[0][1] == "Song"

    def test_finds_project_with_midi_and_audio(self, tmp_path):
        project = tmp_path / "track"
        project.mkdir()
        (project / "song.mid").touch()
        (project / "audio.wav").touch()

        results = scan_for_projects(tmp_path)
        assert len(results) == 1

    def test_skips_processed_directory(self, tmp_path):
        processed = tmp_path / "processed"
        processed.mkdir()
        (processed / "0 Song.wav").touch()

        results = scan_for_projects(tmp_path)
        assert results == []

    def test_skips_git_directory(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "0 Song.wav").touch()

        results = scan_for_projects(tmp_path)
        assert results == []

    def test_finds_nested_projects(self, tmp_path):
        p1 = tmp_path / "songs" / "song1"
        p1.mkdir(parents=True)
        (p1 / "0 First Song.wav").touch()

        p2 = tmp_path / "songs" / "song2"
        p2.mkdir(parents=True)
        (p2 / "0 Second Song.wav").touch()

        results = scan_for_projects(tmp_path)
        assert len(results) == 2
        titles = {r[1] for r in results}
        assert "First Song" in titles
        assert "Second Song" in titles

    def test_max_depth_respected(self, tmp_path):
        deep = tmp_path
        for i in range(8):
            deep = deep / f"level{i}"
        deep.mkdir(parents=True)
        (deep / "0 Deep Song.wav").touch()

        results = scan_for_projects(tmp_path, max_depth=3)
        assert results == []

    def test_no_midi_only_project(self, tmp_path):
        project = tmp_path / "midi_only"
        project.mkdir()
        (project / "song.mid").touch()
        # MIDI alone without audio should not be found
        results = scan_for_projects(tmp_path)
        assert results == []
