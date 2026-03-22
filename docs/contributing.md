# Contributing

Contributions are welcome! This guide covers how to set up a development environment, the project structure, and how to submit changes.

## Getting started

### 1. Fork and clone

```bash
# From your fork:
git clone https://github.com/<your-username>/suno-to-ableton.git
cd suno-to-ableton
```

### 2. Development install

```bash
uv sync --group dev --extra tui

# Optional: install CPU stem-separation stack too
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
uv sync --group dev --extra tui --extra separation
```

### 3. Verify

```bash
uv run suno-to-ableton --help
uv run pytest tests/ -v
```

## Project structure

```
suno_to_ableton/
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
├── progress.py             # Pipeline step status tracking for TUI progress display
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

tests/
├── test_models.py          # Data model unit tests
├── test_config.py          # Config and path resolution tests
├── test_alignment.py       # Alignment computation tests
├── test_discovery.py       # File discovery and classification tests
├── test_progress.py        # Pipeline step tracking tests
└── test_tui_integration.py # End-to-end TUI integration tests (Textual pilot)
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

3. Run the test suite and make sure everything passes:
   ```bash
   uv run pytest tests/ -v
   ```

4. Test your changes against a real Suno export if possible.

5. Push and open a pull request:
   ```bash
   git push origin feature/my-feature
   ```

6. In your PR description, explain what changed and why.

### Running tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_discovery.py -v

# Run the TUI integration tests only
uv run pytest tests/test_tui_integration.py -v
```

Unit tests cover models, config, alignment, discovery, and progress tracking. Integration tests use [Textual's pilot API](https://textual.textualize.io/guide/testing/) to drive the TUI end-to-end with mock project data — no real audio files required.

When adding new features, add tests for any pure logic (models, computation, classification). For TUI changes, add or update integration tests in `test_tui_integration.py`.

### Code style

- Follow existing patterns in the codebase
- Use type hints for function signatures
- Use Pydantic models for structured data
- Keep functions focused — if a function does too many things, split it
- Use `rich` for terminal output (not bare `print`)

### Adding a new advanced feature

Advanced features live in `suno_to_ableton/features/`. To add one:

1. Create a new module in `features/` following the pattern of existing ones
2. Add the CLI flag in `cli.py`
3. Wire it into the pipeline in `pipeline.py`
4. Write a doc in `docs/features/` explaining what decisions the feature makes and when to use it (see existing docs for the format)
5. Add the flag to the CLI flags table in [CLI Flags Reference](cli-flags.md)
6. Add the feature to the [Advanced Features overview](features/index.md)

### Documentation

Documentation lives in `docs/` and is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/). To preview locally:

```bash
uv sync --extra docs
uv run mkdocs serve
# Open http://127.0.0.1:8000
```

When adding or changing features, update the relevant docs.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project. See [LICENSE](https://github.com/steven-ahfu/suno-to-ableton/blob/main/LICENSE).
