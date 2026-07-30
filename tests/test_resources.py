from koreanfa.resources import runtime_root


def test_source_tree_contains_runtime_resources() -> None:
    root = runtime_root()
    assert (root / "pipeline" / "forced_align.sh").is_file()
    assert (root / "model" / "kor_model" / "final.mdl").is_file()
    assert (root / "model" / "jap_model" / "final.mdl").is_file()
    assert (root / "pipeline" / "main_fa.sh").is_file()
    assert (root / "pipeline" / "prepare.sh").is_file()
    assert (root / "languages" / "kor" / "profile.sh").is_file()
    assert (root / "languages" / "jap" / "profile.sh").is_file()
    assert (root / "languages" / "jap" / "kana2phone").is_file()
    assert (root / "languages" / "jap" / "vocab2dic.pl").is_file()
