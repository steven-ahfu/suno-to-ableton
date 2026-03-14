# Stem Quality Judgment

**Flag:** `--choose-stems`

Suno exports numbered stems, but their quality varies — some have audible bleed, phase issues, or missing frequency content. When `--separate-missing` generates AI stems via Demucs or UVR, you now have two versions of each stem. This feature helps you pick the better one.

## What it evaluates

- **Is Suno's provided stem good enough?** Compares RMS energy, spectral centroid, and silence ratio to detect thin or empty stems.
- **Is the Demucs output better than the original?** Computes normalized cross-correlation between both versions, then scores on silence ratio and energy to recommend the cleaner one.
- **Replace one stem or all?** Reports per-stem with individual confidence scores, so you can swap only the bad ones instead of throwing out Suno's work wholesale.

## When to use it

- After running `--separate-missing` to generate AI stems alongside the originals
- When you hear bleed or phasing in a specific stem and want a data-backed second opinion
- When you want to automate "listen to both, pick the better one" across a batch of songs

## Example

```bash
# Generate AI stems, then compare
suno-ableton-preprocessor process /path/to/my-song --separate-missing --choose-stems --apply

# Or standalone after processing
suno-ableton-preprocessor choose-stems /path/to/my-song --apply
```

## What `--apply` does

Without `--apply`, prints a comparison report. With `--apply`, copies the recommended stem into the output directory, replacing the weaker version.
