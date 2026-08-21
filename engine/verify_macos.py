"""Validate a native macOS KoreanFA engine archive before release upload."""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from macos_verification import (
    DEFAULT_MAX_ARCHIVE_BYTES,
    DEFAULT_MAX_EXTRACTED_BYTES,
    assert_architecture,
    assert_code_signature,
    assert_macos_baseline,
    current_platform,
    declares_utf8_dictionary,
    dicrc_charset,
    dictionary_charset,
    is_system_library,
    macho_dependencies,
    mib,
    safe_extract,
    size_limit,
    version_tuple,
)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {Path(sys.argv[0]).name} ENGINE_ARCHIVE")
    archive = Path(sys.argv[1]).resolve()
    maximum_archive_size = size_limit(
        "KOREANFA_MAX_ENGINE_ARCHIVE_BYTES", DEFAULT_MAX_ARCHIVE_BYTES
    )
    maximum_extracted_size = size_limit(
        "KOREANFA_MAX_ENGINE_EXTRACTED_BYTES", DEFAULT_MAX_EXTRACTED_BYTES
    )
    archive_size = archive.stat().st_size
    if archive_size > maximum_archive_size:
        raise RuntimeError(f"Engine archive exceeds the {mib(maximum_archive_size)} size limit: {archive}")
    expected_platform = current_platform()
    architecture = expected_platform.removeprefix("darwin-")
    with tempfile.TemporaryDirectory(prefix="koreanfa-macos-engine-check-") as temporary:
        temporary_root = Path(temporary)
        extracted_size = safe_extract(archive, temporary_root, maximum_extracted_size)
        roots = [path for path in temporary_root.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise RuntimeError("Engine archive must contain exactly one top-level directory.")
        engine = roots[0]
        metadata = json.loads((engine / "engine.json").read_text(encoding="utf-8"))
        engine_version = str(metadata.get("engine_version", ""))
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", engine_version):
            raise RuntimeError(f"Engine metadata has an invalid version: {engine_version!r}")
        expected_name = f"koreanfa-engine-v{engine_version}-{expected_platform}"
        if engine.name != expected_name or archive.name != f"{expected_name}.tar.gz":
            raise RuntimeError(
                f"Engine archive, root, and metadata versions must match: {archive.name}, {engine.name}"
            )
        if metadata.get("platform") != expected_platform:
            raise RuntimeError(f"Engine platform does not match this host: {metadata.get('platform')}")
        if not re.fullmatch(r"[0-9a-f]{40}", str(metadata.get("source_revision", ""))):
            raise RuntimeError("macOS engine must record its 40-character Git source revision.")
        expected_source_revision = os.environ.get("KOREANFA_EXPECTED_SOURCE_REVISION")
        if expected_source_revision and metadata.get("source_revision") != expected_source_revision:
            raise RuntimeError(
                "macOS engine source revision does not match the tested checkout: "
                f"expected {expected_source_revision}, received {metadata.get('source_revision')}"
            )
        source_is_clean = metadata.get("source_tracked_files_clean") is True
        allow_dirty_development = os.environ.get("KOREANFA_ALLOW_DIRTY_BUILD") == "1"
        if not source_is_clean and not allow_dirty_development:
            raise RuntimeError("A release engine must be built without changes to tracked source files.")
        if metadata.get("macos_minimum_version") != "12.0":
            raise RuntimeError("macOS engine must declare the supported macOS 12.0 baseline.")
        if metadata.get("library_path_variable") != "DYLD_FALLBACK_LIBRARY_PATH":
            raise RuntimeError("macOS engine must use DYLD_FALLBACK_LIBRARY_PATH as its fallback library path.")
        if metadata.get("math_library") != "Accelerate":
            raise RuntimeError("macOS Kaldi must use Apple's Accelerate framework.")

        kaldi = engine / metadata["kaldi_dir"] / "src" / "bin" / "ali-to-phones"
        mecab = engine / metadata["mecab_command"]
        dictionary = engine / metadata["mecab_dict"]
        mecabrc = engine / metadata["mecabrc"]
        library_paths = tuple(engine / str(path) for path in metadata["library_paths"])
        for required in (kaldi, mecab, dictionary, mecabrc, *library_paths):
            if not required.exists():
                raise RuntimeError(f"Missing required engine path: {required}")
        for notice in ("KALDI.txt", "OPENFST.txt", "MECAB.txt", "IPADIC.txt"):
            notice_path = engine / "licenses" / notice
            if not notice_path.is_file() or notice_path.stat().st_size == 0:
                raise RuntimeError(f"Missing bundled license notice: {notice_path}")
        forbidden_notices = ("OPENBLAS.txt", "GCC-RUNTIME.txt")
        for notice in forbidden_notices:
            if (engine / "licenses" / notice).exists():
                raise RuntimeError(f"macOS engine contains an unused math runtime notice: {notice}")

        binaries = [
            *sorted(path for path in (engine / "kaldi").rglob("*") if path.is_file() and os.access(path, os.X_OK)),
            mecab,
            *sorted(path for path in (engine / "lib").glob("*.dylib*")),
        ]
        if not binaries:
            raise RuntimeError("Engine contains no Mach-O executables or libraries.")
        accelerate_users = 0
        deployment_targets: list[str] = []
        dependency_summary: list[str] = []
        for binary in binaries:
            assert_architecture(binary, architecture)
            deployment_targets.extend(assert_macos_baseline(binary, "12.0"))
            assert_code_signature(binary)
            dependencies = macho_dependencies(binary)
            dependency_summary.append(f"[{binary.relative_to(engine)}]")
            dependency_summary.extend(f"  {dependency}" for dependency in dependencies)
            for dependency in dependencies:
                if dependency == "/System/Library/Frameworks/Accelerate.framework/Versions/A/Accelerate":
                    accelerate_users += 1
                if "openblas" in dependency.lower() or "gfortran" in dependency.lower():
                    raise RuntimeError(f"macOS engine contains an unexpected math runtime in {binary}: {dependency}")
                if is_system_library(dependency):
                    continue
                if not dependency.startswith("@rpath/"):
                    raise RuntimeError(f"Non-relocatable Mach-O dependency in {binary}: {dependency}")
                if not (engine / "lib" / Path(dependency).name).is_file():
                    raise RuntimeError(f"Missing bundled Mach-O dependency in {binary}: {dependency}")
        if accelerate_users == 0:
            raise RuntimeError("No packaged Kaldi binary links Apple's Accelerate framework.")

        environment = os.environ | {
            "MECABRC": str(mecabrc),
            "DYLD_FALLBACK_LIBRARY_PATH": ":".join(map(str, library_paths)),
        }
        dictionary_result = subprocess.run(
            [mecab, "-d", dictionary, "-D"],
            capture_output=True,
            env=environment,
        )
        if dictionary_result.returncode not in (0, 1):
            detail = dictionary_result.stderr.decode("utf-8", errors="strict")
            raise RuntimeError(f"Bundled MeCab could not inspect IPADIC: {detail}")
        dictionary_details = dictionary_result.stdout.decode("utf-8", errors="strict")
        dictionary_dicrc = (dictionary / "dicrc").read_text(encoding="utf-8", errors="strict")
        if (
            not declares_utf8_dictionary(dictionary_details)
            or dictionary_charset(dictionary_details) != "utf8"
            or dicrc_charset(dictionary_dicrc) != "utf8"
            or dictionary_charset(dictionary_details) != dicrc_charset(dictionary_dicrc)
        ):
            raise RuntimeError(f"Bundled IPADIC is not UTF-8:\n{dictionary_details}")
        mecab_result = subprocess.run(
            [mecab, "-d", dictionary],
            input="日本語の動作確認\n".encode("utf-8"),
            capture_output=True,
            env=environment,
            check=True,
        )
        mecab_output = mecab_result.stdout.decode("utf-8", errors="strict")
        if "\ufffd" in mecab_output:
            raise RuntimeError(f"Bundled MeCab failed strict UTF-8 validation:\n{mecab_output}")
        expected = {
            "日本語": ("ニホンゴ", "ニホンゴ"),
            "の": ("ノ", "ノ"),
            "動作": ("ドウサ", "ドーサ"),
            "確認": ("カクニン", "カクニン"),
        }
        actual = {}
        for line in mecab_output.splitlines():
            if line == "EOS":
                continue
            surface, features = line.split("\t", 1)
            actual[surface] = tuple(features.split(",")[-2:])
        for surface, pronunciation in expected.items():
            if actual.get(surface) != pronunciation:
                raise RuntimeError(
                    f"Bundled MeCab returned the wrong reading for {surface}: "
                    f"expected {pronunciation}, received {actual.get(surface)}\n{mecab_output}"
                )
        kaldi_result = subprocess.run([kaldi], text=True, capture_output=True, env=environment, check=False)
        if kaldi_result.returncode not in (0, 1):
            raise RuntimeError(f"Bundled Kaldi executable could not run: {kaldi_result.stderr}")
        archive_sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
        verification_report = {
            "archive": str(archive),
            "archive_bytes": archive_size,
            "extracted_bytes": extracted_size,
            "sha256": archive_sha256,
            "platform": expected_platform,
            "source_revision": metadata["source_revision"],
            "source_tracked_files_clean": source_is_clean,
            "release_ready": source_is_clean,
            "macho_count": len(binaries),
            "all_macho_architecture": architecture,
            "deployment_targets": sorted(set(deployment_targets), key=version_tuple),
            "maximum_allowed_macos_target": "12.0",
            "all_codesign_strict": True,
            "all_non_system_dependencies_use_rpath": True,
            "accelerate_link_count": accelerate_users,
            "openblas_or_gfortran_dependencies": 0,
            "mecab_dictionary_charset": "utf8",
            "mecab_strict_utf8": True,
        }
        report_destination = os.environ.get("KOREANFA_VERIFICATION_REPORT")
        if report_destination:
            Path(report_destination).write_text(
                json.dumps(verification_report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        dependencies_destination = os.environ.get("KOREANFA_OTOOL_SUMMARY")
        if dependencies_destination:
            Path(dependencies_destination).write_text(
                "\n".join(dependency_summary) + "\n", encoding="utf-8"
            )
        print(
            f"Validated {expected_platform} engine: archive={mib(archive_size)}, "
            f"extracted={mib(extracted_size)}, Mach-O files={len(binaries)}, "
            f"release_ready={str(source_is_clean).lower()}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
