"""Experimental Ableton Live Set (.als) export.

Strategy: Copy the bundled Example.als template, then modify the XML to:
1. Set project tempo from detected BPM
2. Match existing template tracks to processed stems by name/type
3. Inject AudioClip elements into arrangement for each matched track
4. Inject MidiClip elements for processed MIDI files
5. Mute the full mix reference track if present

The template already has the right track layout (Drums, Percussion, Bass,
Synth, Vocals, Backing Vocals, FX, Sample + MIDI tracks). We match
processed stems to template tracks by stem type.
"""

from __future__ import annotations

import gzip
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import soundfile as sf

from ..config import SunoPrepConfig
from ..models import (
    ALSExportResult,
    FeatureInvocation,
    ProcessingManifest,
    StemType,
)
from ..reporting import write_json_report


# Map stem types to expected template track names
_STEM_TO_TRACK_NAME: dict[StemType, str] = {
    StemType.DRUMS: "Drums",
    StemType.PERCUSSION: "Percussion",
    StemType.BASS: "Bass",
    StemType.SYNTH: "Synth",
    StemType.VOCALS: "Vocals",
    StemType.BACKING_VOCALS: "Backing Vocals",
    StemType.FX: "FX",
    StemType.FULL_MIX: "Full Mix",
}

# Ableton track color palette indices
_TRACK_COLORS: dict[StemType, int] = {
    StemType.DRUMS: 69,
    StemType.PERCUSSION: 17,
    StemType.BASS: 4,
    StemType.SYNTH: 24,
    StemType.VOCALS: 57,
    StemType.BACKING_VOCALS: 58,
    StemType.FX: 45,
    StemType.FULL_MIX: 0,
}


def _find_template(config: SunoPrepConfig) -> Path:
    """Locate the Ableton .als template file."""
    # Check explicit config path first
    if config.als_template and config.als_template.exists():
        return config.als_template

    _repo_root = Path(__file__).parent.parent.parent

    # Check common locations
    candidates = [
        _repo_root / "templates" / "Ableton 12.als",
        config.source_dir / "Example.als",
        config.source_dir.parent / "Example.als",
        _repo_root / "Example.als",
    ]
    for p in candidates:
        if p.exists():
            return p

    raise FileNotFoundError(
        "Ableton template not found. Provide --als-template path or "
        "place a template .als in the templates/ directory."
    )


def _get_audio_info(path: Path) -> tuple[int, int]:
    """Get (frames, sample_rate) for an audio file."""
    info = sf.info(str(path))
    return info.frames, info.samplerate


def _build_audio_clip_xml(
    clip_id: int,
    name: str,
    absolute_path: str,
    relative_path: str,
    duration_seconds: float,
    sample_frames: int,
    sample_rate: int,
) -> str:
    """Build an AudioClip XML element string for arrangement view.

    Warping is disabled — the clip plays at original speed.
    For unwarped audio, Loop values are in seconds.
    """
    return f'''<AudioClip Id="{clip_id}" Time="0">
<LomId Value="0" />
<LomIdView Value="0" />
<CurrentStart Value="0" />
<CurrentEnd Value="{duration_seconds}" />
<Loop>
<LoopStart Value="0" />
<LoopEnd Value="{duration_seconds}" />
<StartRelative Value="0" />
<LoopOn Value="false" />
<OutMarker Value="{duration_seconds}" />
<HiddenLoopStart Value="0" />
<HiddenLoopEnd Value="{duration_seconds}" />
</Loop>
<Name Value="{name}" />
<Annotation Value="" />
<Color Value="-1" />
<LaunchMode Value="0" />
<LaunchQuantisation Value="0" />
<TimeSignature>
<TimeSignatures>
<RemoteableTimeSignature Id="0">
<Numerator Value="4" />
<Denominator Value="4" />
<Time Value="0" />
</RemoteableTimeSignature>
</TimeSignatures>
</TimeSignature>
<Envelopes>
<Envelopes />
</Envelopes>
<ScrollerTimePreserver>
<LeftTime Value="0" />
<RightTime Value="0" />
</ScrollerTimePreserver>
<TimeSelection>
<AnchorTime Value="0" />
<OtherTime Value="0" />
</TimeSelection>
<Legato Value="false" />
<Ram Value="false" />
<GrooveSettings>
<GrooveId Value="-1" />
</GrooveSettings>
<Disabled Value="false" />
<VelocityAmount Value="0" />
<FollowTime Value="4" />
<FollowActionEnabled Value="false" />
<FollowAction>
<FollowActionA Value="4" />
<FollowActionB Value="0" />
<FollowChance Value="100" />
<JumpIndexA Value="1" />
<JumpIndexB Value="1" />
<FollowActionLinkA Value="false" />
<FollowActionLinkB Value="false" />
</FollowAction>
<Grid>
<FixedNumerator Value="1" />
<FixedDenominator Value="16" />
<GridIntervalPixel Value="20" />
<Ntoles Value="2" />
<SnapToGrid Value="true" />
<Fixed Value="false" />
</Grid>
<SampleRef>
<FileRef>
<RelativePathType Value="3" />
<RelativePath Value="{relative_path}" />
<Path Value="{absolute_path}" />
<Type Value="1" />
<LivePackName Value="" />
<LivePackId Value="" />
<OriginalFileSize Value="0" />
<OriginalCrc Value="0" />
</FileRef>
<LastModDate Value="0" />
<SourceContext>
<SourceContext Id="0">
<OriginalFileRef>
<FileRef>
<RelativePathType Value="3" />
<RelativePath Value="{relative_path}" />
<Path Value="{absolute_path}" />
<Type Value="1" />
<LivePackName Value="" />
<LivePackId Value="" />
<OriginalFileSize Value="0" />
<OriginalCrc Value="0" />
</FileRef>
</OriginalFileRef>
<BrowserContentPath Value="" />
</SourceContext>
</SourceContext>
<SampleUsageHint Value="0" />
<DefaultDuration Value="{sample_frames}" />
<DefaultSampleRate Value="{sample_rate}" />
</SampleRef>
<Onsets>
<UserOnsets />
<HasUserOnsets Value="false" />
</Onsets>
<Warping Value="false" />
<WarpMode Value="0" />
<GranularityTones Value="30" />
<GranularityTexture Value="65" />
<FluctuationTexture Value="25" />
<TransientResolution Value="6" />
<TransientLoopMode Value="2" />
<TransientEnvelope Value="100" />
<ComplexProFormants Value="100" />
<ComplexProEnvelope Value="128" />
<Sync Value="true" />
<HiQ Value="true" />
<Fade Value="true" />
<Fades>
<FadeInLength Value="0" />
<FadeOutLength Value="0" />
<ClipFadesAreInitialized Value="true" />
<CrossfadeInState Value="0" />
<FadeInCurveSkew Value="0" />
<FadeInCurveSlope Value="0" />
<FadeOutCurveSkew Value="0" />
<FadeOutCurveSlope Value="0" />
<IsDefaultFadeIn Value="true" />
<IsDefaultFadeOut Value="true" />
</Fades>
<PitchCoarse Value="0" />
<PitchFine Value="0" />
<SampleVolume Value="1" />
<MarkerDensity Value="2" />
<AutoWarpTolerance Value="4" />
<WarpMarkers>
<WarpMarker Id="0" SecTime="0" BeatTime="0" />
<WarpMarker Id="1" SecTime="0.03125" BeatTime="0.03125" />
</WarpMarkers>
<SavedWarpMarkersForStretched />
<MarkersGenerated Value="false" />
<IsSongTempoMaster Value="false" />
</AudioClip>'''


def _find_track_by_name(
    tracks_el: ET.Element, name: str, tags: list[str] | None = None,
) -> ET.Element | None:
    """Find a track element by its EffectiveName.

    Searches AudioTrack and MidiTrack by default (template may use either
    for a given instrument, e.g. Drums is often a MidiTrack).
    """
    if tags is None:
        tags = ["AudioTrack", "MidiTrack"]
    for track in tracks_el:
        if track.tag not in tags:
            continue
        name_el = track.find(".//Name/EffectiveName")
        if name_el is not None and name_el.get("Value") == name:
            return track
    return None


def _get_events_element(track: ET.Element) -> ET.Element | None:
    """Get the ArrangerAutomation/Events element for clip injection."""
    if track.tag == "AudioTrack":
        return track.find(".//MainSequencer/Sample/ArrangerAutomation/Events")
    elif track.tag == "MidiTrack":
        return track.find(".//MainSequencer/ClipTimeable/ArrangerAutomation/Events")
    return None


def _make_relative_path(als_path: Path, file_path: Path) -> str:
    """Build a relative path string for Ableton's FileRef format."""
    try:
        rel = file_path.resolve().relative_to(als_path.parent.resolve())
        return str(rel)
    except ValueError:
        return str(file_path.resolve())


def export_als(
    manifest: ProcessingManifest,
    config: SunoPrepConfig,
) -> ALSExportResult:
    """Export a minimal Ableton Live Set from processed stems and MIDI."""
    result = ALSExportResult()

    # Find template
    template_path = _find_template(config)
    result.template_used = template_path

    # Output path
    song_title = manifest.song_title or "Suno Import"
    output_path = config.resolved_output_dir / f"{song_title}.als"
    result.output_path = output_path

    if config.dry_run:
        return result

    # Load template XML
    with gzip.open(str(template_path), "rb") as f:
        xml_content = f.read().decode("utf-8")

    root = ET.fromstring(xml_content)
    liveset = root.find("LiveSet")
    tracks_el = liveset.find("Tracks")

    # Get next available ID for clip elements
    next_id_el = liveset.find("NextPointeeId")
    next_id = int(next_id_el.get("Value"))
    clip_id_counter = next_id + 1000  # leave headroom

    # 1. Set BPM
    bpm = manifest.bpm or 120.0
    result.bpm_set = bpm
    tempo_el = liveset.find(".//Tempo/Manual")
    if tempo_el is not None:
        tempo_el.set("Value", str(bpm))

    # 2. Match stems to tracks and inject AudioClips
    tracks_created = 0
    for processed_file in manifest.stems:
        stem_path = Path(processed_file.output_path)
        if not stem_path.exists():
            continue

        # Find matching track name
        track_name = _STEM_TO_TRACK_NAME.get(processed_file.stem_type)
        if not track_name:
            continue

        track_el = _find_track_by_name(tracks_el, track_name)
        if track_el is None:
            # No matching track in template — skip
            continue

        events_el = _get_events_element(track_el)
        if events_el is None:
            continue

        # Get audio info
        try:
            frames, sr = _get_audio_info(stem_path)
        except Exception:
            continue

        duration_seconds = frames / sr

        # Build relative path from ALS location to stem
        abs_path = str(stem_path.resolve())
        rel_path = _make_relative_path(output_path, stem_path)

        clip_xml = _build_audio_clip_xml(
            clip_id=clip_id_counter,
            name=stem_path.stem,
            absolute_path=abs_path,
            relative_path=rel_path,
            duration_seconds=duration_seconds,
            sample_frames=frames,
            sample_rate=sr,
        )
        clip_id_counter += 1

        # Parse and inject
        clip_el = ET.fromstring(clip_xml)
        events_el.append(clip_el)

        # Mute the full mix track
        if processed_file.stem_type == StemType.FULL_MIX:
            speaker = track_el.find(".//Mixer/Speaker/Manual")
            if speaker is not None:
                speaker.set("Value", "false")

        tracks_created += 1

    result.tracks_created = tracks_created

    # 3. Handle MIDI tracks — place MIDI files as references
    # For MIDI, we need to create MidiClip elements which are more complex.
    # For V1, we note MIDI in the manifest but skip clip injection since
    # MidiClip XML requires note-level data embedded in the XML.
    # Users can drag the .mid files into the tracks manually.
    result.midi_tracks_created = 0

    # Update NextPointeeId
    next_id_el.set("Value", str(clip_id_counter + 100))

    # 4. Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize back to XML string
    xml_out = ET.tostring(root, encoding="unicode", xml_declaration=False)
    xml_out = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_out

    with gzip.open(str(output_path), "wb") as f:
        f.write(xml_out.encode("utf-8"))

    return result


def run_export_als(
    manifest: ProcessingManifest,
    config: SunoPrepConfig,
) -> tuple[ALSExportResult, FeatureInvocation]:
    """Entry point for export-als feature."""
    invocation = FeatureInvocation(
        feature="export_als",
        mode="apply",
    )

    try:
        result = export_als(manifest, config)

        if result.output_path:
            invocation.output_files.append(result.output_path)

        if not config.dry_run:
            report_data = json.loads(result.model_dump_json())
            write_json_report(report_data, "als_export.json", config)
            invocation.output_files.append(config.reports_dir / "als_export.json")

        invocation.recommendation = (
            f"Exported {result.tracks_created} audio tracks, "
            f"BPM={result.bpm_set}"
        )
        if result.output_path:
            invocation.recommendation += f" → {result.output_path.name}"

    except Exception as e:
        invocation.warnings.append(f"export-als failed: {e}")
        result = ALSExportResult()

    return result, invocation
