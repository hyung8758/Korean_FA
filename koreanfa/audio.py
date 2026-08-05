"""Audio preparation independent of the system SoX executable."""

from pathlib import Path

from .errors import AudioPreparationError


def normalize_wav(source: Path, destination: Path, *, sample_rate: int = 16_000) -> None:
    """Write a mono 16-bit PCM WAV accepted by both packaged models."""
    import numpy as np
    import soundfile as sf
    import soxr

    try:
        audio, original_rate = sf.read(source, dtype="float32", always_2d=True)
        if not audio.size:
            raise ValueError("audio contains no samples")
        if original_rate <= 0:
            raise ValueError(f"invalid sample rate: {original_rate}")
        if not np.isfinite(audio).all():
            raise ValueError("audio contains non-finite samples")
        mono = np.mean(audio, axis=1)
        if original_rate != sample_rate:
            mono = soxr.resample(mono, original_rate, sample_rate)
    except (OSError, RuntimeError, ValueError) as error:
        raise AudioPreparationError(f"Invalid or unreadable WAV audio: {source}: {error}") from error
    sf.write(destination, mono, sample_rate, subtype="PCM_16")
