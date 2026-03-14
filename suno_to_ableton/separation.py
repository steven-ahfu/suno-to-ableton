"""Stem separation backends (Demucs + UVR)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .config import SunoPrepConfig
from .models import SeparationResult, SeparatorBackend


class SeparationBackendBase(ABC):
    """Abstract base class for stem separation backends."""

    @abstractmethod
    def separate(self, input_path: Path, output_dir: Path) -> SeparationResult:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...


class DemucsBackend(SeparationBackendBase):
    """GPU-accelerated stem separation using Demucs."""

    def __init__(self, model_name: str = "htdemucs"):
        self.model_name = model_name

    def is_available(self) -> bool:
        try:
            import demucs  # noqa: F401
            return True
        except ImportError:
            return False

    def separate(self, input_path: Path, output_dir: Path) -> SeparationResult:
        import torch
        from demucs.apply import apply_model
        from demucs.audio import save_audio
        from demucs.pretrained import get_model

        model = get_model(self.model_name)
        model.eval()

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model.to(device)

        # Load audio
        from demucs.audio import AudioFile

        wav = AudioFile(input_path).read(
            streams=0, samplerate=model.samplerate, channels=model.audio_channels
        )
        ref = wav.mean(0)
        wav = (wav - ref.mean()) / ref.std()
        wav = wav.to(device)

        # Apply model
        sources = apply_model(
            model, wav[None], device=device, shifts=1, split=True, overlap=0.25
        )[0]

        # Denormalize
        sources = sources * ref.std() + ref.mean()

        # Save each stem
        output_dir.mkdir(parents=True, exist_ok=True)
        output_paths = []
        for i, source_name in enumerate(model.sources):
            stem_path = output_dir / f"{source_name}.wav"
            save_audio(
                sources[i], str(stem_path), model.samplerate,
            )
            output_paths.append(stem_path)

        return SeparationResult(
            backend=SeparatorBackend.DEMUCS,
            model=self.model_name,
            input_path=input_path,
            output_stems=output_paths,
        )


class UVRBackend(SeparationBackendBase):
    """ONNX-GPU stem separation using audio-separator."""

    def __init__(self, model_name: str = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"):
        self.model_name = model_name

    def is_available(self) -> bool:
        try:
            from audio_separator.separator import Separator  # noqa: F401
            return True
        except ImportError:
            return False

    def separate(self, input_path: Path, output_dir: Path) -> SeparationResult:
        from audio_separator.separator import Separator

        output_dir.mkdir(parents=True, exist_ok=True)

        separator = Separator(
            output_dir=str(output_dir),
            output_format="WAV",
        )
        separator.load_model(self.model_name)
        output_files = separator.separate(str(input_path))

        output_paths = [Path(f) for f in output_files]

        return SeparationResult(
            backend=SeparatorBackend.UVR,
            model=self.model_name,
            input_path=input_path,
            output_stems=output_paths,
        )


def get_backend(config: SunoPrepConfig) -> SeparationBackendBase:
    """Factory function to get the configured separation backend."""
    if config.separator == SeparatorBackend.DEMUCS:
        backend = DemucsBackend(model_name=config.demucs_model)
    elif config.separator == SeparatorBackend.UVR:
        backend = UVRBackend()
    else:
        raise ValueError(f"Unknown separator backend: {config.separator}")

    if not backend.is_available():
        raise RuntimeError(
            f"{config.separator.value} is not installed. "
            f"Install with: pip install -e '.[separation]'"
        )

    return backend
