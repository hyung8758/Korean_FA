import json
import wave
from collections.abc import Callable
from pathlib import Path

import pytest

from koreanfa._engine_config import platform_tag


@pytest.fixture
def write_wav() -> Callable[[Path], Path]:
    """Write a short, valid 16 kHz mono PCM WAV fixture."""

    def write(path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16_000)
            stream.writeframes(b"\x00\x00" * 1600)
        return path

    return write


@pytest.fixture
def write_textgrid() -> Callable[..., Path]:
    """Write a valid short-format KoreanFA TextGrid fixture."""

    def write(path: Path, *, word: bool = True, phone: bool = True, label: str = "테스트") -> Path:
        tiers: list[tuple[str, str]] = []
        if phone:
            tiers.append(("phone", "t"))
        if word:
            tiers.append(("word", label.replace('"', '""')))
        lines = ['File type = "ooTextFile short"', '"TextGrid"', "", "0", "1.000000", "<exists>", str(len(tiers))]
        for name, value in tiers:
            lines.extend(['"IntervalTier"', f'"{name}"', "0", "1.000000", "1", "0.000000", "1.000000", f'"{value}"'])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return write


@pytest.fixture
def write_test_manifest() -> Callable[..., Path]:
    """Create an isolated engine manifest for the active test platform."""

    def write(
        directory: Path,
        *,
        url: str | None,
        sha256: str | None,
        version: str = "test-1",
        filename: str = "manifest.json",
        minimum_glibc: str | None = None,
    ) -> Path:
        manifest = directory / filename
        entry = {
            "version": version,
            "url": url,
            "sha256": sha256,
        }
        if minimum_glibc is not None:
            entry["minimum_glibc"] = minimum_glibc
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "engines": {
                        platform_tag(): entry,
                    },
                }
            ),
            encoding="utf-8",
        )
        return manifest

    return write
