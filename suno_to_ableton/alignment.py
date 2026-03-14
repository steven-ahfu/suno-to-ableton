"""Global offset computation for stem/MIDI alignment."""

from __future__ import annotations

from .models import AlignmentResult, BPMResult


def compute_alignment(bpm_result: BPMResult, target_sr: int = 48000) -> AlignmentResult:
    """Compute the global alignment offset from BPM analysis.

    The offset is the time of the first detected downbeat. All stems and
    MIDI files are trimmed by this amount so beat 1 lands at sample 0.
    """
    offset_seconds = bpm_result.downbeat_time
    offset_samples = round(offset_seconds * target_sr)
    samples_per_beat = (60.0 / bpm_result.bpm) * target_sr

    return AlignmentResult(
        offset_seconds=offset_seconds,
        offset_samples=offset_samples,
        bpm=bpm_result.bpm,
        samples_per_beat=samples_per_beat,
    )
