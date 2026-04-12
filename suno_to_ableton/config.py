"""Runtime configuration for suno-to-ableton."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from .models import SeparatorBackend


class SunoPrepConfig(BaseModel):
    source_dir: Path = Field(default_factory=lambda: Path.cwd())
    output_dir: Path = Field(default=Path("processed"))
    dry_run: bool = False
    verbose: bool = False
    skip_existing: bool = False
    force: bool = False
    separate_missing: bool = False

    # Audio
    target_sr: int = 48000
    target_channels: int = 2

    # MIDI
    quantize_grid: str = "1/16"
    min_note_ms: float = 40.0

    # Separation
    separator: SeparatorBackend = SeparatorBackend.DEMUCS
    demucs_model: str = "htdemucs"

    # Advanced optional features (none run by default)
    choose_stems: bool = False
    choose_grid_anchor: bool = False
    detect_sections: bool = False
    repair_midi: bool = False
    requantize_midi: bool = False
    requantize_mode: str = "light"  # strict|light|swing|triplet
    reseparate: bool = False
    apply_features: bool = False  # global --apply for advanced features
    export_als: bool = False
    als_template: Optional[Path] = None  # path to Ableton .als template
    ableton_version: int = 12  # target Ableton Live version (11 or 12)

    @property
    def resolved_output_dir(self) -> Path:
        if self.output_dir.is_absolute():
            return self.output_dir
        return self.source_dir / self.output_dir

    @property
    def stems_dir(self) -> Path:
        return self.resolved_output_dir / "stems"

    @property
    def midi_dir(self) -> Path:
        return self.resolved_output_dir / "midi"

    @property
    def reports_dir(self) -> Path:
        return self.resolved_output_dir / "reports"

    @property
    def generated_stems_dir(self) -> Path:
        return self.resolved_output_dir / "stems_generated"

    @property
    def quantize_fraction(self) -> Fraction:
        return Fraction(self.quantize_grid)

    def ensure_output_dirs(self) -> None:
        if self.dry_run:
            return
        for d in [self.stems_dir, self.midi_dir, self.reports_dir]:
            d.mkdir(parents=True, exist_ok=True)
