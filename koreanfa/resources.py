"""Locate packaged Kaldi pipeline resources after wheel installation."""

from __future__ import annotations

import os
import sysconfig
from pathlib import Path

from .errors import KoreanFAError


def runtime_root() -> Path:
    """Return the read-only runtime root shipped with KoreanFA.

    ``KOREANFA_RUNTIME_ROOT`` is intentionally available for package
    maintainers and editable-development environments.  Normal users never
    need to set it.
    """
    override = os.environ.get("KOREANFA_RUNTIME_ROOT")
    candidates = []
    if override:
        candidates.append(Path(override))
    candidates.append(Path(sysconfig.get_path("data")) / "share" / "koreanfa" / "runtime")
    candidates.append(Path(__file__).resolve().parents[1])

    for candidate in candidates:
        if (candidate / "forced_align.sh").is_file() and (candidate / "model" / "kor_model" / "final.mdl").is_file():
            return candidate
    raise KoreanFAError(
        "KoreanFA runtime resources are missing. Reinstall the koreanfa wheel or set KOREANFA_RUNTIME_ROOT for development."
    )


# Kept temporarily for code using the 0.1.0 foundation API.
legacy_root = runtime_root
