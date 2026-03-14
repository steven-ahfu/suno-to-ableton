# Advanced Features

These features require explicit flags — they never run unless you ask for them. Each one handles a specific analysis or correction task that the automatic pipeline doesn't cover.

## Overview

| Feature | Flag | What it does |
|---------|------|-------------|
| [Stem Quality Judgment](stem-quality-judgment.md) | `--choose-stems` | Compares Suno's stems vs AI-generated ones using RMS energy, spectral centroid, and cross-correlation |
| [Grid Anchor / Bar-1 Detection](grid-anchor.md) | `--choose-grid-anchor` | Handles sparse intros, pickups, weak first kicks, and FX-only openings |
| [Section Detection](section-detection.md) | `--detect-sections` | Uses MFCC recurrence matrix and checkerboard novelty kernel for segmentation |
| [Harmonic MIDI Repair](harmonic-midi-repair.md) | `--repair-midi` | Detects key, flags wrong notes, resolves dissonant chord clusters |
| [MIDI Requantization](requantization.md) | `--requantize-midi` | Groove-aware quantization with strict, light, swing, and triplet modes |
| [Separation Strategy](separation-strategy.md) | `--reseparate`, `--separate-missing` | Demucs vs UVR, targeted re-separation |

## The `--apply` flag

All advanced features support **preview mode** by default — they analyze and print results without modifying files. Pass `--apply` to write changes to the output directory.

```bash
# Preview: prints analysis only
suno-ableton-preprocessor repair-midi /path/to/my-song

# Apply: writes corrected MIDI files
suno-ableton-preprocessor repair-midi /path/to/my-song --apply
```

## Using with the pipeline

Advanced features can be enabled during a full processing run:

```bash
suno-ableton-preprocessor process /path/to/my-song \
  --detect-sections \
  --repair-midi \
  --apply
```

Or run standalone after processing:

```bash
suno-ableton-preprocessor detect-sections /path/to/my-song
suno-ableton-preprocessor repair-midi /path/to/my-song --apply
```
