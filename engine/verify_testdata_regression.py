#!/usr/bin/env python3
"""Validate KoreanFA against the immutable public regression corpus."""

import argparse
import hashlib
import json
import subprocess
import sys
import warnings
from pathlib import Path

from alignment_labels import read_short_textgrid_labels, validate_labels


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8", errors="strict"))


def _progress(phase: str, completed: int, total: int, detail: str) -> None:
    if phase == "summary" or (phase in {"completed", "failed"} and completed % 10 == 0):
        print(f"{phase}: {completed}/{total} {detail}", flush=True)


def _validate_normal(root: Path, output: Path, *, num_jobs: int) -> None:
    from koreanfa import align_directory

    expected_document = _load_json(root / "expected" / "alignment-labels.json")
    expected = expected_document["fixtures"]
    result = align_directory(
        root / "normal",
        recursive=True,
        lang="auto",
        output_dir=output / "normal",
        num_jobs=num_jobs,
        progress=_progress,
    )
    if result.failures or len(result.results) != 100:
        raise RuntimeError(
            f"Normal corpus result changed: success={len(result.results)} failed={len(result.failures)}"
        )

    actual: dict[str, dict[str, list[str]]] = {}
    for item in result.results:
        fixture_id = item.audio.stem
        if fixture_id not in expected:
            raise RuntimeError(f"Unexpected normal fixture result: {fixture_id}")
        validate_labels(item.textgrid, expected[fixture_id])
        actual[fixture_id] = read_short_textgrid_labels(item.textgrid)
    if set(actual) != set(expected):
        raise RuntimeError(
            f"Normal fixture IDs changed: missing={sorted(set(expected) - set(actual))} "
            f"unexpected={sorted(set(actual) - set(expected))}"
        )
    canonical = json.dumps(actual, ensure_ascii=False, sort_keys=True).encode("utf-8")
    actual_sha256 = hashlib.sha256(canonical).hexdigest()
    if actual_sha256 != expected_document["label_sequence_sha256"]:
        raise RuntimeError(
            f"Combined label SHA-256 changed: expected {expected_document['label_sequence_sha256']}, "
            f"received {actual_sha256}"
        )
    print(f"PASS normal fixtures: {len(result.results)}; label SHA-256: {actual_sha256}")


def _run_cli(arguments: list[str], *, expected_status: int = 2) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "koreanfa", *arguments]
    completed = subprocess.run(command, text=True, encoding="utf-8", errors="strict", capture_output=True)
    if completed.returncode != expected_status:
        raise RuntimeError(
            f"CLI status changed: expected {expected_status}, received {completed.returncode}\n"
            f"command={command}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )
    if "Traceback" in completed.stderr:
        raise RuntimeError(f"CLI leaked a traceback: {command}\n{completed.stderr}")
    return completed


def _validate_individual_failures(root: Path, output: Path) -> None:
    from koreanfa import KoreanFAError, align

    manifest = _load_json(root / "manifest.json")
    fixtures = manifest["failure_fixtures"]
    checked = 0
    for fixture in fixtures:
        if fixture["expected"] != "failure" or fixture["expected_reason"] == "unmatched_pair":
            continue
        audio = root / fixture["audio_path"]
        transcript = root / fixture["text_path"]
        try:
            align(audio, transcript, output_dir=output / "api-individual" / fixture["fixture_id"])
        except KoreanFAError as error:
            if not str(error).strip():
                raise RuntimeError(f"Empty API failure reason for {fixture['fixture_id']}") from error
        else:
            raise RuntimeError(f"Expected API failure was accepted: {fixture['fixture_id']}")
        completed = _run_cli(
            [
                "align",
                str(audio),
                str(transcript),
                "--output-dir",
                str(output / "cli-individual" / fixture["fixture_id"]),
            ]
        )
        if not completed.stderr.strip():
            raise RuntimeError(f"CLI omitted its failure reason: {fixture['fixture_id']}")
        checked += 1
    if checked != 5:
        raise RuntimeError(f"Expected five invalid audio/text fixtures, received {checked}")
    print(f"PASS invalid audio/text fixtures: {checked}")


def _validate_unmatched(root: Path, output: Path) -> None:
    from koreanfa import PairingError, discover_pairs

    directory = root / "expected-failures" / "unmatched_pair"
    try:
        discover_pairs(directory, ignore_unmatched=False)
    except PairingError as error:
        message = str(error)
        if "unmatched_audio" not in message or "unmatched_text" not in message:
            raise RuntimeError(f"Unmatched-pair details changed: {message}") from error
    else:
        raise RuntimeError("Strict pair discovery accepted unmatched files")
    completed = _run_cli(
        [
            "align-dir",
            str(directory),
            "--ignore-unmatched",
            "false",
            "--output-dir",
            str(output / "cli-unmatched"),
        ]
    )
    if "unmatched_audio" not in completed.stderr or "unmatched_text" not in completed.stderr:
        raise RuntimeError(f"CLI unmatched-pair details changed: {completed.stderr}")
    print("PASS unmatched-pair fixtures: 2")


def _validate_partial_batch(root: Path, output: Path, *, num_jobs: int) -> None:
    from koreanfa import align_directory

    directory = root / "expected-failures" / "partial_batch"
    api_output = output / "api-partial"
    result = align_directory(directory, output_dir=api_output, num_jobs=num_jobs)
    if len(result.results) != 1 or len(result.failures) != 1:
        raise RuntimeError(
            f"API partial-batch result changed: success={len(result.results)} failed={len(result.failures)}"
        )
    if result.results[0].audio.stem != "good" or result.failures[0].audio.stem != "corrupt":
        raise RuntimeError(
            f"API partial-batch identities changed: results={result.results} failures={result.failures}"
        )
    if not result.results[0].textgrid.is_file() or not result.failures[0].reason.strip():
        raise RuntimeError("API partial batch lost its successful output or failure reason")

    cli_output = output / "cli-partial"
    completed = _run_cli(["align-dir", str(directory), "--output-dir", str(cli_output)])
    if "summary: total=2 success=1 failed=1" not in completed.stderr:
        raise RuntimeError(f"CLI partial-batch summary changed: {completed.stderr}")
    if not (cli_output / "good.TextGrid").is_file() or "failed corrupt.wav" not in completed.stderr:
        raise RuntimeError("CLI partial batch lost its successful output or failure details")
    print("PASS partial-batch fixture: success=1 failed=1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("testdata", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--num-jobs", type=int, default=4)
    args = parser.parse_args()
    root = args.testdata.resolve()
    output = args.output.resolve()
    import koreanfa

    print(f"KoreanFA {koreanfa.__version__}: {Path(koreanfa.__file__).resolve()}")
    if output.exists():
        raise RuntimeError(f"Refusing to replace an existing output directory: {output}")
    output.mkdir(parents=True)

    manifest = _load_json(root / "manifest.json")
    if manifest["dataset"] != "koreanfa-testdata" or manifest["version"] != "1.0.0":
        raise RuntimeError("Unexpected test data identity or version")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _validate_normal(root, output, num_jobs=args.num_jobs)
    _validate_individual_failures(root, output)
    _validate_unmatched(root, output)
    _validate_partial_batch(root, output, num_jobs=args.num_jobs)
    print("PASS KoreanFA public test data regression: normal=100 expected-failure=8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
