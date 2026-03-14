# Grid Anchor (Bar-1 Detection)

**Flag:** `--choose-grid-anchor`

The automatic pipeline estimates where bar 1 starts using the first strong transient. This works for most songs, but some arrangements make it ambiguous.

## Tricky cases this handles

- **Sparse intros** — pad or ambient texture with no clear rhythmic hit
- **Pickups / anacrusis** — a melodic phrase that starts before bar 1 (e.g. "and-a one, two, three, four")
- **Weak first kick** — the downbeat exists but is softer than a later hit, so beat tracking latches onto the wrong transient
- **FX-only openings** — risers, sweeps, or reverse crashes before the actual music starts
- **First transient ≠ musical downbeat** — a vocal ad-lib, guitar scrape, or click that happens before the arrangement begins

## How it works

Analyzes beat interval regularity (sliding-window std dev), onset positions relative to the beat grid, and leading silence duration. Generates a ranked list of anchor candidates with confidence scores and a recommended pick.

## When to use it

- When the automatic alignment sounds off by a beat or half-bar
- When the song starts with a long intro that doesn't have a clear kick
- When you're batch-processing and want to flag songs that need manual review

## Example

```bash
# Analyze candidates
suno-ableton-preprocessor choose-grid-anchor /path/to/my-song

# Apply the recommended anchor during processing
suno-ableton-preprocessor process /path/to/my-song --choose-grid-anchor --apply
```

## What `--apply` does

Without `--apply`, prints the candidate list with confidence scores. With `--apply`, adjusts the global offset to use the recommended anchor point.
