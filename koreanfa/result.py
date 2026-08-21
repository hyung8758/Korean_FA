"""Structured values returned by the public alignment API."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

ExistingOutputPolicy = Literal["overwrite", "skip", "error"]
ExportFormat = Literal["json", "csv", "ctm"]
ProgressCallback = Callable[[str, int, int, str], None]
_ALIGNMENT_EXPORT_FIELDS = ("json", "csv", "words_ctm", "phones_ctm")


@dataclass(frozen=True)
class InputPair:
    """A WAV file and its matching UTF-8 text transcription."""

    audio: Path
    transcript: Path
    relative_stem: Path
    language: str = "auto"


@dataclass(frozen=True)
class AlignmentInterval:
    """One labelled interval in seconds."""

    start: float
    end: float
    label: str

    @property
    def duration(self) -> float:
        """Return the interval duration in seconds."""
        return self.end - self.start


@dataclass(frozen=True)
class AlignmentOutputs:
    """Files emitted for one successful alignment."""

    textgrid: Path
    json: Path | None = None
    csv: Path | None = None
    words_ctm: Path | None = None
    phones_ctm: Path | None = None

    def __getitem__(self, name: str) -> Path:
        """Allow concise access such as ``result.outputs[\"json\"]``."""
        value = getattr(self, name, None)
        if not isinstance(value, Path):
            raise KeyError(name)
        return value


@dataclass(frozen=True)
class AlignmentResult:
    """One successfully aligned WAV/TXT pair."""

    audio: Path
    transcript: Path
    textgrid: Path
    language: str
    work_dir: Path | None = None
    duration: float | None = None
    words: tuple[AlignmentInterval, ...] = ()
    phones: tuple[AlignmentInterval, ...] = ()
    attempts: int = 1
    outputs: AlignmentOutputs | None = None


@dataclass(frozen=True)
class AlignmentFailure:
    """One input pair that the runtime rejected without aborting its batch."""

    audio: Path
    transcript: Path
    language: str
    reason: str
    work_dir: Path | None = None
    attempts: int = 0


@dataclass(frozen=True)
class AlignmentSkip:
    """One valid existing TextGrid deliberately left unchanged."""

    audio: Path
    transcript: Path
    textgrid: Path
    language: str
    reason: str = "valid output already exists"
    duration: float | None = None
    words: tuple[AlignmentInterval, ...] = ()
    phones: tuple[AlignmentInterval, ...] = ()
    outputs: AlignmentOutputs | None = None


@dataclass(frozen=True)
class AlignmentSummary:
    """Counts and elapsed time for one alignment invocation."""

    total: int
    succeeded: int
    failed: int
    skipped: int
    elapsed_seconds: float


@dataclass(frozen=True)
class AlignmentReport:
    """In-memory representation of an optional JSON execution report."""

    path: Path
    schema_version: int
    summary: AlignmentSummary


@dataclass(frozen=True)
class BatchAlignmentResult:
    """Successful results and controlled per-file failures from one batch."""

    results: tuple[AlignmentResult, ...]
    output_dir: Path
    work_dir: Path | None = None
    failures: tuple[AlignmentFailure, ...] = ()
    skipped: tuple[AlignmentSkip, ...] = ()
    summary: AlignmentSummary | None = None
    report: AlignmentReport | None = None
