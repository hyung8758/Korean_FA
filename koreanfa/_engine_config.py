"""Engine manifest, platform compatibility, and cache location logic."""

import json
import os
import platform
import re
from importlib import resources
from pathlib import Path

from ._engine_types import EngineSpec
from .errors import EngineUnavailableError


def engine_spec(manifest_path: str | Path | None = None) -> EngineSpec:
    manifest = load_manifest(manifest_path)
    current_platform = platform_tag()
    engines = manifest.get("engines")
    if not isinstance(engines, dict):
        raise EngineUnavailableError("The KoreanFA engine manifest does not contain an engines mapping.")
    entry = engines.get(current_platform)
    if not isinstance(entry, dict):
        available = ", ".join(sorted(str(name) for name in engines)) or "none"
        raise EngineUnavailableError(
            f"KoreanFA does not publish an engine for {current_platform}. Published targets: {available}."
        )
    version, url, sha256 = entry.get("version"), entry.get("url"), entry.get("sha256")
    if not isinstance(version, str) or not version:
        raise EngineUnavailableError(f"The KoreanFA engine manifest has no valid version for {current_platform}.")
    if url is not None and not isinstance(url, str):
        raise EngineUnavailableError(f"The KoreanFA engine manifest has an invalid URL for {current_platform}.")
    if sha256 is not None and not isinstance(sha256, str):
        raise EngineUnavailableError(f"The KoreanFA engine manifest has an invalid SHA-256 for {current_platform}.")
    minimum_glibc = _minimum_glibc(entry.get("minimum_glibc"), current_platform)
    return EngineSpec(current_platform, version, url, sha256, minimum_glibc)


def _minimum_glibc(value: object, current_platform: str) -> tuple[int, int] | None:
    if value is None:
        return None
    if not isinstance(value, str) or (parsed := parse_version_pair(value)) is None:
        raise EngineUnavailableError(
            f"The KoreanFA engine manifest has an invalid minimum_glibc for {current_platform}."
        )
    return parsed


def load_manifest(manifest_path: str | Path | None) -> dict[str, object]:
    if manifest_path:
        contents = Path(manifest_path).read_text(encoding="utf-8")
    elif configured := os.environ.get("KOREANFA_ENGINE_MANIFEST"):
        contents = Path(configured).expanduser().read_text(encoding="utf-8")
    else:
        contents = resources.files("koreanfa").joinpath("engine_manifest.json").read_text(encoding="utf-8")
    parsed: object = json.loads(contents)
    if not isinstance(parsed, dict) or not all(isinstance(key, str) for key in parsed):
        raise EngineUnavailableError("The KoreanFA engine manifest must be a JSON object with string keys.")
    return {str(key): value for key, value in parsed.items()}


def platform_tag() -> str:
    machine = platform.machine().lower()
    system = platform.system()
    if system == "Linux":
        aliases = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}
        return f"linux-{aliases.get(machine, machine)}"
    if system == "Darwin":
        aliases = {"x86_64": "x86_64", "amd64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}
        return f"darwin-{aliases.get(machine, machine)}"
    return f"{system.lower()}-{machine}"


def parse_version_pair(value: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"(\d+)\.(\d+)", value.strip())
    return (int(match.group(1)), int(match.group(2))) if match else None


def linux_libc() -> tuple[str, tuple[int, int] | None]:
    """Return the detected Linux libc family and major/minor version."""
    try:
        configured = os.confstr("CS_GNU_LIBC_VERSION")
    except (AttributeError, OSError, ValueError):
        configured = None
    if configured:
        match = re.fullmatch(r"glibc\s+(\d+)\.(\d+)(?:\.\d+)?", configured.strip(), flags=re.IGNORECASE)
        if match:
            return "glibc", (int(match.group(1)), int(match.group(2)))
    name, version_text = platform.libc_ver()
    match = re.match(r"(\d+)\.(\d+)", version_text.strip())
    version = (int(match.group(1)), int(match.group(2))) if match else None
    return name.strip().lower() or "unknown", version


def validate_platform_requirements(spec: EngineSpec) -> None:
    """Reject an incompatible Linux libc before downloading."""
    if not spec.platform.startswith("linux-") or spec.minimum_glibc is None:
        return
    libc_name, detected = linux_libc()
    required = ".".join(map(str, spec.minimum_glibc))
    if libc_name != "glibc":
        detected_text = libc_name + (" " + ".".join(map(str, detected)) if detected else "")
        raise EngineUnavailableError(
            f"The KoreanFA Linux engine requires x86_64 Linux with glibc {required} or later; "
            f"detected {detected_text}. Alpine Linux and other musl-based distributions are not supported."
        )
    if detected is None:
        raise EngineUnavailableError(
            f"The KoreanFA Linux engine requires glibc {required} or later, but the installed glibc version "
            "could not be detected."
        )
    if detected < spec.minimum_glibc:
        raise EngineUnavailableError(
            f"The KoreanFA Linux engine requires x86_64 Linux with glibc {required} or later; "
            f"detected glibc {'.'.join(map(str, detected))}. This Linux environment is not supported."
        )


def engine_home(override: str | Path | None = None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    if configured := os.environ.get("KOREANFA_ENGINE_HOME"):
        return Path(configured).expanduser().resolve()
    if configured := os.environ.get("XDG_CACHE_HOME"):
        cache_home = Path(configured)
    elif platform.system() == "Darwin":
        cache_home = Path.home() / "Library" / "Caches"
    else:
        cache_home = Path.home() / ".cache"
    return (cache_home / "koreanfa" / "engines").resolve()
