"""Tests for non-destructive audio processing."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from suno_to_ableton.audio_processing import process_audio_file
from suno_to_ableton.config import SunoPrepConfig
from suno_to_ableton.models import DiscoveredFile, FileRole, StemType


def test_process_audio_file_preserves_source_timing(tmp_path: Path):
    input_path = tmp_path / "0 Drums.wav"
    samples = np.zeros((48000, 2), dtype=np.float32)
    sf.write(input_path, samples, 48000, subtype="FLOAT")

    output_path, steps = process_audio_file(
        DiscoveredFile(
            path=input_path,
            role=FileRole.AUDIO_STEM,
            stem_type=StemType.DRUMS,
            track_number=0,
            sample_rate=48000,
            channels=2,
            subtype="FLOAT",
        ),
        output_dir=tmp_path / "processed" / "stems",
        offset_seconds=1.5,
        config=SunoPrepConfig(source_dir=tmp_path),
    )

    info = sf.info(str(output_path))
    assert info.frames == 48000
    assert any("source timing preserved" in step for step in steps)
