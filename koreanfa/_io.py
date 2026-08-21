"""Small filesystem primitives shared by public-output writers."""

import os
import secrets
import stat
from pathlib import Path


def report_output_path(path: str | Path) -> Path:
    """Resolve a report parent without following or overwriting a leaf symlink."""
    requested = Path(path).expanduser()
    destination = requested.parent.resolve() / requested.name
    if destination.is_symlink():
        raise ValueError(f"Report path must not be a symbolic link: {destination}")
    if destination.exists() and not destination.is_file():
        raise ValueError(f"Report path exists but is not a file: {destination}")
    return destination


def atomic_write_text(path: Path, content: str) -> None:
    """Atomically write UTF-8 text while respecting normal file permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    temporary: Path | None = None
    for _ in range(100):
        candidate = path.parent / f".{path.name}.{secrets.token_hex(8)}"
        try:
            descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        except FileExistsError:  # pragma: no cover - cryptographically improbable
            continue
        temporary = candidate
        break
    if descriptor is None or temporary is None:  # pragma: no cover - requires repeated random collisions
        raise OSError(f"Could not allocate a temporary output file beside {path}")
    try:
        if path.is_file():
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            descriptor = None
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        raise
