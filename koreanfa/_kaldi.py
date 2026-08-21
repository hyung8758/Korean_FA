"""Resolve the Kaldi runtime used by forced alignment."""

import os
from pathlib import Path

from .engine import installed_engine
from .errors import EngineNotFoundError


def resolve_kaldi_dir(kaldi_dir: str | Path | None) -> tuple[Path, dict[str, str]]:
    """Resolve an explicit runtime or the verified managed engine."""
    candidate = kaldi_dir or os.environ.get("KOREANFA_KALDI_DIR")
    if candidate:
        return validate_kaldi_dir(Path(candidate).expanduser().resolve()), {}
    engine = installed_engine()
    if engine is None:
        raise EngineNotFoundError(
            "KoreanFA native engine is required but not installed. Run 'koreanfa engine install' or call "
            "'from koreanfa.engine import install; install()'."
        )
    if engine.kaldi_dir is None:
        raise EngineNotFoundError("The installed KoreanFA engine does not declare a usable Kaldi runtime.")
    return engine.kaldi_dir, engine.environment


def validate_kaldi_dir(root: Path) -> Path:
    """Require the minimum Kaldi executable used by KoreanFA."""
    if not (root / "src" / "bin" / "ali-to-phones").is_file():
        raise EngineNotFoundError(f"No usable Kaldi runtime at {root}")
    return root
