"""Exceptions with actionable messages for KoreanFA users."""

from __future__ import annotations

from pathlib import Path


class KoreanFAError(RuntimeError):
    """Base exception raised by KoreanFA."""


class PairingError(KoreanFAError):
    """A directory does not contain an unambiguous WAV/TXT corpus."""


class EngineNotFoundError(KoreanFAError):
    """No compatible Kaldi runtime was provided."""


class EngineUnavailableError(EngineNotFoundError):
    """An engine is supported but has not been published for installation."""


class AlignmentError(KoreanFAError):
    """The Kaldi pipeline did not create all requested TextGrid files."""

    def __init__(self, message: str, *, work_dir: Path, stdout: str = "", stderr: str = "") -> None:
        super().__init__(message)
        self.work_dir = work_dir
        self.stdout = stdout
        self.stderr = stderr
