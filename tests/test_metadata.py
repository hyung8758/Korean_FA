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
    candidate_report = (ROOT / "engine" / "candidate_report.py").read_text(encoding="utf-8")
    runtime_validator = (ROOT / "engine" / "validate_candidate_runtime.py").read_text(encoding="utf-8")
    runtime_entrypoint = (ROOT / "koreanfa" / "runtime" / "pipeline" / "forced_align.sh").read_text(
        encoding="utf-8"
    )
    single_pair_runtime = (ROOT / "koreanfa" / "runtime" / "pipeline" / "main_fa.sh").read_text(
        encoding="utf-8"
    )

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
    assert '"$iconv_probe_source" -liconv' in builder
    gettext_formula_m4 = '"$gettext_formula_prefix/share/gettext/m4"'
    gettext_homebrew_m4 = '"$(brew --prefix)/share/gettext/m4"'
    assert "brew --prefix gettext" in builder
    assert gettext_formula_m4 in builder
    assert gettext_homebrew_m4 in builder
    assert builder.index(gettext_formula_m4) < builder.index(gettext_homebrew_m4)
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
    assert "config-charset = UTF-8" in builder
    assert "IPADIC failed to use iconv" in builder
    assert "make -j1" in builder
    assert "ensure_macho_rpath" in builder
    assert "|| true" not in builder
    assert '"日本語": ("ニホンゴ", "ニホンゴ")' in builder
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
    assert 'os.environ.get("KOREANFA_ALLOW_DIRTY_BUILD") == "1"' in verifier
    assert "release_ready=" in verifier
    assert "No packaged Kaldi binary links Apple's Accelerate framework" in verifier
    assert "KOREANFA_EXPECTED_SOURCE_REVISION" in verifier
    assert 'decode("utf-8", errors="strict")' in verifier
    assert "dictionary_result.returncode not in (0, 1)" in verifier
    assert "_dicrc_charset(dictionary_dicrc)" in verifier
    assert '"日本語": ("ニホンゴ", "ニホンゴ")' in verifier
    assert "OPENBLAS.txt" in verifier
    assert "_assert_code_signature(binary)" in verifier
    assert "Engine archive, root, and metadata versions must match" in verifier

    assert "Usage: $0 OUTPUT_DIRECTORY ENGINE_VERSION" in candidate
    assert "engine_version=${2:-" not in candidate
    assert "candidate_http_server.py" in candidate
    assert "validate_candidate_runtime.py" in candidate
    assert "candidate_report.py" in candidate
    assert "KOREANFA_REUSE_ARCHIVE is only allowed" in candidate
    assert "and not archive_reused" in candidate_report
    assert 'engine_home="$unicode_root/엔진 설치 日本語"' in candidate
    assert 'virtual_environment="$temporary_directory/venv"' in candidate
    assert 'export TMPDIR="$temporary_directory/tmp"' in candidate
    assert 'export PATH="$virtual_environment/bin:/usr/bin:/bin:/usr/sbin:/sbin"' in candidate
    assert "summary: total=2 success=1 failed=1" in runtime_validator
    assert "failed_name = \"실패 失敗.wav\"" in runtime_validator
    assert 'rglob("summary.tsv")' in runtime_validator
    assert 'rglob("process.pair_1.log")' in runtime_validator
    assert 'read_text(encoding="utf-8", errors="strict")' in runtime_validator
    assert "failure.work_dir is None" in runtime_validator
    assert "partial_api.work_dir is None" in runtime_validator
    assert "Expected 22 TextGrid files" in runtime_validator
    assert "for repeat in range(1, 4)" in runtime_validator
    assert '("今日", "日本", "音声")' in runtime_validator
    assert 'data_dir=$("$python_executable" -c' in runtime_entrypoint
    assert "data_dir=$($python_executable -c" not in runtime_entrypoint
    assert single_pair_runtime.count("--cmd run.pl") == 4
    assert '--cmd "$RUNTIME_ROOT/pipeline/core/run.pl"' not in single_pair_runtime
    assert "local exit_code=$? failed_command=$BASH_COMMAND" in single_pair_runtime
    assert "trap - ERR" in single_pair_runtime
    assert "2.0.1" not in candidate


def test_engine_manifest_setup_is_centralized_in_the_pytest_fixture() -> None:
    fixture = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert "def write_test_manifest" in fixture
    assert "manifest.write_text" in fixture
    for relative in ("test_cli.py", "test_cli_engine_warning.py", "test_engine.py"):
        contents = (ROOT / "tests" / relative).read_text(encoding="utf-8")
        assert "manifest.write_text" not in contents
