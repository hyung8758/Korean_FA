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
import re
import shutil
import tarfile
import tempfile
import time
import uuid
from collections.abc import Callable
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
_TROUBLESHOOTING_URL = "https://github.com/hyung8758/Korean_FA/blob/master/docs/troubleshooting.md"

EngineProgress = Callable[[str], None]


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
    minimum_glibc: tuple[int, int] | None = None


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


def install(
    *,
    force: bool = False,
    engine_home: str | Path | None = None,
    manifest_path: str | Path | None = None,
    progress: EngineProgress | None = None,
) -> EngineStatus:
    """Install the compatible engine archive and return its verified status.

    ``manifest_path`` exists for KoreanFA release tooling and tests. Normal
    callers should use the manifest packaged with the installed library.
    ``progress`` receives human-readable download and retry events; it is
    silent by default for library callers.
    """
    spec = _engine_spec(manifest_path)
    if not spec.url or not spec.sha256:
        raise EngineUnavailableError(
            f"KoreanFA engine {spec.version} for {spec.platform} has not been published yet. "
            "Install a release of koreanfa that has an engine asset, or build the engine from source."
        )
    if len(spec.sha256) != 64 or any(char not in "0123456789abcdef" for char in spec.sha256.lower()):
        raise EngineUnavailableError("The packaged KoreanFA engine manifest has an invalid SHA-256 checksum.")
    _validate_platform_requirements(spec)

    home = _engine_home(engine_home)
    home.mkdir(parents=True, exist_ok=True)
    with _installation_lock(home):
        return _install_locked(spec, home, force=force, progress=progress)


def _install_locked(
    spec: EngineSpec,
    home: Path,
    *,
    force: bool,
    progress: EngineProgress | None,
) -> EngineStatus:
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
        _download(spec.url, archive, expected_sha256=spec.sha256, progress=progress)
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
    minimum_glibc_value = entry.get("minimum_glibc")
    if not isinstance(version, str) or not version:
        raise EngineUnavailableError(f"The KoreanFA engine manifest has no valid version for {current_platform}.")
    if url is not None and not isinstance(url, str):
        raise EngineUnavailableError(f"The KoreanFA engine manifest has an invalid URL for {current_platform}.")
    if sha256 is not None and not isinstance(sha256, str):
        raise EngineUnavailableError(f"The KoreanFA engine manifest has an invalid SHA-256 for {current_platform}.")
    minimum_glibc: tuple[int, int] | None = None
    if minimum_glibc_value is not None:
        if not isinstance(minimum_glibc_value, str):
            raise EngineUnavailableError(f"The KoreanFA engine manifest has an invalid minimum_glibc for {current_platform}.")
        minimum_glibc = _parse_version_pair(minimum_glibc_value)
        if minimum_glibc is None:
            raise EngineUnavailableError(f"The KoreanFA engine manifest has an invalid minimum_glibc for {current_platform}.")
    return EngineSpec(
        platform=current_platform,
        version=version,
        url=url,
        sha256=sha256,
        minimum_glibc=minimum_glibc,
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


def _parse_version_pair(value: str) -> tuple[int, int] | None:
    """Parse a leading major.minor version without accepting partial values."""
    match = re.fullmatch(r"(\d+)\.(\d+)", value.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _linux_libc() -> tuple[str, tuple[int, int] | None]:
    """Return the detected Linux libc family and its major/minor version."""
    try:
        configured = os.confstr("CS_GNU_LIBC_VERSION")
    except (AttributeError, OSError, ValueError):
        configured = None
    if configured:
        match = re.fullmatch(r"glibc\s+(\d+)\.(\d+)(?:\.\d+)?", configured.strip(), flags=re.IGNORECASE)
        if match:
            return "glibc", (int(match.group(1)), int(match.group(2)))

    name, version_text = platform.libc_ver()
    normalized_name = name.strip().lower()
    match = re.match(r"(\d+)\.(\d+)", version_text.strip())
    version = (int(match.group(1)), int(match.group(2))) if match else None
    return normalized_name or "unknown", version


def _validate_platform_requirements(spec: EngineSpec) -> None:
    """Reject an incompatible Linux libc before downloading the engine."""
    if not spec.platform.startswith("linux-") or spec.minimum_glibc is None:
        return
    libc_name, detected = _linux_libc()
    required_text = ".".join(map(str, spec.minimum_glibc))
    if libc_name != "glibc":
        detected_text = libc_name
        if detected is not None:
            detected_text += " " + ".".join(map(str, detected))
        raise EngineUnavailableError(
            f"The KoreanFA Linux engine requires x86_64 Linux with glibc {required_text} or later; "
            f"detected {detected_text}. Alpine Linux and other musl-based distributions are not supported."
        )
    if detected is None:
        raise EngineUnavailableError(
            f"The KoreanFA Linux engine requires glibc {required_text} or later, but the installed glibc version "
            "could not be detected."
        )
    if detected < spec.minimum_glibc:
        detected_text = ".".join(map(str, detected))
        raise EngineUnavailableError(
            f"The KoreanFA Linux engine requires x86_64 Linux with glibc {required_text} or later; "
            f"detected glibc {detected_text}. This Linux environment is not supported."
        )


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
    expected_sha256: str | None = None,
    attempts: int = _DOWNLOAD_ATTEMPTS,
    timeout: float = _DOWNLOAD_TIMEOUT_SECONDS,
    max_bytes: int = _MAX_ENGINE_ARCHIVE_BYTES,
    progress: EngineProgress | None = None,
) -> None:
    """Download and optionally verify an engine with one bounded retry loop."""
    if attempts < 1:
        raise ValueError("Engine download attempts must be at least 1.")
    if timeout <= 0:
        raise ValueError("Engine download timeout must be positive.")
    if max_bytes < 1:
        raise ValueError("Maximum engine archive size must be positive.")
    request = Request(url, headers={"User-Agent": "KoreanFA engine installer"})
    for attempt in range(1, attempts + 1):
        _report(progress, f"downloading engine (attempt {attempt}/{attempts})...")
        try:
            with urlopen(request, timeout=timeout) as response, destination.open("wb") as stream:
                _copy_download(response, stream, max_bytes=max_bytes)
            if expected_sha256 is not None:
                actual_sha256 = _file_sha256(destination)
                if actual_sha256.lower() != expected_sha256.lower():
                    size = destination.stat().st_size
                    if attempt == attempts:
                        raise EngineUnavailableError(
                            f"KoreanFA engine checksum mismatch after {attempts} download attempts. "
                            f"Expected {expected_sha256}, last received {actual_sha256} ({size} bytes). "
                            "The download may have been corrupted or modified by a proxy, VPN, network cache, "
                            f"or security gateway. Please try again later or see {_TROUBLESHOOTING_URL}."
                        )
                    destination.unlink(missing_ok=True)
                    _report(
                        progress,
                        f"checksum verification failed on attempt {attempt}/{attempts}; retrying...",
                    )
                    time.sleep(0.5 * 2 ** (attempt - 1))
                    continue
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
                f"Could not download KoreanFA engine from {url} after {attempt} attempt(s): {failure}. "
                f"Please try again later or see {_TROUBLESHOOTING_URL}."
            ) from failure
        _report(progress, f"download attempt {attempt}/{attempts} failed; retrying...")
        time.sleep(0.5 * 2 ** (attempt - 1))


def _copy_download(response: _DownloadResponse, destination: BinaryIO, *, max_bytes: int) -> None:
    """Copy one HTTP response without accepting an unexpectedly large asset."""
    content_length = response.headers.get("Content-Length")
    declared_size: int | None = None
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError:
            pass
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
    if declared_size is not None and downloaded != declared_size:
        raise OSError(f"incomplete download: expected {declared_size} bytes, received {downloaded}")


def _file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _report(progress: EngineProgress | None, message: str) -> None:
    if progress is not None:
        progress(message)


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
