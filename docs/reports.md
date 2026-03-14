# Reports & Output

After processing, the `processed/` directory contains all output files organized by type.

## Output structure

```
my-song/
└── processed/
    ├── stems/          # Normalized, trimmed WAVs
    ├── midi/           # Cleaned MIDI files
    ├── reports/        # Analysis reports (JSON)
    └── Song.als        # Ableton Live Set (if --export-als was used)
```

## Report files

The `processed/reports/` directory contains:

| File | Contents |
|------|----------|
| `manifest.json` | Full inventory of discovered and processed files, stem mappings, and metadata |
| `bpm_report.json` | Detected BPM, beat positions, confidence score |
| `timing_report.json` | Global offset, alignment details, per-stem timing analysis |

## Viewing reports

Use the `report` subcommand to view an existing manifest in a formatted table:

```bash
suno-to-ableton report /path/to/my-song
```

## manifest.json

Contains the complete inventory of what was discovered and processed:

- Input files found and their detected stem roles
- Output file paths for each processed stem
- Sample rate, frame count, and channel info
- BPM and timing metadata
- Which advanced features were run and their results

## bpm_report.json

Contains BPM detection details:

- Estimated BPM and confidence score
- Beat positions (in seconds and samples)
- Detection method and parameters used

## timing_report.json

Contains grid alignment details:

- Global offset (how much silence was trimmed)
- Per-stem timing analysis
- Downbeat position and alignment confidence
