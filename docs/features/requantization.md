# MIDI Requantization

**Flag:** `--requantize-midi`

The automatic pipeline does basic grid quantization during MIDI cleanup. This feature goes further — it re-evaluates timing with awareness of groove, feel, and musical intent.

## Decisions it makes

- **Quantize tightly or preserve groove?** Some parts (hi-hats, bass) benefit from tight grid; others (keys, pads) sound better with loose timing.
- **Straight vs triplet/swing?** Detects whether the original timing implies a swing or triplet feel and snaps to the appropriate grid.
- **How much humanization to keep?** Measures the average timing deviation and preserves intentional push/pull while correcting drift.

## Modes

| Mode | Behavior |
|------|----------|
| `light` | Gentle nudge toward grid — preserves most of the original feel |
| `strict` | Hard snap to nearest grid position |
| `swing` | Quantizes to a swung grid (alternating long-short subdivisions) |
| `triplet` | Quantizes to a triplet grid |

## When to use it

- When the basic MIDI cleanup sounds too stiff or too loose
- When you want to change the feel (e.g. straighten a swung part, or add swing to a straight part)
- When you're layering the MIDI with a different instrument and need tighter timing

## Example

```bash
# Light requantization
suno-to-ableton requantize-midi /path/to/my-song --mode light --apply

# Add swing
suno-to-ableton requantize-midi /path/to/my-song --mode swing --apply

# During full processing
suno-to-ableton process /path/to/my-song --requantize-midi --requantize-mode light --apply
```

## What `--apply` does

Without `--apply`, prints how many notes would move and by how much. With `--apply`, writes requantized MIDI files to the output directory.
