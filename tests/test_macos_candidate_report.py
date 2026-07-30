import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "koreanfa_macos_candidate_report", ROOT / "engine" / "candidate_report.py"
)
assert SPEC and SPEC.loader
CANDIDATE_REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CANDIDATE_REPORT)


@pytest.mark.parametrize(
    ("archive_reused", "status", "expected_status", "release_ready"),
    [
        (False, [], "PASS", True),
        (True, [], "PASS_DEVELOPMENT_ONLY", False),
        (False, [" M engine/build_macos.sh"], "PASS_DEVELOPMENT_ONLY", False),
        (True, [" M engine/build_macos.sh"], "PASS_DEVELOPMENT_ONLY", False),
    ],
)
def test_candidate_report_never_releases_a_reused_or_dirty_archive(
    archive_reused: bool,
    status: list[str],
    expected_status: str,
    release_ready: bool,
) -> None:
    report = CANDIDATE_REPORT.build_candidate_report(
        verification={"release_ready": True},
        runtime={"runtime_passed": True},
        git_head="a" * 40,
        git_status_porcelain=status,
        elapsed_seconds=1,
        homebrew_prefix="/opt/homebrew",
        archive_reused=archive_reused,
    )

    assert report["validation_status"] == expected_status
    assert report["release_ready"] is release_ready
    assert report["archive_reused"] is archive_reused


def test_candidate_report_preserves_failed_archive_verification() -> None:
    report = CANDIDATE_REPORT.build_candidate_report(
        verification={"release_ready": False},
        runtime={"runtime_passed": True},
        git_head="a" * 40,
        git_status_porcelain=[],
        elapsed_seconds=1,
        homebrew_prefix="/usr/local",
        archive_reused=False,
    )

    assert report["validation_status"] == "PASS_DEVELOPMENT_ONLY"
    assert report["release_ready"] is False
