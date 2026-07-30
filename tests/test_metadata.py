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


def test_macos_engine_candidate_enforces_release_safety_policies() -> None:
    builder = (ROOT / "engine" / "build_macos.sh").read_text(encoding="utf-8")
    verifier = (ROOT / "engine" / "verify_macos.py").read_text(encoding="utf-8")
    candidate = (ROOT / "engine" / "test_macos_candidate.sh").read_text(encoding="utf-8")

    assert "source_revision=$(git" in builder
    assert "source_tracked_files_clean=true" in builder
    assert "KOREANFA_ALLOW_DIRTY_BUILD" in builder
    assert "fetch_git_revision()" in builder
    assert "http.version=HTTP/1.1" in builder
    assert "--depth=1 --no-tags" in builder
    assert "maximum_attempts=5" in builder
    assert "--retry-all-errors" in builder
    assert "am_cv_func_iconv_works=yes" in builder
    assert 'iconv_open("UTF-8", "EUC-JP")' in builder
    assert builder.index("https://github.com/shogo82148/mecab.git") < builder.index(
        'make -j"$build_jobs"'
    )
    assert builder.index('download_archive "$ipadic_url"') < builder.index(
        'make -j"$build_jobs"'
    )
    assert builder.index('cd "$mecab_source/mecab"') < builder.index(
        'cd "$openfst_source"'
    )
    assert "-framework Accelerate" in builder
    assert "OpenMathLib/OpenBLAS" not in builder
    assert "--mathlib=OPENBLAS" not in builder
    assert "gfortran" not in builder.lower()
    assert "--with-charset=utf8" in builder
    assert "#define HAVE_ICONV 1" in builder
    assert "details_result.returncode not in (0, 1)" in builder
    assert 'decode("utf-8", errors="strict")' in builder
    assert 'codesign --force --sign - "$binary"' in builder
    assert 'codesign --verify --strict "$binary"' in builder
    assert '"source_revision": "${source_revision}"' in builder
    assert '"source_tracked_files_clean": ${source_tracked_files_clean}' in builder
    assert '"math_library": "Accelerate"' in builder
    assert '"engine_version": "${engine_version}"' in builder

    assert "DEFAULT_MAX_ARCHIVE_BYTES" in verifier
    assert "DEFAULT_MAX_EXTRACTED_BYTES" in verifier
    assert "without changes to tracked source files" in verifier
    assert "No packaged Kaldi binary links Apple's Accelerate framework" in verifier
    assert "KOREANFA_EXPECTED_SOURCE_REVISION" in verifier
    assert 'decode("utf-8", errors="strict")' in verifier
    assert "dictionary_result.returncode not in (0, 1)" in verifier
    assert "OPENBLAS.txt" in verifier
    assert "_assert_code_signature(binary)" in verifier
    assert "Engine archive, root, and metadata versions must match" in verifier

    assert "Usage: $0 OUTPUT_DIRECTORY ENGINE_VERSION" in candidate
    assert "engine_version=${2:-" not in candidate
    assert "summary: total=2 success=1 failed=1" in candidate
    assert "Expected 22 TextGrid files" in candidate
    assert "2.0.1" not in candidate
