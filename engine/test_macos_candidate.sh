#!/usr/bin/env bash
# Build and validate one native macOS engine through the same install and
# alignment paths that KoreanFA users run.
#
# Usage: engine/test_macos_candidate.sh [OUTPUT_DIRECTORY] [ENGINE_VERSION]

set -euo pipefail

if [[ $(uname -s) != Darwin ]]; then
  echo "This integration test must run on macOS." >&2
  exit 2
fi

script_directory=$(cd "$(dirname "$0")" && pwd -P)
repository_root=$(cd "$script_directory/.." && pwd -P)
output_argument=${1:-$repository_root/build/macos-engine}
mkdir -p "$output_argument"
output_directory=$(cd "$output_argument" && pwd -P)
engine_version=${2:-2.0.1}
python_command=${KOREANFA_PYTHON:-python3}

command -v "$python_command" >/dev/null || {
  echo "Python command is unavailable: $python_command" >&2
  exit 2
}
"$python_command" -c 'import sys; raise SystemExit(sys.version_info < (3, 12))' || {
  echo "KoreanFA requires Python 3.12 or newer." >&2
  exit 2
}

case $(uname -m) in
  x86_64) platform=darwin-x86_64 ;;
  arm64) platform=darwin-arm64 ;;
  *) echo "Unsupported macOS architecture: $(uname -m)" >&2; exit 2 ;;
esac

temporary_directory=$(mktemp -d "${TMPDIR:-/tmp}/koreanfa-macos-test.XXXXXX")
trap 'rm -rf "$temporary_directory"' EXIT
archive="$output_directory/koreanfa-engine-v${engine_version}-${platform}.tar.gz"
manifest="$temporary_directory/engine-manifest.json"
engine_home="$temporary_directory/engine-home"
virtual_environment="$temporary_directory/venv"
results="$temporary_directory/results"

echo "[1/7] Building ${platform} engine ${engine_version}"
KOREANFA_PYTHON="$python_command" \
  bash "$script_directory/build_macos.sh" "$output_directory" "$engine_version"

echo "[2/7] Validating archive structure and Mach-O dependencies"
"$python_command" "$script_directory/verify_macos.py" "$archive"

echo "[3/7] Creating an isolated source installation"
"$python_command" -m venv "$virtual_environment"
"$virtual_environment/bin/python" -m pip install --upgrade pip
"$virtual_environment/bin/python" -m pip install "$repository_root"
"$virtual_environment/bin/python" -m pip check

echo "[4/7] Installing the candidate through 'koreanfa engine install'"
"$virtual_environment/bin/python" - "$archive" "$manifest" "$platform" "$engine_version" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

archive, manifest = map(Path, sys.argv[1:3])
platform, version = sys.argv[3:5]
manifest.write_text(
    json.dumps(
        {
            "schema_version": 1,
            "engines": {
                platform: {
                    "version": version,
                    "url": archive.resolve().as_uri(),
                    "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                }
            },
        },
        indent=2,
    ),
    encoding="utf-8",
)
PY
export KOREANFA_ENGINE_MANIFEST="$manifest"
export KOREANFA_ENGINE_HOME="$engine_home"
"$virtual_environment/bin/koreanfa" engine install
"$virtual_environment/bin/koreanfa" engine status

mkdir -p "$results"
echo "[5/7] Running Korean and Japanese CLI alignment"
"$virtual_environment/bin/koreanfa" align \
  "$repository_root/example/kor_files/fv01_t01_s01.wav" \
  "$repository_root/example/kor_files/fv01_t01_s01.txt" \
  --lang kor --output-dir "$results/cli-kor-single"
"$virtual_environment/bin/koreanfa" align \
  "$repository_root/example/jap_files/csj-0001-me-0001.wav" \
  "$repository_root/example/jap_files/csj-0001-me-0001.txt" \
  --lang auto --output-dir "$results/cli-jap-single"
"$virtual_environment/bin/koreanfa" align-dir \
  "$repository_root/example/kor_files" --lang auto --output-dir "$results/cli-kor-directory"
"$virtual_environment/bin/koreanfa" align-dir \
  "$repository_root/example/jap_files" --lang jap --output-dir "$results/cli-jap-directory"

echo "[6/7] Running Korean and Japanese Python API alignment"
KOREANFA_REPOSITORY_ROOT="$repository_root" KOREANFA_TEST_RESULTS="$results" \
  "$virtual_environment/bin/python" - <<'PY'
import os
from pathlib import Path

from koreanfa import align, align_directory

root = Path(os.environ["KOREANFA_REPOSITORY_ROOT"])
results = Path(os.environ["KOREANFA_TEST_RESULTS"])
kor = root / "example" / "kor_files"
jap = root / "example" / "jap_files"

assert align(
    kor / "fv01_t01_s01.wav",
    kor / "fv01_t01_s01.txt",
    lang="auto",
    output_dir=results / "api-kor-single",
).textgrid.is_file()
assert align(
    jap / "csj-0001-me-0001.wav",
    jap / "csj-0001-me-0001.txt",
    lang="jap",
    output_dir=results / "api-jap-single",
).textgrid.is_file()
assert len(align_directory(kor, lang="kor", output_dir=results / "api-kor-directory").results) == 3
assert len(align_directory(jap, lang="auto", output_dir=results / "api-jap-directory").results) == 5
PY

echo "[7/7] Checking every generated TextGrid"
KOREANFA_TEST_RESULTS="$results" "$virtual_environment/bin/python" - <<'PY'
import os
from pathlib import Path

results = Path(os.environ["KOREANFA_TEST_RESULTS"])
textgrids = sorted(results.rglob("*.TextGrid"))
if len(textgrids) != 20:
    raise RuntimeError(f"Expected 20 TextGrid files, received {len(textgrids)}")
for textgrid in textgrids:
    contents = textgrid.read_text(encoding="utf-8")
    # KoreanFA currently emits Praat's short TextGrid form.  Accept either
    # short or long syntax while requiring a real interval tier.
    if not contents.startswith('File type = "ooTextFile') or "<exists>" not in contents or '"IntervalTier"' not in contents:
        raise RuntimeError(f"Invalid TextGrid: {textgrid}")
print(f"Validated {len(textgrids)} TextGrid files.")
PY

printf 'macOS candidate passed: %s\nArchive: %s\nChecksum: %s.sha256\n' \
  "$platform" "$archive" "$archive"
