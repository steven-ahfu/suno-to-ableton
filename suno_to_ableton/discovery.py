"""File scanning and Suno naming classification."""

from __future__ import annotations

import re
from pathlib import Path

import soundfile as sf

from .models import (
    DiscoveredFile,
    FileRole,
    ProjectInventory,
    StemType,
    STEM_NAME_MAP,
)

AUDIO_EXTENSIONS = {".wav", ".flac", ".aiff", ".aif", ".mp3", ".ogg"}
MIDI_EXTENSIONS = {".mid", ".midi"}

# Matches Suno's "0 name.wav", "1 FX.wav", etc.
NUMBERED_STEM_RE = re.compile(r"^(\d+)\s+(.+)$")


def _classify_stem_name(name: str) -> StemType:
    """Map a stem name like 'Drums' or 'Backing_Vocals' to a StemType."""
    candidates = [name.lower().strip()]

    # MIDI exports often include the stem in parentheses, e.g. "Song (Drums)".
    parenthetical = re.findall(r"\(([^()]+)\)", name)
    for part in reversed(parenthetical):
        candidates.append(part.lower().strip())

    for key in candidates:
        if key in STEM_NAME_MAP:
            return STEM_NAME_MAP[key]
        # Try replacing spaces with underscores
        key_underscore = key.replace(" ", "_")
        if key_underscore in STEM_NAME_MAP:
            return STEM_NAME_MAP[key_underscore]
    return StemType.OTHER


def _probe_audio(path: Path) -> dict:
    """Get audio metadata without loading samples."""
    try:
        info = sf.info(str(path))
        return {
            "sample_rate": info.samplerate,
            "channels": info.channels,
            "frames": info.frames,
            "duration_seconds": info.duration,
            "subtype": info.subtype,
        }
    except Exception:
        return {}


def _sanitize_title(name: str) -> str:
    """Clean up a song title from filename."""
    stem_type = _classify_stem_name(name)
    if stem_type not in (StemType.OTHER, StemType.FULL_MIX):
        match = re.search(r"^(.*?)\s*\(([^()]+)\)\s*$", name)
        if match and _classify_stem_name(match.group(2)) == stem_type:
            name = match.group(1)

    # Remove common suffixes
    for suffix in [" - remix", " - Remix", " remix", " Remix"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()


def scan_for_projects(root: Path, max_depth: int = 5) -> list[tuple[Path, str]]:
    """Recursively scan for Suno export project directories.

    Returns list of (directory_path, song_title) tuples for directories
    that contain at least one numbered audio stem or MIDI file.
    """
    root = root.resolve()
    results: list[tuple[Path, str]] = []

    if not root.is_dir():
        return results

    def _has_project_files(directory: Path) -> str | None:
        """Check if directory looks like a Suno export. Returns song title or None."""
        has_numbered_audio = False
        has_midi = False
        song_title = ""

        try:
            entries = list(directory.iterdir())
        except PermissionError:
            return None

        for entry in entries:
            if not entry.is_file():
                continue
            suffix = entry.suffix.lower()
            stem = entry.stem

            if suffix in MIDI_EXTENSIONS:
                has_midi = True
                if not song_title:
                    song_title = _sanitize_title(stem)

            if suffix in AUDIO_EXTENSIONS:
                match = NUMBERED_STEM_RE.match(stem)
                if match:
                    has_numbered_audio = True
                    if int(match.group(1)) == 0 and not song_title:
                        song_title = _sanitize_title(match.group(2))

        if has_numbered_audio or (has_midi and any(
            e.suffix.lower() in AUDIO_EXTENSIONS for e in entries if e.is_file()
        )):
            return song_title or directory.name
        return None

    def _walk(directory: Path, depth: int) -> None:
        if depth > max_depth:
            return
        # Skip common non-project directories
        skip_names = {"processed", ".git", "__pycache__", "node_modules", ".venv", "venv"}
        if directory.name in skip_names:
            return

        title = _has_project_files(directory)
        if title:
            results.append((directory, title))

        try:
            subdirs = sorted(
                e for e in directory.iterdir()
                if e.is_dir() and e.name not in skip_names
            )
        except PermissionError:
            return

        for subdir in subdirs:
            _walk(subdir, depth + 1)

    _walk(root, 0)
    return results


def discover_project(source_dir: Path) -> ProjectInventory:
    """Scan a directory for Suno export files and classify them."""
    source_dir = source_dir.resolve()
    inventory = ProjectInventory(source_dir=source_dir)

    if not source_dir.is_dir():
        inventory.warnings.append(f"Source directory does not exist: {source_dir}")
        return inventory

    files = sorted(source_dir.iterdir())

    for file_path in files:
        if not file_path.is_file():
            continue

        suffix = file_path.suffix.lower()
        stem = file_path.stem

        # MIDI files
        if suffix in MIDI_EXTENSIONS:
            discovered = DiscoveredFile(
                path=file_path,
                role=FileRole.MIDI,
                stem_type=_classify_stem_name(stem),
                stem_name=stem,
            )
            inventory.midi_files.append(discovered)
            # Derive song title from MIDI filename if not set
            if not inventory.song_title:
                inventory.song_title = _sanitize_title(stem)
            continue

        # Audio files
        if suffix not in AUDIO_EXTENSIONS:
            continue

        match = NUMBERED_STEM_RE.match(stem)
        if match:
            track_num = int(match.group(1))
            stem_name = match.group(2)
            audio_meta = _probe_audio(file_path)
            inferred_stem_type = _classify_stem_name(stem_name)

            if track_num == 0 and inferred_stem_type in (StemType.OTHER, StemType.FULL_MIX):
                # Track 0 = full mix
                discovered = DiscoveredFile(
                    path=file_path,
                    role=FileRole.AUDIO_FULL_MIX,
                    stem_type=StemType.FULL_MIX,
                    track_number=track_num,
                    stem_name=stem_name,
                    **audio_meta,
                )
                inventory.full_mix = discovered
                # Derive song title from track 0
                inventory.song_title = _sanitize_title(stem_name)
            else:
                # Numbered stems. Some exports are stem-only and zero-indexed.
                discovered = DiscoveredFile(
                    path=file_path,
                    role=FileRole.AUDIO_STEM,
                    stem_type=inferred_stem_type,
                    track_number=track_num,
                    stem_name=stem_name,
                    **audio_meta,
                )
                inventory.stems.append(discovered)
        else:
            # Unnumbered audio file — treat as unknown stem
            audio_meta = _probe_audio(file_path)
            discovered = DiscoveredFile(
                path=file_path,
                role=FileRole.AUDIO_STEM,
                stem_type=_classify_stem_name(stem),
                stem_name=stem,
                **audio_meta,
            )
            inventory.stems.append(discovered)
            inventory.warnings.append(
                f"Audio file without track number: {file_path.name}"
            )

    # Sort stems by track number
    inventory.stems.sort(
        key=lambda f: (f.track_number if f.track_number is not None else 999, f.stem_name)
    )

    # Validate
    if not inventory.full_mix and not inventory.stems:
        inventory.warnings.append("No audio files found")
    if not inventory.midi_files:
        inventory.warnings.append("No MIDI files found")

    # Check frame consistency
    all_audio = []
    if inventory.full_mix:
        all_audio.append(inventory.full_mix)
    all_audio.extend(inventory.stems)

    frame_counts = {f.frames for f in all_audio if f.frames is not None}
    if len(frame_counts) > 1:
        inventory.warnings.append(
            f"Inconsistent frame counts across audio files: {frame_counts}"
        )

    sample_rates = {f.sample_rate for f in all_audio if f.sample_rate is not None}
    if len(sample_rates) > 1:
        inventory.warnings.append(
            f"Inconsistent sample rates across audio files: {sample_rates} — "
            "Suno exports should be tempo-locked at the same sample rate"
        )

    return inventory
