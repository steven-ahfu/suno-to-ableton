# ALS Export

The `--export-als` flag generates an Ableton Live Set (`.als` file) from your processed stems.

## How it works

1. **Copies the template** — uses the bundled `Example.als` template (or specify a custom one with `--als-template`)
2. **Sets project tempo** — writes the detected BPM into the Live Set
3. **Matches stems to tracks** — maps processed stems to template tracks by type (Drums, Bass, Vocals, etc.)
4. **Injects AudioClips** — places unwarped audio clips into arrangement view
5. **Mutes the full mix** — the reference track is included but muted so it doesn't double the audio

## Template tracks

The bundled template has pre-configured tracks:

| Track | Stem type |
|-------|-----------|
| Drums | Drums |
| Percussion | Percussion |
| Bass | Bass |
| Synth | Synth |
| Vocals | Vocals |
| Backing Vocals | Backing Vocals |
| FX | FX |
| Sample | Sample |
| MIDI tracks | For cleaned MIDI files |

## Usage

### During processing

```bash
suno-to-ableton process /path/to/my-song --export-als
```

### From already-processed output

```bash
suno-to-ableton export-als /path/to/my-song
```

### With a custom template

```bash
suno-to-ableton process /path/to/my-song --export-als --als-template /path/to/MyTemplate.als
```

## Output

The generated `.als` file is written to the `processed/` directory. Open it directly in Ableton Live.

!!! note "Experimental"
    ALS export is experimental. The generated Live Set should work out of the box, but complex template customizations may require manual adjustment in Ableton.
