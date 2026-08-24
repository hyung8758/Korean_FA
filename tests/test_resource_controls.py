import pytest

from koreanfa._resource_controls import apply_thread_limit, threads_per_job


def test_per_worker_thread_limit_defaults_to_one() -> None:
    assert threads_per_job({}) == 1


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "many", "", "３"])
def test_per_worker_thread_limit_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="KOREANFA_THREADS_PER_JOB"):
        threads_per_job({"KOREANFA_THREADS_PER_JOB": value})


def test_native_library_thread_limits_are_applied_consistently() -> None:
    environment = {"OMP_NUM_THREADS": "8", "UNRELATED": "keep"}

    apply_thread_limit(environment, 3)

    assert environment == {
        "OMP_NUM_THREADS": "3",
        "OPENBLAS_NUM_THREADS": "3",
        "MKL_NUM_THREADS": "3",
        "VECLIB_MAXIMUM_THREADS": "3",
        "NUMEXPR_NUM_THREADS": "3",
        "UNRELATED": "keep",
    }
