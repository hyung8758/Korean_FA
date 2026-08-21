import tarfile
from pathlib import Path

import pytest

from engine import macos_verification


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

    extracted_size = macos_verification.safe_extract(archive, destination, 1024)

    assert extracted_size == 128
    assert (destination / "engine" / "payload.bin").read_bytes() == b"x" * 128


def test_safe_extract_rejects_an_oversized_engine_before_extraction(tmp_path: Path) -> None:
    archive = _archive_with_file(tmp_path, 128)
    destination = tmp_path / "destination"
    destination.mkdir()

    with pytest.raises(RuntimeError, match="Extracted engine exceeds"):
        macos_verification.safe_extract(archive, destination, 64)

    assert not (destination / "engine" / "payload.bin").exists()


@pytest.mark.parametrize("value", ["0", "-1", "not-a-number"])
def test_size_limit_requires_a_positive_byte_count(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("KOREANFA_TEST_SIZE_LIMIT", value)

    with pytest.raises(RuntimeError, match="positive byte count"):
        macos_verification.size_limit("KOREANFA_TEST_SIZE_LIMIT", 1)


@pytest.mark.parametrize("charset", ["utf8", "utf-8", "UTF-8"])
def test_accepts_equivalent_utf8_dictionary_labels(charset: str) -> None:
    assert macos_verification.declares_utf8_dictionary(
        f"filename:\t/sys.dic\ncharset:\t{charset}\n"
    )


@pytest.mark.parametrize("charset", ["euc-jp", "shift-jis", "utf16", "utf-8-extra"])
def test_rejects_non_utf8_dictionary_labels(charset: str) -> None:
    assert not macos_verification.declares_utf8_dictionary(f"charset:\t{charset}\n")
