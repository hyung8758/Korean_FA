"""Command-line interface for KoreanFA."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .aligner import Aligner
from .errors import KoreanFAError


def _options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--lang", choices=("auto", "kor", "jap"), default="auto", help="Model language (default: auto)")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--kaldi-dir", type=Path)
    parser.add_argument("-j", "--num-jobs", type=int, default=1)
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--allow-unmatched", action="store_true")
    parser.add_argument("--no-word", action="store_true")
    parser.add_argument("--no-phone", action="store_true")
    parser.add_argument("--keep-workdir", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koreanfa", description="Korean/Japanese forced alignment powered by Kaldi")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    align_parser = commands.add_parser("align", help="Align a WAV/TXT pair or a directory of pairs")
    align_parser.add_argument("input", type=Path, help="WAV file or corpus directory")
    align_parser.add_argument("transcript", nargs="?", type=Path, help="TXT transcript; required for a WAV input")
    _options(align_parser)
    directory_parser = commands.add_parser("align-dir", help="Alias for 'align DIRECTORY'")
    directory_parser.add_argument("input", type=Path)
    _options(directory_parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        aligner = Aligner(lang=args.lang, kaldi_dir=args.kaldi_dir, num_jobs=args.num_jobs)
        options = {
            "output_dir": args.output_dir,
            "word_tier": not args.no_word,
            "phone_tier": not args.no_phone,
            "keep_workdir": args.keep_workdir,
        }
        if args.input.is_dir():
            options["recursive"] = args.recursive
            options["strict"] = not args.allow_unmatched
        result = aligner.align(args.input, args.transcript, **options)
        if hasattr(result, "results"):
            for item in result.results:
                print(item.textgrid)
        else:
            print(result.textgrid)
    except (KoreanFAError, ValueError) as error:
        print(f"koreanfa: error: {error}")
        return 2
    return 0
