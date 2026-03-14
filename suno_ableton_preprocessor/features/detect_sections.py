"""Estimate rough arrangement boundaries (intro/verse/chorus/bridge/outro)."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
from scipy.ndimage import median_filter

from ..config import SunoPrepConfig
from ..models import (
    FeatureInvocation,
    Section,
    SectionDetectionResult,
)
from ..reporting import write_json_report


# Heuristic section labels based on position and energy
_SECTION_LABELS = ["intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro"]


def detect_sections(
    audio_path: Path,
    bpm: float,
    config: SunoPrepConfig,
) -> SectionDetectionResult:
    """Detect arrangement sections using spectral clustering."""
    y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
    duration = len(y) / sr
    beat_duration = 60.0 / bpm
    bar_duration = beat_duration * 4  # assumes 4/4 — Suno exports are always 4/4

    # Compute MFCCs for self-similarity
    hop_length = 512
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=hop_length)

    # Compute self-similarity via recurrence matrix
    R = librosa.segment.recurrence_matrix(
        mfcc, mode="affinity", sym=True, width=3
    )

    # Novelty curve via checkerboard kernel on recurrence matrix
    # (librosa.segment.novelty was removed in 0.11)
    n = R.shape[0]
    kernel_size = min(64, n // 4)
    novelty = np.zeros(n)
    for i in range(kernel_size, n - kernel_size):
        block = R[i - kernel_size : i + kernel_size, i - kernel_size : i + kernel_size]
        k = kernel_size
        # Checkerboard kernel: positive in off-diagonal blocks, negative in diagonal
        tl = block[:k, :k].mean()
        br = block[k:, k:].mean()
        tr = block[:k, k:].mean()
        bl = block[k:, :k].mean()
        novelty[i] = (tl + br) - (tr + bl)
    novelty = np.maximum(novelty, 0)
    # Smooth
    if len(novelty) > 5:
        novelty = median_filter(novelty, size=5)

    # Peak-pick to find section boundaries
    # Use a minimum distance of ~4 bars
    min_frames = int((bar_duration * 4 * sr) / hop_length)
    novelty = novelty.astype(np.float64)
    peaks = librosa.util.peak_pick(
        novelty,
        pre_max=min_frames // 2,
        post_max=min_frames // 2,
        pre_avg=min_frames,
        post_avg=min_frames,
        delta=float(np.std(novelty) * 0.3),
        wait=min_frames,
    )

    # Convert frame indices to times
    boundary_times = librosa.frames_to_time(peaks, sr=sr, hop_length=hop_length)
    boundary_times = [0.0] + list(boundary_times) + [duration]

    # Compute RMS energy per segment for labeling
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    segment_energies = []
    for i in range(len(boundary_times) - 1):
        start_frame = librosa.time_to_frames(boundary_times[i], sr=sr, hop_length=hop_length)
        end_frame = librosa.time_to_frames(boundary_times[i + 1], sr=sr, hop_length=hop_length)
        start_frame = max(0, min(start_frame, len(rms) - 1))
        end_frame = max(start_frame + 1, min(end_frame, len(rms)))
        segment_energies.append(float(np.mean(rms[start_frame:end_frame])))

    # Assign labels heuristically
    sections = []
    energy_threshold = np.median(segment_energies) if segment_energies else 0
    n_segments = len(boundary_times) - 1

    for i in range(n_segments):
        start = boundary_times[i]
        end = boundary_times[i + 1]

        # Bar estimates (1-indexed)
        start_bar = max(1, round(start / bar_duration) + 1)
        end_bar = max(start_bar, round(end / bar_duration) + 1)

        # Label assignment
        if i < len(_SECTION_LABELS):
            label = _SECTION_LABELS[i]
        else:
            label = "chorus" if segment_energies[i] > energy_threshold else "verse"

        # Override first/last
        if i == 0 and (end - start) < bar_duration * 8:
            label = "intro"
        if i == n_segments - 1:
            label = "outro"

        # Confidence based on novelty peak strength
        if i > 0 and i - 1 < len(peaks):
            peak_idx = peaks[i - 1]
            if peak_idx < len(novelty):
                confidence = min(1.0, float(novelty[peak_idx]) / (np.max(novelty) + 1e-8))
            else:
                confidence = 0.3
        else:
            confidence = 0.5

        sections.append(Section(
            label=label,
            start_time=round(start, 3),
            end_time=round(end, 3),
            start_bar=start_bar,
            end_bar=end_bar,
            confidence=round(confidence, 2),
        ))

    return SectionDetectionResult(
        sections=sections,
        method="mfcc_recurrence_novelty",
    )


def run_detect_sections(
    audio_path: Path,
    bpm: float,
    config: SunoPrepConfig,
) -> tuple[SectionDetectionResult, FeatureInvocation]:
    """Entry point for detect-sections feature."""
    invocation = FeatureInvocation(
        feature="detect_sections",
        mode="report",  # always report-only
    )

    try:
        result = detect_sections(audio_path, bpm, config)

        if not config.dry_run:
            import json
            report_data = json.loads(result.model_dump_json())
            write_json_report(report_data, "sections.json", config)
            invocation.output_files.append(config.reports_dir / "sections.json")

        invocation.recommendation = f"{len(result.sections)} sections detected"
        if result.sections:
            labels = [s.label for s in result.sections]
            invocation.recommendation += f": {', '.join(labels)}"

    except Exception as e:
        invocation.warnings.append(f"detect-sections failed: {e}")
        result = SectionDetectionResult()

    return result, invocation
