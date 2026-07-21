from koreanfa.cli import build_parser


def test_cli_accepts_directory_alignment() -> None:
    args = build_parser().parse_args(["align-dir", "example/kor_files", "-j", "2"])
    assert args.command == "align-dir"
    assert args.num_jobs == 2


def test_cli_accepts_single_alignment() -> None:
    args = build_parser().parse_args(["align", "audio.wav", "audio.txt", "--no-phone"])
    assert args.command == "align"
    assert args.no_phone is True
