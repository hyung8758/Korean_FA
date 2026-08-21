"""Bounded download and safe extraction of native engine archives."""

import hashlib
import tarfile
import time
from pathlib import Path
from typing import BinaryIO, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ._engine_types import EngineProgress
from .errors import EngineUnavailableError

DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 30.0
MAX_ENGINE_ARCHIVE_BYTES = 256 * 1024 * 1024
RETRYABLE_HTTP_STATUS = frozenset({408, 429, 500, 502, 503, 504})
TROUBLESHOOTING_URL = "https://github.com/hyung8758/Korean_FA/blob/master/docs/troubleshooting.md"


class ResponseHeaders(Protocol):
    def get(self, name: str, default: str | None = None) -> str | None: ...


class DownloadResponse(Protocol):
    headers: ResponseHeaders

    def read(self, size: int = -1) -> bytes: ...


def download(
    url: str,
    destination: Path,
    *,
    expected_sha256: str | None = None,
    attempts: int = DOWNLOAD_ATTEMPTS,
    timeout: float = DOWNLOAD_TIMEOUT_SECONDS,
    max_bytes: int = MAX_ENGINE_ARCHIVE_BYTES,
    progress: EngineProgress | None = None,
) -> None:
    """Download and optionally verify an engine with bounded retries."""
    if attempts < 1:
        raise ValueError("Engine download attempts must be at least 1.")
    if timeout <= 0:
        raise ValueError("Engine download timeout must be positive.")
    if max_bytes < 1:
        raise ValueError("Maximum engine archive size must be positive.")
    request = Request(url, headers={"User-Agent": "KoreanFA engine installer"})
    for attempt in range(1, attempts + 1):
        report(progress, f"downloading engine (attempt {attempt}/{attempts})...")
        try:
            with urlopen(request, timeout=timeout) as response, destination.open("wb") as stream:
                copy_download(response, stream, max_bytes=max_bytes)
            if expected_sha256 is not None and file_sha256(destination).lower() != expected_sha256.lower():
                _handle_checksum_mismatch(destination, expected_sha256, attempt, attempts, progress)
                continue
            return
        except HTTPError as error:
            should_retry = error.code in RETRYABLE_HTTP_STATUS and attempt < attempts
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
                f"Please try again later or see {TROUBLESHOOTING_URL}."
            ) from failure
        report(progress, f"download attempt {attempt}/{attempts} failed; retrying...")
        time.sleep(0.5 * 2 ** (attempt - 1))


def _handle_checksum_mismatch(
    destination: Path,
    expected: str,
    attempt: int,
    attempts: int,
    progress: EngineProgress | None,
) -> None:
    actual, size = file_sha256(destination), destination.stat().st_size
    if attempt == attempts:
        raise EngineUnavailableError(
            f"KoreanFA engine checksum mismatch after {attempts} download attempts. "
            f"Expected {expected}, last received {actual} ({size} bytes). "
            "The download may have been corrupted or modified by a proxy, VPN, network cache, "
            f"or security gateway. Please try again later or see {TROUBLESHOOTING_URL}."
        )
    destination.unlink(missing_ok=True)
    report(progress, f"checksum verification failed on attempt {attempt}/{attempts}; retrying...")
    time.sleep(0.5 * 2 ** (attempt - 1))


def copy_download(response: DownloadResponse, destination: BinaryIO, *, max_bytes: int) -> None:
    """Copy one response without accepting an unexpectedly large asset."""
    declared_size = _declared_size(response.headers.get("Content-Length"))
    if declared_size is not None and declared_size > max_bytes:
        raise EngineUnavailableError(
            f"KoreanFA engine archive is too large: {declared_size} bytes exceeds the {max_bytes}-byte limit."
        )
    downloaded = 0
    while chunk := response.read(DOWNLOAD_CHUNK_BYTES):
        downloaded += len(chunk)
        if downloaded > max_bytes:
            raise EngineUnavailableError(
                f"KoreanFA engine archive exceeded the {max_bytes}-byte download limit."
            )
        destination.write(chunk)
    if declared_size is not None and downloaded != declared_size:
        raise OSError(f"incomplete download: expected {declared_size} bytes, received {downloaded}")


def _declared_size(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def report(progress: EngineProgress | None, message: str) -> None:
    if progress is not None:
        progress(message)


def safe_extract(archive: Path, destination: Path) -> None:
    """Extract regular archive data without links or path traversal."""
    with tarfile.open(archive, "r:gz") as tar:
        root = destination.resolve()
        for member in tar.getmembers():
            member_path = (destination / member.name).resolve()
            if not member_path.is_relative_to(root) or member.issym() or member.islnk():
                raise EngineUnavailableError("KoreanFA engine archive contains an unsafe path.")
        tar.extractall(destination, filter="data")


def find_engine_root(extracted: Path) -> Path:
    """Locate the single engine root accepted by the package runtime."""
    candidates = [extracted, *sorted(path for path in extracted.iterdir() if path.is_dir())]
    for candidate in candidates:
        if (candidate / "kaldi" / "src" / "bin" / "ali-to-phones").is_file():
            return candidate
    raise EngineUnavailableError("KoreanFA engine archive does not contain kaldi/src/bin/ali-to-phones.")
