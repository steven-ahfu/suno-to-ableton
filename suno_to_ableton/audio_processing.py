"""Audio normalization with source timing preserved."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import soundfile as sf

from .config import SunoPrepConfig
from .models import DiscoveredFile, StemType


def generate_output_filename(file: DiscoveredFile, index: int | None = None) -> str:
    """Generate a standardized output filename.

    e.g., "00_full_mix.wav", "01_fx.wav", "05_drums.wav"
    """
    if file.track_number is not None:
        num = file.track_number
    elif index is not None:
        num = index
    else:
        num = 0

    name = file.stem_type.value
    return f"{num:02d}_{name}.wav"


def needs_conversion(file: DiscoveredFile, config: SunoPrepConfig) -> bool:
    """Check if an audio file needs format conversion."""
    return (
        file.sample_rate != config.target_sr
        or file.channels != config.target_channels
        or file.subtype != "FLOAT"
    )


def normalize_audio(
    input_path: Path, output_path: Path, config: SunoPrepConfig
) -> list[str]:
    """Normalize audio to target format using ffmpeg.

    Returns list of processing steps applied.
    """
    steps = []

    # Check if conversion is needed
    try:
        info = sf.info(str(input_path))
        needs_work = (
            info.samplerate != config.target_sr
            or info.channels != config.target_channels
            or info.subtype != "FLOAT"
        )
    except Exception:
        needs_work = True

    if not needs_work:
        if input_path != output_path:
            shutil.copy2(input_path, output_path)
            steps.append("copied (already correct format)")
        return steps

    if config.dry_run:
        steps.append(f"would normalize: sr={config.target_sr}, ch={config.target_channels}, float32")
        return steps

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-ar", str(config.target_sr),
        "-ac", str(config.target_channels),
        "-c:a", "pcm_f32le",
        str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        stderr = proc.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"ffmpeg normalization failed: {stderr}")
    steps.append(f"normalized: sr={config.target_sr}, ch={config.target_channels}, float32")
    return steps


def trim_audio(
    input_path: Path, output_path: Path, offset_seconds: float, config: SunoPrepConfig
) -> list[str]:
    """Trim audio by the global offset using ffmpeg.

    Returns list of processing steps applied.
    """
    steps = []

    if offset_seconds <= 0:
        if input_path != output_path:
            shutil.copy2(input_path, output_path)
            steps.append("copied (no trim needed)")
        return steps

    if config.dry_run:
        steps.append(f"would trim: offset={offset_seconds:.4f}s")
        return steps

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-ss", str(offset_seconds),
        "-c:a", "pcm_f32le",
        str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        stderr = proc.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"ffmpeg trim failed: {stderr}")
    steps.append(f"trimmed: offset={offset_seconds:.4f}s")
    return steps


def process_audio_file(
    file: DiscoveredFile,
    output_dir: Path,
    offset_seconds: float,
    config: SunoPrepConfig,
    index: int | None = None,
) -> tuple[Path, list[str]]:
    """Full audio processing pipeline for a single file.

    1. Normalize format if needed
    2. Preserve the original timeline

    Returns (output_path, processing_steps).
    """
    output_name = generate_output_filename(file, index)
    final_output = output_dir / output_name
    steps = []

    if config.skip_existing and final_output.exists() and not config.force:
        return final_output, ["skipped (already exists)"]

    if config.dry_run:
        steps.append(f"would write: {final_output}")
        if needs_conversion(file, config):
            steps.append(f"would normalize: sr={config.target_sr}")
        if offset_seconds > 0:
            steps.append(
                f"would preserve source timing (detected alignment offset={offset_seconds:.4f}s)"
            )
        return final_output, steps

    # Normalize if needed, but do not destructively trim the source files.
    needs_norm = needs_conversion(file, config)

    if needs_norm:
        final_output.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-y", "-i", str(file.path)]
        cmd.extend([
            "-ar", str(config.target_sr),
            "-ac", str(config.target_channels),
            "-c:a", "pcm_f32le",
            str(final_output),
        ])
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            stderr = proc.stderr.decode(errors="replace").strip()
            raise RuntimeError(f"ffmpeg processing failed: {stderr}")

        if needs_norm:
            steps.append(f"normalized: sr={config.target_sr}, ch={config.target_channels}")
    else:
        # Just copy
        final_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file.path, final_output)
        steps.append("copied (no processing needed)")

    if offset_seconds > 0:
        steps.append(
            f"source timing preserved (detected alignment offset={offset_seconds:.4f}s)"
        )

    return final_output, steps
