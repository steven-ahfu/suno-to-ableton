"""BPM detection and rhythm analysis using librosa."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np

from .models import BPMResult, DiscoveredFile, ProjectInventory, StemType


def _select_rhythm_source(inventory: ProjectInventory) -> Path | None:
    """Pick the best audio file for rhythm analysis.

    Priority: drums → percussion → full mix → first stem.
    """
    # Look for drums stem
    for stem in inventory.stems:
        if stem.stem_type == StemType.DRUMS:
            return stem.path

    # Look for percussion stem
    for stem in inventory.stems:
        if stem.stem_type == StemType.PERCUSSION:
            return stem.path

    # Fall back to full mix
    if inventory.full_mix:
        return inventory.full_mix.path

    # Last resort: first stem
    if inventory.stems:
        return inventory.stems[0].path

    return None


def _detect_leading_silence(y: np.ndarray, sr: int, hop_length: int = 512) -> float:
    """Find the leading silence duration using RMS energy."""
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    peak = rms.max()
    if peak == 0:
        return 0.0

    threshold = peak * 0.01
    for i, val in enumerate(rms):
        if val >= threshold:
            return librosa.frames_to_time(i, sr=sr, hop_length=hop_length)
    return 0.0


def _compute_confidence(
    onset_envelope: np.ndarray, sr: int, hop_length: int, bpm: float
) -> float:
    """Estimate BPM confidence from tempogram autocorrelation peak."""
    tempogram = librosa.feature.tempogram(
        onset_envelope=onset_envelope, sr=sr, hop_length=hop_length
    )
    # Global mean tempogram
    avg_tempogram = tempogram.mean(axis=1)
    if avg_tempogram.max() == 0:
        return 0.0

    # Normalize
    avg_tempogram = avg_tempogram / avg_tempogram.max()

    # Find the bin corresponding to the detected BPM
    tempi = librosa.tempo_frequencies(len(avg_tempogram), sr=sr, hop_length=hop_length)
    closest_idx = np.argmin(np.abs(tempi - bpm))
    confidence = float(avg_tempogram[closest_idx])

    return min(max(confidence, 0.0), 1.0)


def analyze_bpm(audio_path: Path) -> BPMResult:
    """Run full BPM analysis on an audio file."""
    # Load at native sample rate, mono
    y, sr = librosa.load(str(audio_path), sr=None, mono=True)

    hop_length = 512

    # Onset strength envelope
    onset_envelope = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)

    # Global tempo estimate
    tempo = librosa.feature.tempo(
        onset_envelope=onset_envelope, sr=sr, hop_length=hop_length, start_bpm=120
    )
    bpm = float(tempo[0]) if hasattr(tempo, "__len__") else float(tempo)

    # Beat tracking
    _, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_envelope, sr=sr, hop_length=hop_length, bpm=bpm
    )
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length)

    # Onset detection
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_envelope, sr=sr, hop_length=hop_length, backtrack=True
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)

    # Leading silence
    leading_silence = _detect_leading_silence(y, sr, hop_length)

    # Confidence
    confidence = _compute_confidence(onset_envelope, sr, hop_length, bpm)

    # First downbeat
    downbeat_time = float(beat_times[0]) if len(beat_times) > 0 else 0.0

    # Clamp BPM to Ableton's valid range (20–999)
    bpm = max(20.0, min(999.0, bpm))

    return BPMResult(
        bpm=bpm,
        confidence=confidence,
        beat_times=[float(t) for t in beat_times],
        downbeat_time=downbeat_time,
        onset_times=[float(t) for t in onset_times],
        leading_silence=leading_silence,
    )


def analyze_bpm_from_inventory(inventory: ProjectInventory) -> BPMResult:
    """Analyze BPM using the best available rhythm source."""
    path = _select_rhythm_source(inventory)
    if path is None:
        raise ValueError("No audio files available for BPM analysis")
    return analyze_bpm(path)
