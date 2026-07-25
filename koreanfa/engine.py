"""Download, verify, and locate the optional native KoreanFA engine.

The Python package intentionally does not compile Kaldi during installation.
Instead, this module installs an immutable, versioned engine archive published
by KoreanFA.  The archive contains the exact Kaldi and MeCab binaries used by
the packaged alignment pipeline.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import tarfile
import tempfile
import uuid
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from urllib.request import urlopen

from .errors import EngineNotFoundError, EngineUnavailableError


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
        if self.library_paths:
            values["LD_LIBRARY_PATH"] = ":".join(str(path) for path in self.library_paths)
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
    target = home / spec.version / spec.platform
    current = _status_for(spec, home)
    if current.installed and not force:
        return current
    if target.exists() and not force:
        raise EngineUnavailableError(
            f"An incomplete KoreanFA engine exists at {target}. Run 'koreanfa engine install --force' to replace it."
        )
    home.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="koreanfa-engine-", dir=home))
    archive = staging / "engine.tar.gz"
    replacement = target.parent / f".{target.name}.new-{uuid.uuid4().hex}"
    backup: Path | None = None
    try:
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
        try:
            replacement.rename(target)
        except Exception:
            if backup and backup.exists():
                backup.rename(target)
            raise
    except Exception:
        shutil.rmtree(replacement, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if backup and backup.exists():
            shutil.rmtree(backup, ignore_errors=True)

    installed = _status_for(spec, home)
    if not installed.installed:
        raise EngineNotFoundError(f"Downloaded KoreanFA engine is invalid: {target}")
    return installed


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
    current = status(engine_home=engine_home, manifest_path=manifest_path)
    if not current.root.exists():
        return False
    shutil.rmtree(current.root)
    return True


def _engine_spec(manifest_path: str | Path | None = None) -> EngineSpec:
    manifest = _load_manifest(manifest_path)
    current_platform = _platform_tag()
    entry = manifest.get("engines", {}).get(current_platform)
    if not entry:
        raise EngineUnavailableError(
            f"KoreanFA does not publish an engine for {current_platform}. "
            "The first supported target is Linux x86_64."
        )
    return EngineSpec(
        platform=current_platform,
        version=str(entry["version"]),
        url=entry.get("url"),
        sha256=entry.get("sha256"),
    )


def _load_manifest(manifest_path: str | Path | None) -> dict[str, object]:
    if manifest_path:
        return json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    manifest = resources.files("koreanfa").joinpath("engine_manifest.json")
    return json.loads(manifest.read_text(encoding="utf-8"))


def _platform_tag() -> str:
    if platform.system() != "Linux":
        return f"{platform.system().lower()}-{platform.machine().lower()}"
    machine = platform.machine().lower()
    aliases = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}
    return f"linux-{aliases.get(machine, machine)}"


def _engine_home(override: str | Path | None = None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    configured = os.environ.get("KOREANFA_ENGINE_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
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
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
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
    )


def _missing_status(spec: EngineSpec, root: Path) -> EngineStatus:
    return EngineStatus(spec.platform, spec.version, root, False, None, None, None, None, ())


def _download(url: str, destination: Path) -> None:
    try:
        with urlopen(url) as response, destination.open("wb") as stream:
            shutil.copyfileobj(response, stream)
    except OSError as error:
        raise EngineUnavailableError(f"Could not download KoreanFA engine from {url}: {error}") from error


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
