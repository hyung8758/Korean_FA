import json
from collections.abc import Callable
from pathlib import Path

import pytest

from koreanfa.engine import _platform_tag


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
                        _platform_tag(): entry,
                    },
                }
            ),
            encoding="utf-8",
        )
        return manifest

    return write
