"""Command-line interface for KoreanFA."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .aligner import Aligner
from .api import DEFAULT_NUM_JOBS
from .engine import install as install_engine
from .engine import remove as remove_engine
from .engine import status as engine_status
from .errors import EngineNotFoundError, EngineUnavailableError, KoreanFAError
from .result import AlignmentResult, AlignmentSkip, BatchAlignmentResult
from .validation import validate


class _CliProgress:
    """Small dependency-free progress display for shell-runtime events."""

    def __init__(self) -> None:
        self._interactive = sys.stderr.isatty()
        self._last_length = 0

    def __call__(self, phase: str, completed: int, total: int, detail: str) -> None:
        if phase == "summary":
            message = f"summary: {detail}"
        elif phase in {"preparing", "attempt"}:
            message = f"{phase}: {detail}"
        elif phase == "started":
            message = f"processing: {detail}"
        else:
            width = 24
            filled = round(width * completed / total) if total else 0
            message = f"[{('#' * filled).ljust(width, '-')}] {completed}/{total} {phase}: {detail}"
        if self._interactive and phase == "summary":
            sys.stderr.write(message + "\n")
            sys.stderr.flush()
            return
        if self._interactive:
            sys.stderr.write("\r" + message.ljust(self._last_length))
            sys.stderr.flush()
            self._last_length = len(message)
            if phase in {"completed", "failed", "skipped"} and completed == total:
                sys.stderr.write("\n")
        else:
            print(message, file=sys.stderr)


def _boolean_argument(value: str) -> bool:
    """Parse an explicit CLI boolean without introducing a second option name."""
    normalized = value.lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def _engine_install_progress(message: str) -> None:
    """Display engine download progress without making library calls noisy."""
    print(f"koreanfa: {message}", file=sys.stderr)


def _options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-l", "--lang", default="auto", help="Language adapter ID; use auto for Korean/Japanese detection")
    parser.add_argument("-o", "--output-dir", type=Path)
    parser.add_argument("-kd", "--kaldi-dir", type=Path)
    parser.add_argument("-nj", "--num-jobs", type=int, default=DEFAULT_NUM_JOBS)
    parser.add_argument("-r", "--recursive", action="store_true")
    parser.add_argument(
        "-iu", "--ignore-unmatched", dest="ignore_unmatched", type=_boolean_argument, nargs="?", const=True,
        default=True, metavar="{true,false}",
        help="Skip unmatched WAV/TXT files and report a warning (default: true)",
    )
    parser.add_argument("-nw", "--no-word", action="store_true")
    parser.add_argument("-np", "--no-phone", action="store_true")
    parser.add_argument("-nr", "--no-romanization", action="store_true", help="Omit the romanization tier")
    parser.add_argument("-kw", "--keep-workdir", action="store_true")
    parser.add_argument(
        "--existing", choices=("overwrite", "skip", "error"), default="overwrite",
        help="How to handle an existing TextGrid (default: overwrite)",
    )
    parser.add_argument(
        "--export", dest="exports", action="append", choices=("json", "csv", "ctm"), default=[],
        help="Write an additional format; may be repeated",
    )
    parser.add_argument(
        "--pronunciation-dictionary",
        type=Path,
        help="UTF-8 TSV overrides: language, word, pronunciation",
    )
    parser.add_argument("--report", type=Path, help="Write an atomic JSON execution report")
    parser.add_argument(
        "--quality-report",
        type=Path,
        help="Write TextGrid-based heuristic alignment diagnostics as JSON",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="koreanfa", description="Korean/Japanese forced alignment powered by Kaldi")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    align_parser = commands.add_parser("align", help="Align a WAV/TXT pair or a directory of pairs")
    align_parser.add_argument("input", type=Path, help="WAV file or corpus directory")
    align_parser.add_argument("transcript", nargs="?", type=Path, help="TXT transcript; required for a WAV input")
    _options(align_parser)
    directory_parser = commands.add_parser("align-dir", help="Alias for 'align DIRECTORY'")
    directory_parser.add_argument("input", type=Path)
    _options(directory_parser)

    validate_parser = commands.add_parser("validate", help="Check inputs and engine readiness without alignment")
    validate_parser.add_argument("input", type=Path, help="WAV file or corpus directory")
    validate_parser.add_argument("transcript", nargs="?", type=Path, help="TXT transcript; required for a WAV input")
    validate_parser.add_argument("-l", "--lang", default="auto")
    validate_parser.add_argument("-r", "--recursive", action="store_true")
    validate_parser.add_argument(
        "-iu", "--ignore-unmatched", dest="ignore_unmatched", type=_boolean_argument, nargs="?", const=True,
        default=True, metavar="{true,false}",
    )
    validate_parser.add_argument("--no-engine-check", action="store_true")
    validate_parser.add_argument("--strict", action="store_true", help="Treat warnings as a failed validation")
    validate_parser.add_argument(
        "--pronunciation-dictionary",
        type=Path,
        help="UTF-8 TSV overrides: language, word, pronunciation",
    )
    validate_parser.add_argument("--report", type=Path, help="Write an atomic JSON validation report")

    engine_parser = commands.add_parser("engine", help="Install and manage the local KoreanFA engine")
    engine_commands = engine_parser.add_subparsers(dest="engine_command", required=True)
    install_parser = engine_commands.add_parser("install", help="Download and install the compatible engine")
    install_parser.add_argument("-f", "--force", action="store_true", help="Replace an existing engine of the same version")
    engine_commands.add_parser("status", help="Show the compatible engine and its installation state")
    remove_parser = engine_commands.add_parser("remove", help="Remove the installed compatible engine")
    remove_parser.add_argument("-y", "--yes", action="store_true", help="Confirm engine removal")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "engine":
            if args.engine_command == "install":
                installed = install_engine(force=args.force, progress=_engine_install_progress)
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
        if args.command == "validate":
            report = validate(
                args.input,
                args.transcript,
                lang=args.lang,
                recursive=args.recursive,
                ignore_unmatched=args.ignore_unmatched,
                check_engine=not args.no_engine_check,
                report_path=args.report,
                pronunciation_dictionary=args.pronunciation_dictionary,
            )
            for issue in report.issues:
                location = f" {issue.path}" if issue.path else ""
                details = f" ({', '.join(issue.details)})" if issue.details else ""
                print(
                    f"koreanfa: {issue.severity}: {issue.code}:{location}: {issue.message}{details} {issue.suggestion}",
                    file=sys.stderr,
                )
            print(
                f"pairs={len(report.pairs)} errors={report.error_count} warnings={report.warning_count} "
                f"valid={str(report.valid).lower()}"
            )
            return 2 if not report.valid or (args.strict and report.warning_count) else 0
        aligner = Aligner(lang=args.lang, kaldi_dir=args.kaldi_dir, num_jobs=args.num_jobs)
        result: AlignmentResult | AlignmentSkip | BatchAlignmentResult
        if args.command == "align-dir" and not args.input.is_dir():
            raise ValueError(f"Input directory does not exist: {args.input.expanduser().resolve()}")
        if args.command == "align-dir" or args.input.is_dir():
            result = aligner.align(
                args.input,
                output_dir=args.output_dir,
                recursive=args.recursive,
                ignore_unmatched=args.ignore_unmatched,
                word_tier=not args.no_word,
                phone_tier=not args.no_phone,
                romanization_tier=not args.no_romanization,
                keep_workdir=args.keep_workdir,
                progress=_CliProgress(),
                existing=args.existing,
                exports=tuple(args.exports),
                report_path=args.report,
                quality_report_path=args.quality_report,
                pronunciation_dictionary=args.pronunciation_dictionary,
            )
        else:
            transcript: Path | None = getattr(args, "transcript", None)
            if transcript is None:
                raise ValueError("A WAV input requires its matching TXT transcript.")
            result = aligner.align(
                args.input,
                transcript,
                output_dir=args.output_dir,
                word_tier=not args.no_word,
                phone_tier=not args.no_phone,
                romanization_tier=not args.no_romanization,
                keep_workdir=args.keep_workdir,
                progress=_CliProgress(),
                existing=args.existing,
                exports=tuple(args.exports),
                report_path=args.report,
                quality_report_path=args.quality_report,
                pronunciation_dictionary=args.pronunciation_dictionary,
            )
        has_partial_failures = False
        if isinstance(result, BatchAlignmentResult):
            for item in result.results:
                print(item.textgrid)
            for failure in result.failures:
                print(f"koreanfa: failed {failure.audio.name}: {failure.reason}", file=sys.stderr)
            for skipped in result.skipped:
                print(f"koreanfa: skipped {skipped.audio.name}: {skipped.reason}", file=sys.stderr)
            has_partial_failures = bool(result.failures)
        else:
            print(result.textgrid)
            if isinstance(result, AlignmentSkip):
                print(f"koreanfa: skipped {result.audio.name}: {result.reason}", file=sys.stderr)
        if args.quality_report is not None:
            print(f"koreanfa: quality report: {args.quality_report}", file=sys.stderr)
        work_dir = getattr(result, "work_dir", None)
        if args.keep_workdir and work_dir:
            print(f"koreanfa: diagnostics: {work_dir}", file=sys.stderr)
        if has_partial_failures:
            return 2
    except EngineUnavailableError as error:
        print(f"koreanfa: error: {error}", file=sys.stderr)
        return 2
    except EngineNotFoundError as error:
        print(f"koreanfa: warning: {error}", file=sys.stderr)
        return 2
    except (KoreanFAError, OSError, ValueError) as error:
        print(f"koreanfa: error: {error}", file=sys.stderr)
        return 2
    return 0
