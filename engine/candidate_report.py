#!/usr/bin/env python3
"""Write the final macOS candidate report from verified build/runtime evidence."""

import argparse
import json
import platform
import subprocess
from pathlib import Path


def build_candidate_report(
    *,
    verification: dict[str, object],
    runtime: dict[str, object],
    git_head: str,
    git_status_porcelain: list[str],
    elapsed_seconds: int,
    homebrew_prefix: str,
    archive_reused: bool,
) -> dict[str, object]:
    """Combine evidence while preventing reused archives from becoming releases."""
    release_ready = bool(
        verification["release_ready"]
        and not git_status_porcelain
        and not archive_reused
    )
    return {
        "validation_status": "PASS" if release_ready else "PASS_DEVELOPMENT_ONLY",
        "release_ready": release_ready,
        "git_head": git_head,
        "git_status_porcelain": git_status_porcelain,
        "macos_version": platform.mac_ver()[0],
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "homebrew_prefix": homebrew_prefix,
        "elapsed_seconds": elapsed_seconds,
        "archive_reused": archive_reused,
        "verification": verification,
        "runtime": runtime,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verification", type=Path)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("repository", type=Path)
    parser.add_argument("elapsed_seconds", type=int)
    parser.add_argument("homebrew_prefix")
    parser.add_argument("archive_reused", choices=("true", "false"))
    args = parser.parse_args()

    verification = json.loads(
        args.verification.read_text(encoding="utf-8", errors="strict")
    )
    runtime = json.loads(args.runtime.read_text(encoding="utf-8", errors="strict"))
    status = subprocess.run(
        ["git", "-C", args.repository, "status", "--porcelain"],
        text=True,
        encoding="utf-8",
        errors="strict",
        capture_output=True,
        check=True,
    ).stdout.splitlines()
    git_head = subprocess.run(
        ["git", "-C", args.repository, "rev-parse", "HEAD"],
        text=True,
        encoding="ascii",
        errors="strict",
        capture_output=True,
        check=True,
    ).stdout.strip()
    report = build_candidate_report(
        verification=verification,
        runtime=runtime,
        git_head=git_head,
        git_status_porcelain=status,
        elapsed_seconds=args.elapsed_seconds,
        homebrew_prefix=args.homebrew_prefix,
        archive_reused=args.archive_reused == "true",
    )
    args.destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        errors="strict",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
