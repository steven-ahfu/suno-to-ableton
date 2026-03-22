# Installation

## Step 1: Install Python 3.11+

The preprocessor requires Python 3.11 or later.

=== "macOS"

    ```bash
    brew install python@3.12
    ```

=== "Ubuntu / Debian"

    ```bash
    sudo apt update && sudo apt install python3.12 python3.12-venv python3-pip
    ```

=== "Windows"

    Download the installer from [python.org](https://www.python.org/downloads/) and check **"Add Python to PATH"** during setup. Or use `winget`:

    ```powershell
    winget install Python.Python.3.12
    ```

Verify your version:

```bash
python3 --version   # should print 3.11.x or later
```

## Step 2: Install ffmpeg

Used for audio normalization, sample-rate conversion, and format conversion.

=== "macOS"

    ```bash
    brew install ffmpeg
    ```

=== "Ubuntu / Debian"

    ```bash
    sudo apt update && sudo apt install ffmpeg
    ```

=== "Windows"

    ```powershell
    winget install Gyan.FFmpeg
    ```

    Or download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

Verify it's available:

```bash
ffmpeg -version
```

## Step 3: Install uv

Install [uv](https://docs.astral.sh/uv/) to manage the virtualenv, dependencies, and commands.

=== "macOS / Linux"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Homebrew"

    ```bash
    brew install uv
    ```

=== "Windows"

    ```powershell
    winget install astral-sh.uv
    ```

Verify it's available:

```bash
uv --version
```

## Step 4: Clone and install the preprocessor

```bash
git clone https://github.com/steven-ahfu/suno-to-ableton.git
cd suno-to-ableton
uv sync
```

This installs everything needed for the default processing pipeline: stem discovery, naming, sample-rate conversion, silence trimming, BPM detection, grid alignment, MIDI cleanup, and report generation.

## Optional extras

### TUI (interactive terminal interface)

Adds a point-and-click terminal UI for browsing projects, toggling options, and running the pipeline.

```bash
uv sync --extra tui
```

Installs [Textual](https://textual.textualize.io/) automatically.

### Stem separation (CPU)

Adds AI-powered stem separation via [Demucs](https://github.com/facebookresearch/demucs) (Meta) and [UVR](https://github.com/Anjok07/ultimatevocalremovergui) (Ultimate Vocal Remover).

!!! warning "Install PyTorch first"
    The separation extras depend on PyTorch for inference. You must install PyTorch before installing the separation extras.

```bash
# 1. Install PyTorch (CPU-only)
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# 2. Install separation extras
uv sync --extra separation
```

### Stem separation (NVIDIA GPU)

CUDA acceleration significantly speeds up stem separation. Requires an NVIDIA GPU with CUDA support.

```bash
# 1. Install PyTorch with CUDA 12.1 support
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# 2. Install GPU separation extras
uv sync --extra separation-gpu
```

!!! tip
    Visit [pytorch.org/get-started](https://pytorch.org/get-started/locally/) to find the install command matching your platform and CUDA version.

### Everything at once

=== "CPU"

    ```bash
    uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
    uv sync --extra tui --extra separation
    ```

=== "GPU (NVIDIA)"

    ```bash
    uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
    uv sync --extra tui --extra separation-gpu
    ```

## Verify the installation

```bash
# Should print usage info
uv run suno-to-ableton --help

# Check ffmpeg
ffmpeg -version

# (Optional) Check PyTorch — only needed for stem separation
uv run python -c "import torch; print(f'PyTorch {torch.__version__}, CUDA: {torch.cuda.is_available()}')"
```

## Updating

```bash
cd suno-to-ableton
git pull
uv sync
```

## Uninstalling

```bash
rm -rf .venv
```

## Dependency reference

| Package | Role |
|---------|------|
| **librosa** | BPM detection, onset analysis, section detection |
| **pretty_midi** | MIDI reading, writing, and cleanup |
| **soundfile** | Audio metadata probing |
| **scipy** | Signal processing for feature analysis |
| **ffmpeg** | Audio normalization and format conversion (external) |
| **rich** | Terminal output formatting |
| **typer** | CLI framework |
| **pydantic** | Data models and serialization |
| **textual** | TUI (optional — `.[tui]`) |
| **demucs** | AI stem separation — Meta's model (optional — `.[separation]`) |
| **audio-separator** | UVR stem separation backend (optional — `.[separation]`) |
| **onnxruntime** / **onnxruntime-gpu** | ONNX inference for UVR models (optional) |
| **PyTorch** | Neural network inference for Demucs (install separately before separation extras) |
