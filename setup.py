"""Build configuration for KoreanFA's Python distribution.

The Kaldi runtime is deliberately not bundled yet.  Korean/Japanese models
and the pipeline resources that drive an installed Kaldi runtime are installed
as data so that a wheel has no dependency on a source checkout.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from setuptools import setup


ROOT = Path(__file__).parent.resolve()
RUNTIME_ROOT = Path("share/koreanfa/runtime")
RUNTIME_SOURCES = (
    ROOT / "forced_align.sh",
    ROOT / "path.sh",
    ROOT / "model" / "kor_model",
    ROOT / "model" / "jap_model",
    ROOT / "runtime" / "config",
    ROOT / "runtime" / "pipeline",
)


def runtime_data_files() -> list[tuple[str, list[str]]]:
    """Keep the runtime layout expected by the shell pipelines."""
    files_by_destination: dict[Path, list[str]] = defaultdict(list)
    for source in RUNTIME_SOURCES:
        files = [source] if source.is_file() else sorted(
            path
            for path in source.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        )
        for file_path in files:
            # ``RUNTIME_ROOT`` already ends in ``runtime``.  Resources from
            # the source ``runtime/`` directory must therefore drop that
            # leading path component; otherwise a wheel installs them below
            # ``share/koreanfa/runtime/runtime`` and the pipeline cannot find
            # its configuration or scripts.
            if file_path.is_relative_to(ROOT / "runtime"):
                relative_parent = file_path.relative_to(ROOT / "runtime").parent
            else:
                relative_parent = file_path.relative_to(ROOT).parent
            files_by_destination[RUNTIME_ROOT / relative_parent].append(str(file_path.relative_to(ROOT)))
    return [(str(destination), files) for destination, files in sorted(files_by_destination.items())]


setup(data_files=runtime_data_files())
