"""Smoke-test a release archive before it is uploaded to GitHub Releases."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {Path(sys.argv[0]).name} ENGINE_ARCHIVE")
    archive = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="koreanfa-engine-check-") as temporary:
        root = Path(temporary)
        with tarfile.open(archive, "r:gz") as contents:
            contents.extractall(root, filter="data")
        engine_roots = [path for path in root.iterdir() if path.is_dir()]
        if len(engine_roots) != 1:
            raise RuntimeError("Engine archive must contain exactly one top-level directory.")
        engine = engine_roots[0]
        metadata = json.loads((engine / "engine.json").read_text(encoding="utf-8"))
        kaldi = engine / metadata["kaldi_dir"] / "src" / "bin" / "ali-to-phones"
        mecab = engine / metadata["mecab_command"]
        dictionary = engine / metadata["mecab_dict"]
        mecabrc = engine / metadata["mecabrc"]
        for required in (kaldi, mecab, dictionary, mecabrc):
            if not required.exists():
                raise RuntimeError(f"Missing required engine path: {required}")
        env = os.environ | {
            "MECABRC": str(mecabrc),
            "LD_LIBRARY_PATH": ":".join(str(engine / path) for path in metadata["library_paths"]),
        }
        mecab_result = subprocess.run(
            [mecab, "-d", dictionary], input="日本語の動作確認\n", text=True, capture_output=True, env=env, check=True
        )
        if "EOS" not in mecab_result.stdout:
            raise RuntimeError("Bundled MeCab did not return EOS.")
        # Supplying no input exits non-zero, but proves the binary and all of
        # its runtime libraries can be loaded without running an alignment.
        kaldi_result = subprocess.run([kaldi], text=True, capture_output=True, env=env, check=False)
        if kaldi_result.returncode not in (0, 1):
            raise RuntimeError(f"Bundled Kaldi executable could not run: {kaldi_result.stderr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
