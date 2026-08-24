# ALS Export

The `--export-als` flag generates an Ableton Live Set (`.als` file) from processed stems and cleaned MIDI.

## How it works

1. Starts from a shipped Ableton-authored internal reference set
2. Writes the detected project tempo into the set
3. Rebuilds arrangement clips against canonical track names
4. Retargets audio clip file references to processed stem files
5. Rebuilds MIDI clips from cleaned MIDI files
6. Prunes unused managed tracks for the current project

## Important constraints

- ALS export must work from shipped internal templates only.
- User-authored `.als` files in a project directory are for reverse-engineering and debugging only. They are not used at runtime.
- Audio clips must live on `AudioTrack`s and MIDI clips must live on `MidiTrack`s.
- Processed filenames and exported track names are standardized by stem type, not copied through from raw Suno source filenames.

## Current managed track layout

The shipped reference currently supports these canonical lanes:

| Track | Type |
|-------|------|
| Drums | AudioTrack |
| Bass | AudioTrack |
| Synth | AudioTrack |
| Other | AudioTrack |
| MIDI Drums | MidiTrack |
| MIDI Bass | MidiTrack |
| MIDI Synth | MidiTrack |
| MIDI FX | MidiTrack |
| MIDI (Song) | MidiTrack |

Unused managed tracks are removed from the final export.

## Tempo formatting

Tempo is written using Ableton-style fixed precision such as `144.230769` instead of long Python float strings like `144.23076923076923`.

## Ableton version targeting

By default, exports target **Ableton Live 12**. Use `--ableton-version 11` or `--ableton-version 10` to target an older version.

Live 12 and Live 11 each use their own native template, so no XML downgrading is needed.

Live 10 is derived from the Live 11 template, because Live 10 cannot open a Live 11 set unchanged. Targeting it applies three conversions:

- The version header is rewritten to the Live 10 schema.
- Elements introduced in Live 11 are removed: comping take lanes (`TakeLanes`/`TakeId`), linked-track groups, clip key/scale metadata, and MPE data.
- Sample references are converted from the Live 11 string-path form back to the Live 10 element form (`HasRelativePath` / `RelativePathElement` / `Name`). The export directory is also marked as a Live project root so those project-relative paths resolve.

## Usage

### During processing

```bash
uv run suno-to-ableton process /path/to/my-song --export-als
```

### For Ableton 11 or 10

```bash
uv run suno-to-ableton export-als /path/to/my-song --ableton-version 11
```

```bash
uv run suno-to-ableton export-als /path/to/my-song --ableton-version 10
```

### From already-processed output

```bash
uv run suno-to-ableton export-als /path/to/my-song
```

### With a custom template

```bash
uv run suno-to-ableton process /path/to/my-song --export-als --als-template /path/to/MyTemplate.als
```

## Output

The generated `.als` file is written to the `processed/` directory. Open it directly in Ableton Live.

!!! note "Experimental"
    ALS export is still experimental. If you change the shipped reference/template structure, validate the regenerated `.als` in Live and inspect the exported XML, not just unit tests.
