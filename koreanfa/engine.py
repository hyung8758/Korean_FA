"""Install and locate the optional immutable KoreanFA native engine."""

import json
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ._engine_config import engine_home as _engine_home
from ._engine_config import engine_spec as _engine_spec
from ._engine_config import validate_platform_requirements as _validate_platform_requirements
from ._engine_download import download as _download
from ._engine_download import find_engine_root as _find_engine_root
from ._engine_download import safe_extract as _safe_extract
from ._engine_types import EngineProgress, EngineSpec, EngineStatus
from .errors import EngineNotFoundError, EngineUnavailableError


def install(
    *,
    force: bool = False,
    engine_home: str | Path | None = None,
    manifest_path: str | Path | None = None,
    progress: EngineProgress | None = None,
) -> EngineStatus:
    """Install the compatible engine archive and return verified status."""
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
    replacement = target.parent / f".{target.name}.new-{uuid.uuid4().hex}"
    backup: Path | None = None
    try:
        _install_candidate(spec, staging, replacement, target, progress)
        if target.exists():
            backup = target.parent / f".{target.name}.backup-{uuid.uuid4().hex}"
            target.rename(backup)
        replacement.rename(target)
        installed = _status_for(spec, home)
        if not installed.installed:
            raise EngineNotFoundError(f"Downloaded KoreanFA engine is invalid after installation: {target}")
    except BaseException:
        _restore_installation(target, replacement, backup, target_existed)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    if backup and backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    return installed


def _install_candidate(
    spec: EngineSpec,
    staging: Path,
    replacement: Path,
    target: Path,
    progress: EngineProgress | None,
) -> None:
    if spec.url is None or spec.sha256 is None:  # validated by ``install``; typed boundary only.
        raise EngineUnavailableError("The KoreanFA engine specification is incomplete.")
    archive = staging / "engine.tar.gz"
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


def _restore_installation(
    target: Path, replacement: Path, backup: Path | None, target_existed: bool
) -> None:
    shutil.rmtree(replacement, ignore_errors=True)
    if backup and backup.exists():
        try:
            if target.exists():
                shutil.rmtree(target)
            backup.rename(target)
        except OSError as error:
            raise EngineUnavailableError(
                "KoreanFA could not restore the previous engine after installation failed. "
                f"The preserved backup remains at {backup}."
            ) from error
    elif not target_existed and target.exists():
        shutil.rmtree(target, ignore_errors=True)


@contextmanager
def _installation_lock(home: Path) -> Iterator[None]:
    """Serialize installers and removers, releasing the lock after crashes."""
    try:
        import fcntl
    except ImportError as error:  # pragma: no cover - published engines target POSIX platforms
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
    """Return a verified installed engine without triggering a download."""
    current = status(engine_home=engine_home)
    return current if current.installed else None


def remove(*, engine_home: str | Path | None = None, manifest_path: str | Path | None = None) -> bool:
    """Remove only the compatible engine version managed by this package."""
    spec, home = _engine_spec(manifest_path), _engine_home(engine_home)
    if not home.exists():
        return False
    with _installation_lock(home):
        current = _status_for(spec, home)
        if not current.root.exists():
            return False
        shutil.rmtree(current.root)
        return True


def _status_for(spec: EngineSpec, home: Path) -> EngineStatus:
    return _status_from_root(spec, home / spec.version / spec.platform)


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
        variable = str(metadata.get("library_path_variable", "LD_LIBRARY_PATH"))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
        return _missing_status(spec, root)
    if variable not in {"LD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"}:
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
        variable,
    )


def _missing_status(spec: EngineSpec, root: Path) -> EngineStatus:
    return EngineStatus(spec.platform, spec.version, root, False, None, None, None, None, (), None)
