from pathlib import Path

import pytest

from koreanfa.audio import normalize_wav
from koreanfa.errors import AudioPreparationError


@pytest.mark.parametrize("contents", [b"", b"not a wav file"])
def test_rejects_unreadable_audio_without_leaking_backend_errors(
    tmp_path: Path, contents: bytes
) -> None:
    source = tmp_path / "broken.wav"
    source.write_bytes(contents)

    with pytest.raises(AudioPreparationError, match="Invalid or unreadable WAV audio"):
        normalize_wav(source, tmp_path / "normalized.wav")
