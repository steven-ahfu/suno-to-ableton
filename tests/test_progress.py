"""Tests for progress tracking types."""

import time

from suno_to_ableton.progress import (
    PIPELINE_STEPS,
    PipelineStep,
    StepStatus,
    make_steps,
)


class TestStepStatus:
    def test_values(self):
        assert StepStatus.PENDING == "pending"
        assert StepStatus.RUNNING == "running"
        assert StepStatus.DONE == "done"
        assert StepStatus.SKIPPED == "skipped"
        assert StepStatus.ERROR == "error"


class TestPipelineStep:
    def test_defaults(self):
        step = PipelineStep(key="test", label="Test Step", number=1)
        assert step.status == StepStatus.PENDING
        assert step.started_at is None
        assert step.finished_at is None
        assert step.detail == ""
        assert step.error_msg == ""

    def test_elapsed_not_started(self):
        step = PipelineStep(key="test", label="Test", number=1)
        assert step.elapsed is None

    def test_elapsed_running(self):
        step = PipelineStep(key="test", label="Test", number=1)
        step.started_at = time.monotonic() - 2.0
        elapsed = step.elapsed
        assert elapsed is not None
        assert elapsed >= 1.5  # at least ~2s minus timing jitter

    def test_elapsed_finished(self):
        step = PipelineStep(key="test", label="Test", number=1)
        step.started_at = 100.0
        step.finished_at = 103.5
        assert step.elapsed == 3.5


class TestMakeSteps:
    def test_creates_correct_count(self):
        steps = make_steps()
        assert len(steps) == len(PIPELINE_STEPS)

    def test_numbering(self):
        steps = make_steps()
        for i, step in enumerate(steps):
            assert step.number == i + 1

    def test_keys_match_pipeline_steps(self):
        steps = make_steps()
        for step, (key, label) in zip(steps, PIPELINE_STEPS):
            assert step.key == key
            assert step.label == label

    def test_all_start_pending(self):
        steps = make_steps()
        for step in steps:
            assert step.status == StepStatus.PENDING

    def test_expected_step_keys(self):
        steps = make_steps()
        keys = [s.key for s in steps]
        assert "discovery" in keys
        assert "bpm" in keys
        assert "audio" in keys
        assert "midi" in keys
        assert "reports" in keys
