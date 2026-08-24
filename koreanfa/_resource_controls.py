"""Bound native-library thread use for file-level alignment workers."""

from collections.abc import Mapping

_THREAD_ENVIRONMENT = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def threads_per_job(environment: Mapping[str, str]) -> int:
    """Read the optional advanced per-worker thread limit from the environment."""
    raw_value = environment.get("KOREANFA_THREADS_PER_JOB", "1")
    if not raw_value.isascii() or not raw_value.isdecimal() or int(raw_value) < 1:
        raise ValueError("KOREANFA_THREADS_PER_JOB must be a positive integer")
    return int(raw_value)


def apply_thread_limit(environment: dict[str, str], limit: int) -> None:
    """Set every relevant numerical-library limit consistently for one worker."""
    value = str(limit)
    for name in _THREAD_ENVIRONMENT:
        environment[name] = value
