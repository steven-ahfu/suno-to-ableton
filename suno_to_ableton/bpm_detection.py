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


def _detect_downbeat_phase(
    y: np.ndarray,
    sr: int,
    beat_frames: np.ndarray,
    beats_per_bar: int = 4,
    hop_length: int = 512,
) -> int:
    """Vote across {0..beats_per_bar-1} for the phase whose beats carry the most kick energy.

    Suno (and most pop/dance) puts a kick on beat 1 of every bar. We compute a low-band
    onset envelope, then for each candidate phase p we sum the envelope value at every
    beat at indices [p, p+N, p+2N, ...]. The phase with maximum total wins.
    """
    if len(beat_frames) < beats_per_bar:
        return 0
    low = librosa.effects.preemphasis(y, coef=-0.97)
    low_onset = librosa.onset.onset_strength(
        y=low, sr=sr, hop_length=hop_length, fmax=200, n_mels=32
    )
    n_frames = len(low_onset)
    scores = []
    for phase in range(beats_per_bar):
        idxs = beat_frames[phase::beats_per_bar]
        idxs = idxs[idxs < n_frames]
        scores.append(float(low_onset[idxs].sum()) if len(idxs) else 0.0)
    return int(np.argmax(scores))


def analyze_bpm(audio_path: Path, detect_downbeat: bool = True) -> BPMResult:
    """Run full BPM analysis on an audio file."""
    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    hop_length = 512

    onset_envelope = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    tempo = librosa.feature.tempo(
        onset_envelope=onset_envelope, sr=sr, hop_length=hop_length, start_bpm=120
    )
    bpm = float(tempo[0]) if hasattr(tempo, "__len__") else float(tempo)

    _, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_envelope, sr=sr, hop_length=hop_length, bpm=bpm
    )
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length)

    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_envelope, sr=sr, hop_length=hop_length, backtrack=True
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)

    leading_silence = _detect_leading_silence(y, sr, hop_length)
    confidence = _compute_confidence(onset_envelope, sr, hop_length, bpm)

    if detect_downbeat and len(beat_frames) > 0:
        phase = _detect_downbeat_phase(y, sr, np.asarray(beat_frames), 4, hop_length)
        downbeat_time = float(beat_times[phase]) if phase < len(beat_times) else float(beat_times[0])
    else:
        downbeat_time = float(beat_times[0]) if len(beat_times) > 0 else 0.0

    bpm = max(20.0, min(999.0, bpm))

    return BPMResult(
        bpm=bpm,
        confidence=confidence,
        beat_times=[float(t) for t in beat_times],
        downbeat_time=downbeat_time,
        onset_times=[float(t) for t in onset_times],
        leading_silence=leading_silence,
    )


def analyze_bpm_from_inventory(
    inventory: ProjectInventory, detect_downbeat: bool = True
) -> BPMResult:
    path = _select_rhythm_source(inventory)
    if path is None:
        raise ValueError("No audio files available for BPM analysis")
    return analyze_bpm(path, detect_downbeat=detect_downbeat)
