"""Textual TUI for suno-to-ableton."""

from __future__ import annotations

import io
from pathlib import Path

from rich.console import Console
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.containers import Vertical as VContainer
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    Rule,
    Select,
    Static,
)


class HelpFooter(VContainer):
    """Two-line footer: help text on top, key bindings on bottom."""

    DEFAULT_CSS = """
    HelpFooter {
        dock: bottom;
        height: auto;
        max-height: 2;
    }
    HelpFooter #help-bar {
        height: 1;
        padding: 0 2;
        background: $panel;
        color: $text-muted;
    }
    HelpFooter Footer {
        height: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="help-bar")
        yield Footer()

import suno_to_ableton.pipeline as pipeline_module
import suno_to_ableton.reporting as reporting_module
from .config import SunoPrepConfig
from .discovery import discover_project, scan_for_projects
from .models import ProcessingManifest, ProjectInventory

# ── Help text for every interactive widget ──────────────────────────────

TOOLTIPS: dict[str, str] = {
    # Toolbar
    "source-dir": (
        "Path to the directory containing Suno AI export files. "
        "Expects numbered WAV stems (0 Song.wav, 1 Drums.wav, ...) and MIDI files."
    ),
    "scan": (
        "Scan the source directory for Suno export files (F5). "
        "If no project files are found, automatically scans subdirectories."
    ),
    "find-projects": (
        "Recursively scan for nested project folders. "
        "Select a found project to set it as the source directory."
    ),
    "process": (
        "Run the full preprocessing pipeline (F9). "
        "Detects BPM, aligns to grid, normalizes audio, cleans MIDI."
    ),

    # Audio config
    "target-sr": (
        "Target sample rate (Hz) for output audio. "
        "48000 is standard for Ableton Live."
    ),
    "quantize-grid": (
        "MIDI quantization grid (e.g. 1/16, 1/8, 1/32). "
        "Finer grids preserve more timing nuance."
    ),
    "min-note-ms": (
        "Minimum MIDI note duration (ms). "
        "Shorter notes are removed to eliminate glitch artifacts."
    ),

    # Core options
    "dry-run": (
        "Preview mode \u2014 show what would be done without writing any files."
    ),
    "verbose": (
        "Show detailed per-file progress and intermediate processing steps."
    ),
    "skip-existing": (
        "Skip files that already exist in the output directory."
    ),
    "force": (
        "Overwrite existing output files without prompting."
    ),
    "separate-missing": (
        "Run AI stem separation (Demucs) on the full mix "
        "to generate missing stems. Requires separation backend."
    ),

    # Advanced features
    "choose-stems": (
        "Compare original vs AI-generated stems. "
        "Recommends the better version based on energy and spectral analysis."
    ),
    "choose-grid-anchor": (
        "Analyze grid anchor candidates for ambiguous intros. "
        "Finds the best downbeat alignment point."
    ),
    "detect-sections": (
        "Detect arrangement sections (intro, verse, chorus, etc.) "
        "using spectral segmentation."
    ),
    "repair-midi": (
        "Conservative MIDI repair \u2014 detects key, flags out-of-key notes, "
        "fixes stacked chords, removes ghost notes."
    ),
    "requantize-midi": (
        "Feel-based MIDI requantization. "
        "Re-snaps notes to grid while preserving groove."
    ),
    "reseparate": (
        "Re-run AI stem separation. "
        "Useful to retry with different settings."
    ),
    "apply-features": (
        "Write advanced feature changes to output files. "
        "Without this, features only print analysis."
    ),
    "requantize-mode": (
        "Light = gentle nudge, Strict = hard snap, "
        "Swing = add swing feel, Triplet = triplet grid."
    ),

    # Export ALS
    "export-als": (
        "Generate an Ableton Live Set (.als) from processed output. Experimental."
    ),
    "als-template": (
        "Path to Example.als template. "
        "Leave blank for auto-detection."
    ),

    # Tables / panels
    "inventory": (
        "File inventory \u2014 audio stems and MIDI discovered by scan."
    ),
    "pipeline-log": (
        "Live processing log with real-time pipeline output."
    ),
    "projects-table": (
        "Projects found by recursive scan. "
        "Click a row to select that project."
    ),
}


class SunoPrepTUI(App):
    """Suno export preprocessor TUI."""

    TITLE = "suno-to-ableton"
    SUB_TITLE = "Suno AI Export Preprocessor for Ableton Live"

    CSS = """
    Screen {
        padding: 0;
    }

    /* ── Toolbar ── */
    #toolbar {
        height: 3;
        margin: 1 1 0 1;
    }
    #source-dir {
        width: 1fr;
        margin-right: 1;
    }
    #scan, #process, #find-projects {
        min-width: 14;
        margin-left: 1;
    }

    /* ── Config sections ── */
    #config-row-1 {
        height: auto;
        margin: 1 1 0 1;
        align: left middle;
    }
    .config-field {
        width: auto;
        height: auto;
        margin: 0 1 0 0;
    }
    .config-field Label {
        height: 1;
        width: auto;
        margin: 0 0 0 1;
        color: $text-muted;
    }
    .config-field Input {
        width: 16;
    }

    #config-row-2 {
        height: 3;
        margin: 0 1 0 1;
        align: left middle;
    }
    #config-row-2 Checkbox {
        width: auto;
        margin: 0 1 0 0;
    }

    /* ── Advanced ── */
    .section-rule {
        margin: 0 1;
        color: $text-muted;
    }
    #phase2-label {
        height: 1;
        margin: 0 1;
        color: $text-muted;
    }
    #phase2-row-1 {
        height: 3;
        margin: 0 1 0 1;
        align: left middle;
    }
    #phase2-row-2 {
        height: auto;
        margin: 0 1 0 1;
        align: left middle;
    }
    #phase2-row-1 Checkbox {
        width: auto;
        margin: 0 1 0 0;
    }
    #phase2-row-2 Checkbox {
        width: auto;
        margin: 1 1 0 0;
    }
    .phase2-field {
        width: auto;
        height: auto;
        margin: 0 0 0 0;
    }
    .phase2-field Label {
        height: 1;
        width: auto;
        margin: 0 0 0 0;
        color: $text-muted;
    }
    .phase2-field Select {
        width: 18;
        margin-left: -2;
    }

    /* ── Export ── */
    #export-row {
        height: auto;
        margin: 0 1 0 1;
        align: left middle;
    }
    #export-row Checkbox {
        width: auto;
        margin: 1 1 0 0;
    }
    .export-field {
        width: 1fr;
        height: auto;
        margin: 0 0 0 2;
    }
    .export-field Label {
        height: 1;
        width: auto;
        margin: 0 0 0 1;
        color: $text-muted;
    }
    .export-field Input {
        width: 1fr;
    }
    .export-field.-disabled {
        opacity: 40%;
    }

    /* ── Projects table ── */
    #projects-table {
        height: auto;
        max-height: 10;
        margin: 1 1;
        display: none;
    }

    /* ── Inventory ── */
    #inventory {
        height: auto;
        max-height: 14;
        margin: 1 1 0 1;
    }

    /* ── Log + results ── */
    #pipeline-log {
        height: 1fr;
        min-height: 6;
        margin: 1 1;
        border: solid $accent;
    }
    #results {
        height: auto;
        max-height: 5;
        margin: 0 1;
        display: none;
    }

    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "toggle_dark", "Dark/Light"),
        Binding("f5", "scan", "Scan"),
        Binding("f9", "process", "Process"),
    ]

    def __init__(self):
        super().__init__()
        self._inventory: ProjectInventory | None = None
        self._buffer_pos: int = 0
        self._found_projects: list[tuple[Path, str]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            # Source dir + buttons
            with Horizontal(id="toolbar"):
                yield Input(
                    placeholder="Source directory...",
                    value=str(Path.cwd()),
                    id="source-dir",
                )
                yield Button("Scan", id="scan", variant="default")
                yield Button("Find Projects", id="find-projects", variant="default")
                yield Button("Process", id="process", variant="primary")

            # Project browser table (hidden until Find Projects is clicked)
            yield DataTable(id="projects-table", cursor_type="row")

            # Audio config
            with Horizontal(id="config-row-1"):
                with Vertical(classes="config-field"):
                    yield Label("SR:")
                    yield Input(value="48000", id="target-sr")
                with Vertical(classes="config-field"):
                    yield Label("Grid:")
                    yield Input(value="1/16", id="quantize-grid")
                with Vertical(classes="config-field"):
                    yield Label("Min Note:")
                    yield Input(value="40", id="min-note-ms")

            # Core options
            with Horizontal(id="config-row-2"):
                yield Checkbox("Dry Run", id="dry-run")
                yield Checkbox("Verbose", id="verbose")
                yield Checkbox("Skip Existing", id="skip-existing")
                yield Checkbox("Force", id="force")
                yield Checkbox("Separate Missing", id="separate-missing")

            # Advanced features
            yield Rule(classes="section-rule")
            yield Static("[bold]Advanced Features[/bold]", id="phase2-label")
            with Horizontal(id="phase2-row-1"):
                yield Checkbox("Choose Stems", id="choose-stems")
                yield Checkbox("Grid Anchor", id="choose-grid-anchor")
                yield Checkbox("Detect Sections", id="detect-sections")
                yield Checkbox("Repair MIDI", id="repair-midi")
                yield Checkbox("Requantize MIDI", id="requantize-midi")
                yield Checkbox("Reseparate", id="reseparate")
            with Horizontal(id="phase2-row-2"):
                yield Checkbox("Apply Changes", id="apply-features")
                with Vertical(classes="phase2-field"):
                    yield Label("Requantize Mode:")
                    yield Select(
                        [(label, val) for val, label in [
                            ("light", "Light"),
                            ("strict", "Strict"),
                            ("swing", "Swing"),
                            ("triplet", "Triplet"),
                        ]],
                        value="light",
                        id="requantize-mode",
                        allow_blank=False,
                    )

            # Export ALS
            yield Rule(classes="section-rule")
            with Horizontal(id="export-row"):
                yield Checkbox("Export ALS (experimental)", id="export-als")
                with Vertical(classes="export-field"):
                    yield Label("Template:")
                    yield Input(
                        placeholder="(auto-detect)",
                        id="als-template",
                    )

            yield DataTable(id="inventory")
            yield Log(id="pipeline-log", auto_scroll=True)
            yield Static(id="results")
        yield HelpFooter()

    def on_mount(self) -> None:
        self.query_one("#process", Button).disabled = True
        table = self.query_one("#inventory", DataTable)
        table.add_columns("#", "Role", "Type", "Filename", "SR", "Ch", "Duration")

        # Set up projects table columns
        proj_table = self.query_one("#projects-table", DataTable)
        proj_table.add_columns("Song Title", "Directory")

        # Template field starts disabled (Export ALS unchecked by default)
        self._toggle_template_field(False)

        # Apply tooltips to all interactive widgets
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        """Set tooltip text on all interactive widgets."""
        for widget_id, tip in TOOLTIPS.items():
            try:
                widget = self.query_one(f"#{widget_id}")
                widget.tooltip = tip
            except Exception:
                pass

    def _update_help_bar(self, focused) -> None:
        """Update the help bar based on the focused widget."""
        help_bar = self.query_one("#help-bar", Static)
        if focused is None:
            help_bar.update("")
            return
        # Walk up the widget tree to find an ID that has help text
        widget = focused
        help_text = ""
        while widget is not None:
            wid = getattr(widget, "id", None)
            if wid and wid in TOOLTIPS:
                help_text = TOOLTIPS[wid]
                break
            widget = getattr(widget, "parent", None)
        help_bar.update(help_text)

    def on_descendant_focus(self, event) -> None:
        """Fires when any descendant widget receives focus."""
        self._update_help_bar(event.widget)

    def on_descendant_blur(self, event) -> None:
        """Clear help bar when focus leaves."""
        # Only clear if nothing else is focused
        if self.screen.focused is None:
            self._update_help_bar(None)

    def _toggle_template_field(self, enabled: bool) -> None:
        """Enable/disable the template field based on Export ALS checkbox."""
        template_input = self.query_one("#als-template", Input)
        template_input.disabled = not enabled
        export_field = self.query_one(".export-field")
        if enabled:
            export_field.remove_class("-disabled")
        else:
            export_field.add_class("-disabled")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "export-als":
            self._toggle_template_field(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "scan":
            self.action_scan()
        elif event.button.id == "process":
            self.action_process()
        elif event.button.id == "find-projects":
            self._find_projects()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle clicking a row in the projects table."""
        if event.data_table.id != "projects-table":
            return
        row_index = event.cursor_row
        if 0 <= row_index < len(self._found_projects):
            project_path, title = self._found_projects[row_index]
            # Set source dir to the selected project
            self.query_one("#source-dir", Input).value = str(project_path)
            log = self.query_one("#pipeline-log", Log)
            log.write_line(f"Selected project: {title} ({project_path})")
            # Auto-scan the selected project
            self.action_scan()

    @work(thread=True, exclusive=True, group="find")
    def _find_projects(self) -> None:
        """Recursively scan for project directories."""
        source = Path(
            self.call_from_thread(self._get_input_value, "#source-dir")
        ).resolve()
        log_msg = f"Scanning for projects in {source}..."
        self.call_from_thread(
            self.query_one("#pipeline-log", Log).write_line, log_msg
        )

        try:
            projects = scan_for_projects(source)
        except Exception as e:
            self.call_from_thread(
                self.query_one("#pipeline-log", Log).write_line,
                f"Error scanning for projects: {e}",
            )
            return

        self._found_projects = projects
        self.call_from_thread(self._populate_projects_table, projects)

    def _populate_projects_table(
        self, projects: list[tuple[Path, str]]
    ) -> None:
        """Populate the projects table with found directories."""
        proj_table = self.query_one("#projects-table", DataTable)
        proj_table.clear()

        if not projects:
            self.query_one("#pipeline-log", Log).write_line(
                "No projects found in subdirectories."
            )
            proj_table.styles.display = "none"
            return

        for project_path, title in projects:
            proj_table.add_row(title, str(project_path))

        proj_table.styles.display = "block"
        self.query_one("#pipeline-log", Log).write_line(
            f"Found {len(projects)} project(s). Click a row to select."
        )

    def action_scan(self) -> None:
        source = Path(self.query_one("#source-dir", Input).value).resolve()
        log = self.query_one("#pipeline-log", Log)
        log.clear()
        self.query_one("#results", Static).update("")
        self.query_one("#results", Static).styles.display = "none"

        try:
            inventory = discover_project(source)
            self._inventory = inventory
        except Exception as e:
            log.write_line(f"Error scanning: {e}")
            return

        # If the directory has no project files, try nested scan
        has_files = inventory.full_mix or inventory.stems or inventory.midi_files
        if not has_files:
            log.write_line(
                f"No project files in {source}, scanning subdirectories..."
            )
            self._find_projects()
            return

        # Hide projects table when scanning a specific project
        self.query_one("#projects-table", DataTable).styles.display = "none"

        self._show_inventory(inventory)

    def _show_inventory(self, inventory: ProjectInventory) -> None:
        """Populate the inventory table and log scan results."""
        log = self.query_one("#pipeline-log", Log)
        table = self.query_one("#inventory", DataTable)
        table.clear()

        if inventory.full_mix:
            f = inventory.full_mix
            table.add_row(
                str(f.track_number or "-"),
                f.role.value,
                f.stem_type.value,
                f.path.name,
                str(f.sample_rate or "-"),
                str(f.channels or "-"),
                f"{f.duration_seconds:.2f}s" if f.duration_seconds else "-",
            )

        for f in inventory.stems:
            table.add_row(
                str(f.track_number or "-"),
                f.role.value,
                f.stem_type.value,
                f.path.name,
                str(f.sample_rate or "-"),
                str(f.channels or "-"),
                f"{f.duration_seconds:.2f}s" if f.duration_seconds else "-",
            )

        for f in inventory.midi_files:
            table.add_row("-", f.role.value, "-", f.path.name, "-", "-", "-")

        for w in inventory.warnings:
            log.write_line(f"Warning: {w}")

        stem_count = len(inventory.stems) + (1 if inventory.full_mix else 0)
        log.write_line(
            f"Scanned: {stem_count} audio files, "
            f"{len(inventory.midi_files)} MIDI files"
        )
        if inventory.song_title:
            log.write_line(f"Song: {inventory.song_title}")

        self.query_one("#process", Button).disabled = False

    def action_process(self) -> None:
        if self.query_one("#process", Button).disabled:
            return
        self._run_pipeline()

    @work(thread=True, exclusive=True)
    def _run_pipeline(self) -> None:
        log = self.call_from_thread(self.query_one, "#pipeline-log", Log)
        self.call_from_thread(log.clear)
        self._buffer_pos = 0

        # Build config from UI
        source_dir = Path(
            self.call_from_thread(self._get_input_value, "#source-dir")
        ).resolve()

        # ALS template
        als_template_str = self.call_from_thread(
            self._get_input_value, "#als-template"
        )
        als_template = Path(als_template_str) if als_template_str.strip() else None

        config = SunoPrepConfig(
            source_dir=source_dir,
            output_dir=Path("processed"),
            dry_run=self.call_from_thread(self._get_checkbox_value, "#dry-run"),
            verbose=self.call_from_thread(self._get_checkbox_value, "#verbose"),
            skip_existing=self.call_from_thread(
                self._get_checkbox_value, "#skip-existing"
            ),
            force=self.call_from_thread(self._get_checkbox_value, "#force"),
            target_sr=int(
                self.call_from_thread(self._get_input_value, "#target-sr")
            ),
            quantize_grid=self.call_from_thread(
                self._get_input_value, "#quantize-grid"
            ),
            min_note_ms=float(
                self.call_from_thread(self._get_input_value, "#min-note-ms")
            ),
            separate_missing=self.call_from_thread(
                self._get_checkbox_value, "#separate-missing"
            ),
            # Phase 2 features
            choose_stems=self.call_from_thread(
                self._get_checkbox_value, "#choose-stems"
            ),
            choose_grid_anchor=self.call_from_thread(
                self._get_checkbox_value, "#choose-grid-anchor"
            ),
            detect_sections=self.call_from_thread(
                self._get_checkbox_value, "#detect-sections"
            ),
            repair_midi=self.call_from_thread(
                self._get_checkbox_value, "#repair-midi"
            ),
            requantize_midi=self.call_from_thread(
                self._get_checkbox_value, "#requantize-midi"
            ),
            requantize_mode=self.call_from_thread(
                self._get_select_value, "#requantize-mode"
            ),
            reseparate=self.call_from_thread(
                self._get_checkbox_value, "#reseparate"
            ),
            apply_features=self.call_from_thread(
                self._get_checkbox_value, "#apply-features"
            ),
            # ALS export
            export_als=self.call_from_thread(
                self._get_checkbox_value, "#export-als"
            ),
            als_template=als_template,
        )

        # Redirect console output to buffer
        buffer = io.StringIO()
        captured = Console(file=buffer, width=120, force_terminal=False)

        orig_reporting = reporting_module.console
        orig_pipeline = pipeline_module.console
        orig_pipeline_console = pipeline_module._console

        reporting_module.console = captured
        pipeline_module.console = captured
        pipeline_module._console = captured

        # Start drain timer
        timer = self.call_from_thread(self.set_interval, 0.1, self._drain_buffer, buffer)

        try:
            self.call_from_thread(self._set_processing, True)
            manifest = pipeline_module.run_pipeline(config)

            # Final drain
            self._drain_sync(buffer)

            self.call_from_thread(self._show_results, manifest)
        except Exception as e:
            self._drain_sync(buffer)
            self.call_from_thread(log.write_line, f"\nERROR: {e}")
        finally:
            reporting_module.console = orig_reporting
            pipeline_module.console = orig_pipeline
            pipeline_module._console = orig_pipeline_console

            self.call_from_thread(timer.stop)
            self.call_from_thread(self._set_processing, False)

    def _drain_buffer(self, buffer: io.StringIO) -> None:
        content = buffer.getvalue()
        if len(content) > self._buffer_pos:
            new_text = content[self._buffer_pos :]
            self._buffer_pos = len(content)
            log = self.query_one("#pipeline-log", Log)
            for line in new_text.splitlines():
                stripped = line.strip()
                if stripped:
                    log.write_line(stripped)

    def _drain_sync(self, buffer: io.StringIO) -> None:
        content = buffer.getvalue()
        if len(content) > self._buffer_pos:
            new_text = content[self._buffer_pos :]
            self._buffer_pos = len(content)
            log = self.query_one("#pipeline-log", Log)
            for line in new_text.splitlines():
                stripped = line.strip()
                if stripped:
                    self.call_from_thread(log.write_line, stripped)

    def _get_input_value(self, selector: str) -> str:
        return self.query_one(selector, Input).value

    def _get_checkbox_value(self, selector: str) -> bool:
        return self.query_one(selector, Checkbox).value

    def _get_select_value(self, selector: str) -> str:
        return self.query_one(selector, Select).value

    def _set_processing(self, processing: bool) -> None:
        self.query_one("#scan", Button).disabled = processing
        self.query_one("#process", Button).disabled = processing
        self.query_one("#source-dir", Input).disabled = processing

    def _show_results(self, manifest: ProcessingManifest) -> None:
        results = self.query_one("#results", Static)
        lines = [f"Song: {manifest.song_title}"]
        if manifest.bpm is not None:
            lines.append(
                f"BPM: {manifest.bpm:.1f} (confidence: {manifest.bpm_confidence:.2f})"
            )
        lines.append(
            f"Stems: {len(manifest.stems)} | MIDI: {len(manifest.midi_files)}"
        )
        if manifest.generated_stems:
            lines.append(f"Generated stems: {len(manifest.generated_stems)}")
        if manifest.features_invoked:
            features = [f.feature for f in manifest.features_invoked]
            lines.append(f"Features: {', '.join(features)}")
        if manifest.warnings:
            lines.append(f"Warnings: {len(manifest.warnings)}")
        results.update("\n".join(lines))
        results.styles.display = "block"


def run_tui() -> None:
    """Launch the TUI application."""
    app = SunoPrepTUI()
    app.run()
