# Workflow Examples

Common recipes for different use cases.

## Minimal — just get stems into Ableton

```bash
suno-to-ableton process ~/suno-exports/my-song --export-als
# Open processed/Song.als in Ableton
```

## Full analysis — inspect before committing

```bash
# 1. Read-only scan — see BPM, stem inventory, alignment info
suno-to-ableton analyze ~/suno-exports/my-song

# 2. Dry run — see what processing would do without writing files
suno-to-ableton process ~/suno-exports/my-song --dry-run

# 3. Process for real
suno-to-ableton process ~/suno-exports/my-song --export-als
```

## Fix bad stems

When Suno's stems have bleed or quality issues, generate AI alternatives and auto-pick the better version:

```bash
suno-to-ableton process ~/suno-exports/my-song \
  --separate-missing \
  --choose-stems \
  --apply \
  --export-als
```

See [Stem Quality Judgment](features/stem-quality-judgment.md) and [Separation Strategy](features/separation-strategy.md) for details.

## Clean up MIDI for your own synths

When you want to use Suno's MIDI with your own instruments but the transcription has wrong notes:

```bash
suno-to-ableton process ~/suno-exports/my-song \
  --repair-midi \
  --requantize-midi --requantize-mode light \
  --apply \
  --export-als
```

See [Harmonic MIDI Repair](features/harmonic-midi-repair.md) and [MIDI Requantization](features/requantization.md) for details.

## Deep analysis — everything on

Run every advanced feature for maximum analysis and cleanup:

```bash
suno-to-ableton process ~/suno-exports/my-song \
  --export-als \
  --detect-sections \
  --choose-grid-anchor \
  --repair-midi \
  --requantize-midi --requantize-mode light \
  --separate-missing \
  --choose-stems \
  --apply
```

## Preview without applying

Most advanced features support preview mode — analyze and print results without modifying files. Just omit `--apply`:

```bash
# See what MIDI repair would fix
suno-to-ableton repair-midi ~/suno-exports/my-song

# See which stems would be replaced
suno-to-ableton choose-stems ~/suno-exports/my-song

# See detected sections
suno-to-ableton detect-sections ~/suno-exports/my-song
```

## Batch processing

Process multiple songs in sequence:

```bash
for song in ~/suno-exports/*/; do
  echo "Processing: $song"
  suno-to-ableton process "$song" --export-als
done
```
