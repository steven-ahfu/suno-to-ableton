"""Textual TUI for suno-to-ableton."""

from __future__ import annotations

import io
import time
from pathlib import Path

from rich.console import Console
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.containers import Vertical as VContainer
from textual.screen import Screen
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
    TabbedContent,
    TabPane,
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
from .progress import PipelineStep, StepStatus, make_steps

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
        "Path to Ableton .als template. "
        "Auto-detected from templates/ directory if left blank."
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


# ── Status display helpers ───────────────────────────────────────────────

_STATUS_ICONS: dict[StepStatus, str] = {
    StepStatus.PENDING: "[ ]",
    StepStatus.RUNNING: "[>>]",
    StepStatus.DONE: "[ok]",
    StepStatus.SKIPPED: "[--]",
    StepStatus.ERROR: "[!!]",
}


def _fmt_elapsed(step: PipelineStep) -> str:
    elapsed = step.elapsed
    if elapsed is None:
        return ""
    return f"{elapsed:.1f}s"


# ── ProcessingScreen ─────────────────────────────────────────────────────


class ProcessingScreen(Screen):
    """Dedicated screen showing real-time pipeline progress."""

    CSS = """
    ProcessingScreen {
        padding: 0;
    }
    #step-table {
        height: auto;
        max-height: 14;
        margin: 1 1 0 1;
    }
    #proc-log {
        height: 1fr;
        min-height: 6;
        margin: 1 1;
        border: solid $accent;
    }
    #results-tabs {
        height: auto;
        max-height: 14;
        margin: 0 1;
        display: none;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("enter", "finish", "Close", show=False),
        Binding("q", "finish", "Close", show=False),
    ]

    def __init__(self, config: SunoPrepConfig) -> None:
        super().__init__()
        self._config = config
        self._steps = make_steps()
        self._step_map: dict[str, PipelineStep] = {s.key: s for s in self._steps}
        self._step_row_keys: dict[str, object] = {}
        self._step_column_keys: dict[str, object] = {}
        self._finished = False
        self._output_dir: Path | None = None
        self._buffer_pos: int = 0
        self._manifest: ProcessingManifest | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield DataTable(id="step-table", cursor_type="none")
            yield Log(id="proc-log", auto_scroll=True)
            with TabbedContent(id="results-tabs"):
                with TabPane("Stems", id="tab-stems"):
                    yield DataTable(id="stems-table", cursor_type="none")
                with TabPane("MIDI", id="tab-midi"):
                    yield DataTable(id="midi-table", cursor_type="none")
                with TabPane("Features", id="tab-features"):
                    yield DataTable(id="features-table", cursor_type="none")
                with TabPane("Warnings", id="tab-warnings"):
                    yield DataTable(id="warnings-table", cursor_type="none")
        yield Footer()

    def on_mount(self) -> None:
        # Set up step table
        table = self.query_one("#step-table", DataTable)
        column_keys = table.add_columns("#", "Step", "Status", "Time", "Detail")
        self._step_column_keys = dict(
            zip(["number", "step", "status", "time", "detail"], column_keys)
        )
        for step in self._steps:
            row_key = table.add_row(
                str(step.number),
                step.label,
                _STATUS_ICONS[step.status],
                "",
                "",
                key=step.key,
            )
            self._step_row_keys[step.key] = row_key

        # Set up result tables (columns only — rows added when done)
        stems_t = self.query_one("#stems-table", DataTable)
        stems_t.add_columns("File", "Type", "Generated", "Steps")

        midi_t = self.query_one("#midi-table", DataTable)
        midi_t.add_columns("File", "Steps")

        features_t = self.query_one("#features-table", DataTable)
        features_t.add_columns("Feature", "Mode", "Confidence", "Recommendation")

        warnings_t = self.query_one("#warnings-table", DataTable)
        warnings_t.add_columns("Warning",)

        # Start pipeline worker
        self._run_pipeline()

    # ── Progress callback (called from pipeline thread) ──────────────

    def _handle_progress(self, step_key: str, status: StepStatus, detail: str) -> None:
        step = self._step_map.get(step_key)
        if step is None:
            return

        now = time.monotonic()
        if status == StepStatus.RUNNING and step.status != StepStatus.RUNNING:
            step.started_at = now
        if status in (StepStatus.DONE, StepStatus.SKIPPED, StepStatus.ERROR):
            step.finished_at = now

        step.status = status
        if detail:
            step.detail = detail
        if status == StepStatus.ERROR:
            step.error_msg = detail

        self.app.call_from_thread(self._refresh_step_row, step_key)

    def _refresh_step_row(self, step_key: str) -> None:
        step = self._step_map[step_key]
        table = self.query_one("#step-table", DataTable)
        row_key = self._step_row_keys.get(step_key)
        if row_key is None:
            return
        try:
            table.update_cell(row_key, self._step_column_keys["number"], str(step.number))
            table.update_cell(row_key, self._step_column_keys["step"], step.label)
            table.update_cell(row_key, self._step_column_keys["status"], _STATUS_ICONS[step.status])
            table.update_cell(row_key, self._step_column_keys["time"], _fmt_elapsed(step))
            table.update_cell(row_key, self._step_column_keys["detail"], step.detail)
        except Exception:
            pass

    def _tick_elapsed(self) -> None:
        """Refresh elapsed time for any running steps."""
        table = self.query_one("#step-table", DataTable)
        for step in self._steps:
            if step.status == StepStatus.RUNNING:
                row_key = self._step_row_keys.get(step.key)
                if row_key is None:
                    continue
                try:
                    table.update_cell(
                        row_key,
                        self._step_column_keys["time"],
                        _fmt_elapsed(step),
                    )
                except Exception:
                    pass

    # ── Pipeline worker ──────────────────────────────────────────────

    @work(thread=True, exclusive=True)
    def _run_pipeline(self) -> None:
        # Redirect console output to buffer
        buffer = io.StringIO()
        captured = Console(file=buffer, width=120, force_terminal=False)

        orig_reporting = reporting_module.console
        orig_pipeline = pipeline_module.console
        orig_pipeline_console = pipeline_module._console

        reporting_module.console = captured
        pipeline_module.console = captured
        pipeline_module._console = captured

        # Start drain timer + elapsed ticker
        drain_timer = self.app.call_from_thread(
            self.app.set_interval, 0.1, lambda: self._drain_buffer(buffer)
        )
        elapsed_timer = self.app.call_from_thread(
            self.app.set_interval, 0.5, self._tick_elapsed
        )

        try:
            manifest = pipeline_module.run_pipeline(
                self._config, on_progress=self._handle_progress
            )
            self._manifest = manifest
            self._output_dir = self._config.resolved_output_dir

            # Final drain
            self._drain_sync(buffer)

            self.app.call_from_thread(self._show_results, manifest)
        except Exception as e:
            self._drain_sync(buffer)
            self.app.call_from_thread(
                self.query_one("#proc-log", Log).write_line, f"\nERROR: {e}"
            )
        finally:
            reporting_module.console = orig_reporting
            pipeline_module.console = orig_pipeline
            pipeline_module._console = orig_pipeline_console

            self.app.call_from_thread(drain_timer.stop)
            self.app.call_from_thread(elapsed_timer.stop)
            self._finished = True

    def _drain_buffer(self, buffer: io.StringIO) -> None:
        content = buffer.getvalue()
        if len(content) > self._buffer_pos:
            new_text = content[self._buffer_pos:]
            self._buffer_pos = len(content)
            log = self.query_one("#proc-log", Log)
            for line in new_text.splitlines():
                stripped = line.strip()
                if stripped:
                    log.write_line(stripped)

    def _drain_sync(self, buffer: io.StringIO) -> None:
        content = buffer.getvalue()
        if len(content) > self._buffer_pos:
            new_text = content[self._buffer_pos:]
            self._buffer_pos = len(content)
            log = self.query_one("#proc-log", Log)
            for line in new_text.splitlines():
                stripped = line.strip()
                if stripped:
                    self.app.call_from_thread(log.write_line, stripped)

    # ── Results ──────────────────────────────────────────────────────

    def _show_results(self, manifest: ProcessingManifest) -> None:
        # Stems tab
        stems_t = self.query_one("#stems-table", DataTable)
        for pf in manifest.stems:
            stems_t.add_row(
                pf.output_path.name,
                pf.stem_type.value,
                "yes" if pf.was_generated else "",
                ", ".join(pf.processing_steps[:3]),
            )
        for pf in manifest.generated_stems:
            stems_t.add_row(
                pf.output_path.name,
                pf.stem_type.value,
                "yes",
                ", ".join(pf.processing_steps[:3]),
            )

        # MIDI tab
        midi_t = self.query_one("#midi-table", DataTable)
        for pf in manifest.midi_files:
            midi_t.add_row(
                pf.output_path.name,
                ", ".join(pf.processing_steps[:4]),
            )

        # Features tab
        features_t = self.query_one("#features-table", DataTable)
        for fi in manifest.features_invoked:
            features_t.add_row(
                fi.feature,
                fi.mode,
                f"{fi.confidence:.2f}" if fi.confidence is not None else "",
                fi.recommendation or "",
            )

        # Warnings tab
        warnings_t = self.query_one("#warnings-table", DataTable)
        for w in manifest.warnings:
            warnings_t.add_row(w)

        # Show the tabs
        self.query_one("#results-tabs", TabbedContent).styles.display = "block"

    # ── Actions ──────────────────────────────────────────────────────

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action == "finish" and not self._finished:
            return False
        return True

    def action_finish(self) -> None:
        self.dismiss(self._output_dir)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Main TUI App ─────────────────────────────────────────────────────────


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

    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "toggle_dark", "Dark/Light"),
        Binding("f5", "scan", "Scan", priority=True),
        Binding("f9", "process", "Process", priority=True),
    ]

    def __init__(self):
        super().__init__()
        self._inventory: ProjectInventory | None = None
        self._found_projects: list[tuple[Path, str]] = []
        self._final_output_dir: Path | None = None

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
            # Auto-detect template if field is empty
            if not template_input.value.strip():
                detected = self._detect_template()
                if detected:
                    template_input.value = str(detected)
        else:
            export_field.add_class("-disabled")

    def _detect_template(self) -> Path | None:
        """Try to find the Ableton template in common locations."""
        repo_root = Path(__file__).parent.parent
        source_dir_str = self.query_one("#source-dir", Input).value.strip()
        source_dir = Path(source_dir_str) if source_dir_str else None

        candidates = [
            repo_root / "templates" / "Ableton 12 Template.als",
        ]
        if source_dir:
            candidates.extend([
                source_dir / "Example.als",
                source_dir.parent / "Example.als",
            ])
        candidates.append(repo_root / "Example.als")

        for p in candidates:
            if p.exists():
                return p
        return None

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
            self.notify("Scan a directory first before processing.", severity="warning")
            return
        config = self._build_config()
        self.push_screen(ProcessingScreen(config), callback=self._on_processing_done)

    def _build_config(self) -> SunoPrepConfig:
        """Build a SunoPrepConfig from current UI widget values."""
        source_dir = Path(self.query_one("#source-dir", Input).value).resolve()

        als_template_str = self.query_one("#als-template", Input).value.strip()
        als_template = Path(als_template_str) if als_template_str else None

        return SunoPrepConfig(
            source_dir=source_dir,
            output_dir=Path("processed"),
            dry_run=self.query_one("#dry-run", Checkbox).value,
            verbose=self.query_one("#verbose", Checkbox).value,
            skip_existing=self.query_one("#skip-existing", Checkbox).value,
            force=self.query_one("#force", Checkbox).value,
            target_sr=int(self.query_one("#target-sr", Input).value),
            quantize_grid=self.query_one("#quantize-grid", Input).value,
            min_note_ms=float(self.query_one("#min-note-ms", Input).value),
            separate_missing=self.query_one("#separate-missing", Checkbox).value,
            # Phase 2 features
            choose_stems=self.query_one("#choose-stems", Checkbox).value,
            choose_grid_anchor=self.query_one("#choose-grid-anchor", Checkbox).value,
            detect_sections=self.query_one("#detect-sections", Checkbox).value,
            repair_midi=self.query_one("#repair-midi", Checkbox).value,
            requantize_midi=self.query_one("#requantize-midi", Checkbox).value,
            requantize_mode=str(self.query_one("#requantize-mode", Select).value),
            reseparate=self.query_one("#reseparate", Checkbox).value,
            apply_features=self.query_one("#apply-features", Checkbox).value,
            # ALS export
            export_als=self.query_one("#export-als", Checkbox).value,
            als_template=als_template,
        )

    def _on_processing_done(self, output_dir: Path | None) -> None:
        """Called when ProcessingScreen is dismissed."""
        self._final_output_dir = output_dir
        self.exit()

    def _get_input_value(self, selector: str) -> str:
        return self.query_one(selector, Input).value

    def _get_checkbox_value(self, selector: str) -> bool:
        return self.query_one(selector, Checkbox).value

    def _get_select_value(self, selector: str) -> str:
        return self.query_one(selector, Select).value


def run_tui() -> None:
    """Launch the TUI application."""
    app = SunoPrepTUI()
    app.run()
    if app._final_output_dir:
        print(f"\nOutput directory: {app._final_output_dir}")
