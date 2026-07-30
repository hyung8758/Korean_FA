import json
import re
import tomllib
from pathlib import Path

from koreanfa import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_package_and_engine_release_metadata_are_consistent() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "koreanfa" / "engine_manifest.json").read_text(encoding="utf-8"))
    workflow = (ROOT / ".github" / "workflows" / "engine-candidate.yml").read_text(encoding="utf-8")
    engine = manifest["engines"]["linux-x86_64"]
    engine_version = engine["version"]

    assert pyproject["project"]["dynamic"] == ["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)
    assert engine["url"].endswith(f"koreanfa-engine-v{engine_version}-linux-x86_64.tar.gz")
    assert re.search(rf'ENGINE_VERSION: "{re.escape(engine_version)}"', workflow)


def test_engine_candidate_uses_the_supported_glibc_baseline() -> None:
    workflow = (ROOT / ".github" / "workflows" / "engine-candidate.yml").read_text(encoding="utf-8")

    assert "quay.io/pypa/manylinux2014_x86_64" in workflow
    assert "KOREANFA_GLIBC_BASELINE=2.17" in workflow
    assert "yum --setopt=tsflags= reinstall -y devtoolset-10-gcc" in workflow


def test_release_legal_documents_are_declared_in_package_metadata() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    third_party_notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    assert pyproject["project"]["license"] == "Apache-2.0 AND LicenseRef-Proprietary"
    assert pyproject["project"]["license-files"] == [
        "license",
        "THIRD_PARTY_NOTICES.md",
        "koreanfa/runtime/model/kor_model/NOTICE.md",
    ]
    assert "GCC-RUNTIME.txt" in third_party_notices
    assert "ko-speech-tools" in third_party_notices


def test_model_notices_describe_their_terms() -> None:
    japanese_notice = (
        ROOT / "koreanfa" / "runtime" / "model" / "jap_model" / "NOTICE.md"
    ).read_text(encoding="utf-8")
    korean_notice = (
        ROOT / "koreanfa" / "runtime" / "model" / "kor_model" / "NOTICE.md"
    ).read_text(encoding="utf-8")

    assert "Apache License, Version 2.0" in japanese_notice
    assert "cmqim4lxy00tunr07cjkcupeg" in japanese_notice
    assert "Mediazen" in korean_notice
    assert "may not modify" in korean_notice
    assert "may not redistribute" in korean_notice


def test_korean_g2p_no_longer_ships_kog2p_sources() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert "ko-speech-tools[g2p]==0.1.0" in dependencies
    runtime_pipeline = ROOT / "koreanfa" / "runtime" / "pipeline"
    assert not (runtime_pipeline / "g2p.py").exists()
    assert not (runtime_pipeline / "rulebook.txt").exists()
    assert not (runtime_pipeline / "text2lexicon.py").exists()
