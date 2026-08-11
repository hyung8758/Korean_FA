"""Download, verify, and locate the optional native KoreanFA engine.

The Python package intentionally does not compile Kaldi during installation.
Instead, this module installs an immutable, versioned engine archive published
by KoreanFA.  The archive contains the exact Kaldi and MeCab binaries used by
the packaged alignment pipeline.
"""

import hashlib
import json
import os
import platform
import shutil
import tarfile
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import BinaryIO, Iterator, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .errors import EngineNotFoundError, EngineUnavailableError

_DOWNLOAD_ATTEMPTS = 3
_DOWNLOAD_CHUNK_BYTES = 1024 * 1024
_DOWNLOAD_TIMEOUT_SECONDS = 30.0
_MAX_ENGINE_ARCHIVE_BYTES = 256 * 1024 * 1024
_RETRYABLE_HTTP_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class _ResponseHeaders(Protocol):
    def get(self, name: str, default: str | None = None) -> str | None: ...


class _DownloadResponse(Protocol):
    headers: _ResponseHeaders

    def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True)
class EngineSpec:
    """The immutable release asset compatible with this KoreanFA version."""

    platform: str
    version: str
    url: str | None
    sha256: str | None


@dataclass(frozen=True)
class EngineStatus:
    """The expected engine and, when present, its locally installed runtime."""

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
        """Environment variables that make the legacy pipeline use this engine."""
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


def install(*, force: bool = False, engine_home: str | Path | None = None, manifest_path: str | Path | None = None) -> EngineStatus:
    """Install the compatible engine archive and return its verified status.

    ``manifest_path`` exists for KoreanFA release tooling and tests.  Normal
    callers should use the manifest packaged with the installed library.
    """
    spec = _engine_spec(manifest_path)
    if not spec.url or not spec.sha256:
        raise EngineUnavailableError(
            f"KoreanFA engine {spec.version} for {spec.platform} has not been published yet. "
            "Install a release of koreanfa that has an engine asset, or build the engine from source."
        )
    if len(spec.sha256) != 64 or any(char not in "0123456789abcdef" for char in spec.sha256.lower()):
        raise EngineUnavailableError("The packaged KoreanFA engine manifest has an invalid SHA-256 checksum.")

    home = _engine_home(engine_home)
    home.mkdir(parents=True, exist_ok=True)
    with _installation_lock(home):
        return _install_locked(spec, home, force=force)


def _install_locked(spec: EngineSpec, home: Path, *, force: bool) -> EngineStatus:
    """Install one engine while the cache-wide process lock is held."""
    target = home / spec.version / spec.platform
    target_existed = target.exists()
    current = _status_for(spec, home)
    if current.installed and not force:
        return current
    if target.exists() and not force:
        raise EngineUnavailableError(
            f"An incomplete KoreanFA engine exists at {target}. Run 'koreanfa engine install --force' to replace it."
        )
    staging = Path(tempfile.mkdtemp(prefix="koreanfa-engine-", dir=home))
    archive = staging / "engine.tar.gz"
    replacement = target.parent / f".{target.name}.new-{uuid.uuid4().hex}"
    backup: Path | None = None
    try:
        if spec.url is None or spec.sha256 is None:  # validated by ``install``; retain a typed boundary here.
            raise EngineUnavailableError("The KoreanFA engine specification is incomplete.")
        _download(spec.url, archive)
        _verify_checksum(archive, spec.sha256)
        extracted = staging / "extracted"
        extracted.mkdir()
        _safe_extract(archive, extracted)
        source = _find_engine_root(extracted)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(replacement))
        candidate = _status_from_root(spec, replacement)
        if not candidate.installed:
            raise EngineNotFoundError(f"Downloaded KoreanFA engine is invalid: {replacement}")
        if target.exists():
            backup = target.parent / f".{target.name}.backup-{uuid.uuid4().hex}"
            target.rename(backup)
        replacement.rename(target)
        installed = _status_for(spec, home)
        if not installed.installed:
            raise EngineNotFoundError(f"Downloaded KoreanFA engine is invalid after installation: {target}")
    except BaseException:
        shutil.rmtree(replacement, ignore_errors=True)
        if backup and backup.exists():
            try:
                if target.exists():
                    shutil.rmtree(target)
                backup.rename(target)
            except OSError as rollback_error:
                raise EngineUnavailableError(
                    "KoreanFA could not restore the previous engine after installation failed. "
                    f"The preserved backup remains at {backup}."
                ) from rollback_error
        elif backup is None and not target_existed and target.exists():
            shutil.rmtree(target, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    if backup and backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    return installed


@contextmanager
def _installation_lock(home: Path) -> Iterator[None]:
    """Serialize installers and removers, with automatic release after crashes."""
    try:
        import fcntl
    except ImportError as error:  # pragma: no cover - published engines currently target POSIX platforms only
        raise EngineUnavailableError("KoreanFA engine installation requires a POSIX file-lock implementation.") from error
    lock_path = home / ".install.lock"
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def ensure_installed(*, install_if_missing: bool = False, engine_home: str | Path | None = None) -> EngineStatus:
    """Return the local engine or explicitly install it when requested."""
    current = status(engine_home=engine_home)
    if current.installed:
        return current
    if install_if_missing:
        return install(engine_home=engine_home)
    raise EngineNotFoundError(
        "KoreanFA native engine is required but not installed. Run 'koreanfa engine install' or call "
        "'from koreanfa.engine import install; install()'."
    )


def status(*, engine_home: str | Path | None = None, manifest_path: str | Path | None = None) -> EngineStatus:
    """Report the expected engine version and whether it is installed."""
    return _status_for(_engine_spec(manifest_path), _engine_home(engine_home))


def installed_engine(*, engine_home: str | Path | None = None) -> EngineStatus | None:
    """Return a verified installed engine, without triggering a download."""
    current = status(engine_home=engine_home)
    return current if current.installed else None


def remove(*, engine_home: str | Path | None = None, manifest_path: str | Path | None = None) -> bool:
    """Remove only the compatible engine version managed by this package."""
    spec = _engine_spec(manifest_path)
    home = _engine_home(engine_home)
    if not home.exists():
        return False
    with _installation_lock(home):
        current = _status_for(spec, home)
        if not current.root.exists():
            return False
        shutil.rmtree(current.root)
        return True


def _engine_spec(manifest_path: str | Path | None = None) -> EngineSpec:
    manifest = _load_manifest(manifest_path)
    current_platform = _platform_tag()
    engines = manifest.get("engines")
    if not isinstance(engines, dict):
        raise EngineUnavailableError("The KoreanFA engine manifest does not contain an engines mapping.")
    entry = engines.get(current_platform)
    if not isinstance(entry, dict):
        available = ", ".join(sorted(str(platform_name) for platform_name in engines)) or "none"
        raise EngineUnavailableError(
            f"KoreanFA does not publish an engine for {current_platform}. "
            f"Published targets: {available}."
        )
    version = entry.get("version")
    url = entry.get("url")
    sha256 = entry.get("sha256")
    if not isinstance(version, str) or not version:
        raise EngineUnavailableError(f"The KoreanFA engine manifest has no valid version for {current_platform}.")
    if url is not None and not isinstance(url, str):
        raise EngineUnavailableError(f"The KoreanFA engine manifest has an invalid URL for {current_platform}.")
    if sha256 is not None and not isinstance(sha256, str):
        raise EngineUnavailableError(f"The KoreanFA engine manifest has an invalid SHA-256 for {current_platform}.")
    return EngineSpec(
        platform=current_platform,
        version=version,
        url=url,
        sha256=sha256,
    )


def _load_manifest(manifest_path: str | Path | None) -> dict[str, object]:
    if manifest_path:
        contents = Path(manifest_path).read_text(encoding="utf-8")
    else:
        configured = os.environ.get("KOREANFA_ENGINE_MANIFEST")
        if configured:
            contents = Path(configured).expanduser().read_text(encoding="utf-8")
        else:
            manifest = resources.files("koreanfa").joinpath("engine_manifest.json")
            contents = manifest.read_text(encoding="utf-8")
    parsed: object = json.loads(contents)
    if not isinstance(parsed, dict) or not all(isinstance(key, str) for key in parsed):
        raise EngineUnavailableError("The KoreanFA engine manifest must be a JSON object with string keys.")
    return {str(key): value for key, value in parsed.items()}


def _platform_tag() -> str:
    machine = platform.machine().lower()
    system = platform.system()
    if system == "Linux":
        aliases = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}
        return f"linux-{aliases.get(machine, machine)}"
    if system == "Darwin":
        aliases = {"x86_64": "x86_64", "amd64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}
        return f"darwin-{aliases.get(machine, machine)}"
    return f"{system.lower()}-{machine}"


def _engine_home(override: str | Path | None = None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    configured = os.environ.get("KOREANFA_ENGINE_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    if "XDG_CACHE_HOME" in os.environ:
        cache_home = Path(os.environ["XDG_CACHE_HOME"])
    elif platform.system() == "Darwin":
        cache_home = Path.home() / "Library" / "Caches"
    else:
        cache_home = Path.home() / ".cache"
    return (cache_home / "koreanfa" / "engines").resolve()


def _status_for(spec: EngineSpec, home: Path) -> EngineStatus:
    root = home / spec.version / spec.platform
    return _status_from_root(spec, root)


def _status_from_root(spec: EngineSpec, root: Path) -> EngineStatus:
    metadata_path = root / "engine.json"
    if not metadata_path.is_file():
        return _missing_status(spec, root)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        kaldi_dir = root / str(metadata["kaldi_dir"])
        mecab_command = root / str(metadata["mecab_command"])
        mecab_dict = root / str(metadata["mecab_dict"])
        mecabrc = root / str(metadata["mecabrc"])
        library_paths = tuple(root / str(path) for path in metadata["library_paths"])
        library_path_variable = str(metadata.get("library_path_variable", "LD_LIBRARY_PATH"))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
        return _missing_status(spec, root)
    if library_path_variable not in {"LD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"}:
        return _missing_status(spec, root)
    required = (
        (kaldi_dir / "src" / "bin" / "ali-to-phones").is_file(),
        mecab_command.is_file(),
        mecab_dict.is_dir(),
        mecabrc.is_file(),
        bool(library_paths),
        all(path.is_dir() for path in library_paths),
    )
    if not all(required):
        return _missing_status(spec, root)
    return EngineStatus(
        spec.platform,
        spec.version,
        root,
        True,
        kaldi_dir,
        mecab_command,
        mecab_dict,
        mecabrc,
        library_paths,
        library_path_variable,
    )


def _missing_status(spec: EngineSpec, root: Path) -> EngineStatus:
    return EngineStatus(spec.platform, spec.version, root, False, None, None, None, None, (), None)


def _download(
    url: str,
    destination: Path,
    *,
    attempts: int = _DOWNLOAD_ATTEMPTS,
    timeout: float = _DOWNLOAD_TIMEOUT_SECONDS,
    max_bytes: int = _MAX_ENGINE_ARCHIVE_BYTES,
) -> None:
    """Download an engine with bounded retries, time, and archive size."""
    if attempts < 1:
        raise ValueError("Engine download attempts must be at least 1.")
    if timeout <= 0:
        raise ValueError("Engine download timeout must be positive.")
    if max_bytes < 1:
        raise ValueError("Maximum engine archive size must be positive.")
    request = Request(url, headers={"User-Agent": "KoreanFA engine installer"})
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response, destination.open("wb") as stream:
                _copy_download(response, stream, max_bytes=max_bytes)
            return
        except HTTPError as error:
            should_retry = error.code in _RETRYABLE_HTTP_STATUS and attempt < attempts
            failure: OSError = error
        except (OSError, URLError, TimeoutError) as error:
            should_retry = attempt < attempts
            failure = error
        except EngineUnavailableError:
            destination.unlink(missing_ok=True)
            raise
        destination.unlink(missing_ok=True)
        if not should_retry:
            raise EngineUnavailableError(
                f"Could not download KoreanFA engine from {url} after {attempt} attempt(s): {failure}"
            ) from failure
        time.sleep(0.5 * 2 ** (attempt - 1))


def _copy_download(response: _DownloadResponse, destination: BinaryIO, *, max_bytes: int) -> None:
    """Copy one HTTP response without accepting an unexpectedly large asset."""
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError:
            declared_size = None
        if declared_size is not None and declared_size > max_bytes:
            raise EngineUnavailableError(
                f"KoreanFA engine archive is too large: {declared_size} bytes exceeds the {max_bytes}-byte limit."
            )
    downloaded = 0
    while chunk := response.read(_DOWNLOAD_CHUNK_BYTES):
        downloaded += len(chunk)
        if downloaded > max_bytes:
            raise EngineUnavailableError(
                f"KoreanFA engine archive exceeded the {max_bytes}-byte download limit."
            )
        destination.write(chunk)


def _verify_checksum(path: Path, expected: str) -> None:
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual.lower() != expected.lower():
        raise EngineUnavailableError(
            f"KoreanFA engine checksum mismatch for {path.name}. Expected {expected}, received {actual}."
        )


def _safe_extract(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            member_path = (destination / member.name).resolve()
            if not member_path.is_relative_to(destination.resolve()) or member.issym() or member.islnk():
                raise EngineUnavailableError("KoreanFA engine archive contains an unsafe path.")
        tar.extractall(destination, filter="data")


def _find_engine_root(extracted: Path) -> Path:
    candidates = [extracted, *sorted(path for path in extracted.iterdir() if path.is_dir())]
    for candidate in candidates:
        if (candidate / "kaldi" / "src" / "bin" / "ali-to-phones").is_file():
            return candidate
    raise EngineUnavailableError("KoreanFA engine archive does not contain kaldi/src/bin/ali-to-phones.")
