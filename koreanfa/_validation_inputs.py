"""Identify validation input files that must not be overwritten by reports."""

from pathlib import Path


def validation_input_paths(
    source: Path, transcript: str | Path | None, *, recursive: bool
) -> tuple[Path, ...]:
    """Collect report-protected inputs even when corpus discovery is ambiguous."""
    if not source.is_dir():
        values = [source]
        if transcript is not None:
            values.append(Path(transcript).expanduser().resolve())
        return tuple(values)
    candidates = source.rglob("*") if recursive else source.iterdir()
    return tuple(
        path
        for path in candidates
        if path.is_file() and path.suffix.lower() in {".wav", ".txt"}
    )
