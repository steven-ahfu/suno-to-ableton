"""Compare original Suno stems vs regenerated stems using QC metrics."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np

from ..config import SunoPrepConfig
from ..models import (
    FeatureInvocation,
    StemComparisonEntry,
    StemComparisonMetrics,
    StemComparisonResult,
    StemType,
)
from ..reporting import write_json_report


def _compute_metrics(audio_path: Path) -> StemComparisonMetrics:
    """Compute QC metrics for a single audio file."""
    y, sr = librosa.load(str(audio_path), sr=None, mono=True)

    # RMS energy
    rms = float(np.sqrt(np.mean(y ** 2)))

    # Spectral centroid mean
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    centroid_mean = float(np.mean(centroid))

    # Silence ratio (frames below 1% of peak RMS)
    rms_frames = librosa.feature.rms(y=y)[0]
    peak = rms_frames.max()
    if peak > 0:
        silence_ratio = float(np.mean(rms_frames < peak * 0.01))
    else:
        silence_ratio = 1.0

    return StemComparisonMetrics(
        rms_energy=rms,
        spectral_centroid_mean=centroid_mean,
        silence_ratio=silence_ratio,
        correlation=0.0,  # filled in during comparison
    )


def _compute_correlation(path_a: Path, path_b: Path) -> float:
    """Cross-correlation between two audio files (similarity score)."""
    y_a, _ = librosa.load(str(path_a), sr=22050, mono=True)
    y_b, _ = librosa.load(str(path_b), sr=22050, mono=True)

    # Truncate to same length
    min_len = min(len(y_a), len(y_b))
    y_a = y_a[:min_len]
    y_b = y_b[:min_len]

    # Normalized cross-correlation
    norm = np.linalg.norm(y_a) * np.linalg.norm(y_b)
    if norm == 0:
        return 0.0
    return float(np.dot(y_a, y_b) / norm)


def compare_stems(
    original_stems_dir: Path,
    generated_stems_dir: Path,
    config: SunoPrepConfig,
) -> StemComparisonResult:
    """Compare original stems vs generated stems and produce recommendations."""
    result = StemComparisonResult()

    if not generated_stems_dir.exists():
        return result

    # Map generated stems by stem type
    generated_files: dict[str, Path] = {}
    for f in generated_stems_dir.iterdir():
        if f.suffix.lower() == ".wav":
            generated_files[f.stem.lower()] = f

    # Map original stems by stem type
    original_files: dict[str, Path] = {}
    for f in original_stems_dir.iterdir():
        if f.suffix.lower() == ".wav":
            # Extract stem type from filename like "05_drums.wav"
            parts = f.stem.split("_", 1)
            if len(parts) == 2:
                original_files[parts[1].lower()] = f

    # Compare overlapping stem types
    all_types = set(original_files.keys()) | set(generated_files.keys())
    for stem_name in sorted(all_types):
        orig = original_files.get(stem_name)
        gen = generated_files.get(stem_name)

        entry = StemComparisonEntry()

        # Map name to StemType
        for st in StemType:
            if st.value == stem_name:
                entry.stem_type = st
                break

        if orig:
            entry.original_path = orig
            entry.original_metrics = _compute_metrics(orig)
        if gen:
            entry.generated_path = gen
            entry.generated_metrics = _compute_metrics(gen)

        # Compute correlation if both exist
        if orig and gen:
            corr = _compute_correlation(orig, gen)
            if entry.original_metrics:
                entry.original_metrics.correlation = corr
            if entry.generated_metrics:
                entry.generated_metrics.correlation = corr

            # Recommendation heuristic:
            # Prefer lower silence ratio (more content)
            # and higher RMS (more energy)
            orig_score = 0.0
            gen_score = 0.0
            if entry.original_metrics and entry.generated_metrics:
                # Less silence is better
                if entry.original_metrics.silence_ratio < entry.generated_metrics.silence_ratio:
                    orig_score += 1
                else:
                    gen_score += 1
                # More energy is better
                if entry.original_metrics.rms_energy > entry.generated_metrics.rms_energy:
                    orig_score += 1
                else:
                    gen_score += 1

            entry.recommendation = "original" if orig_score >= gen_score else "generated"
            entry.confidence = abs(orig_score - gen_score) / 2.0
        elif orig:
            entry.recommendation = "original"
            entry.confidence = 1.0
        else:
            entry.recommendation = "generated"
            entry.confidence = 1.0

        result.comparisons.append(entry)

    return result


def apply_stem_choices(
    result: StemComparisonResult,
    output_stems_dir: Path,
    config: SunoPrepConfig,
) -> list[Path]:
    """Copy preferred stems to the output directory. Returns list of applied paths."""
    import shutil

    applied = []
    for entry in result.comparisons:
        src = (
            entry.generated_path
            if entry.recommendation == "generated"
            else entry.original_path
        )
        if src and src.exists():
            dest = output_stems_dir / src.name
            if not config.dry_run:
                shutil.copy2(src, dest)
            applied.append(dest)
    return applied


def run_choose_stems(
    config: SunoPrepConfig,
    apply: bool = False,
) -> tuple[StemComparisonResult, FeatureInvocation]:
    """Entry point for choose-stems feature."""
    invocation = FeatureInvocation(
        feature="choose_stems",
        mode="apply" if apply else "report",
    )

    result = StemComparisonResult()
    try:
        result = compare_stems(
            config.stems_dir,
            config.generated_stems_dir,
            config,
        )

        if apply:
            applied = apply_stem_choices(result, config.stems_dir, config)
            result.applied = True
            invocation.output_files = applied

        # Write report
        if not config.dry_run:
            import json
            report_data = json.loads(result.model_dump_json())
            write_json_report(report_data, "stem_comparison.json", config)
            invocation.output_files.append(config.reports_dir / "stem_comparison.json")

        # Summary
        if result.comparisons:
            recs = [c.recommendation for c in result.comparisons]
            invocation.recommendation = (
                f"{recs.count('original')} original, {recs.count('generated')} generated"
            )
            avg_conf = sum(c.confidence for c in result.comparisons) / len(result.comparisons)
            invocation.confidence = avg_conf

    except Exception as e:
        invocation.warnings.append(f"choose-stems failed: {e}")

    return result, invocation
