# Suno Ableton Preprocessor

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

### Advanced (opt-in)

These require explicit flags — they never run unless you ask for them. Each has a detailed doc explaining what decisions it makes and when to use it.

- **[Stem quality judgment](features/stem-quality-judgment.md)** (`--choose-stems`) — compares original vs AI-generated stems and recommends the better version
- **[Grid anchor / bar-1 detection](features/grid-anchor.md)** (`--choose-grid-anchor`) — analyzes grid anchor candidates when the intro downbeat is unclear
- **[Section detection](features/section-detection.md)** (`--detect-sections`) — identifies arrangement sections (intro, verse, chorus, etc.)
- **[Harmonic MIDI repair](features/harmonic-midi-repair.md)** (`--repair-midi`) — detects key, flags out-of-key notes, fixes stacked chords
- **[MIDI requantization](features/requantization.md)** (`--requantize-midi`) — re-snaps notes to grid while preserving feel
- **[Separation strategy](features/separation-strategy.md)** (`--reseparate`, `--separate-missing`) — AI stem separation with Demucs or UVR
- **[ALS export](als-export.md)** (experimental) (`--export-als`) — generates an Ableton Live Set with stems placed on matching tracks

## Quick start

```bash
# 1. Install prerequisites (Python 3.11+, ffmpeg) — see Installation page
# 2. Clone and install
git clone https://github.com/steven-ahfu/suno-ableton-preprocessor.git
cd suno-ableton-preprocessor
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 3. Export stems from Suno, unzip into a directory

# 4. Process
suno-ableton-preprocessor process ~/suno-exports/my-song --export-als

# 5. Open processed/Song.als in Ableton Live
```

## Next steps

- **[Installation](install.md)** — prerequisites, platform-specific install commands, optional extras
- **[Exporting from Suno](suno-export.md)** — how to get your stems and MIDI out of Suno
- **[CLI Usage](usage-cli.md)** — all commands and what they do
- **[Workflow Examples](workflows.md)** — common recipes for different use cases

## Acknowledgments

- [ableton-lom-skill](https://github.com/mikecfisher/ableton-lom-skill) — Ableton Live Object Model API reference used for Remote Script and ALS integration development

## License

See [LICENSE](https://github.com/steven-ahfu/suno-ableton-preprocessor/blob/main/LICENSE).
