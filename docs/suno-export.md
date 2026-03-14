# Exporting from Suno

Before using this tool, you need to export your song from Suno with stems and (optionally) MIDI.

## How to export

1. Open your song on [suno.ai](https://suno.ai)
2. Click the **download** button and select **Stems** — this downloads a ZIP containing individually numbered WAV files for each instrument
3. If available, download the **MIDI** file for the same song (Suno Studio can export MIDI derived from stems — useful for recreating melodies or drum patterns with your own instruments)
4. Create a project directory and unzip/move all files into it:

```bash
mkdir ~/suno-exports/my-song
# Unzip the stems ZIP into this directory
# Move the .mid file into the same directory (if available)
```

## What Suno exports

Suno exports **tempo-locked WAV stems** — all stems share the same BPM, sample rate, and frame count. This means:

- Stems stay aligned to the song's BPM when imported into a DAW
- They line up on the grid without manual adjustment
- Minimal warping is required in Ableton

The preprocessor verifies this: it checks that all stems have consistent sample rates and frame counts, and warns if anything is off.

!!! info "MIDI is optional"
    Not every Suno export includes MIDI. When available, it's a transcription (not the original sequence), so it may contain wrong notes or phantom chords — the preprocessor's [harmonic MIDI repair](features/harmonic-midi-repair.md) feature can help clean these up.

## Expected project directory structure

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

### File naming details

- WAV files are numbered `0`–`8` and prefixed with the stem type
- Track 0 is always the full mix; tracks 1–8 are the individual stems
- The MIDI file has no number prefix — it matches the song name
- All WAVs should be 48kHz stereo float with identical frame counts (tempo-locked)
- Not all stems may be present in every export (e.g. some songs have no sample or FX stem) — the preprocessor handles missing stems gracefully
