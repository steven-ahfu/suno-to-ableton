# Separation Strategy

**Flags:** `--separate-missing`, `--reseparate`, `--separator`

Suno provides stems, but sometimes they're incomplete or low quality. AI stem separation (Demucs, UVR) can generate alternatives from the full mix.

## Decisions involved

- **Run separation at all?** Only needed if stems are missing, damaged, or have too much bleed. The automatic pipeline skips this unless you pass `--separate-missing`.
- **Demucs vs UVR?** Demucs (Meta's model) is the default — good general-purpose separation. UVR (Ultimate Vocal Remover) can be better for vocal isolation specifically.
- **Targeted re-separation?** Use `--reseparate` to re-run separation on the full mix or a specific stem (e.g. to isolate vocals from a bleed-heavy stem).
- **Lighter/faster model vs slower/better?** Demucs `htdemucs` is the default balance. Heavier models take longer but produce cleaner stems.

## When to use each flag

| Flag | Use case |
|------|----------|
| `--separate-missing` | First-time processing — generate stems that Suno didn't provide |
| `--reseparate` | Re-run separation after changing settings or to try a different backend |
| `--separator demucs` | General-purpose separation (default) |
| `--separator uvr` | When you specifically need cleaner vocal isolation |

## Example

```bash
# Generate missing stems with Demucs
suno-to-ableton process /path/to/my-song --separate-missing

# Re-run with UVR instead
suno-to-ableton reseparate /path/to/my-song --separator uvr

# Standalone separation
suno-to-ableton separate /path/to/my-song --separator demucs
```

## Combining with stem quality judgment

Run `--choose-stems` after separation to automatically compare originals vs generated stems:

```bash
suno-to-ableton process /path/to/my-song \
  --separate-missing \
  --choose-stems \
  --apply
```
