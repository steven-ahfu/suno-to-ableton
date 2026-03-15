"""Tests for alignment computation."""

from suno_to_ableton.alignment import compute_alignment
from suno_to_ableton.models import BPMResult


class TestComputeAlignment:
    def test_basic_alignment(self):
        bpm = BPMResult(bpm=120.0, downbeat_time=0.5)
        result = compute_alignment(bpm, target_sr=48000)

        assert result.bpm == 120.0
        assert result.offset_seconds == 0.5
        assert result.offset_samples == 24000  # 0.5 * 48000
        # At 120 BPM: 60/120 = 0.5s per beat * 48000 = 24000 samples/beat
        assert result.samples_per_beat == 24000.0

    def test_zero_downbeat(self):
        bpm = BPMResult(bpm=140.0, downbeat_time=0.0)
        result = compute_alignment(bpm, target_sr=48000)

        assert result.offset_seconds == 0.0
        assert result.offset_samples == 0

    def test_different_sample_rate(self):
        bpm = BPMResult(bpm=120.0, downbeat_time=0.1)
        result = compute_alignment(bpm, target_sr=44100)

        assert result.offset_samples == round(0.1 * 44100)
        # 60/120 * 44100 = 22050
        assert result.samples_per_beat == 22050.0

    def test_fractional_bpm(self):
        bpm = BPMResult(bpm=128.5, downbeat_time=0.05)
        result = compute_alignment(bpm, target_sr=48000)

        assert result.bpm == 128.5
        expected_spb = (60.0 / 128.5) * 48000
        assert abs(result.samples_per_beat - expected_spb) < 0.001

    def test_high_bpm(self):
        bpm = BPMResult(bpm=180.0, downbeat_time=0.02)
        result = compute_alignment(bpm, target_sr=48000)

        assert result.offset_samples == round(0.02 * 48000)
        expected_spb = (60.0 / 180.0) * 48000
        assert result.samples_per_beat == expected_spb
