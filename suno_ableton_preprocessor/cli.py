"""Typer CLI for suno-ableton-preprocessor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .alignment import compute_alignment
from .bpm_detection import analyze_bpm_from_inventory
from .config import SunoPrepConfig
from .discovery import discover_project
from .models import SeparatorBackend
from .pipeline import run_pipeline
from .reporting import (
    console,
    print_alignment,
    print_bpm_result,
    print_inventory,
)

app = typer.Typer(
    name="suno-ableton-preprocessor",
    help="Suno AI export preprocessor for Ableton Live",
    no_args_is_help=True,
)


@app.command()
def analyze(
    source_dir: Path = typer.Argument(
        ".", help="Directory containing Suno export files"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Analyze a Suno export directory (read-only, no output files)."""
    source = source_dir.resolve()
    console.print(f"[bold]Analyzing:[/bold] {source}\n")

    # Discovery
    inventory = discover_project(source)
    print_inventory(inventory)

    if not inventory.full_mix and not inventory.stems:
        console.print("[red]No audio files found.[/red]")
        raise typer.Exit(1)

    # BPM detection
    console.print()
    try:
        bpm_result = analyze_bpm_from_inventory(inventory)
        print_bpm_result(bpm_result)

        # Alignment
        alignment = compute_alignment(bpm_result)
        print_alignment(alignment)
    except Exception as e:
        console.print(f"[yellow]BPM detection failed: {e}[/yellow]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())


@app.command()
def process(
    source_dir: Path = typer.Argument(
        ".", help="Directory containing Suno export files"
    ),
    output_dir: Path = typer.Option(
        "processed", "--output-dir", "-o", help="Output directory"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    skip_existing: bool = typer.Option(
        False, "--skip-existing", help="Skip already-processed files"
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files"),
    target_sr: int = typer.Option(48000, "--target-sr", help="Target sample rate"),
    quantize_grid: str = typer.Option(
        "1/16", "--quantize-grid", help="MIDI quantization grid"
    ),
    min_note_ms: float = typer.Option(
        40.0, "--min-note-ms", help="Minimum MIDI note duration (ms)"
    ),
    separate_missing: bool = typer.Option(
        False, "--separate-missing", help="Run stem separation on full mix"
    ),
    separator: str = typer.Option(
        "demucs", "--separator", help="Separation backend: demucs or uvr"
    ),
    demucs_model: str = typer.Option(
        "htdemucs", "--demucs-model", help="Demucs model name (e.g. htdemucs, htdemucs_ft)"
    ),
    # Advanced optional features
    choose_stems: bool = typer.Option(
        False, "--choose-stems", help="Compare original vs generated stems"
    ),
    choose_grid_anchor: bool = typer.Option(
        False, "--choose-grid-anchor", help="Analyze grid anchor candidates"
    ),
    detect_sections: bool = typer.Option(
        False, "--detect-sections", help="Detect arrangement sections"
    ),
    repair_midi_flag: bool = typer.Option(
        False, "--repair-midi", help="Conservative harmonic MIDI repair"
    ),
    requantize_midi: bool = typer.Option(
        False, "--requantize-midi", help="Feel-based MIDI requantization"
    ),
    requantize_mode: str = typer.Option(
        "light", "--requantize-mode", help="Requantize mode: strict|light|swing|triplet"
    ),
    reseparate: bool = typer.Option(
        False, "--reseparate", help="Re-run stem separation"
    ),
    apply_features: bool = typer.Option(
        False, "--apply", help="Write advanced feature changes to output files"
    ),
    export_als: bool = typer.Option(
        False, "--export-als", help="Generate Ableton Live Set file"
    ),
    als_template: Optional[Path] = typer.Option(
        None, "--als-template", help="Path to Example.als template"
    ),
) -> None:
    """Run the full preprocessing pipeline."""
    config = SunoPrepConfig(
        source_dir=source_dir.resolve(),
        output_dir=Path(output_dir),
        dry_run=dry_run,
        verbose=verbose,
        skip_existing=skip_existing,
        force=force,
        target_sr=target_sr,
        quantize_grid=quantize_grid,
        min_note_ms=min_note_ms,
        separate_missing=separate_missing,
        separator=SeparatorBackend(separator),
        demucs_model=demucs_model,
        choose_stems=choose_stems,
        choose_grid_anchor=choose_grid_anchor,
        detect_sections=detect_sections,
        repair_midi=repair_midi_flag,
        requantize_midi=requantize_midi,
        requantize_mode=requantize_mode,
        reseparate=reseparate,
        apply_features=apply_features,
        export_als=export_als,
        als_template=als_template,
    )

    console.print(f"[bold]Processing:[/bold] {config.source_dir}")
    console.print(f"[bold]Output:[/bold] {config.resolved_output_dir}")
    if config.dry_run:
        console.print("[yellow]DRY RUN — no files will be modified[/yellow]")

    run_pipeline(config)


@app.command()
def separate(
    source_dir: Path = typer.Argument(
        ".", help="Directory containing Suno export files"
    ),
    output_dir: Path = typer.Option(
        "processed", "--output-dir", "-o", help="Output directory"
    ),
    separator: str = typer.Option(
        "demucs", "--separator", help="Separation backend: demucs or uvr"
    ),
    demucs_model: str = typer.Option(
        "htdemucs", "--demucs-model", help="Demucs model name (e.g. htdemucs, htdemucs_ft)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Run stem separation on the full mix only."""
    from .separation import get_backend

    source = source_dir.resolve()
    inventory = discover_project(source)

    if not inventory.full_mix:
        console.print("[red]No full mix (track 0) found.[/red]")
        raise typer.Exit(1)

    config = SunoPrepConfig(
        source_dir=source,
        output_dir=Path(output_dir),
        separator=SeparatorBackend(separator),
        demucs_model=demucs_model,
        verbose=verbose,
    )

    console.print(f"[bold]Separating:[/bold] {inventory.full_mix.path.name}")
    console.print(f"[bold]Backend:[/bold] {config.separator.value}")

    backend = get_backend(config)
    result = backend.separate(inventory.full_mix.path, config.generated_stems_dir)

    console.print(f"\n[green]Generated {len(result.output_stems)} stems:[/green]")
    for stem_path in result.output_stems:
        console.print(f"  {stem_path.name}")


@app.command()
def report(
    source_dir: Path = typer.Argument(
        ".", help="Directory containing processed output"
    ),
    output_dir: Path = typer.Option(
        "processed", "--output-dir", "-o", help="Output directory"
    ),
) -> None:
    """Display an existing processing manifest."""
    source = source_dir.resolve()
    manifest_path = source / output_dir / "reports" / "manifest.json"

    if not manifest_path.exists():
        console.print(f"[red]No manifest found at {manifest_path}[/red]")
        console.print("Run 'suno-ableton-preprocessor process' first to generate a manifest.")
        raise typer.Exit(1)

    with open(manifest_path) as f:
        data = json.load(f)

    console.print(f"\n[bold]Manifest:[/bold] {manifest_path}\n")
    console.print_json(json.dumps(data, indent=2))


# --- Advanced standalone commands ---


def _make_config(source_dir: Path, output_dir: Path = Path("processed"), **kwargs) -> SunoPrepConfig:
    """Helper to build config for standalone commands."""
    return SunoPrepConfig(source_dir=source_dir.resolve(), output_dir=output_dir, **kwargs)


@app.command(name="choose-stems")
def choose_stems_cmd(
    source_dir: Path = typer.Argument(".", help="Project directory"),
    output_dir: Path = typer.Option("processed", "--output-dir", "-o"),
    apply: bool = typer.Option(False, "--apply", help="Apply stem choices"),
) -> None:
    """Compare original vs generated stems and recommend preferences."""
    from .features.choose_stems import run_choose_stems

    config = _make_config(source_dir, output_dir, apply_features=apply)
    config.ensure_output_dirs()
    result, invocation = run_choose_stems(config, apply=apply)
    if invocation.recommendation:
        console.print(invocation.recommendation)
    for w in invocation.warnings:
        console.print(f"[yellow]{w}[/yellow]")


@app.command(name="choose-grid-anchor")
def choose_grid_anchor_cmd(
    source_dir: Path = typer.Argument(".", help="Project directory"),
    output_dir: Path = typer.Option("processed", "--output-dir", "-o"),
    apply: bool = typer.Option(False, "--apply", help="Apply recommended anchor"),
) -> None:
    """Analyze grid anchor candidates for ambiguous intros."""
    from .features.choose_grid_anchor import run_choose_grid_anchor

    config = _make_config(source_dir, output_dir)
    config.ensure_output_dirs()
    inventory = discover_project(config.source_dir)
    bpm_result = analyze_bpm_from_inventory(inventory)
    result, invocation = run_choose_grid_anchor(bpm_result, config, apply=apply)

    if result.candidates:
        console.print(f"\n[bold]Grid Anchor Candidates:[/bold]")
        for i, c in enumerate(result.candidates):
            marker = " [green]<< recommended[/green]" if c == result.recommended else ""
            console.print(
                f"  {i+1}. t={c.time:.4f}s  bar={c.bar_estimate}  "
                f"conf={c.confidence:.2f}  {c.reason}{marker}"
            )
    for note in result.analysis_notes:
        console.print(f"  {note}")
    for w in invocation.warnings:
        console.print(f"[yellow]{w}[/yellow]")


@app.command(name="detect-sections")
def detect_sections_cmd(
    source_dir: Path = typer.Argument(".", help="Project directory"),
    output_dir: Path = typer.Option("processed", "--output-dir", "-o"),
) -> None:
    """Detect arrangement sections (intro/verse/chorus/etc.)."""
    from .features.detect_sections import run_detect_sections

    config = _make_config(source_dir, output_dir)
    config.ensure_output_dirs()
    inventory = discover_project(config.source_dir)
    bpm_result = analyze_bpm_from_inventory(inventory)
    audio_path = (inventory.full_mix.path if inventory.full_mix
                  else inventory.stems[0].path if inventory.stems else None)

    if not audio_path:
        console.print("[red]No audio files found.[/red]")
        raise typer.Exit(1)

    result, invocation = run_detect_sections(audio_path, bpm_result.bpm, config)
    if result.sections:
        console.print(f"\n[bold]Sections ({result.method}):[/bold]")
        for s in result.sections:
            console.print(
                f"  {s.label:>8s}  {s.start_time:6.1f}s - {s.end_time:6.1f}s  "
                f"bars {s.start_bar}-{s.end_bar}  conf={s.confidence:.2f}"
            )
    for w in invocation.warnings:
        console.print(f"[yellow]{w}[/yellow]")


@app.command(name="repair-midi")
def repair_midi_cmd(
    source_dir: Path = typer.Argument(".", help="Project directory"),
    output_dir: Path = typer.Option("processed", "--output-dir", "-o"),
    apply: bool = typer.Option(False, "--apply", help="Apply repairs"),
) -> None:
    """Analyze and optionally repair MIDI harmonics."""
    from .features.repair_midi import run_repair_midi

    config = _make_config(source_dir, output_dir)
    config.ensure_output_dirs()
    inventory = discover_project(config.source_dir)

    for midi_file in inventory.midi_files:
        console.print(f"\n[bold]Analyzing:[/bold] {midi_file.path.name}")
        result, invocation = run_repair_midi(midi_file.path, config, apply=apply)
        console.print(f"  Key: {result.key_detected}")
        console.print(f"  Notes flagged: {result.notes_flagged}")
        if apply:
            console.print(f"  Notes repaired: {result.notes_repaired}")
            console.print(f"  Stacked chords fixed: {result.stacked_chords_fixed}")
            if result.output_path:
                console.print(f"  Output: {result.output_path}")
        for w in invocation.warnings:
            console.print(f"[yellow]{w}[/yellow]")


@app.command(name="requantize-midi")
def requantize_midi_cmd(
    source_dir: Path = typer.Argument(".", help="Project directory"),
    output_dir: Path = typer.Option("processed", "--output-dir", "-o"),
    mode: str = typer.Option("light", "--mode", help="strict|light|swing|triplet"),
    apply: bool = typer.Option(False, "--apply", help="Apply requantization"),
) -> None:
    """Apply feel-based MIDI requantization."""
    from .features.requantize_midi import run_requantize_midi

    config = _make_config(source_dir, output_dir, requantize_mode=mode)
    config.ensure_output_dirs()
    inventory = discover_project(config.source_dir)
    bpm_result = analyze_bpm_from_inventory(inventory)

    for midi_file in inventory.midi_files:
        console.print(f"\n[bold]Requantizing:[/bold] {midi_file.path.name} (mode={mode})")
        result, invocation = run_requantize_midi(
            midi_file.path, bpm_result.bpm, config, apply=apply
        )
        console.print(f"  Notes affected: {result.notes_moved}")
        console.print(f"  Max shift: {result.max_shift_ms:.1f}ms")
        console.print(f"  Avg shift: {result.avg_shift_ms:.1f}ms")
        if apply and result.output_path:
            console.print(f"  Output: {result.output_path}")
        for w in invocation.warnings:
            console.print(f"[yellow]{w}[/yellow]")


@app.command(name="reseparate")
def reseparate_cmd(
    source_dir: Path = typer.Argument(".", help="Project directory"),
    output_dir: Path = typer.Option("processed", "--output-dir", "-o"),
    target: str = typer.Option("full_mix", "--target", help="Target: full_mix or stem name"),
    separator: str = typer.Option("demucs", "--separator", help="Backend: demucs or uvr"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing"),
) -> None:
    """Re-run stem separation on full mix or a specific stem."""
    from .features.reseparate import run_reseparate

    config = _make_config(
        source_dir, output_dir,
        separator=SeparatorBackend(separator),
        force=force,
    )
    config.ensure_output_dirs()
    inventory = discover_project(config.source_dir)
    result, invocation = run_reseparate(inventory, config, target=target)

    if result.output_stems:
        console.print(f"\n[green]Generated {len(result.output_stems)} stems:[/green]")
        for p in result.output_stems:
            console.print(f"  {p.name}")
    for w in invocation.warnings:
        console.print(f"[yellow]{w}[/yellow]")


@app.command(name="export-als")
def export_als_cmd(
    source_dir: Path = typer.Argument(".", help="Project directory"),
    output_dir: Path = typer.Option("processed", "--output-dir", "-o"),
    als_template: Optional[Path] = typer.Option(
        None, "--als-template", help="Path to Example.als template"
    ),
) -> None:
    """Generate an Ableton Live Set from processed outputs (experimental)."""
    from .features.export_als import run_export_als

    config = _make_config(source_dir, output_dir, als_template=als_template)
    config.ensure_output_dirs()

    # Load manifest
    manifest_path = config.reports_dir / "manifest.json"
    if not manifest_path.exists():
        console.print("[red]No manifest found. Run 'suno-ableton-preprocessor process' first.[/red]")
        raise typer.Exit(1)

    import json as json_mod
    from .models import ProcessingManifest

    with open(manifest_path) as f:
        data = json_mod.load(f)
    manifest = ProcessingManifest(**data)

    result, invocation = run_export_als(manifest, config)
    if result.output_path:
        console.print(f"\n[green]Exported:[/green] {result.output_path}")
        console.print(f"  Audio tracks: {result.tracks_created}")
        console.print(f"  BPM: {result.bpm_set}")
    for w in invocation.warnings:
        console.print(f"[yellow]{w}[/yellow]")


@app.command()
def tui() -> None:
    """Launch the interactive TUI."""
    from .tui import run_tui

    run_tui()


if __name__ == "__main__":
    app()
