# TUI (Interactive Terminal Interface)

The TUI provides a point-and-click terminal interface for the preprocessor.

## Requirements

Install the `tui` extra:

```bash
pip install -e '.[tui]'
```

## Launch

```bash
suno-ableton-preprocessor tui
```

<img src="tui.png" alt="TUI screenshot" width="800">

## Features

The TUI lets you:

- **Browse and select** project directories
- **Toggle processing options** with checkboxes — no need to remember CLI flags
- **Run the pipeline** and view results in real time
- **Review reports** after processing completes

The TUI exposes all the same options as the CLI — it's a visual wrapper, not a separate tool.
