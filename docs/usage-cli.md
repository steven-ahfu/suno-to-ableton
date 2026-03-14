# CLI Usage

The command-line tool is called `suno-ableton-preprocessor`.

## Quick analysis (read-only)

Scan a project directory and print BPM, alignment, and inventory info without writing any files:

```bash
suno-ableton-preprocessor analyze /path/to/my-song
```

This is useful for previewing what the tool will detect before committing to a full processing run.

## Full processing pipeline

Process audio and MIDI, write normalized stems and cleaned MIDI to a `processed/` subdirectory:

```bash
suno-ableton-preprocessor process /path/to/my-song
```

Output structure:

```
my-song/
└── processed/
    ├── stems/          # Normalized, trimmed WAVs
    ├── midi/           # Cleaned MIDI files
    └── reports/        # manifest.json, bpm_report.json, timing_report.json
```

## Process and export an Ableton Live Set

```bash
suno-ableton-preprocessor process /path/to/my-song --export-als
```

This adds a `Song.als` file to `processed/` that you can open directly in Ableton Live, with stems placed on pre-configured tracks. See [ALS Export](als-export.md) for details.

## Process with all options

```bash
suno-ableton-preprocessor process /path/to/my-song \
  --export-als \
  --detect-sections \
  --choose-grid-anchor \
  --repair-midi \
  --requantize-midi --requantize-mode light \
  --apply
```

## Standalone commands

Each subcommand can be run independently:

```bash
# Stem separation only
suno-ableton-preprocessor separate /path/to/my-song --separator demucs

# View existing manifest
suno-ableton-preprocessor report /path/to/my-song

# Generate Ableton Live Set from already-processed output
suno-ableton-preprocessor export-als /path/to/my-song
```

### Advanced feature commands

These can also be run standalone outside the main pipeline:

```bash
suno-ableton-preprocessor choose-stems /path/to/my-song --apply
suno-ableton-preprocessor choose-grid-anchor /path/to/my-song
suno-ableton-preprocessor detect-sections /path/to/my-song
suno-ableton-preprocessor repair-midi /path/to/my-song --apply
suno-ableton-preprocessor requantize-midi /path/to/my-song --mode swing --apply
suno-ableton-preprocessor reseparate /path/to/my-song --target full_mix
```

See [Advanced Features](features/index.md) for detailed documentation on each.

## The `--apply` flag

Many advanced features operate in **preview mode** by default — they analyze and print results but don't modify files. Pass `--apply` to write changes to the output directory.

This lets you inspect what the tool would do before committing:

```bash
# Preview: prints analysis only
suno-ableton-preprocessor repair-midi /path/to/my-song

# Apply: writes corrected MIDI files
suno-ableton-preprocessor repair-midi /path/to/my-song --apply
```

For the full flag reference, see [CLI Flags](cli-flags.md).
