# suno-ableton-preprocessor

Suno AI export preprocessor for Ableton Live. Takes Suno's numbered WAV stems and MIDI export and produces grid-aligned, normalized files ready for an Ableton Live session.

## What it does

### Automatic (runs by default)

1. **Discovery** — finds and identifies numbered WAV stems and MIDI files
2. **Naming** — maps Suno's numbered filenames to stem roles (Drums, Bass, Vocals, etc.)
3. **Sample-rate conversion** — resamples all audio to 48kHz stereo WAV
4. **Silence trim** — removes leading silence so clips start cleanly
5. **BPM estimation** — beat-tracks the drums/percussion stem with librosa
6. **Global offset alignment** — computes downbeat offset so every clip lands on the Ableton grid
7. **Conservative MIDI cleanup** — removes empty tracks, short/duplicate notes, quantizes to grid, sets tempo
8. **Manifest + reports** — writes `manifest.json`, `bpm_report.json`, and `timing_report.json`

### Advanced (opt-in, only when you need it)

These require explicit flags — they never run unless you ask for them. Each has a detailed doc explaining what decisions it makes and when to use it.

- **[Stem quality judgment](docs/features/stem-quality-judgment.md)** (`--choose-stems`) — compares original vs AI-generated stems and recommends the better version
- **[Grid anchor / bar-1 detection](docs/features/grid-anchor.md)** (`--choose-grid-anchor`) — analyzes grid anchor candidates when the intro downbeat is unclear
- **[Section detection](docs/features/section-detection.md)** (`--detect-sections`) — identifies arrangement sections (intro, verse, chorus, etc.)
- **[Harmonic MIDI repair](docs/features/harmonic-midi-repair.md)** (`--repair-midi`) — detects key, flags out-of-key notes, fixes stacked chords
- **[MIDI requantization](docs/features/requantization.md)** (`--requantize-midi`) — re-snaps notes to grid while preserving feel
- **[Separation strategy](docs/features/separation-strategy.md)** (`--reseparate`, `--separate-missing`) — AI stem separation with Demucs or UVR
- **ALS export (experimental)** (`--export-als`) — generates an Ableton Live Set with stems placed on matching tracks

## Quick start

### Prerequisites

- **Python 3.11+** — [install guide](INSTALL.md#python-311)
- **ffmpeg** on PATH — [install guide](INSTALL.md#ffmpeg)
- **pip** (bundled with Python) — [install guide](INSTALL.md#pip)
- **PyTorch** (only for stem separation) — [install guide](INSTALL.md#stem-separation-cpu)

> See **[INSTALL.md](INSTALL.md)** for full platform-specific installation instructions, optional extras, and dependency details.

### Install

```bash
git clone https://github.com/steven-ahfu/suno-ableton-preprocessor.git
cd suno-ableton-preprocessor
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

For the TUI, stem separation, or GPU acceleration, see **[INSTALL.md](INSTALL.md#optional-extras)**.

### Export from Suno

1. Open your song on [suno.com](https://suno.com)
2. Download **Stems** (ZIP of numbered WAV files)
3. Optionally download the **MIDI** file
4. Unzip into a project directory:

```bash
mkdir ~/suno-exports/my-song
# Unzip stems ZIP and move .mid file here
```

Expected layout:
```
my-song/
├── 0 Song Name.wav       # Full mix
├── 1 FX.wav              # FX stem
├── 2 Synth.wav           # Synth stem
├── 3 Percussion.wav      # Percussion
├── 4 Bass.wav            # Bass
├── 5 Drums.wav           # Drums
├── 6 Backing_Vocals.wav  # Backing vocals
├── 7 Vocals.wav          # Vocals
├── 8 sample.wav          # Sample
└── Song Name.mid         # MIDI (optional)
```

> See **[USAGE.md — Exporting from Suno](USAGE.md#exporting-from-suno)** for details on what Suno exports and how to handle edge cases.

### Process

```bash
# Read-only analysis
suno-ableton-preprocessor analyze ~/suno-exports/my-song

# Full processing pipeline
suno-ableton-preprocessor process ~/suno-exports/my-song

# Process + generate Ableton Live Set
suno-ableton-preprocessor process ~/suno-exports/my-song --export-als
```

> See **[USAGE.md](USAGE.md)** for the complete CLI/TUI reference, all flags, workflow examples, and advanced feature usage.

## Documentation

| Doc | Contents |
|-----|----------|
| **[INSTALL.md](INSTALL.md)** | Prerequisites, platform-specific install commands, optional extras, dependency reference |
| **[USAGE.md](USAGE.md)** | CLI commands, TUI, all flags, ALS export, workflow examples, report formats |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | Dev setup, project structure, code style, how to add features, PR process |
| [Stem Quality Judgment](docs/features/stem-quality-judgment.md) | How stem comparison works, when to use `--choose-stems` |
| [Grid Anchor](docs/features/grid-anchor.md) | Bar-1 detection for ambiguous intros |
| [Section Detection](docs/features/section-detection.md) | Arrangement section identification |
| [Harmonic MIDI Repair](docs/features/harmonic-midi-repair.md) | Key detection, wrong-note flagging, chord repair |
| [MIDI Requantization](docs/features/requantization.md) | Groove-aware quantization modes |
| [Separation Strategy](docs/features/separation-strategy.md) | Demucs vs UVR, targeted re-separation |

## Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for development setup, project structure, and how to submit changes.

## Acknowledgments

- [ableton-lom-skill](https://github.com/mikecfisher/ableton-lom-skill) — Ableton Live Object Model API reference used for Remote Script and ALS integration development

## License

See [LICENSE](LICENSE).
