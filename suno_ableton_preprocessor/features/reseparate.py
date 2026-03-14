"""Selective re-separation of full mix or specific stems."""

from __future__ import annotations

from pathlib import Path

from ..config import SunoPrepConfig
from ..models import (
    FeatureInvocation,
    ProjectInventory,
    ReseparationResult,
    SeparatorBackend,
)
from ..reporting import write_json_report
from ..separation import get_backend


def reseparate(
    inventory: ProjectInventory,
    target: str,
    config: SunoPrepConfig,
) -> ReseparationResult:
    """Run stem separation on a target audio file."""
    result = ReseparationResult(
        backend=config.separator,
        model=config.demucs_model if config.separator == SeparatorBackend.DEMUCS else "bs_roformer",
        target=target,
        was_forced=config.force,
    )

    # Determine input file
    if target == "full_mix":
        if not inventory.full_mix:
            raise ValueError("No full mix found in project")
        input_path = inventory.full_mix.path
    else:
        # Find matching stem
        matched = None
        for stem in inventory.stems:
            if stem.stem_type.value == target or stem.stem_name.lower() == target.lower():
                matched = stem
                break
        if not matched:
            raise ValueError(f"No stem matching '{target}' found")
        input_path = matched.path

    result.input_path = input_path

    # Output directory with run isolation
    output_dir = config.generated_stems_dir / f"resep_{target}"

    # Check existing
    if output_dir.exists() and not config.force:
        existing = list(output_dir.glob("*.wav"))
        if existing:
            result.output_stems = existing
            return result

    if config.dry_run:
        return result

    # Run separation
    backend = get_backend(config)
    sep_result = backend.separate(input_path, output_dir)
    result.output_stems = sep_result.output_stems

    return result


def run_reseparate(
    inventory: ProjectInventory,
    config: SunoPrepConfig,
    target: str = "full_mix",
) -> tuple[ReseparationResult, FeatureInvocation]:
    """Entry point for reseparate feature."""
    invocation = FeatureInvocation(
        feature="reseparate",
        mode="apply",  # separation always produces output
    )

    try:
        result = reseparate(inventory, target, config)

        if not config.dry_run:
            import json
            report_data = json.loads(result.model_dump_json())
            write_json_report(report_data, "reseparation.json", config)
            invocation.output_files = list(result.output_stems)
            invocation.output_files.append(config.reports_dir / "reseparation.json")

        invocation.recommendation = (
            f"Separated '{target}' with {result.backend.value}, "
            f"{len(result.output_stems)} stems generated"
        )

    except Exception as e:
        invocation.warnings.append(f"reseparate failed: {e}")
        result = ReseparationResult(target=target)

    return result, invocation
