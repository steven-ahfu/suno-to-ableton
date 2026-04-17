# CLI Flags Reference

## Pipeline tuning

These adjust the automatic pipeline. You usually don't need to change them.

| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir`, `-o` | `processed` | Output directory |
| `--dry-run` | off | Show what would be done without writing files |
| `--verbose`, `-v` | off | Verbose output |
| `--skip-existing` | off | Skip already-processed files |
| `--force` | off | Overwrite existing files |
| `--target-sr` | 48000 | Target sample rate |
| `--quantize-grid` | 1/16 | MIDI quantization grid |
| `--min-note-ms` | 40 | Minimum MIDI note duration in ms |
| `--separate-missing` | off | Run stem separation on full mix |
| `--separator` | demucs | Separation backend: `demucs` or `uvr` |

## Advanced features (opt-in)

None of these run unless you explicitly pass the flag. Use them when the automatic results need manual correction or deeper analysis. Each has a detailed doc explaining the decisions it makes.

| Flag | Description | Details |
|------|-------------|---------|
| `--choose-stems` | Compare original vs AI-generated stems, recommend the better version | [Stem Quality Judgment](features/stem-quality-judgment.md) |
| `--choose-grid-anchor` | Analyze grid anchor candidates when the intro downbeat is unclear | [Grid Anchor](features/grid-anchor.md) |
| `--detect-sections` | Identify arrangement sections (intro, verse, chorus, etc.) | [Section Detection](features/section-detection.md) |
| `--repair-midi` | Detect key, flag out-of-key notes, fix stacked chords | [Harmonic MIDI Repair](features/harmonic-midi-repair.md) |
| `--requantize-midi` | Re-snap notes to grid while preserving feel | [MIDI Requantization](features/requantization.md) |
| `--requantize-mode` | Requantize mode: `strict`, `light`, `swing`, `triplet` | [MIDI Requantization](features/requantization.md) |
| `--reseparate` | Re-run AI stem separation on the full mix or a specific stem | [Separation Strategy](features/separation-strategy.md) |
| `--apply` | Write advanced feature changes to output files (without this, features only print analysis) | — |

## Export

| Flag | Default | Description |
|------|---------|-------------|
| `--export-als` | off | Generate Ableton Live Set from processed output |
| `--als-template` | auto | Path to custom `.als` template (auto-detected if not set) |
| `--ableton-version` | 12 | Target Ableton Live version (`11` or `12`) |

See [ALS Export](als-export.md) for details on how the export works.
