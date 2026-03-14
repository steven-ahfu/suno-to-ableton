# Section Detection (Arrangement Reconstruction)

**Flag:** `--detect-sections`

Identifies structural sections in the song — intro, verse, pre-chorus, chorus, bridge, outro — using spectral segmentation.

## What it evaluates

- **Where do sections start and end?** Builds an MFCC recurrence matrix and applies a checkerboard novelty kernel to find boundaries.
- **What is each section?** Labels boundaries based on energy profiles, repetition, and position in the song.
- **Where are good loop/cut points?** Identifies section boundaries that align with bar lines for clean arrangement editing in Ableton.

## When to use it

- When you want Ableton locators placed at section boundaries
- When you're rearranging a song and need to know where the chorus starts
- When batch-processing and want a structural overview of each song without listening

## Example

```bash
# Analyze sections
suno-to-ableton detect-sections /path/to/my-song

# Include in full processing
suno-to-ableton process /path/to/my-song --detect-sections
```

## Output

Writes section data to the manifest and prints a table like:

```
   intro    0.0s -   8.2s  bars 1-4    conf=0.91
   verse    8.2s -  24.5s  bars 5-12   conf=0.87
  chorus   24.5s -  40.8s  bars 13-20  conf=0.93
```
