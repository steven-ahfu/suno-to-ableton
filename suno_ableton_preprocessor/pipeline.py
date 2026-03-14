"""Process command orchestrator."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .alignment import compute_alignment
from .audio_processing import process_audio_file
from .bpm_detection import analyze_bpm_from_inventory
from .config import SunoPrepConfig
from .discovery import discover_project
from .midi_cleanup import cleanup_midi
from .models import (
    AlignmentResult,
    BPMResult,
    ProcessedFile,
    ProcessingManifest,
    StemType,
)
from .reporting import (
    console,
    print_alignment,
    print_bpm_result,
    print_inventory,
    print_summary,
    write_json_report,
    write_manifest,
)
from .separation import get_backend

_console = Console()


def run_pipeline(config: SunoPrepConfig) -> ProcessingManifest:
    """Run the full processing pipeline."""
    manifest = ProcessingManifest(target_sr=config.target_sr)

    # Step 1: Discovery
    console.print("\n[bold]Step 1:[/bold] Discovering files...")
    inventory = discover_project(config.source_dir)
    print_inventory(inventory)
    manifest.song_title = inventory.song_title
    manifest.warnings.extend(inventory.warnings)

    if not inventory.full_mix and not inventory.stems:
        console.print("[red]No audio files found. Aborting.[/red]")
        return manifest

    # Step 2: Create output dirs
    console.print("\n[bold]Step 2:[/bold] Creating output directories...")
    config.ensure_output_dirs()
    if config.dry_run:
        console.print("  [dim](dry run — no directories created)[/dim]")

    # Step 3: BPM detection
    console.print("\n[bold]Step 3:[/bold] Detecting BPM...")
    bpm_result: BPMResult | None = None
    try:
        bpm_result = analyze_bpm_from_inventory(inventory)
        print_bpm_result(bpm_result)
        manifest.bpm = bpm_result.bpm
        manifest.bpm_confidence = bpm_result.confidence
    except Exception as e:
        msg = f"BPM detection failed: {e}"
        console.print(f"  [yellow]Warning: {msg}[/yellow]")
        manifest.warnings.append(msg)

    # Step 4: Alignment
    console.print("\n[bold]Step 4:[/bold] Computing alignment...")
    alignment: AlignmentResult | None = None
    if bpm_result:
        alignment = compute_alignment(bpm_result, config.target_sr)
        print_alignment(alignment)
        manifest.offset_seconds = alignment.offset_seconds
        manifest.offset_samples = alignment.offset_samples
        manifest.samples_per_beat = alignment.samples_per_beat
    else:
        console.print("  [yellow]Skipping alignment (no BPM data)[/yellow]")

    offset = alignment.offset_seconds if alignment else 0.0

    # Step 5: Audio processing
    console.print("\n[bold]Step 5:[/bold] Processing audio files...")
    all_audio_files = []
    if inventory.full_mix:
        all_audio_files.append(inventory.full_mix)
    all_audio_files.extend(inventory.stems)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=_console,
    ) as progress:
        for file in all_audio_files:
            task = progress.add_task(f"Processing {file.path.name}...", total=None)
            try:
                output_path, steps = process_audio_file(
                    file, config.stems_dir, offset, config
                )
                manifest.stems.append(
                    ProcessedFile(
                        output_path=output_path,
                        stem_type=file.stem_type,
                        processing_steps=steps,
                    )
                )
                if config.verbose:
                    for step in steps:
                        console.print(f"    {step}")
            except Exception as e:
                msg = f"Failed to process {file.path.name}: {e}"
                console.print(f"  [yellow]Warning: {msg}[/yellow]")
                manifest.warnings.append(msg)
            finally:
                progress.remove_task(task)

    # Step 6: MIDI cleanup
    if inventory.midi_files:
        console.print("\n[bold]Step 6:[/bold] Cleaning MIDI files...")
        bpm_for_midi = manifest.bpm
        if bpm_for_midi is None:
            bpm_for_midi = 120.0
            console.print("  [yellow]Warning: No BPM detected, falling back to 120 BPM for MIDI cleanup[/yellow]")
            manifest.warnings.append("No BPM detected — MIDI cleanup used fallback of 120 BPM")

        for midi_file in inventory.midi_files:
            try:
                result = cleanup_midi(
                    midi_file.path,
                    config.midi_dir,
                    offset,
                    bpm_for_midi,
                    config,
                )
                manifest.midi_files.append(
                    ProcessedFile(
                        output_path=result.output_path,
                        stem_type=StemType.OTHER,
                        processing_steps=[
                            f"tracks kept: {result.tracks_kept}",
                            f"tracks removed: {result.tracks_removed}",
                            f"short notes removed: {result.notes_removed_short}",
                            f"duplicate notes removed: {result.notes_removed_duplicate}",
                            f"pre-offset notes removed: {result.notes_removed_pre_offset}",
                            f"notes quantized: {result.notes_quantized}",
                            f"tempo set: {result.tempo_set:.1f}",
                            f"offset applied: {result.offset_applied:.4f}s",
                        ],
                    )
                )
                if config.verbose:
                    console.print(f"    {midi_file.path.name} → {result.output_path.name}")
                    console.print(f"      Tracks: {result.tracks_kept} kept, {result.tracks_removed} removed")
                    console.print(f"      Notes quantized: {result.notes_quantized}")
            except Exception as e:
                msg = f"Failed to process MIDI {midi_file.path.name}: {e}"
                console.print(f"  [yellow]Warning: {msg}[/yellow]")
                manifest.warnings.append(msg)
    else:
        console.print("\n[bold]Step 6:[/bold] No MIDI files to process.")

    # Step 7: Optional stem separation
    if config.separate_missing and inventory.full_mix:
        console.print("\n[bold]Step 7:[/bold] Running stem separation...")
        try:
            backend = get_backend(config)
            result = backend.separate(
                inventory.full_mix.path, config.generated_stems_dir
            )
            for stem_path in result.output_stems:
                stem_name = stem_path.stem.lower()
                stem_type = StemType.OTHER
                for st in StemType:
                    if st.value == stem_name:
                        stem_type = st
                        break
                manifest.generated_stems.append(
                    ProcessedFile(
                        output_path=stem_path,
                        stem_type=stem_type,
                        was_generated=True,
                        processing_steps=[
                            f"separated by {result.backend.value}",
                            f"model: {result.model}",
                        ],
                    )
                )
            console.print(f"  Generated {len(result.output_stems)} stems")
        except Exception as e:
            msg = f"Stem separation failed: {e}"
            console.print(f"  [yellow]Warning: {msg}[/yellow]")
            manifest.warnings.append(msg)

    # Advanced optional features (only if explicitly requested)
    _run_advanced_features(config, manifest, inventory, bpm_result, alignment)

    # ALS Export (after all processing, before reports)
    if config.export_als:
        console.print("\n[bold]ALS Export:[/bold] Generating Ableton Live Set...")
        try:
            from .features.export_als import run_export_als
            als_result, als_invocation = run_export_als(manifest, config)
            manifest.features_invoked.append(als_invocation)
            if als_result.output_path:
                console.print(f"  Exported: {als_result.output_path}")
                console.print(f"  Tracks: {als_result.tracks_created} audio, BPM: {als_result.bpm_set}")
            for w in als_invocation.warnings:
                console.print(f"  [yellow]{w}[/yellow]")
        except Exception as e:
            msg = f"ALS export failed: {e}"
            console.print(f"  [yellow]{msg}[/yellow]")
            manifest.warnings.append(msg)

    # Step 8: Write reports
    if not config.dry_run:
        console.print("\n[bold]Step 8:[/bold] Writing reports...")
        manifest_path = write_manifest(manifest, config)
        console.print(f"  Manifest: {manifest_path}")

        if bpm_result:
            bpm_report = {
                "bpm": bpm_result.bpm,
                "confidence": bpm_result.confidence,
                "downbeat_time": bpm_result.downbeat_time,
                "leading_silence": bpm_result.leading_silence,
                "beat_count": len(bpm_result.beat_times),
                "onset_count": len(bpm_result.onset_times),
            }
            write_json_report(bpm_report, "bpm_report.json", config)

        if alignment:
            timing_report = {
                "offset_seconds": alignment.offset_seconds,
                "offset_samples": alignment.offset_samples,
                "bpm": alignment.bpm,
                "samples_per_beat": alignment.samples_per_beat,
                "target_sr": config.target_sr,
            }
            write_json_report(timing_report, "timing_report.json", config)
    else:
        console.print("\n[bold]Step 8:[/bold] [dim](dry run — no reports written)[/dim]")

    # Step 9: Summary
    print_summary(manifest)

    return manifest


def _run_advanced_features(
    config: SunoPrepConfig,
    manifest: ProcessingManifest,
    inventory,
    bpm_result: BPMResult | None,
    alignment: AlignmentResult | None,
) -> None:
    """Run any advanced optional features that were requested."""
    any_advanced = (
        config.choose_grid_anchor
        or config.detect_sections
        or config.reseparate
        or config.choose_stems
        or config.repair_midi
        or config.requantize_midi
    )
    if not any_advanced:
        return

    apply = config.apply_features
    bpm = manifest.bpm
    if bpm is None:
        bpm = 120.0
        console.print("  [yellow]Warning: No BPM detected, advanced features using fallback of 120 BPM[/yellow]")

    console.print("\n[bold]Advanced:[/bold] Running optional features...")

    # 1. choose-grid-anchor (may adjust offset)
    if config.choose_grid_anchor and bpm_result:
        console.print("  Running choose-grid-anchor...")
        try:
            from .features.choose_grid_anchor import run_choose_grid_anchor
            _, invocation = run_choose_grid_anchor(bpm_result, config, apply=apply)
            manifest.features_invoked.append(invocation)
            if invocation.recommendation:
                console.print(f"    {invocation.recommendation}")
            for w in invocation.warnings:
                console.print(f"    [yellow]{w}[/yellow]")
        except Exception as e:
            msg = f"choose-grid-anchor failed: {e}"
            console.print(f"    [yellow]{msg}[/yellow]")
            manifest.warnings.append(msg)

    # 2. detect-sections
    if config.detect_sections:
        audio_path = None
        if inventory.full_mix:
            audio_path = inventory.full_mix.path
        elif inventory.stems:
            audio_path = inventory.stems[0].path

        if audio_path:
            console.print("  Running detect-sections...")
            try:
                from .features.detect_sections import run_detect_sections
                _, invocation = run_detect_sections(audio_path, bpm, config)
                manifest.features_invoked.append(invocation)
                if invocation.recommendation:
                    console.print(f"    {invocation.recommendation}")
                for w in invocation.warnings:
                    console.print(f"    [yellow]{w}[/yellow]")
            except Exception as e:
                msg = f"detect-sections failed: {e}"
                console.print(f"    [yellow]{msg}[/yellow]")
                manifest.warnings.append(msg)

    # 3. reseparate
    if config.reseparate:
        console.print("  Running reseparate...")
        try:
            from .features.reseparate import run_reseparate
            _, invocation = run_reseparate(inventory, config, target="full_mix")
            manifest.features_invoked.append(invocation)
            if invocation.recommendation:
                console.print(f"    {invocation.recommendation}")
            for w in invocation.warnings:
                console.print(f"    [yellow]{w}[/yellow]")
        except Exception as e:
            msg = f"reseparate failed: {e}"
            console.print(f"    [yellow]{msg}[/yellow]")
            manifest.warnings.append(msg)

    # 4. choose-stems (after reseparation)
    if config.choose_stems:
        console.print("  Running choose-stems...")
        try:
            from .features.choose_stems import run_choose_stems
            _, invocation = run_choose_stems(config, apply=apply)
            manifest.features_invoked.append(invocation)
            if invocation.recommendation:
                console.print(f"    {invocation.recommendation}")
            for w in invocation.warnings:
                console.print(f"    [yellow]{w}[/yellow]")
        except Exception as e:
            msg = f"choose-stems failed: {e}"
            console.print(f"    [yellow]{msg}[/yellow]")
            manifest.warnings.append(msg)

    # 5. repair-midi
    if config.repair_midi and manifest.midi_files:
        console.print("  Running repair-midi...")
        for midi_pf in manifest.midi_files:
            try:
                from .features.repair_midi import run_repair_midi
                _, invocation = run_repair_midi(
                    midi_pf.output_path, config, apply=apply
                )
                manifest.features_invoked.append(invocation)
                if invocation.recommendation:
                    console.print(f"    {invocation.recommendation}")
                for w in invocation.warnings:
                    console.print(f"    [yellow]{w}[/yellow]")
            except Exception as e:
                msg = f"repair-midi failed on {midi_pf.output_path.name}: {e}"
                console.print(f"    [yellow]{msg}[/yellow]")
                manifest.warnings.append(msg)

    # 6. requantize-midi (last MIDI step)
    if config.requantize_midi and manifest.midi_files:
        console.print("  Running requantize-midi...")
        for midi_pf in manifest.midi_files:
            try:
                from .features.requantize_midi import run_requantize_midi
                _, invocation = run_requantize_midi(
                    midi_pf.output_path, bpm, config, apply=apply
                )
                manifest.features_invoked.append(invocation)
                if invocation.recommendation:
                    console.print(f"    {invocation.recommendation}")
                for w in invocation.warnings:
                    console.print(f"    [yellow]{w}[/yellow]")
            except Exception as e:
                msg = f"requantize-midi failed on {midi_pf.output_path.name}: {e}"
                console.print(f"    [yellow]{msg}[/yellow]")
                manifest.warnings.append(msg)
