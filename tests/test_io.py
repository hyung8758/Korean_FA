import stat
from pathlib import Path

import pytest

from koreanfa._io import atomic_write_text, report_output_path


def test_atomic_write_creates_readable_utf8_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    destination = tmp_path / "결과.json"

    atomic_write_text(destination, '{"문장": "테스트"}\n')

    assert destination.read_text(encoding="utf-8") == '{"문장": "테스트"}\n'
    assert list(tmp_path.iterdir()) == [destination]


def test_atomic_write_preserves_existing_file_permissions(tmp_path: Path) -> None:
    destination = tmp_path / "report.json"
    destination.write_text("old", encoding="utf-8")
    destination.chmod(0o640)

    atomic_write_text(destination, "new\n")

    assert destination.read_text(encoding="utf-8") == "new\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o640


def test_report_output_rejects_leaf_symlink_without_changing_target(tmp_path: Path) -> None:
    target = tmp_path / "outside.txt"
    target.write_text("keep", encoding="utf-8")
    report = tmp_path / "report.json"
    report.symlink_to(target)

    with pytest.raises(ValueError, match="must not be a symbolic link"):
        report_output_path(report)

    assert report.is_symlink()
    assert target.read_text(encoding="utf-8") == "keep"


def test_report_output_rejects_existing_directory(tmp_path: Path) -> None:
    destination = tmp_path / "report.json"
    destination.mkdir()

    with pytest.raises(ValueError, match="exists but is not a file"):
        report_output_path(destination)
