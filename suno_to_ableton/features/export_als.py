"""Experimental Ableton Live Set (.als) export.

This exporter starts from a bundled Ableton-authored export template and then
retargets its arrangement clips to the processed stems and MIDI files.
"""

from __future__ import annotations

import copy
import gzip
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pretty_midi
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
    StemType.OTHER: "Other",
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
    StemType.OTHER: 6,
}

_TEMPLATE_MIDI_TRACK_NAMES = [
    "MIDI Drums",
    "MIDI Bass",
    "MIDI Synth",
    "MIDI FX",
    "MIDI (Song)",
]

_PREFERRED_MIDI_TRACK_BY_STEM: dict[StemType, str] = {
    StemType.DRUMS: "MIDI Drums",
    StemType.PERCUSSION: "MIDI Drums",
    StemType.BASS: "MIDI Bass",
    StemType.SYNTH: "MIDI Synth",
    StemType.FX: "MIDI FX",
    StemType.FULL_MIX: "MIDI (Song)",
    StemType.OTHER: "MIDI (Song)",
}

_DEFAULT_TEMPLATE_NAMES: dict[int, str] = {
    11: "Ableton 11 Template.als",
    12: "Ableton 12 Template.als",
}

# Version attributes for downgrading to Ableton 11
_ABLETON_VERSION_ATTRS: dict[int, dict[str, str]] = {
    11: {
        "MinorVersion": "11.0_433",
        "SchemaChangeCount": "6",
        "Creator": "Ableton Live 11.0.12",
    },
    12: {
        "MinorVersion": "12.0_12120",
        "SchemaChangeCount": "4",
        "Creator": "Ableton Live 12.1.11",
    },
}

# Attributes that only exist in Ableton 12 tracks
_ABLETON_12_TRACK_ATTRS = [
    "SelectedToolPanel",
    "SelectedTransformationName",
    "SelectedGeneratorName",
]

_INLINE_AUDIO_CLIP_PROTOTYPE = """
<AudioClip Id="24583" Time="0">
  <LomId Value="0" />
  <LomIdView Value="0" />
  <CurrentStart Value="0" />
  <CurrentEnd Value="401.86593549679486" />
  <Loop>
    <LoopStart Value="0" />
    <LoopEnd Value="167.17622916666667" />
    <StartRelative Value="0" />
    <LoopOn Value="false" />
    <OutMarker Value="167.17622916666667" />
    <HiddenLoopStart Value="0" />
    <HiddenLoopEnd Value="167.17622916666667" />
  </Loop>
  <Name Value="Drums" />
  <Annotation Value="" />
  <Color Value="69" />
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
  <Envelopes><Envelopes /></Envelopes>
  <ScrollerTimePreserver>
    <LeftTime Value="0" />
    <RightTime Value="401.86593549679486" />
  </ScrollerTimePreserver>
  <TimeSelection>
    <AnchorTime Value="0" />
    <OtherTime Value="0" />
  </TimeSelection>
  <Legato Value="false" />
  <Ram Value="false" />
  <GrooveSettings><GrooveId Value="-1" /></GrooveSettings>
  <Disabled Value="false" />
  <VelocityAmount Value="0" />
  <FollowAction>
    <FollowTime Value="4" />
    <IsLinked Value="true" />
    <LoopIterations Value="1" />
    <FollowActionA Value="4" />
    <FollowActionB Value="0" />
    <FollowChanceA Value="100" />
    <FollowChanceB Value="0" />
    <JumpIndexA Value="1" />
    <JumpIndexB Value="1" />
    <FollowActionEnabled Value="false" />
  </FollowAction>
  <Grid>
    <FixedNumerator Value="1" />
    <FixedDenominator Value="16" />
    <GridIntervalPixel Value="20" />
    <Ntoles Value="2" />
    <SnapToGrid Value="true" />
    <Fixed Value="false" />
  </Grid>
  <FreezeStart Value="0" />
  <FreezeEnd Value="0" />
  <IsWarped Value="false" />
  <TakeId Value="1" />
  <IsInKey Value="true" />
  <ScaleInformation>
    <Root Value="0" />
    <Name Value="0" />
  </ScaleInformation>
  <SampleRef>
    <FileRef>
      <RelativePathType Value="1" />
      <RelativePath Value="stems/00_drums.wav" />
      <Path Value="/tmp/placeholder.wav" />
      <Type Value="1" />
      <LivePackName Value="" />
      <LivePackId Value="" />
      <OriginalFileSize Value="0" />
      <OriginalCrc Value="0" />
    </FileRef>
    <LastModDate Value="0" />
    <SourceContext />
    <SampleUsageHint Value="0" />
    <DefaultDuration Value="1" />
    <DefaultSampleRate Value="48000" />
    <SamplesToAutoWarp Value="0" />
  </SampleRef>
  <Onsets>
    <UserOnsets />
    <HasUserOnsets Value="false" />
  </Onsets>
  <WarpMode Value="4" />
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
  <Fade Value="false" />
  <Fades>
    <FadeInLength Value="0.0482553904428904418" />
    <FadeOutLength Value="0" />
    <ClipFadesAreInitialized Value="true" />
    <CrossfadeInState Value="0" />
    <FadeInCurveSkew Value="0" />
    <FadeInCurveSlope Value="0" />
    <FadeOutCurveSkew Value="0" />
    <FadeOutCurveSlope Value="0" />
    <IsDefaultFadeIn Value="false" />
    <IsDefaultFadeOut Value="false" />
  </Fades>
  <PitchCoarse Value="0" />
  <PitchFine Value="0" />
  <SampleVolume Value="1" />
  <WarpMarkers>
    <WarpMarker Id="0" SecTime="0" BeatTime="0" />
    <WarpMarker Id="1" SecTime="167.17622916666667" BeatTime="401.86593549679486" />
  </WarpMarkers>
  <SavedWarpMarkersForStretched />
  <MarkersGenerated Value="false" />
  <IsSongTempoLeader Value="false" />
  <AutoWarpPending Value="false" />
  <WasMuted Value="false" />
</AudioClip>
""".strip()


def _find_template(config: SunoPrepConfig) -> Path:
    """Locate the Ableton .als template file."""
    # Check explicit config path first
    if config.als_template and config.als_template.exists():
        return config.als_template

    _repo_root = Path(__file__).parent.parent.parent
    version = getattr(config, "ableton_version", 12)
    default_name = _DEFAULT_TEMPLATE_NAMES.get(version, _DEFAULT_TEMPLATE_NAMES[12])

    # Check common locations
    candidates = [
        _repo_root / "templates" / default_name,
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


def _downgrade_to_ableton_version(root: ET.Element, version: int) -> None:
    """Rewrite the root <Ableton> attributes for the target Live version."""
    attrs = _ABLETON_VERSION_ATTRS.get(version)
    if attrs is None:
        return
    for key, value in attrs.items():
        root.set(key, value)
    if version < 12:
        # Strip Ableton 12-only attributes from track elements
        for track in root.iter():
            for attr in _ABLETON_12_TRACK_ATTRS:
                if attr in track.attrib:
                    del track.attrib[attr]


def _template_has_arrangement_clips(root: ET.Element) -> bool:
    """Return True when the template already contains usable audio and MIDI clip scaffolds."""
    return (
        root.find(".//AudioTrack//MainSequencer/Sample/ArrangerAutomation/Events/AudioClip") is not None
        and root.find(".//MidiTrack//MainSequencer/ClipTimeable/ArrangerAutomation/Events/MidiClip") is not None
    )


def _first_clip(root: ET.Element, xpath: str) -> ET.Element:
    """Return the first clip matching an XPath, or raise."""
    clip = root.find(xpath)
    if clip is None:
        raise ValueError(f"Missing clip prototype at {xpath}")
    return clip


def _audio_clip_prototype(root: ET.Element) -> ET.Element:
    """Load an audio clip prototype from the template or the built-in fallback."""
    clip = root.find(".//AudioClip")
    if clip is not None:
        return clip
    return ET.fromstring(_INLINE_AUDIO_CLIP_PROTOTYPE)


def _get_audio_info(path: Path) -> tuple[int, int]:
    """Get (frames, sample_rate) for an audio file."""
    info = sf.info(str(path))
    return info.frames, info.samplerate


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


def _track_name(track: ET.Element) -> str | None:
    """Get the display name for a template track."""
    name_el = track.find(".//Name/EffectiveName")
    if name_el is None:
        return None
    value = name_el.get("Value", "").strip()
    return value or None


def _set_track_name(track: ET.Element, value: str) -> None:
    """Update both user and effective track names."""
    effective = track.find("./Name/EffectiveName")
    user = track.find("./Name/UserName")
    if effective is not None:
        effective.set("Value", value)
    if user is not None:
        user.set("Value", value)


def _set_child_value(parent: ET.Element, path: str, value: str) -> None:
    """Set the Value attribute on a nested child element if it exists."""
    child = parent.find(path)
    if child is not None:
        child.set("Value", value)


def _format_ableton_float(value: float) -> str:
    """Format numeric values the way Ableton-authored sets typically store them."""
    return f"{value:.6f}"


def _update_file_ref(file_ref: ET.Element, output_path: Path, asset_path: Path) -> None:
    """Rewrite a FileRef to point at the requested asset path."""
    relative_path = _make_relative_path(output_path, asset_path)
    rel_el = file_ref.find("./RelativePath")
    if rel_el is not None:
        rel_el.set("Value", relative_path)
    rel_type_el = file_ref.find("./RelativePathType")
    if rel_type_el is not None:
        rel_type_el.set("Value", "1")
    path_el = file_ref.find("./Path")
    if path_el is not None:
        path_el.set("Value", str(asset_path.resolve()))


def _replace_events(events_el: ET.Element, clip_el: ET.Element) -> None:
    """Replace a track's arranger events with a single clip."""
    for child in list(events_el):
        events_el.remove(child)
    events_el.append(clip_el)


def _update_reference_audio_clips(
    tracks_el: ET.Element,
    manifest: ProcessingManifest,
    output_path: Path,
    bpm: float,
    clip_id_start: int,
) -> int:
    """Replace reference audio clips with rebuilt clips for processed stems."""
    tracks_created = 0
    clip_id_counter = clip_id_start
    for processed_file in manifest.stems:
        track_name = _STEM_TO_TRACK_NAME.get(processed_file.stem_type)
        if not track_name:
            continue
        track_el = _find_track_by_name(tracks_el, track_name, tags=["AudioTrack"])
        if track_el is None:
            continue
        events_el = track_el.find(".//MainSequencer/Sample/ArrangerAutomation/Events")
        if events_el is None:
            continue
        stem_path = Path(processed_file.output_path)
        if not stem_path.exists():
            continue
        prototype = events_el.find("./AudioClip")
        if prototype is None:
            continue
        clip_el = _build_audio_clip_from_prototype(
            prototype=prototype,
            processed_file=processed_file,
            output_path=output_path,
            bpm=bpm,
            clip_id=clip_id_counter,
        )
        clip_id_counter += 1
        _replace_events(events_el, clip_el)
        tracks_created += 1
    return tracks_created


def _audio_end_beats(duration_seconds: float, bpm: float) -> float:
    """Convert audio duration in seconds to clip beat length."""
    return max(duration_seconds * bpm / 60.0, 1.0)


def _rounded_clip_end_beats(max_note_beats: float) -> float:
    """Round MIDI clip length up to a musically useful boundary."""
    if max_note_beats <= 0:
        return 4.0
    return max(4.0, math.ceil(max_note_beats / 4.0) * 4.0)


def _rebuild_warp_markers(
    clip_el: ET.Element,
    duration_seconds: float,
    end_beats: float,
) -> None:
    """Replace prototype warp markers with a minimal start/end pair."""
    markers = clip_el.find("./WarpMarkers")
    if markers is None:
        return
    for child in list(markers):
        markers.remove(child)
    markers.append(
        ET.Element(
            "WarpMarker",
            {"Id": "0", "SecTime": "0", "BeatTime": "0"},
        )
    )
    markers.append(
        ET.Element(
            "WarpMarker",
            {
                "Id": "1",
                "SecTime": str(duration_seconds),
                "BeatTime": str(end_beats),
            },
        )
    )


def _build_audio_clip_from_prototype(
    prototype: ET.Element,
    processed_file,
    output_path: Path,
    bpm: float,
    clip_id: int,
) -> ET.Element:
    """Clone an Ableton-authored audio clip and retarget it to a stem file."""
    stem_path = Path(processed_file.output_path)
    frames, sr = _get_audio_info(stem_path)
    duration_seconds = frames / sr
    end_beats = _audio_end_beats(duration_seconds, bpm)

    clip_el = copy.deepcopy(prototype)
    clip_el.set("Id", str(clip_id))
    clip_el.set("Time", "0")
    _set_child_value(clip_el, "./CurrentStart", "0")
    _set_child_value(clip_el, "./CurrentEnd", str(end_beats))
    _set_child_value(clip_el, "./Loop/LoopStart", "0")
    _set_child_value(clip_el, "./Loop/LoopEnd", str(duration_seconds))
    _set_child_value(clip_el, "./Loop/StartRelative", "0")
    _set_child_value(clip_el, "./Loop/OutMarker", str(duration_seconds))
    _set_child_value(clip_el, "./Loop/HiddenLoopStart", "0")
    _set_child_value(clip_el, "./Loop/HiddenLoopEnd", str(duration_seconds))
    clip_label = _STEM_TO_TRACK_NAME.get(processed_file.stem_type, stem_path.stem.title())
    _set_child_value(clip_el, "./Name", clip_label)
    _set_child_value(
        clip_el,
        "./Color",
        str(_TRACK_COLORS.get(processed_file.stem_type, 0)),
    )
    _set_child_value(clip_el, "./ScrollerTimePreserver/LeftTime", "0")
    _set_child_value(clip_el, "./ScrollerTimePreserver/RightTime", str(end_beats))
    _set_child_value(clip_el, "./FreezeStart", "0")
    _set_child_value(clip_el, "./FreezeEnd", "0")
    _set_child_value(clip_el, "./IsWarped", "false")
    _set_child_value(clip_el, "./TakeId", "1")
    _set_child_value(clip_el, "./SampleRef/DefaultDuration", str(frames))
    _set_child_value(clip_el, "./SampleRef/DefaultSampleRate", str(sr))
    _set_child_value(clip_el, "./SampleRef/LastModDate", str(int(stem_path.stat().st_mtime)))
    file_ref = clip_el.find("./SampleRef/FileRef")
    if file_ref is not None:
        _update_file_ref(file_ref, output_path, stem_path)
    _rebuild_warp_markers(clip_el, duration_seconds, end_beats)
    _set_child_value(clip_el, "./MarkersGenerated", "false")
    _set_child_value(clip_el, "./IsSongTempoLeader", "false")
    _set_child_value(clip_el, "./AutoWarpPending", "false")
    _set_child_value(clip_el, "./WasMuted", "false")
    return clip_el


def _midi_clip_display_name(midi_path: Path, stem_type: StemType) -> str:
    """Build a human-readable MIDI clip name from the cleaned filename."""
    if stem_type in (StemType.OTHER, StemType.FULL_MIX):
        return "MIDI (Song)"
    return f"MIDI {stem_type.value.replace('_', ' ').title()}"


def _populate_midi_notes(
    notes_el: ET.Element,
    midi: pretty_midi.PrettyMIDI,
    bpm: float,
) -> int:
    """Rewrite a Notes block from pretty_midi data. Returns the next note id."""
    key_tracks_el = notes_el.find("./KeyTracks")
    if key_tracks_el is None:
        return 1
    for child in list(key_tracks_el):
        key_tracks_el.remove(child)

    grouped: dict[int, list[pretty_midi.Note]] = {}
    for instrument in midi.instruments:
        for note in instrument.notes:
            grouped.setdefault(note.pitch, []).append(note)

    next_note_id = 1
    for key_track_id, pitch in enumerate(sorted(grouped)):
        key_track_el = ET.Element("KeyTrack", {"Id": str(key_track_id)})
        pitch_notes_el = ET.SubElement(key_track_el, "Notes")
        sorted_notes = sorted(grouped[pitch], key=lambda note: (note.start, note.end))
        for note in sorted_notes:
            start_beats = note.start * bpm / 60.0
            duration_beats = max((note.end - note.start) * bpm / 60.0, 1e-6)
            ET.SubElement(
                pitch_notes_el,
                "MidiNoteEvent",
                {
                    "Time": str(start_beats),
                    "Duration": str(duration_beats),
                    "Velocity": str(int(note.velocity)),
                    "VelocityDeviation": "0",
                    "OffVelocity": "0",
                    "Probability": "1",
                    "IsEnabled": "true",
                    "NoteId": str(next_note_id),
                },
            )
            next_note_id += 1
        ET.SubElement(key_track_el, "MidiKey", {"Value": str(pitch)})
        key_tracks_el.append(key_track_el)

    per_note_event_store = notes_el.find("./PerNoteEventStore/EventLists")
    if per_note_event_store is not None:
        for child in list(per_note_event_store):
            per_note_event_store.remove(child)
    probability_groups = notes_el.find("./NoteProbabilityGroups")
    if probability_groups is not None:
        for child in list(probability_groups):
            probability_groups.remove(child)
    _set_child_value(notes_el, "./ProbabilityGroupIdGenerator/NextId", "1")
    _set_child_value(notes_el, "./NoteIdGenerator/NextId", str(next_note_id))
    return next_note_id


def _build_midi_clip_from_prototype(
    prototype: ET.Element,
    midi_path: Path,
    stem_type: StemType,
    bpm: float,
    clip_id: int,
) -> ET.Element:
    """Clone an Ableton-authored MIDI clip and populate it from a MIDI file."""
    midi = pretty_midi.PrettyMIDI(str(midi_path))
    max_note_end_seconds = max(
        (note.end for instrument in midi.instruments for note in instrument.notes),
        default=0.0,
    )
    end_beats = _rounded_clip_end_beats(max_note_end_seconds * bpm / 60.0)

    clip_el = copy.deepcopy(prototype)
    clip_el.set("Id", str(clip_id))
    clip_el.set("Time", "0")
    _set_child_value(clip_el, "./CurrentStart", "0")
    _set_child_value(clip_el, "./CurrentEnd", str(end_beats))
    _set_child_value(clip_el, "./Loop/LoopStart", "0")
    _set_child_value(clip_el, "./Loop/LoopEnd", str(end_beats))
    _set_child_value(clip_el, "./Loop/StartRelative", "0")
    _set_child_value(clip_el, "./Loop/OutMarker", str(end_beats))
    _set_child_value(clip_el, "./Loop/HiddenLoopStart", "0")
    _set_child_value(clip_el, "./Loop/HiddenLoopEnd", str(end_beats))
    _set_child_value(clip_el, "./Name", _midi_clip_display_name(midi_path, stem_type))
    _set_child_value(
        clip_el,
        "./Color",
        str(_TRACK_COLORS.get(stem_type, 0)),
    )
    _set_child_value(clip_el, "./ScrollerTimePreserver/LeftTime", "0")
    _set_child_value(clip_el, "./ScrollerTimePreserver/RightTime", str(end_beats))
    _set_child_value(clip_el, "./FreezeStart", "0")
    _set_child_value(clip_el, "./FreezeEnd", "0")
    _set_child_value(clip_el, "./IsWarped", "true")
    _set_child_value(clip_el, "./TakeId", "1")
    _populate_midi_notes(clip_el.find("./Notes"), midi, bpm)

    first_instrument = midi.instruments[0] if midi.instruments else None
    program_change = -1 if first_instrument is None else first_instrument.program
    _set_child_value(clip_el, "./BankSelectCoarse", "-1")
    _set_child_value(clip_el, "./BankSelectFine", "-1")
    _set_child_value(clip_el, "./ProgramChange", str(program_change))
    return clip_el


def _select_midi_template_tracks(
    manifest: ProcessingManifest,
    available_track_names: list[str],
) -> set[str]:
    """Choose which template MIDI tracks to keep for discovered MIDI files."""
    available = [name for name in _TEMPLATE_MIDI_TRACK_NAMES if name in available_track_names]
    if not manifest.midi_files or not available:
        return set()

    selected: list[str] = []
    remaining = [name for name in available]

    for midi_file in manifest.midi_files:
        if (
            len(manifest.midi_files) == 1
            and midi_file.stem_type in (StemType.OTHER, StemType.FULL_MIX)
            and "MIDI FX" in remaining
        ):
            selected.append("MIDI (Song)")
            remaining.remove("MIDI FX")
            continue
        if (
            len(manifest.midi_files) == 1
            and midi_file.stem_type == StemType.OTHER
            and "MIDI (Song)" in remaining
        ):
            selected.append("MIDI (Song)")
            remaining.remove("MIDI (Song)")
            continue
        preferred = _PREFERRED_MIDI_TRACK_BY_STEM.get(
            midi_file.stem_type, "MIDI - Lead"
        )
        if preferred in remaining:
            selected.append(preferred)
            remaining.remove(preferred)
            continue
        if remaining:
            selected.append(remaining.pop(0))

    return set(selected)


def _assign_midi_template_tracks(
    manifest: ProcessingManifest,
    available_track_names: list[str],
) -> list[tuple[Path, StemType, str]]:
    """Assign each processed MIDI file to a specific template track."""
    available = [name for name in _TEMPLATE_MIDI_TRACK_NAMES if name in available_track_names]
    assignments: list[tuple[Path, StemType, str]] = []
    if not manifest.midi_files or not available:
        return assignments

    remaining = [name for name in available]
    for midi_file in manifest.midi_files:
        if (
            len(manifest.midi_files) == 1
            and midi_file.stem_type in (StemType.OTHER, StemType.FULL_MIX)
            and "MIDI FX" in remaining
        ):
            track_name = "MIDI (Song)"
            remaining.remove("MIDI FX")
        elif (
            len(manifest.midi_files) == 1
            and midi_file.stem_type == StemType.OTHER
            and "MIDI (Song)" in remaining
        ):
            track_name = "MIDI (Song)"
            remaining.remove(track_name)
        else:
            preferred = _PREFERRED_MIDI_TRACK_BY_STEM.get(
                midi_file.stem_type, "MIDI - Lead"
            )
            if preferred in remaining:
                track_name = preferred
                remaining.remove(track_name)
            elif remaining:
                track_name = remaining.pop(0)
            else:
                break
        assignments.append((Path(midi_file.output_path), midi_file.stem_type, track_name))

    return assignments


def _promote_fx_track_to_song_midi(
    tracks_el: ET.Element, desired_midi_tracks: set[str]
) -> None:
    """Reuse the FX MIDI lane as a generic song MIDI lane when needed."""
    if "MIDI (Song)" not in desired_midi_tracks:
        return
    if _find_track_by_name(tracks_el, "MIDI (Song)", tags=["MidiTrack"]) is not None:
        return
    fx_track = _find_track_by_name(tracks_el, "MIDI FX", tags=["MidiTrack"])
    if fx_track is None:
        return
    _set_track_name(fx_track, "MIDI (Song)")


def _prune_unused_template_tracks(
    tracks_el: ET.Element,
    desired_audio_tracks: set[str],
    desired_midi_tracks: set[str],
    managed_audio_tracks: set[str],
) -> None:
    """Remove bundled stem/MIDI scaffold tracks that are not used by this export."""
    for track in list(tracks_el):
        name = _track_name(track)
        if not name:
            continue
        if name in managed_audio_tracks and name not in desired_audio_tracks:
            tracks_el.remove(track)
            continue
        if name in _TEMPLATE_MIDI_TRACK_NAMES and name not in desired_midi_tracks:
            tracks_el.remove(track)


def _promote_fx_track_to_other(tracks_el: ET.Element, desired_audio_tracks: set[str]) -> None:
    """Reuse the FX track as Other when the shipped template lacks a dedicated Other lane."""
    if "Other" not in desired_audio_tracks or "FX" in desired_audio_tracks:
        return
    if _find_track_by_name(tracks_el, "Other", tags=["AudioTrack"]) is not None:
        return
    fx_track = _find_track_by_name(tracks_el, "FX", tags=["AudioTrack"])
    if fx_track is None:
        return
    _set_track_name(fx_track, "Other")


def _update_reference_midi_clips(
    tracks_el: ET.Element,
    manifest: ProcessingManifest,
    midi_assignments: list[tuple[Path, StemType, str]],
    bpm: float,
    clip_id_start: int,
) -> int:
    """Replace reference MIDI clips with rebuilt clips for processed MIDI."""
    tracks_created = 0
    clip_id_counter = clip_id_start
    for midi_path, stem_type, track_name in midi_assignments:
        if not midi_path.exists():
            continue
        track_el = _find_track_by_name(tracks_el, track_name, tags=["MidiTrack"])
        if track_el is None:
            continue
        events_el = track_el.find(".//MainSequencer/ClipTimeable/ArrangerAutomation/Events")
        if events_el is None:
            continue
        prototype = events_el.find("./MidiClip")
        if prototype is None:
            continue
        clip_el = _build_midi_clip_from_prototype(
            prototype=prototype,
            midi_path=midi_path,
            stem_type=stem_type,
            bpm=bpm,
            clip_id=clip_id_counter,
        )
        clip_id_counter += 1
        _replace_events(events_el, clip_el)
        tracks_created += 1
    return tracks_created


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

    # Downgrade version attributes if targeting an older Ableton version
    if config.ableton_version != 12:
        _downgrade_to_ableton_version(root, config.ableton_version)

    liveset = root.find("LiveSet")
    tracks_el = liveset.find("Tracks")

    available_track_names = [
        name for name in (_track_name(track) for track in tracks_el) if name
    ]
    midi_assignments = _assign_midi_template_tracks(manifest, available_track_names)

    # Get next available ID for clip elements
    next_id_el = liveset.find("NextPointeeId")
    next_id = int(next_id_el.get("Value"))
    clip_id_counter = next_id + 1000  # leave headroom

    # 1. Set BPM
    bpm = manifest.bpm or 120.0
    result.bpm_set = bpm
    tempo_el = liveset.find(".//Tempo/Manual")
    if tempo_el is not None:
        tempo_el.set("Value", _format_ableton_float(bpm))

    desired_audio_tracks = {
        track_name
        for processed_file in manifest.stems
        if processed_file.output_path.exists()
        for track_name in [_STEM_TO_TRACK_NAME.get(processed_file.stem_type)]
        if track_name
    }
    desired_midi_tracks = _select_midi_template_tracks(
        manifest, available_track_names
    )
    _promote_fx_track_to_other(tracks_el, desired_audio_tracks)
    _promote_fx_track_to_song_midi(tracks_el, desired_midi_tracks)
    _prune_unused_template_tracks(
        tracks_el,
        desired_audio_tracks=desired_audio_tracks,
        desired_midi_tracks=desired_midi_tracks,
        managed_audio_tracks=set(_STEM_TO_TRACK_NAME.values()),
    )

    if _template_has_arrangement_clips(root):
        result.tracks_created = _update_reference_audio_clips(
            tracks_el=tracks_el,
            manifest=manifest,
            output_path=output_path,
            bpm=bpm,
            clip_id_start=clip_id_counter,
        )
        clip_id_counter += result.tracks_created
        result.midi_tracks_created = _update_reference_midi_clips(
            tracks_el=tracks_el,
            manifest=manifest,
            midi_assignments=midi_assignments,
            bpm=bpm,
            clip_id_start=clip_id_counter,
        )
        clip_id_counter += result.midi_tracks_created
        next_id_el.set("Value", str(clip_id_counter + 100))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        xml_out = ET.tostring(root, encoding="unicode", xml_declaration=False)
        xml_out = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_out
        with gzip.open(str(output_path), "wb") as f:
            f.write(xml_out.encode("utf-8"))
        return result

    audio_prototype = _audio_clip_prototype(root)
    midi_prototype = _first_clip(root, ".//MidiClip")

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

        clip_el = _build_audio_clip_from_prototype(
            prototype=audio_prototype,
            processed_file=processed_file,
            output_path=output_path,
            bpm=bpm,
            clip_id=clip_id_counter,
        )
        clip_id_counter += 1
        events_el.append(clip_el)

        # Mute the full mix track
        if processed_file.stem_type == StemType.FULL_MIX:
            speaker = track_el.find(".//Mixer/Speaker/Manual")
            if speaker is not None:
                speaker.set("Value", "false")

        tracks_created += 1

    result.tracks_created = tracks_created

    # 3. Inject MIDI clips.
    midi_tracks_created = 0
    for midi_path, stem_type, track_name in midi_assignments:
        if not midi_path.exists():
            continue
        track_el = _find_track_by_name(tracks_el, track_name, tags=["MidiTrack"])
        if track_el is None:
            continue
        events_el = _get_events_element(track_el)
        if events_el is None:
            continue
        clip_el = _build_midi_clip_from_prototype(
            prototype=midi_prototype,
            midi_path=midi_path,
            stem_type=stem_type,
            bpm=bpm,
            clip_id=clip_id_counter,
        )
        clip_id_counter += 1
        events_el.append(clip_el)
        midi_tracks_created += 1
    result.midi_tracks_created = midi_tracks_created

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
