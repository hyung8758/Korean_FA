#!/usr/bin/env python3
"""Exercise an installed candidate engine through CLI and Python APIs three times."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from alignment_labels import read_short_textgrid_labels, validate_labels


def _copy_pair(source: Path, stem: str, destination: Path) -> tuple[Path, Path]:
    destination.mkdir(parents=True, exist_ok=True)
    audio = destination / f"{stem}.wav"
    transcript = destination / f"{stem}.txt"
    shutil.copy2(source.with_suffix(".wav"), audio)
    shutil.copy2(source.with_suffix(".txt"), transcript)
    return audio, transcript


def _run_cli(
    command: list[str], *, environment: dict[str, str], log, expected_status: int = 0
) -> subprocess.CompletedProcess[str]:
    log.write(f"$ {' '.join(command)}\n")
    result = subprocess.run(command, text=True, capture_output=True, env=environment)
    log.write(result.stdout)
    log.write(result.stderr)
    log.flush()
    if result.returncode != expected_status:
        raise RuntimeError(
            f"CLI status mismatch: expected {expected_status}, received {result.returncode}: {command}"
        )
    return result


def _assert_textgrid(path: Path) -> dict[str, list[str]]:
    contents = path.read_text(encoding="utf-8", errors="strict")
    if "\ufffd" in contents:
        raise RuntimeError(f"Replacement character found in {path}")
    tiers = read_short_textgrid_labels(path)
    if "word" not in tiers or "phone" not in tiers:
        raise RuntimeError(f"Missing word or phone tier in {path}: {sorted(tiers)}")
    for tier in ("word", "phone"):
        if not tiers[tier] or not any(tiers[tier]):
            raise RuntimeError(f"Empty {tier} tier in {path}")
        if any(left == right == "" for left, right in zip(tiers[tier], tiers[tier][1:])):
            raise RuntimeError(f"Consecutive empty labels in {tier} tier: {path}")
    return tiers


def _language_examples(repository: Path, workspace: Path) -> dict[str, Path | tuple[Path, Path]]:
    inputs = workspace / "입력 경로 Korean 日本語"
    kor_source = repository / "example" / "kor_files" / "fv01_t01_s01"
    jap_source = repository / "example" / "jap_files" / "csj-0001-me-0001"
    kor_single = _copy_pair(kor_source, "한국어 단일 파일", inputs / "단일 파일")
    jap_single = _copy_pair(jap_source, "日本語 単一ファイル", inputs / "단일 파일")
    kor_directory = inputs / "한국어 디렉터리"
    jap_directory = inputs / "日本語 ディレクトリ"
    shutil.copytree(repository / "example" / "kor_files", kor_directory)
    shutil.copytree(repository / "example" / "jap_files", jap_directory)
    partial = inputs / "부분 실패 部分失敗"
    _copy_pair(jap_source, "성공 成功", partial)
    shutil.copy2(jap_source.with_suffix(".wav"), partial / "실패 失敗.wav")
    (partial / "실패 失敗.txt").write_text("", encoding="utf-8")
    return {
        "kor_single": kor_single,
        "jap_single": jap_single,
        "kor_directory": kor_directory,
        "jap_directory": jap_directory,
        "partial": partial,
    }


def _validate_repeat(
    repeat: int,
    *,
    examples: dict[str, Path | tuple[Path, Path]],
    results_root: Path,
    cli: Path,
    environment: dict[str, str],
    expected: dict[str, object],
    log,
) -> tuple[dict[str, dict[str, list[str]]], dict[str, int]]:
    from koreanfa import align, align_directory

    repeat_root = results_root / f"repeat-{repeat}"
    kor_audio, kor_text = examples["kor_single"]  # type: ignore[misc]
    jap_audio, jap_text = examples["jap_single"]  # type: ignore[misc]
    kor_directory = examples["kor_directory"]
    jap_directory = examples["jap_directory"]
    partial = examples["partial"]

    cli_kor_single = repeat_root / "cli-kor-single"
    cli_jap_single = repeat_root / "cli-jap-single"
    _run_cli(
        [str(cli), "align", str(kor_audio), str(kor_text), "--lang", "kor", "--output-dir", str(cli_kor_single)],
        environment=environment,
        log=log,
    )
    _run_cli(
        [str(cli), "align", str(jap_audio), str(jap_text), "--lang", "auto", "--output-dir", str(cli_jap_single)],
        environment=environment,
        log=log,
    )
    _run_cli(
        [str(cli), "align-dir", str(kor_directory), "--lang", "auto", "--output-dir", str(repeat_root / "cli-kor-directory")],
        environment=environment,
        log=log,
    )
    _run_cli(
        [str(cli), "align-dir", str(jap_directory), "--lang", "jap", "--output-dir", str(repeat_root / "cli-jap-directory")],
        environment=environment,
        log=log,
    )
    partial_cli = _run_cli(
        [str(cli), "align-dir", str(partial), "--lang", "jap", "--keep-workdir", "--output-dir", str(repeat_root / "cli-partial")],
        environment=environment,
        log=log,
        expected_status=2,
    )
    if "summary: total=2 success=1 failed=1" not in partial_cli.stderr:
        raise RuntimeError("CLI partial-failure summary changed")
    if not (repeat_root / "cli-partial" / "성공 成功.TextGrid").is_file():
        raise RuntimeError("CLI partial failure removed its successful TextGrid")

    api_kor_single = align(
        kor_audio, kor_text, lang="auto", output_dir=repeat_root / "api-kor-single"
    ).textgrid
    api_jap_single = align(
        jap_audio, jap_text, lang="jap", output_dir=repeat_root / "api-jap-single"
    ).textgrid
    if len(align_directory(kor_directory, lang="kor", output_dir=repeat_root / "api-kor-directory").results) != 3:
        raise RuntimeError("Korean API directory result count changed")
    if len(align_directory(jap_directory, lang="auto", output_dir=repeat_root / "api-jap-directory").results) != 5:
        raise RuntimeError("Japanese API directory result count changed")
    partial_api = align_directory(
        partial, lang="jap", output_dir=repeat_root / "api-partial", keep_workdir=True
    )
    if len(partial_api.results) != 1 or len(partial_api.failures) != 1:
        raise RuntimeError("Python API partial-failure counts changed")
    if not partial_api.results[0].textgrid.is_file():
        raise RuntimeError("Python API partial failure removed its successful TextGrid")

    textgrids = sorted(repeat_root.rglob("*.TextGrid"))
    if len(textgrids) != 22:
        raise RuntimeError(f"Expected 22 TextGrid files in repeat {repeat}, received {len(textgrids)}")
    sequences = {
        str(path.relative_to(repeat_root)): _assert_textgrid(path) for path in textgrids
    }
    golden_languages = expected["languages"]
    validate_labels(cli_kor_single / f"{kor_audio.stem}.TextGrid", golden_languages["kor"]["tiers"])
    validate_labels(cli_jap_single / f"{jap_audio.stem}.TextGrid", golden_languages["jap"]["tiers"])
    validate_labels(api_kor_single, golden_languages["kor"]["tiers"])
    validate_labels(api_jap_single, golden_languages["jap"]["tiers"])
    japanese_words = sequences[
        "cli-jap-directory/csj-0001-me-0001.TextGrid"
    ]["word"]
    for label in ("今日", "日本", "音声"):
        if label not in japanese_words:
            raise RuntimeError(f"Expected Japanese word label {label!r} is absent")
    return sequences, {"success": 22, "failed": 2, "textgrids": len(textgrids)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("cli", type=Path)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("log", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    repository = args.repository.resolve()
    workspace = args.workspace.resolve()
    results = args.results.resolve()
    workspace.mkdir(parents=True)
    results.mkdir(parents=True)
    expected = json.loads(args.fixture.read_text(encoding="utf-8", errors="strict"))

    import koreanfa

    package_path = Path(koreanfa.__file__).resolve()
    if package_path.is_relative_to(repository):
        raise RuntimeError(f"Runtime imported KoreanFA from the source checkout: {package_path}")
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    if any(entry.startswith("/opt/homebrew") or entry.startswith("/usr/local/Homebrew") for entry in path_entries):
        raise RuntimeError(f"Homebrew remains in runtime PATH: {os.environ.get('PATH')}")

    examples = _language_examples(repository, workspace)
    baseline = None
    counts = []
    with args.log.open("w", encoding="utf-8", errors="strict") as log:
        log.write(f"installed_package={package_path}\nPATH={os.environ.get('PATH')}\n")
        for repeat in range(1, 4):
            log.write(f"\n=== runtime repeat {repeat}/3 ===\n")
            sequences, repeat_counts = _validate_repeat(
                repeat,
                examples=examples,
                results_root=results,
                cli=args.cli,
                environment=os.environ.copy(),
                expected=expected,
                log=log,
            )
            if baseline is None:
                baseline = sequences
            elif sequences != baseline:
                raise RuntimeError(f"TextGrid label sequences changed in repeat {repeat}")
            counts.append(repeat_counts)
            log.write(f"repeat {repeat}: {repeat_counts}\n")

    assert baseline is not None
    digest = hashlib.sha256(
        json.dumps(baseline, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    report = {
        "runtime_passed": True,
        "repeats": 3,
        "counts_per_repeat": counts,
        "total_textgrids": sum(item["textgrids"] for item in counts),
        "stable_label_sequence_sha256": digest,
        "source_isolated_install": True,
        "http_server_offline_during_alignment": True,
        "homebrew_excluded_from_path": True,
        "unicode_and_space_paths": True,
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
