"""Audio preparation independent of the system SoX executable."""

from __future__ import annotations

from pathlib import Path


def normalize_wav(source: Path, destination: Path, *, sample_rate: int = 16_000) -> None:
    """Write a mono 16-bit PCM WAV accepted by both packaged models."""
    import numpy as np
    import soundfile as sf
    import soxr

    audio, original_rate = sf.read(source, dtype="float32", always_2d=True)
    mono = np.mean(audio, axis=1)
    if original_rate != sample_rate:
        mono = soxr.resample(mono, original_rate, sample_rate)
    sf.write(destination, mono, sample_rate, subtype="PCM_16")
