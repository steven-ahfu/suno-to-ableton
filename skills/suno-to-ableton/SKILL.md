---
name: suno-to-ableton
description: Import a Suno export of audio stems and optional MIDI into a fresh Ableton Live Set using the suno-to-ableton project. Use for repeat imports or improving that importer.
---

# Suno to Ableton

The [suno-to-ableton Git repository](https://github.com/steven-ahfu/suno-to-ableton) is the source of truth for code and templates. This skill only describes how to use and maintain it; do not copy its implementation into the skill.

For an import, inspect the source folder and choose a new output directory so the original export and existing Live sets remain intact. Find an installed `suno-to-ableton` command or a local repository checkout. Read its current CLI help before running it. Use `process <source> --output-dir <new-project-dir> --export-als` for a new set. Use a BPM override only when supported by a trustworthy song or Live reference. Keep optional separation, MIDI repair, and requantization off unless the task calls for them.

After processing, inspect the report and the generated `.als`: each expected audio stem should have its own track and clip, each expected MIDI file should have its own lane, the tempo should match the chosen value, and every sample reference should resolve. Check reported warnings. Confirm the set opens in Live when it can be done without interrupting an active unsaved session; otherwise state that the check was structural only.

When updating the importer, work from its Git checkout. Inspect local changes before fetching. Review upstream changes, preserve local work, update dependencies with `uv sync`, and run the project tests plus a real export when changes affect the ALS format. Keep this skill linked to the Git checkout so a repository update updates the skill instructions too. Do not blindly overwrite existing music projects during an update.
