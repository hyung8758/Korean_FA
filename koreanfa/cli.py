"""Command-line interface for KoreanFA."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .aligner import Aligner
from .engine import install as install_engine
from .engine import remove as remove_engine
from .engine import status as engine_status
from .errors import EngineNotFoundError, KoreanFAError


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

    engine_parser = commands.add_parser("engine", help="Install and manage the local KoreanFA engine")
    engine_commands = engine_parser.add_subparsers(dest="engine_command", required=True)
    install_parser = engine_commands.add_parser("install", help="Download and install the compatible engine")
    install_parser.add_argument("--force", action="store_true", help="Replace an existing engine of the same version")
    engine_commands.add_parser("status", help="Show the compatible engine and its installation state")
    remove_parser = engine_commands.add_parser("remove", help="Remove the installed compatible engine")
    remove_parser.add_argument("--yes", action="store_true", help="Confirm engine removal")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "engine":
            if args.engine_command == "install":
                installed = install_engine(force=args.force)
                print(f"Installed KoreanFA engine {installed.version} at {installed.root}")
            elif args.engine_command == "status":
                installed = engine_status()
                state = "installed" if installed.installed else "not installed"
                print(f"KoreanFA engine {installed.version} ({installed.platform}): {state}")
                if installed.installed:
                    print(installed.root)
            elif args.engine_command == "remove":
                if not args.yes:
                    raise ValueError("Engine removal requires --yes.")
                removed = remove_engine()
                print("Removed KoreanFA engine." if removed else "No KoreanFA engine was installed.")
            return 0
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
    except EngineNotFoundError as error:
        print(f"koreanfa: warning: {error}", file=sys.stderr)
        return 2
    except (KoreanFAError, ValueError) as error:
        print(f"koreanfa: error: {error}")
        return 2
    return 0
