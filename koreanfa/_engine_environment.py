"""Environment composition shared by managed and external native engines."""


_LIBRARY_PATH_VARIABLES = frozenset({"LD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"})


def merge_engine_environment(environment: dict[str, str], engine_environment: dict[str, str]) -> None:
    """Add engine settings without discarding caller library paths."""
    for key, value in engine_environment.items():
        if key in _LIBRARY_PATH_VARIABLES:
            environment[key] = ":".join(filter(None, (value, environment.get(key))))
        else:
            environment.setdefault(key, value)
