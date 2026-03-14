"""Handle ambiguous intros by proposing ranked grid anchor candidates."""

from __future__ import annotations

import numpy as np

from ..config import SunoPrepConfig
from ..models import (
    AnchorCandidate,
    BPMResult,
    FeatureInvocation,
    GridAnchorResult,
    ProjectInventory,
)
from ..reporting import write_json_report


def analyze_grid_anchors(
    bpm_result: BPMResult,
    config: SunoPrepConfig,
) -> GridAnchorResult:
    """Propose ranked candidate grid anchors from BPM analysis."""
    result = GridAnchorResult()
    beat_times = bpm_result.beat_times
    onset_times = bpm_result.onset_times

    if not beat_times:
        result.analysis_notes.append("No beat times available")
        return result

    bpm = bpm_result.bpm
    beat_duration = 60.0 / bpm
    bar_duration = beat_duration * 4  # assumes 4/4 — Suno exports are always 4/4

    # Candidate 1: first detected beat (Phase 1 default)
    result.candidates.append(AnchorCandidate(
        time=beat_times[0],
        bar_estimate=1,
        confidence=0.5,
        reason="First detected beat (pipeline default)",
    ))

    # Candidate 2: first onset if different from first beat
    if onset_times and abs(onset_times[0] - beat_times[0]) > 0.05:
        result.candidates.append(AnchorCandidate(
            time=onset_times[0],
            bar_estimate=1,
            confidence=0.3,
            reason="First onset (may be pickup note or FX)",
        ))

    # Candidate 3: look for first strong beat cluster
    # Find where beats become regular (std dev of intervals drops)
    if len(beat_times) >= 8:
        intervals = np.diff(beat_times)
        # Sliding window of 4 beats
        for i in range(len(intervals) - 3):
            window = intervals[i : i + 4]
            std = float(np.std(window))
            mean = float(np.mean(window))
            # Regular if std < 5% of mean
            if mean > 0 and std / mean < 0.05:
                candidate_time = beat_times[i]
                # Estimate which bar this is
                bar_est = max(1, round(candidate_time / bar_duration))
                if abs(candidate_time - beat_times[0]) > beat_duration:
                    result.candidates.append(AnchorCandidate(
                        time=candidate_time,
                        bar_estimate=bar_est,
                        confidence=0.7,
                        reason=f"First regular beat cluster (interval std={std:.3f}s)",
                    ))
                break

    # Candidate 4: snap to nearest bar boundary from leading silence
    silence_end = bpm_result.leading_silence
    if silence_end > 0:
        # Find nearest beat after silence
        post_silence_beats = [t for t in beat_times if t >= silence_end]
        if post_silence_beats:
            nearest = post_silence_beats[0]
            # Snap to bar boundary
            bar_num = max(1, round(nearest / bar_duration))
            snapped = bar_num * bar_duration
            # Only add if meaningfully different
            existing_times = {round(c.time, 3) for c in result.candidates}
            if round(snapped, 3) not in existing_times:
                result.candidates.append(AnchorCandidate(
                    time=snapped,
                    bar_estimate=bar_num,
                    confidence=0.4,
                    reason=f"Bar-snapped anchor after {silence_end:.3f}s silence",
                ))

    # Score and rank
    result.candidates.sort(key=lambda c: -c.confidence)

    if result.candidates:
        result.recommended = result.candidates[0]
        result.analysis_notes.append(
            f"Recommended anchor at {result.recommended.time:.4f}s "
            f"(bar {result.recommended.bar_estimate})"
        )

    # Analysis notes
    result.analysis_notes.append(f"BPM: {bpm:.1f}, bar duration: {bar_duration:.3f}s")
    result.analysis_notes.append(f"Leading silence: {bpm_result.leading_silence:.3f}s")
    result.analysis_notes.append(f"{len(result.candidates)} candidates evaluated")

    return result


def run_choose_grid_anchor(
    bpm_result: BPMResult,
    config: SunoPrepConfig,
    apply: bool = False,
) -> tuple[GridAnchorResult, FeatureInvocation]:
    """Entry point for choose-grid-anchor feature."""
    invocation = FeatureInvocation(
        feature="choose_grid_anchor",
        mode="apply" if apply else "report",
    )

    try:
        result = analyze_grid_anchors(bpm_result, config)

        if not config.dry_run:
            import json
            report_data = json.loads(result.model_dump_json())
            write_json_report(report_data, "grid_anchor.json", config)
            invocation.output_files.append(config.reports_dir / "grid_anchor.json")

        if result.recommended:
            invocation.recommendation = (
                f"Anchor at {result.recommended.time:.4f}s "
                f"(bar {result.recommended.bar_estimate})"
            )
            invocation.confidence = result.recommended.confidence

    except Exception as e:
        invocation.warnings.append(f"choose-grid-anchor failed: {e}")
        result = GridAnchorResult()

    return result, invocation
