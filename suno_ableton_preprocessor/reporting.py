"""Rich console output and JSON report generation."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import SunoPrepConfig
from .models import (
    AlignmentResult,
    BPMResult,
    ProcessingManifest,
    ProjectInventory,
)

console = Console()


def print_inventory(inventory: ProjectInventory) -> None:
    """Print a Rich table of discovered files."""
    table = Table(title=f"Project: {inventory.song_title or 'Unknown'}")
    table.add_column("#", style="dim", width=4)
    table.add_column("Role", style="cyan")
    table.add_column("Stem Type", style="green")
    table.add_column("Filename", style="white")
    table.add_column("SR", justify="right")
    table.add_column("Ch", justify="right")
    table.add_column("Duration", justify="right")

    if inventory.full_mix:
        f = inventory.full_mix
        table.add_row(
            str(f.track_number or "-"),
            f.role.value,
            f.stem_type.value,
            f.path.name,
            str(f.sample_rate or "-"),
            str(f.channels or "-"),
            f"{f.duration_seconds:.2f}s" if f.duration_seconds else "-",
        )

    for f in inventory.stems:
        table.add_row(
            str(f.track_number or "-"),
            f.role.value,
            f.stem_type.value,
            f.path.name,
            str(f.sample_rate or "-"),
            str(f.channels or "-"),
            f"{f.duration_seconds:.2f}s" if f.duration_seconds else "-",
        )

    for f in inventory.midi_files:
        table.add_row(
            "-",
            f.role.value,
            "-",
            f.path.name,
            "-",
            "-",
            "-",
        )

    console.print(table)

    for warning in inventory.warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")


def print_bpm_result(result: BPMResult) -> None:
    """Print BPM analysis results in a Rich panel."""
    lines = [
        f"[bold]BPM:[/bold] {result.bpm:.1f}",
        f"[bold]Confidence:[/bold] {result.confidence:.2f}",
        f"[bold]Downbeat:[/bold] {result.downbeat_time:.4f}s",
        f"[bold]Leading silence:[/bold] {result.leading_silence:.4f}s",
        f"[bold]Beats detected:[/bold] {len(result.beat_times)}",
        f"[bold]Onsets detected:[/bold] {len(result.onset_times)}",
    ]
    console.print(Panel("\n".join(lines), title="BPM Analysis"))


def print_alignment(alignment: AlignmentResult) -> None:
    """Print alignment results."""
    lines = [
        f"[bold]Offset:[/bold] {alignment.offset_seconds:.4f}s ({alignment.offset_samples} samples)",
        f"[bold]BPM:[/bold] {alignment.bpm:.1f}",
        f"[bold]Samples/beat:[/bold] {alignment.samples_per_beat:.1f}",
    ]
    console.print(Panel("\n".join(lines), title="Alignment"))


def print_summary(manifest: ProcessingManifest) -> None:
    """Print final processing summary."""
    console.print()
    console.print("[bold green]Processing complete![/bold green]")
    console.print(f"  Song: {manifest.song_title}")
    if manifest.bpm is not None:
        console.print(f"  BPM: {manifest.bpm:.1f} (confidence: {manifest.bpm_confidence:.2f})")
    console.print(f"  Stems: {len(manifest.stems)}")
    console.print(f"  MIDI files: {len(manifest.midi_files)}")
    if manifest.generated_stems:
        console.print(f"  Generated stems: {len(manifest.generated_stems)}")
    if manifest.warnings:
        console.print(f"  [yellow]Warnings: {len(manifest.warnings)}[/yellow]")
        for w in manifest.warnings:
            console.print(f"    [yellow]- {w}[/yellow]")


def write_manifest(manifest: ProcessingManifest, config: SunoPrepConfig) -> Path:
    """Write the processing manifest to JSON."""
    output_path = config.reports_dir / "manifest.json"
    data = json.loads(manifest.model_dump_json())
    return _write_json(data, output_path)


def write_json_report(data: dict, filename: str, config: SunoPrepConfig) -> Path:
    """Write a generic JSON report."""
    output_path = config.reports_dir / filename
    return _write_json(data, output_path)


def _write_json(data: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return output_path


