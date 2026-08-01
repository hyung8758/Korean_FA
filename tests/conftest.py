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
    ) -> Path:
        manifest = directory / filename
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "engines": {
                        _platform_tag(): {
                            "version": version,
                            "url": url,
                            "sha256": sha256,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        return manifest

    return write
