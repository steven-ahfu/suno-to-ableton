"""Lightweight progress callback types for the processing pipeline."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class PipelineStep:
    key: str
    label: str
    number: int
    status: StepStatus = StepStatus.PENDING
    started_at: float | None = None
    finished_at: float | None = None
    detail: str = ""
    error_msg: str = ""

    @property
    def elapsed(self) -> float | None:
        if self.started_at is None:
            return None
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return end - self.started_at


# (key, label) for each pipeline step
PIPELINE_STEPS: list[tuple[str, str]] = [
    ("discovery", "Discover files"),
    ("output_dirs", "Create output dirs"),
    ("bpm", "Detect BPM"),
    ("alignment", "Compute alignment"),
    ("audio", "Process audio"),
    ("midi", "Clean MIDI"),
    ("separation", "Stem separation"),
    ("advanced", "Advanced features"),
    ("reports", "Write reports"),
]


def make_steps() -> list[PipelineStep]:
    """Create a fresh list of pipeline steps in PENDING state."""
    return [
        PipelineStep(key=key, label=label, number=i + 1)
        for i, (key, label) in enumerate(PIPELINE_STEPS)
    ]


# Type alias for the progress callback.
# Signature: (step_key, status, detail) -> None
ProgressCallback = Callable[[str, StepStatus, str], None]
