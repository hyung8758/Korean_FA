"""Reusable archive and Mach-O checks for the macOS engine verifier."""

import os
import platform
import re
import subprocess
import tarfile
from pathlib import Path

DEFAULT_MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_EXTRACTED_BYTES = 512 * 1024 * 1024


def size_limit(environment_name: str, default: int) -> int:
    raw = os.environ.get(environment_name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise RuntimeError(f"{environment_name} must be a positive byte count.") from error
    if value <= 0:
        raise RuntimeError(f"{environment_name} must be a positive byte count.")
    return value


def mib(value: int) -> str:
    return f"{value / (1024 * 1024):.1f} MiB"


def declares_utf8_dictionary(details: str) -> bool:
    return bool(re.search(r"^charset:\s*utf-?8\s*$", details, flags=re.IGNORECASE | re.MULTILINE))


def dictionary_charset(details: str) -> str | None:
    match = re.search(r"^charset:\s*(\S+)\s*$", details, flags=re.IGNORECASE | re.MULTILINE)
    return match.group(1).lower().replace("-", "") if match else None


def dicrc_charset(contents: str) -> str | None:
    match = re.search(
        r"^config-charset\s*=\s*(\S+)\s*$",
        contents,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return match.group(1).lower().replace("-", "") if match else None


def current_platform() -> str:
    if platform.system() != "Darwin":
        raise RuntimeError("The macOS engine verifier must run on macOS.")
    aliases = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    machine = aliases.get(platform.machine().lower(), platform.machine().lower())
    return f"darwin-{machine}"


def macho_dependencies(binary: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ["otool", "-L", str(binary)],
        text=True,
        capture_output=True,
        check=True,
    )
    return tuple(
        line.lstrip().split(" ", 1)[0]
        for line in result.stdout.splitlines()[1:]
        if line.strip()
    )


def is_system_library(path: str) -> bool:
    return path.startswith(("/System/Library/", "/usr/lib/", "/Library/Apple/"))


def assert_architecture(binary: Path, architecture: str) -> None:
    result = subprocess.run(
        ["lipo", "-archs", str(binary)],
        text=True,
        capture_output=True,
        check=True,
    )
    if architecture not in result.stdout.split():
        raise RuntimeError(f"Expected {architecture} Mach-O binary: {binary}")


def assert_code_signature(binary: Path) -> None:
    result = subprocess.run(
        ["codesign", "--verify", "--strict", str(binary)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown codesign error"
        raise RuntimeError(f"Invalid Mach-O code signature in {binary}: {detail}")


def version_tuple(value: str) -> tuple[int, ...]:
    parts = [int(part) for part in value.split(".")]
    return tuple((parts + [0, 0, 0])[:3])


def assert_macos_baseline(binary: Path, maximum: str) -> tuple[str, ...]:
    """Reject dependencies that secretly require a newer deployment target."""
    result = subprocess.run(
        ["otool", "-l", str(binary)],
        text=True,
        capture_output=True,
        check=True,
    )
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
    maximum_tuple = version_tuple(maximum)
    for version in versions:
        normalized = re.match(r"[0-9]+(?:\.[0-9]+)*", version)
        if not normalized or version_tuple(normalized.group(0)) > maximum_tuple:
            raise RuntimeError(
                f"Mach-O file requires macOS {version}, newer than the {maximum} baseline: {binary}"
            )
    return tuple(versions)


def safe_extract(archive: Path, destination: Path, maximum_size: int) -> int:
    with tarfile.open(archive, "r:gz") as contents:
        root = destination.resolve()
        extracted_size = 0
        for member in contents.getmembers():
            member_path = (destination / member.name).resolve()
            if not member_path.is_relative_to(root) or member.issym() or member.islnk():
                raise RuntimeError("Engine archive contains an unsafe path.")
            if member.isfile():
                extracted_size += member.size
                if extracted_size > maximum_size:
                    raise RuntimeError(f"Extracted engine exceeds the {mib(maximum_size)} size limit.")
        contents.extractall(destination, filter="data")
    return extracted_size
