"""Locate packaged Kaldi pipeline resources after wheel installation."""

import os
from pathlib import Path

from .errors import KoreanFAError


def runtime_root() -> Path:
    """Return the read-only runtime root shipped with KoreanFA.

    Runtime scripts, profiles, and acoustic models are package data beneath
    ``koreanfa/runtime``.  The override is only for development diagnostics.
    """
    override = os.environ.get("KOREANFA_RUNTIME_ROOT")
    candidates = [Path(override)] if override else []
    candidates.append(Path(__file__).resolve().parent / "runtime")

    for candidate in candidates:
        if (candidate / "pipeline" / "forced_align.sh").is_file() and (candidate / "model" / "kor_model" / "final.mdl").is_file():
            return candidate
    raise KoreanFAError(
        "KoreanFA package runtime resources are missing. Reinstall the koreanfa wheel or set KOREANFA_RUNTIME_ROOT for development."
    )


# Kept temporarily for code using the 0.1.0 foundation API.
legacy_root = runtime_root
