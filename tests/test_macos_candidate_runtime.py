import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine"
SPEC = importlib.util.spec_from_file_location(
    "koreanfa_macos_candidate_runtime", ENGINE / "validate_candidate_runtime.py"
)
assert SPEC and SPEC.loader
sys.path.insert(0, str(ENGINE))
try:
    CANDIDATE_RUNTIME = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(CANDIDATE_RUNTIME)
finally:
    sys.path.pop(0)


def _write_partial_diagnostics(root: Path) -> Path:
    logs = root / "jap-diagnostics" / "logs"
    process = logs / "log_pair_1" / "process.pair_1.log"
    process.parent.mkdir(parents=True)
    (logs / "summary.tsv").write_text(
        "total\t2\nsuccess\t1\nfailed\t1\n", encoding="utf-8"
    )
    process.write_text("koreanfa: error: Transcript is empty: 실패 失敗.txt\n", encoding="utf-8")
    return process


def test_partial_failure_helpers_validate_cli_and_diagnostics(tmp_path: Path) -> None:
    _write_partial_diagnostics(tmp_path)
    failed_name = "실패 失敗.wav"
    stderr = (
        f"koreanfa: failed {failed_name}: rejected transcript\n"
        f"koreanfa: diagnostics: {tmp_path}\n"
    )

    assert CANDIDATE_RUNTIME._partial_failure_reason(stderr, failed_name) == "rejected transcript"
    assert CANDIDATE_RUNTIME._cli_diagnostics_root(stderr) == tmp_path
    CANDIDATE_RUNTIME._assert_partial_diagnostics(tmp_path)


def test_partial_diagnostics_reject_non_utf8_process_log(tmp_path: Path) -> None:
    process = _write_partial_diagnostics(tmp_path)
    process.write_bytes(b"\xff")

    with pytest.raises(UnicodeDecodeError):
        CANDIDATE_RUNTIME._assert_partial_diagnostics(tmp_path)


def test_partial_diagnostics_requires_summary_and_failed_pair_log(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)

    with pytest.raises(RuntimeError, match="summary.tsv"):
        CANDIDATE_RUNTIME._assert_partial_diagnostics(tmp_path)
