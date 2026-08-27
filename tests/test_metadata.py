import ast
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
    engines = manifest["engines"]
    linux_engine = engines["linux-x86_64"]

    assert pyproject["project"]["dynamic"] == ["version"]
    assert pyproject["project"]["requires-python"] == ">=3.12,<3.14"
    assert "Development Status :: 4 - Beta" in pyproject["project"]["classifiers"]
    assert "Programming Language :: Python :: 3.13" in pyproject["project"]["classifiers"]
    assert __version__ == "2.4.0"
    assert set(engines) == {"linux-x86_64", "darwin-arm64", "darwin-x86_64"}
    assert linux_engine["minimum_glibc"] == "2.17"
    for platform, engine in engines.items():
        engine_version = engine["version"]
        filename = f"koreanfa-engine-v{engine_version}-{platform}.tar.gz"
        assert engine["url"].endswith(
            f"/koreanfa-engine-v{engine_version}/{filename}"
        )
        assert re.fullmatch(r"[0-9a-f]{64}", engine["sha256"])
    assert re.search(
        rf'ENGINE_VERSION: "{re.escape(linux_engine["version"])}"', workflow
    )


def test_package_quality_tooling_and_typed_marker_are_declared() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]["koreanfa"]

    assert set(pyproject["project"]["optional-dependencies"]["dev"]) >= {
        "build>=1.2,<2",
        "mypy>=1.11,<2",
        "pytest>=8.3,<10",
        "ruff>=0.9,<1",
        "twine>=5.1,<8",
    }
    assert "py.typed" in package_data
    assert (ROOT / "koreanfa" / "py.typed").is_file()
    assert not (ROOT / "setup.py").exists()


def test_workflows_separate_lightweight_and_native_engine_checks() -> None:
    package_workflow = (ROOT / ".github" / "workflows" / "package.yml").read_text(encoding="utf-8")
    engine_workflow = (ROOT / ".github" / "workflows" / "engine-candidate.yml").read_text(encoding="utf-8")

    assert "pull_request:\n    branches: [master]" in package_workflow
    assert '"engine/build_linux_x86_64.sh"' in engine_workflow
    assert '"engine/verify_linux_x86_64.py"' in engine_workflow
    assert '"koreanfa/runtime/**"' not in engine_workflow
    assert '"koreanfa/**"' not in engine_workflow


def test_macos_release_metadata_matches_verified_archives() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "koreanfa" / "engine_manifest.json").read_text(encoding="utf-8"))
    engines = manifest["engines"]

    assert "Operating System :: MacOS :: MacOS X" in pyproject["project"]["classifiers"]
    assert engines["darwin-arm64"] == {
        "version": "2.2.0",
        "url": "https://github.com/hyung8758/Korean_FA/releases/download/koreanfa-engine-v2.2.0/koreanfa-engine-v2.2.0-darwin-arm64.tar.gz",
        "sha256": "cd6cca74141a088a856fb8c55256ec61e798ab10ef2a24e68fb21d00cff013b9",
    }
    assert engines["darwin-x86_64"] == {
        "version": "2.2.0",
        "url": "https://github.com/hyung8758/Korean_FA/releases/download/koreanfa-engine-v2.2.0/koreanfa-engine-v2.2.0-darwin-x86_64.tar.gz",
        "sha256": "45a273853044191fe55221db933112766c36fe4abce4fdffeed8d4c8831a700d",
    }


def test_engine_candidate_uses_the_supported_glibc_baseline() -> None:
    workflow = (ROOT / ".github" / "workflows" / "engine-candidate.yml").read_text(encoding="utf-8")

    assert "quay.io/pypa/manylinux2014_x86_64" in workflow
    assert "KOREANFA_GLIBC_BASELINE=2.17" in workflow
    assert "yum --setopt=tsflags= reinstall -y devtoolset-10-gcc" in workflow


def test_linux_support_and_engine_troubleshooting_are_documented() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    korean_readme = (ROOT / "README.ko.md").read_text(encoding="utf-8")
    troubleshooting = (ROOT / "docs" / "troubleshooting.md").read_text(encoding="utf-8")
    source_manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")

    for document in (readme, korean_readme):
        assert "glibc 2.17" in document
        assert "Ubuntu 22.04 LTS" in document
        assert "24.04 LTS" in document
        assert "docs/troubleshooting.md" in document
    assert "sha256sum --check --strict" in troubleshooting
    assert "Do not bypass checksum verification" in troubleshooting
    assert "Alpine Linux and other musl-based distributions are not supported" in troubleshooting
    assert "include docs/troubleshooting.md" in source_manifest


def test_release_legal_documents_are_declared_in_package_metadata() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    third_party_notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    assert pyproject["project"]["license"] == "Apache-2.0 AND LicenseRef-Proprietary"
    assert pyproject["project"]["license-files"] == [
        "license",
        "THIRD_PARTY_NOTICES.md",
        "koreanfa/runtime/model/kor_model/NOTICE.md",
        "koreanfa/runtime/model/jap_model/NOTICE.md",
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
    assert "cv-corpus-26.0-2026-06-12" in japanese_notice
    assert "prohibit attempts to identify speakers" in japanese_notice
    assert "Mediazen" in korean_notice
    assert "commercial or non-commercial purposes" in korean_notice
    assert "may not modify" in korean_notice
    assert "may not redistribute" in korean_notice


def test_example_data_notices_and_japanese_fixtures_are_current() -> None:
    notice = (ROOT / "example" / "NOTICE.md").read_text(encoding="utf-8")
    japanese_directory = ROOT / "example" / "jap_files"
    expected_stems = {
        "covost2-native-ja-dev0004",
        "covost2-native-ja-train0008",
        "covost2-native-ja-train0252",
        "covost2-native-ja-train0602",
        "covost2-native-ja-train1056",
    }

    assert "서울말 낭독체 발화 말뭉치" in notice
    assert "Korea Open Government License Type 1" in notice
    assert "CoVoST 2 Native Japanese Dataset" in notice
    assert "Creative Commons Attribution 4.0 International" in notice
    assert "48 kHz mono MP3" in notice
    assert "16 kHz mono PCM WAV" in notice
    assert {path.stem for path in japanese_directory.glob("*.wav")} == expected_stems
    assert {path.stem for path in japanese_directory.glob("*.txt")} == expected_stems
    assert not list(japanese_directory.glob("csj-*"))


def test_korean_g2p_no_longer_ships_kog2p_sources() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert "ko-speech-tools[g2p]==0.1.0" in dependencies
    runtime_pipeline = ROOT / "koreanfa" / "runtime" / "pipeline"
    assert not (runtime_pipeline / "g2p.py").exists()
    assert not (runtime_pipeline / "rulebook.txt").exists()
    assert not (runtime_pipeline / "text2lexicon.py").exists()


def test_korean_phone_label_reference_documents_the_packaged_inventory() -> None:
    document = (ROOT / "docs" / "korean-phone-labels.md").read_text(encoding="utf-8")
    source_manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    english_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    korean_readme = (ROOT / "README.ko.md").read_text(encoding="utf-8")

    assert "`k0 xx nn xx nf`" in document
    assert "https://doi.org/10.13064/KSSS.2015.7.2.103" in document
    assert "KoreanFA does not bundle" in document
    assert "or use the KoG2P implementation." in document
    assert "include docs/korean-phone-labels.md" in source_manifest
    assert "include docs/japanese-romanization.md" in source_manifest
    assert "docs/korean-phone-labels.md" in english_readme
    assert "docs/korean-phone-labels.md" in korean_readme

    module = ast.parse((ROOT / "koreanfa" / "_korean_g2p.py").read_text(encoding="utf-8"))
    inventory = {
        value.value
        for assignment in ast.walk(module)
        if isinstance(assignment, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id in {"_ONSETS", "_VOWELS", "_CODAS"} for target in assignment.targets)
        and isinstance(assignment.value, ast.Tuple)
        for value in assignment.value.elts
        if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value
    }
    documented = set(re.findall(r"^\| `([^`]+)` \|", document, flags=re.MULTILINE))
    assert documented == inventory


def test_macos_engine_candidate_enforces_release_safety_policies() -> None:
    builder_entrypoint = (ROOT / "engine" / "build_macos.sh").read_text(encoding="utf-8")
    builder_helpers = (ROOT / "engine" / "macos_build_helpers.sh").read_text(encoding="utf-8")
    mecab_builder = (ROOT / "engine" / "macos_build_mecab.sh").read_text(encoding="utf-8")
    builder = "\n".join((builder_entrypoint, builder_helpers, mecab_builder))
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
    assert builder_entrypoint.index(gettext_formula_m4) < builder_entrypoint.index(gettext_homebrew_m4)
    assert builder_entrypoint.index("https://github.com/shogo82148/mecab.git") < builder_entrypoint.index(
        'make -j"$build_jobs"'
    )
    assert builder_entrypoint.index('download_archive "$ipadic_url"') < builder_entrypoint.index(
        'make -j"$build_jobs"'
    )
    assert builder_entrypoint.index("build_macos_mecab") < builder_entrypoint.index(
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
    assert "dicrc_charset(dictionary_dicrc)" in verifier
    assert '"日本語": ("ニホンゴ", "ニホンゴ")' in verifier
    assert "OPENBLAS.txt" in verifier
    assert "assert_code_signature(binary)" in verifier
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
    assert '("朝", "雨", "今", "晴れ")' in runtime_validator
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
