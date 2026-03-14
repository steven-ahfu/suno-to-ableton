# Harmonic MIDI Repair

**Flag:** `--repair-midi`

Suno's MIDI export is a transcription, not the original sequence — it contains wrong notes, phantom chords, and ambiguous key signatures. This feature does conservative harmonic cleanup.

## What it evaluates

- **What key is the song in?** Analyzes note distribution to detect the most likely key and scale.
- **Which notes are wrong?** Flags notes that fall outside the detected key, weighted by duration and velocity.
- **Are these passing tones or mistakes?** Short chromatic notes between scale tones are likely intentional; sustained out-of-key notes are likely errors.
- **Are there bad chords?** Detects stacked notes that form dissonant clusters (e.g. C and C# sounding together) and resolves them.

## When to use it

- When the MIDI sounds off and you don't want to manually fix every note
- When you're using the MIDI to drive a different synth and need clean harmonic content
- When batch-processing and want to flag songs with the most MIDI errors

## Example

```bash
# Analyze without modifying
suno-ableton-preprocessor repair-midi /path/to/my-song

# Fix and write corrected MIDI
suno-ableton-preprocessor repair-midi /path/to/my-song --apply
```

## What `--apply` does

Without `--apply`, prints a report of detected key, flagged notes, and problem chords. With `--apply`, writes corrected MIDI files to the output directory.
