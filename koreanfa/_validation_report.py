"""Structured preflight validation results and JSON serialization."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from ._io import atomic_write_text, report_output_path
from .pairing import _portable_path_key

ValidationSeverity = Literal["error", "warning"]

__all__ = [
    "ValidatedPair",
    "ValidationIssue",
    "ValidationReport",
    "ValidationSeverity",
]


@dataclass(frozen=True)
class ValidationIssue:
    """One actionable problem found during corpus preflight."""

    code: str
    severity: ValidationSeverity
    path: Path | None
    message: str
    suggestion: str


@dataclass(frozen=True)
class ValidatedPair:
    """One pair that passed transcript, language, and audio checks."""

    audio: Path
    transcript: Path
    language: str


@dataclass(frozen=True)
class ValidationReport:
    """Complete preflight result; issues never stop at the first file."""

    root: Path
    pairs: tuple[ValidatedPair, ...]
    issues: tuple[ValidationIssue, ...]
    engine_installed: bool | None
    engine_platform: str | None
    engine_version: str | None

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)

    @property
    def error_count(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    def write_json(self, path: str | Path) -> Path:
        """Atomically write a privacy-conscious JSON validation report."""
        destination = report_output_path(path)
        inputs = {value.resolve() for pair in self.pairs for value in (pair.audio, pair.transcript)}
        inputs.update(issue.path.resolve() for issue in self.issues if issue.path is not None)
        if _portable_path_key(destination) in {_portable_path_key(value) for value in inputs}:
            raise ValueError("report_path must not overwrite an input file")

        def relative(value: Path | None) -> str | None:
            if value is None:
                return None
            try:
                return value.relative_to(self.root).as_posix()
            except ValueError:
                return value.name

        def safe_text(value: str, issue_path: Path | None) -> str:
            replacements = {self.root.resolve(): "."}
            if issue_path is not None:
                replacements[issue_path.resolve()] = relative(issue_path) or issue_path.name
            for source, replacement in sorted(
                replacements.items(), key=lambda item: len(str(item[0])), reverse=True
            ):
                value = value.replace(str(source), replacement)
            return value

        payload = {
            "schema_version": 1,
            "valid": self.valid,
            "summary": {
                "pairs": len(self.pairs),
                "errors": self.error_count,
                "warnings": self.warning_count,
            },
            "engine": {
                "installed": self.engine_installed,
                "platform": self.engine_platform,
                "version": self.engine_version,
            },
            "pairs": [
                {"audio": relative(pair.audio), "transcript": relative(pair.transcript), "language": pair.language}
                for pair in self.pairs
            ],
            "issues": [
                {
                    **asdict(issue),
                    "path": relative(issue.path),
                    "message": safe_text(issue.message, issue.path),
                    "suggestion": safe_text(issue.suggestion, issue.path),
                }
                for issue in self.issues
            ],
        }
        atomic_write_text(destination, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return destination
