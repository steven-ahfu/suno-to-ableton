# Usage Guide

## Exporting from Suno

Before using this tool, export your song from Suno with stems and (optionally) MIDI.

### How to export

1. Open your song on [suno.com](https://suno.com)
2. Click the **download** button and select **Stems** — this downloads a ZIP containing individually numbered WAV files for each instrument
3. If available, download the **MIDI** file for the same song (Suno Studio can export MIDI derived from stems — useful for recreating melodies or drum patterns with your own instruments)
4. Create a project directory and unzip/move all files into it:

```bash
mkdir ~/suno-exports/my-song
# Unzip the stems ZIP into this directory
# Move the .mid file into the same directory (if available)
```

### What Suno exports

Suno exports **tempo-locked WAV stems** — all stems share the same BPM, sample rate, and frame count. This means:

- Stems stay aligned to the song's BPM when imported into a DAW
- They line up on the grid without manual adjustment
- Minimal warping is required in Ableton

The preprocessor verifies this: it checks that all stems have consistent sample rates and frame counts, and warns if anything is off.

**MIDI is optional.** Not every Suno export includes MIDI. When available, it's a transcription (not the original sequence), so it may contain wrong notes or phantom chords — the preprocessor's [harmonic MIDI repair](docs/features/harmonic-midi-repair.md) feature can help clean these up.

### Expected project directory structure

```
my-song/
├── 0 Song Name.wav          # Full mix (track 0)
├── 1 FX.wav                 # FX stem
├── 2 Synth.wav              # Synth stem
├── 3 Percussion.wav         # Percussion stem
├── 4 Bass.wav               # Bass stem
├── 5 Drums.wav              # Drums stem
├── 6 Backing_Vocals.wav     # Backing vocals stem
├── 7 Vocals.wav             # Vocals stem
├── 8 sample.wav             # Sample stem
└── Song Name.mid            # MIDI file (optional)
```

**Notes:**
- WAV files are numbered `0`–`8` and prefixed with the stem type
- Track 0 is always the full mix; tracks 1–8 are the individual stems
- The MIDI file has no number prefix — it matches the song name
- All WAVs should be 48kHz stereo float with identical frame counts (tempo-locked)
- Not all stems may be present in every export (e.g. some songs have no sample or FX stem) — the preprocessor handles missing stems gracefully

---

## CLI

The command-line tool is called `suno-ableton-preprocessor`.

### Quick analysis (read-only)

Scan a project directory and print BPM, alignment, and inventory info without writing any files:

```bash
suno-ableton-preprocessor analyze /path/to/my-song
```

### Full processing pipeline

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

### Process and export an Ableton Live Set

```bash
suno-ableton-preprocessor process /path/to/my-song --export-als
```

This adds a `Song.als` file to `processed/` that you can open directly in Ableton Live, with stems placed on pre-configured tracks.

### Process with all options

```bash
suno-ableton-preprocessor process /path/to/my-song \
  --export-als \
  --detect-sections \
  --choose-grid-anchor \
  --repair-midi \
  --requantize-midi --requantize-mode light \
  --apply
```

### Standalone commands

Each subcommand can be run independently:

```bash
# Stem separation only
suno-ableton-preprocessor separate /path/to/my-song --separator demucs

# View existing manifest
suno-ableton-preprocessor report /path/to/my-song

# Generate Ableton Live Set from already-processed output
suno-ableton-preprocessor export-als /path/to/my-song

# Advanced features (standalone)
suno-ableton-preprocessor choose-stems /path/to/my-song --apply
suno-ableton-preprocessor choose-grid-anchor /path/to/my-song
suno-ableton-preprocessor detect-sections /path/to/my-song
suno-ableton-preprocessor repair-midi /path/to/my-song --apply
suno-ableton-preprocessor requantize-midi /path/to/my-song --mode swing --apply
suno-ableton-preprocessor reseparate /path/to/my-song --target full_mix
```

---

## TUI (interactive terminal interface)

Requires the `tui` extra: `pip install -e '.[tui]'`

```bash
suno-ableton-preprocessor tui
```

![TUI screenshot](docs/tui.png)

The TUI lets you:
- Browse and select project directories
- Toggle processing options with checkboxes
- Run the pipeline and view results in real time

---

## CLI flags reference

### Pipeline tuning

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

### Advanced features (opt-in)

None of these run unless you explicitly pass the flag. Use them when the automatic results need manual correction or deeper analysis. Each has a detailed doc explaining the decisions it makes.

| Flag | Description | Details |
|------|-------------|---------|
| `--choose-stems` | Compare original vs AI-generated stems, recommend the better version | [docs/features/stem-quality-judgment.md](docs/features/stem-quality-judgment.md) |
| `--choose-grid-anchor` | Analyze grid anchor candidates when the intro downbeat is unclear | [docs/features/grid-anchor.md](docs/features/grid-anchor.md) |
| `--detect-sections` | Identify arrangement sections (intro, verse, chorus, etc.) | [docs/features/section-detection.md](docs/features/section-detection.md) |
| `--repair-midi` | Detect key, flag out-of-key notes, fix stacked chords | [docs/features/harmonic-midi-repair.md](docs/features/harmonic-midi-repair.md) |
| `--requantize-midi` | Re-snap notes to grid while preserving feel | [docs/features/requantization.md](docs/features/requantization.md) |
| `--requantize-mode` | Requantize mode: `strict`, `light`, `swing`, `triplet` | [docs/features/requantization.md](docs/features/requantization.md) |
| `--reseparate` | Re-run AI stem separation on the full mix or a specific stem | [docs/features/separation-strategy.md](docs/features/separation-strategy.md) |
| `--apply` | Write advanced feature changes to output files (without this, features only print analysis) | — |

### Export

| Flag | Description |
|------|-------------|
| `--export-als` | Generate Ableton Live Set from processed output |
| `--als-template` | Path to `Example.als` template (auto-detected if not set) |

---

## ALS export

The `--export-als` flag generates an Ableton Live Set by:

1. Copying the `Example.als` template (bundled or specify with `--als-template`)
2. Setting project tempo to detected BPM
3. Matching processed stems to template tracks by type (Drums, Bass, Vocals, etc.)
4. Injecting unwarped AudioClips into arrangement view
5. Muting the full mix reference track

The template has pre-configured tracks: Drums, Percussion, Bass, Synth, Vocals, Backing Vocals, FX, Sample, plus MIDI tracks.

---

## Advanced feature details

Each advanced feature has its own documentation with explanations of the decisions it makes, when to use it, and example commands:

| Feature | Doc | Summary |
|---------|-----|---------|
| Stem quality judgment | [docs/features/stem-quality-judgment.md](docs/features/stem-quality-judgment.md) | Compares Suno's stems vs AI-generated ones using RMS energy, spectral centroid, and cross-correlation |
| Grid anchor / bar-1 detection | [docs/features/grid-anchor.md](docs/features/grid-anchor.md) | Handles sparse intros, pickups, weak first kicks, and FX-only openings |
| Section detection | [docs/features/section-detection.md](docs/features/section-detection.md) | Uses MFCC recurrence matrix and checkerboard novelty kernel for segmentation |
| Harmonic MIDI repair | [docs/features/harmonic-midi-repair.md](docs/features/harmonic-midi-repair.md) | Detects key, flags wrong notes, resolves dissonant chord clusters |
| MIDI requantization | [docs/features/requantization.md](docs/features/requantization.md) | Groove-aware quantization with strict, light, swing, and triplet modes |
| Separation strategy | [docs/features/separation-strategy.md](docs/features/separation-strategy.md) | Demucs vs UVR, targeted re-separation, combining with stem quality judgment |

---

## Workflow examples

### Minimal — just get stems into Ableton

```bash
suno-ableton-preprocessor process ~/suno-exports/my-song --export-als
# Open processed/Song.als in Ableton
```

### Full analysis — inspect before committing

```bash
# 1. Read-only scan
suno-ableton-preprocessor analyze ~/suno-exports/my-song

# 2. Process with dry-run to see what would happen
suno-ableton-preprocessor process ~/suno-exports/my-song --dry-run

# 3. Process for real
suno-ableton-preprocessor process ~/suno-exports/my-song --export-als
```

### Fix bad stems

```bash
# Generate AI alternatives and auto-pick the best
suno-ableton-preprocessor process ~/suno-exports/my-song \
  --separate-missing \
  --choose-stems \
  --apply \
  --export-als
```

### Clean up MIDI for use with your own synths

```bash
suno-ableton-preprocessor process ~/suno-exports/my-song \
  --repair-midi \
  --requantize-midi --requantize-mode light \
  --apply \
  --export-als
```

### Deep analysis — everything on

```bash
suno-ableton-preprocessor process ~/suno-exports/my-song \
  --export-als \
  --detect-sections \
  --choose-grid-anchor \
  --repair-midi \
  --requantize-midi --requantize-mode light \
  --separate-missing \
  --choose-stems \
  --apply
```

---

## Reports and output files

After processing, the `processed/reports/` directory contains:

| File | Contents |
|------|----------|
| `manifest.json` | Full inventory of discovered and processed files, stem mappings, and metadata |
| `bpm_report.json` | Detected BPM, beat positions, confidence score |
| `timing_report.json` | Global offset, alignment details, per-stem timing analysis |

Use the `report` subcommand to view an existing manifest:

```bash
suno-ableton-preprocessor report /path/to/my-song
```
