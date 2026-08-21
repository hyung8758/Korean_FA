"""Data contracts shared by KoreanFA engine management modules."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

EngineProgress = Callable[[str], None]


@dataclass(frozen=True)
class EngineSpec:
    """The immutable release asset compatible with this KoreanFA version."""

    platform: str
    version: str
    url: str | None
    sha256: str | None
    minimum_glibc: tuple[int, int] | None = None


@dataclass(frozen=True)
class EngineStatus:
    """The expected engine and, when present, its installed runtime."""

    platform: str
    version: str
    root: Path
    installed: bool
    kaldi_dir: Path | None
    mecab_command: Path | None
    mecab_dict: Path | None
    mecabrc: Path | None
    library_paths: tuple[Path, ...]
    library_path_variable: str | None

    @property
    def environment(self) -> dict[str, str]:
        """Environment variables that make the pipeline use this engine."""
        values: dict[str, str] = {}
        if self.mecab_command:
            values["KOREANFA_MECAB_COMMAND"] = str(self.mecab_command)
        if self.mecab_dict:
            values["KOREANFA_MECAB_DICT"] = str(self.mecab_dict)
        if self.mecabrc:
            values["MECABRC"] = str(self.mecabrc)
        if self.library_paths and self.library_path_variable:
            values[self.library_path_variable] = ":".join(str(path) for path in self.library_paths)
        return values
