import importlib.util
import tarfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "koreanfa_macos_verifier", ROOT / "engine" / "verify_macos.py"
)
assert SPEC and SPEC.loader
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


def _archive_with_file(tmp_path: Path, size: int) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    payload = source / "payload.bin"
    payload.write_bytes(b"x" * size)
    archive = tmp_path / "engine.tar.gz"
    with tarfile.open(archive, "w:gz") as contents:
        contents.add(source, arcname="engine")
    return archive


def test_safe_extract_reports_the_uncompressed_size(tmp_path: Path) -> None:
    archive = _archive_with_file(tmp_path, 128)
    destination = tmp_path / "destination"
    destination.mkdir()

    extracted_size = VERIFIER._safe_extract(archive, destination, 1024)

    assert extracted_size == 128
    assert (destination / "engine" / "payload.bin").read_bytes() == b"x" * 128


def test_safe_extract_rejects_an_oversized_engine_before_extraction(tmp_path: Path) -> None:
    archive = _archive_with_file(tmp_path, 128)
    destination = tmp_path / "destination"
    destination.mkdir()

    with pytest.raises(RuntimeError, match="Extracted engine exceeds"):
        VERIFIER._safe_extract(archive, destination, 64)

    assert not (destination / "engine" / "payload.bin").exists()


@pytest.mark.parametrize("value", ["0", "-1", "not-a-number"])
def test_size_limit_requires_a_positive_byte_count(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("KOREANFA_TEST_SIZE_LIMIT", value)

    with pytest.raises(RuntimeError, match="positive byte count"):
        VERIFIER._size_limit("KOREANFA_TEST_SIZE_LIMIT", 1)
