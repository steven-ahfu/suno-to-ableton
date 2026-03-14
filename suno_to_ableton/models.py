"""Data models for suno-to-ableton."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class StemType(str, Enum):
    DRUMS = "drums"
    BASS = "bass"
    VOCALS = "vocals"
    BACKING_VOCALS = "backing_vocals"
    SYNTH = "synth"
    FX = "fx"
    PERCUSSION = "percussion"
    SAMPLE = "sample"
    FULL_MIX = "full_mix"
    OTHER = "other"


class FileRole(str, Enum):
    AUDIO_STEM = "audio_stem"
    AUDIO_FULL_MIX = "audio_full_mix"
    MIDI = "midi"
    UNKNOWN = "unknown"


class SeparatorBackend(str, Enum):
    DEMUCS = "demucs"
    UVR = "uvr"


# Mapping from Suno stem names to StemType
STEM_NAME_MAP: dict[str, StemType] = {
    "drums": StemType.DRUMS,
    "bass": StemType.BASS,
    "vocals": StemType.VOCALS,
    "backing_vocals": StemType.BACKING_VOCALS,
    "synth": StemType.SYNTH,
    "fx": StemType.FX,
    "percussion": StemType.PERCUSSION,
    "sample": StemType.SAMPLE,
}


class DiscoveredFile(BaseModel):
    path: Path
    role: FileRole
    stem_type: StemType = StemType.OTHER
    track_number: Optional[int] = None
    stem_name: str = ""
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    frames: Optional[int] = None
    duration_seconds: Optional[float] = None
    subtype: Optional[str] = None


class ProjectInventory(BaseModel):
    source_dir: Path
    full_mix: Optional[DiscoveredFile] = None
    stems: list[DiscoveredFile] = Field(default_factory=list)
    midi_files: list[DiscoveredFile] = Field(default_factory=list)
    song_title: str = ""
    warnings: list[str] = Field(default_factory=list)


class BPMResult(BaseModel):
    bpm: float
    confidence: float = 0.0
    beat_times: list[float] = Field(default_factory=list)
    downbeat_time: float = 0.0
    onset_times: list[float] = Field(default_factory=list)
    leading_silence: float = 0.0


class AlignmentResult(BaseModel):
    offset_seconds: float
    offset_samples: int
    bpm: float
    samples_per_beat: float


class MIDICleanupResult(BaseModel):
    input_path: Path
    output_path: Path
    tracks_removed: int = 0
    tracks_kept: int = 0
    notes_removed_short: int = 0
    notes_removed_duplicate: int = 0
    notes_removed_pre_offset: int = 0
    notes_quantized: int = 0
    offset_applied: float = 0.0
    tempo_set: float = 0.0


class SeparationResult(BaseModel):
    backend: SeparatorBackend
    model: str
    input_path: Path
    output_stems: list[Path] = Field(default_factory=list)


class ProcessedFile(BaseModel):
    output_path: Path
    stem_type: StemType
    was_generated: bool = False
    processing_steps: list[str] = Field(default_factory=list)


class FeatureInvocation(BaseModel):
    """Record of an advanced optional feature invocation."""
    feature: str = ""
    mode: str = "report"  # "report" or "apply"
    output_files: list[Path] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    recommendation: Optional[str] = None


# --- Advanced feature result models ---

class StemComparisonMetrics(BaseModel):
    """QC metrics for a single stem comparison."""
    rms_energy: float = 0.0
    spectral_centroid_mean: float = 0.0
    silence_ratio: float = 0.0
    correlation: float = 0.0


class StemComparisonEntry(BaseModel):
    """Comparison of an original stem vs a generated stem."""
    stem_type: StemType = StemType.OTHER
    original_path: Optional[Path] = None
    generated_path: Optional[Path] = None
    original_metrics: Optional[StemComparisonMetrics] = None
    generated_metrics: Optional[StemComparisonMetrics] = None
    recommendation: str = "original"  # "original" or "generated"
    confidence: float = 0.0


class StemComparisonResult(BaseModel):
    """Result of choose-stems feature."""
    comparisons: list[StemComparisonEntry] = Field(default_factory=list)
    applied: bool = False


class AnchorCandidate(BaseModel):
    """A candidate grid anchor point."""
    time: float
    bar_estimate: int = 1
    confidence: float = 0.0
    reason: str = ""


class GridAnchorResult(BaseModel):
    """Result of choose-grid-anchor feature."""
    candidates: list[AnchorCandidate] = Field(default_factory=list)
    recommended: Optional[AnchorCandidate] = None
    analysis_notes: list[str] = Field(default_factory=list)


class Section(BaseModel):
    """A detected arrangement section."""
    label: str
    start_time: float
    end_time: float
    start_bar: int = 0
    end_bar: int = 0
    confidence: float = 0.0


class SectionDetectionResult(BaseModel):
    """Result of detect-sections feature."""
    sections: list[Section] = Field(default_factory=list)
    method: str = ""


class MIDIRepairResult(BaseModel):
    """Result of repair-midi feature."""
    input_path: Optional[Path] = None
    output_path: Optional[Path] = None
    key_detected: str = ""
    notes_flagged: int = 0
    notes_repaired: int = 0
    stacked_chords_fixed: int = 0
    details: list[dict] = Field(default_factory=list)


class RequantizeResult(BaseModel):
    """Result of requantize-midi feature."""
    input_path: Optional[Path] = None
    output_path: Optional[Path] = None
    mode: str = "light"
    notes_moved: int = 0
    max_shift_ms: float = 0.0
    avg_shift_ms: float = 0.0


class ReseparationResult(BaseModel):
    """Result of reseparate feature."""
    backend: SeparatorBackend = SeparatorBackend.DEMUCS
    model: str = ""
    target: str = "full_mix"
    input_path: Optional[Path] = None
    output_stems: list[Path] = Field(default_factory=list)
    was_forced: bool = False


class ALSExportResult(BaseModel):
    """Result of ALS export feature."""
    output_path: Optional[Path] = None
    tracks_created: int = 0
    midi_tracks_created: int = 0
    bpm_set: Optional[float] = None
    template_used: Optional[Path] = None


class ProcessingManifest(BaseModel):
    song_title: str = ""
    bpm: Optional[float] = None
    bpm_confidence: Optional[float] = None
    offset_seconds: Optional[float] = None
    offset_samples: Optional[int] = None
    samples_per_beat: Optional[float] = None
    target_sr: int = 48000
    stems: list[ProcessedFile] = Field(default_factory=list)
    midi_files: list[ProcessedFile] = Field(default_factory=list)
    generated_stems: list[ProcessedFile] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    features_invoked: list[FeatureInvocation] = Field(default_factory=list)
