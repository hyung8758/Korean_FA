import json
import re
import tomllib
from pathlib import Path

from koreanfa import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_metadata_stays_in_sync() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "koreanfa" / "engine_manifest.json").read_text(encoding="utf-8"))
    workflow = (ROOT / ".github" / "workflows" / "engine-candidate.yml").read_text(encoding="utf-8")

    assert pyproject["project"]["dynamic"] == ["version"]
    assert manifest["engines"]["linux-x86_64"]["version"] == __version__
    assert re.search(rf'ENGINE_VERSION: "{re.escape(__version__)}"', workflow)


def test_engine_candidate_uses_the_supported_glibc_baseline() -> None:
    workflow = (ROOT / ".github" / "workflows" / "engine-candidate.yml").read_text(encoding="utf-8")

    assert "quay.io/pypa/manylinux2014_x86_64" in workflow
    assert "KOREANFA_GLIBC_BASELINE=2.17" in workflow


def test_release_legal_documents_are_declared_in_package_metadata() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    third_party_notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    model_release_checklist = (
        ROOT / "docs" / "maintainer" / "model-release-checklist.md"
    ).read_text(encoding="utf-8")

    assert pyproject["project"]["license"] == "Apache-2.0"
    assert pyproject["project"]["license-files"] == [
        "license",
        "THIRD_PARTY_NOTICES.md",
    ]
    assert "GCC-RUNTIME.txt" in third_party_notices
    assert "Pending maintainer confirmation" in model_release_checklist
