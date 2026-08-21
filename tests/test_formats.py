import csv
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from koreanfa.errors import AlignmentError
from koreanfa.formats import is_valid_textgrid, parse_textgrid, require_tiers, write_exports


def test_parses_structured_intervals_and_escaped_labels(
    tmp_path: Path, write_textgrid: Callable[..., Path]
) -> None:
    textgrid = write_textgrid(tmp_path / "sample.TextGrid", label='인용 "문장"')

    parsed = parse_textgrid(textgrid)

    assert parsed.duration == 1.0
    assert parsed.words[0].label == '인용 "문장"'
    assert parsed.words[0].duration == 1.0
    assert parsed.phones[0].label == "t"


def test_rejects_non_monotonic_textgrid(tmp_path: Path, write_textgrid: Callable[..., Path]) -> None:
    textgrid = write_textgrid(tmp_path / "bad.TextGrid")
    textgrid.write_text(textgrid.read_text(encoding="utf-8").replace("0.000000\n1.000000", "0.800000\n0.200000", 1), encoding="utf-8")

    with pytest.raises(AlignmentError, match="Invalid KoreanFA TextGrid"):
        parse_textgrid(textgrid)
    assert not is_valid_textgrid(textgrid, word_tier=True, phone_tier=True)


def test_rejects_unescaped_quotes_in_textgrid_labels(
    tmp_path: Path, write_textgrid: Callable[..., Path]
) -> None:
    textgrid = write_textgrid(tmp_path / "bad-quote.TextGrid")
    textgrid.write_text(
        textgrid.read_text(encoding="utf-8").replace('"테스트"', '"잘못된 "인용""'),
        encoding="utf-8",
    )

    with pytest.raises(AlignmentError, match="Unescaped quote"):
        parse_textgrid(textgrid)


def test_rejects_submicrosecond_interval_discontinuity(
    tmp_path: Path, write_textgrid: Callable[..., Path]
) -> None:
    textgrid = write_textgrid(tmp_path / "discontinuous.TextGrid")
    textgrid.write_text(
        textgrid.read_text(encoding="utf-8").replace("0.000000\n1.000000", "0.0000005\n1.000000", 1),
        encoding="utf-8",
    )

    with pytest.raises(AlignmentError, match="Non-continuous"):
        parse_textgrid(textgrid)


def test_required_tier_validation_rejects_omitted_runtime_tier(
    tmp_path: Path, write_textgrid: Callable[..., Path]
) -> None:
    parsed = parse_textgrid(write_textgrid(tmp_path / "phone-only.TextGrid", word=False))

    with pytest.raises(AlignmentError, match="missing requested tier.*word"):
        require_tiers(parsed, word_tier=True, phone_tier=True)


def test_writes_json_csv_and_ctm_from_one_canonical_parse(
    tmp_path: Path, write_textgrid: Callable[..., Path]
) -> None:
    textgrid = write_textgrid(tmp_path / "日本語.TextGrid", label="日本語")
    parsed = parse_textgrid(textgrid)
    outputs = write_exports(
        textgrid, parsed, ("json", "csv", "ctm"), audio=tmp_path / "日本語.wav",
        transcript=tmp_path / "日本語.txt", language="jap",
    )

    payload = json.loads(outputs["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["recording_id"] == "日本語"
    assert payload["tiers"]["word"][0] == {"start": 0.0, "end": 1.0, "label": "日本語"}
    with outputs["csv"].open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert {row["tier"] for row in rows} == {"word", "phone"}
    assert outputs["words_ctm"].read_text(encoding="utf-8") == "日本語 1 0.000000 1.000000 日本語\n"
    assert outputs["phones_ctm"].read_text(encoding="utf-8") == "日本語 1 0.000000 1.000000 t\n"


def test_ctm_recording_id_uses_encoded_corpus_relative_stem(
    tmp_path: Path, write_textgrid: Callable[..., Path]
) -> None:
    parsed = parse_textgrid(write_textgrid(tmp_path / "sample.TextGrid"))

    first = write_exports(
        tmp_path / "first.TextGrid", parsed, ("ctm",), audio=tmp_path / "sample.wav",
        transcript=tmp_path / "sample.txt", language="kor", relative_stem=Path("speaker a/sample"),
    )
    second = write_exports(
        tmp_path / "second.TextGrid", parsed, ("ctm",), audio=tmp_path / "sample.wav",
        transcript=tmp_path / "sample.txt", language="kor", relative_stem=Path("speaker-b/sample"),
    )

    assert first.words_ctm is not None and second.words_ctm is not None
    assert first.words_ctm.read_text(encoding="utf-8").startswith("speaker%20a/sample 1 ")
    assert second.words_ctm.read_text(encoding="utf-8").startswith("speaker-b/sample 1 ")


def test_ctm_percent_encodes_label_whitespace_and_percent(
    tmp_path: Path, write_textgrid: Callable[..., Path]
) -> None:
    textgrid = write_textgrid(tmp_path / "sample.TextGrid", label="two words\t100%\x7f")
    parsed = parse_textgrid(textgrid)

    outputs = write_exports(
        textgrid, parsed, ("ctm",), audio=tmp_path / "sample.wav",
        transcript=tmp_path / "sample.txt", language="kor",
    )

    assert outputs.words_ctm is not None
    row = outputs.words_ctm.read_text(encoding="utf-8").strip()
    assert row.split() == ["sample", "1", "0.000000", "1.000000", "two%20words%09100%25%7F"]
