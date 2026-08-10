import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "koreanfa_alignment_labels", ROOT / "engine" / "alignment_labels.py"
)
assert SPEC and SPEC.loader
LABELS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LABELS)


def _textgrid(phone: str = "a", word: str = "테스트") -> str:
    return (
        'File type = "ooTextFile short"\n"TextGrid"\n\n0\n1\n<exists>\n2\n'
        f'"IntervalTier"\n"phone"\n0\n1\n1\n0\n1\n"{phone}"\n'
        f'"IntervalTier"\n"word"\n0\n1\n1\n0\n1\n"{word}"\n'
    )


def test_reads_ordered_short_textgrid_labels(tmp_path: Path) -> None:
    path = tmp_path / "result.TextGrid"
    path.write_text(_textgrid(), encoding="utf-8")

    assert LABELS.read_short_textgrid_labels(path) == {
        "phone": ["a"],
        "word": ["테스트"],
    }


def test_reports_the_first_semantic_label_difference(tmp_path: Path) -> None:
    path = tmp_path / "result.TextGrid"
    path.write_text(_textgrid(phone="b"), encoding="utf-8")

    with pytest.raises(RuntimeError, match="index 0.*expected 'a'.*received 'b'"):
        LABELS.validate_labels(path, {"phone": ["a"], "word": ["테스트"]})


def test_rejects_invalid_utf8_textgrid(tmp_path: Path) -> None:
    path = tmp_path / "result.TextGrid"
    path.write_bytes(b'File type = "ooTextFile short"\n\xff')

    with pytest.raises(UnicodeDecodeError):
        LABELS.read_short_textgrid_labels(path)
