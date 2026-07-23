from koreanfa.resources import runtime_root


def test_source_tree_contains_runtime_resources() -> None:
    root = runtime_root()
    assert (root / "forced_align.sh").is_file()
    assert (root / "model" / "kor_model" / "final.mdl").is_file()
    assert (root / "model" / "jap_model" / "final.mdl").is_file()
    assert (root / "runtime" / "pipeline" / "main_fa.sh").is_file()
    assert (root / "runtime" / "pipeline" / "main_jap_fa.sh").is_file()
