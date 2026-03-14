# Contributing

Contributions are welcome! This guide covers how to set up a development environment, the project structure, and how to submit changes.

## Getting started

### 1. Fork and clone

```bash
git clone https://github.com/<your-username>/suno-ableton-preprocessor.git
cd suno-ableton-preprocessor
```

### 2. Development install

```bash
python3 -m venv .venv
source .venv/bin/activate

# Install with all extras for development
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -e '.[tui,separation]'
```

### 3. Verify

```bash
suno-ableton-preprocessor --help
```

## Project structure

```
suno_ableton_preprocessor/
├── cli.py                  # Typer CLI entry point and subcommands
├── pipeline.py             # Main processing pipeline orchestration
├── discovery.py            # Stem/MIDI file discovery and naming
├── audio_processing.py     # Sample-rate conversion, silence trimming
├── bpm_detection.py        # BPM estimation with librosa
├── alignment.py            # Global offset and grid alignment
├── midi_cleanup.py         # Conservative MIDI cleanup (empty tracks, short notes, quantize)
├── separation.py           # Stem separation (Demucs/UVR) integration
├── models.py               # Pydantic data models
├── config.py               # Configuration and defaults
├── reporting.py            # Manifest and report generation
├── tui.py                  # Textual TUI application
└── features/               # Advanced opt-in features
    ├── choose_stems.py     # Stem quality comparison
    ├── choose_grid_anchor.py  # Bar-1 / grid anchor detection
    ├── detect_sections.py  # Section segmentation
    ├── repair_midi.py      # Harmonic MIDI repair
    ├── requantize_midi.py  # Groove-aware requantization
    ├── reseparate.py       # Targeted re-separation
    └── export_als.py       # Ableton Live Set generation
```

## How to contribute

### Reporting bugs

Open an issue with:

- What you expected to happen
- What actually happened
- Steps to reproduce (include the command you ran)
- OS, Python version, and any relevant package versions

### Suggesting features

Open an issue describing:

- The problem you're trying to solve
- Your proposed solution (if you have one)
- Any alternative approaches you considered

### Submitting changes

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/my-feature
   ```

2. Make your changes. Keep commits focused — one logical change per commit.

3. Test your changes against a real Suno export if possible.

4. Push and open a pull request:
   ```bash
   git push origin feature/my-feature
   ```

5. In your PR description, explain what changed and why.

### Code style

- Follow existing patterns in the codebase
- Use type hints for function signatures
- Use Pydantic models for structured data
- Keep functions focused — if a function does too many things, split it
- Use `rich` for terminal output (not bare `print`)

### Adding a new advanced feature

Advanced features live in `suno_ableton_preprocessor/features/`. To add one:

1. Create a new module in `features/` following the pattern of existing ones
2. Add the CLI flag in `cli.py`
3. Wire it into the pipeline in `pipeline.py`
4. Write a doc in `docs/features/` explaining what decisions the feature makes and when to use it (see existing docs for the format)
5. Add the flag to the CLI flags table in [CLI Flags Reference](cli-flags.md)
6. Add the feature to the [Advanced Features overview](features/index.md)

### Documentation

Documentation lives in `docs/` and is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/). To preview locally:

```bash
pip install mkdocs-material
mkdocs serve
# Open http://127.0.0.1:8000
```

When adding or changing features, update the relevant docs.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project. See [LICENSE](https://github.com/steven-ahfu/suno-ableton-preprocessor/blob/main/LICENSE).
