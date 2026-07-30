"""Validate a native macOS KoreanFA engine archive before release upload."""

import json
import os
import platform
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def _current_platform() -> str:
    if platform.system() != "Darwin":
        raise RuntimeError("The macOS engine verifier must run on macOS.")
    aliases = {"x86_64": "x86_64", "amd64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}
    machine = aliases.get(platform.machine().lower(), platform.machine().lower())
    return f"darwin-{machine}"


def _macho_dependencies(binary: Path) -> tuple[str, ...]:
    result = subprocess.run(["otool", "-L", str(binary)], text=True, capture_output=True, check=True)
    return tuple(line.lstrip().split(" ", 1)[0] for line in result.stdout.splitlines()[1:] if line.strip())


def _is_system_library(path: str) -> bool:
    return path.startswith(("/System/Library/", "/usr/lib/", "/Library/Apple/"))


def _assert_architecture(binary: Path, architecture: str) -> None:
    result = subprocess.run(["lipo", "-archs", str(binary)], text=True, capture_output=True, check=True)
    if architecture not in result.stdout.split():
        raise RuntimeError(f"Expected {architecture} Mach-O binary: {binary}")


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = [int(part) for part in value.split(".")]
    return tuple((parts + [0, 0, 0])[:3])


def _assert_macos_baseline(binary: Path, maximum: str) -> None:
    """Reject dependencies that secretly require a newer deployment target."""
    result = subprocess.run(["otool", "-l", str(binary)], text=True, capture_output=True, check=True)
    versions: list[str] = []
    command = ""
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("Load command "):
            command = ""
        elif stripped.startswith("cmd "):
            command = stripped.split(maxsplit=1)[1]
        elif command == "LC_BUILD_VERSION" and stripped.startswith("minos "):
            versions.append(stripped.split(maxsplit=1)[1])
        elif command == "LC_VERSION_MIN_MACOSX" and stripped.startswith("version "):
            versions.append(stripped.split(maxsplit=1)[1])
    if not versions:
        raise RuntimeError(f"Mach-O file has no macOS deployment target: {binary}")
    maximum_tuple = _version_tuple(maximum)
    for version in versions:
        normalized = re.match(r"[0-9]+(?:\.[0-9]+)*", version)
        if not normalized or _version_tuple(normalized.group(0)) > maximum_tuple:
            raise RuntimeError(
                f"Mach-O file requires macOS {version}, newer than the {maximum} baseline: {binary}"
            )


def _safe_extract(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:gz") as contents:
        root = destination.resolve()
        for member in contents.getmembers():
            member_path = (destination / member.name).resolve()
            if not member_path.is_relative_to(root) or member.issym() or member.islnk():
                raise RuntimeError("Engine archive contains an unsafe path.")
        contents.extractall(destination, filter="data")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {Path(sys.argv[0]).name} ENGINE_ARCHIVE")
    archive = Path(sys.argv[1]).resolve()
    expected_platform = _current_platform()
    architecture = expected_platform.removeprefix("darwin-")

    with tempfile.TemporaryDirectory(prefix="koreanfa-macos-engine-check-") as temporary:
        temporary_root = Path(temporary)
        _safe_extract(archive, temporary_root)
        roots = [path for path in temporary_root.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise RuntimeError("Engine archive must contain exactly one top-level directory.")
        engine = roots[0]
        metadata = json.loads((engine / "engine.json").read_text(encoding="utf-8"))
        if metadata.get("platform") != expected_platform:
            raise RuntimeError(f"Engine platform does not match this host: {metadata.get('platform')}")
        if metadata.get("macos_minimum_version") != "12.0":
            raise RuntimeError("macOS engine must declare the supported macOS 12.0 baseline.")
        if metadata.get("library_path_variable") != "DYLD_FALLBACK_LIBRARY_PATH":
            raise RuntimeError("macOS engine must use DYLD_FALLBACK_LIBRARY_PATH as its fallback library path.")

        kaldi = engine / metadata["kaldi_dir"] / "src" / "bin" / "ali-to-phones"
        mecab = engine / metadata["mecab_command"]
        dictionary = engine / metadata["mecab_dict"]
        mecabrc = engine / metadata["mecabrc"]
        library_paths = tuple(engine / str(path) for path in metadata["library_paths"])
        for required in (kaldi, mecab, dictionary, mecabrc, *library_paths):
            if not required.exists():
                raise RuntimeError(f"Missing required engine path: {required}")
        for notice in ("KALDI.txt", "OPENFST.txt", "OPENBLAS.txt", "MECAB.txt", "IPADIC.txt"):
            notice_path = engine / "licenses" / notice
            if not notice_path.is_file() or notice_path.stat().st_size == 0:
                raise RuntimeError(f"Missing bundled license notice: {notice_path}")

        binaries = [
            *sorted(path for path in (engine / "kaldi").rglob("*") if path.is_file() and os.access(path, os.X_OK)),
            mecab,
            *sorted(path for path in (engine / "lib").glob("*.dylib*")),
        ]
        if not binaries:
            raise RuntimeError("Engine contains no Mach-O executables or libraries.")
        for binary in binaries:
            _assert_architecture(binary, architecture)
            _assert_macos_baseline(binary, "12.0")
            for dependency in _macho_dependencies(binary):
                if _is_system_library(dependency):
                    continue
                if not dependency.startswith("@rpath/"):
                    raise RuntimeError(f"Non-relocatable Mach-O dependency in {binary}: {dependency}")
                if not (engine / "lib" / Path(dependency).name).is_file():
                    raise RuntimeError(f"Missing bundled Mach-O dependency in {binary}: {dependency}")

        environment = os.environ | {
            "MECABRC": str(mecabrc),
            "DYLD_FALLBACK_LIBRARY_PATH": ":".join(map(str, library_paths)),
        }
        mecab_result = subprocess.run(
            [mecab, "-d", dictionary],
            input="日本語の動作確認\n",
            text=True,
            capture_output=True,
            env=environment,
            check=True,
        )
        if "EOS" not in mecab_result.stdout:
            raise RuntimeError("Bundled MeCab did not return EOS.")
        kaldi_result = subprocess.run([kaldi], text=True, capture_output=True, env=environment, check=False)
        if kaldi_result.returncode not in (0, 1):
            raise RuntimeError(f"Bundled Kaldi executable could not run: {kaldi_result.stderr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
