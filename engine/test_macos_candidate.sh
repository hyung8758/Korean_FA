#!/usr/bin/env bash
# Build and validate one native macOS engine through the same install and
# alignment paths that KoreanFA users run.
#
# Usage: engine/test_macos_candidate.sh OUTPUT_DIRECTORY ENGINE_VERSION

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 OUTPUT_DIRECTORY ENGINE_VERSION" >&2
  exit 2
fi
engine_version=$2
if [[ ! $engine_version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ENGINE_VERSION must use X.Y.Z format: $engine_version" >&2
  exit 2
fi

if [[ $(uname -s) != Darwin ]]; then
  echo "This integration test must run on macOS." >&2
  exit 2
fi

script_directory=$(cd "$(dirname "$0")" && pwd -P)
repository_root=$(cd "$script_directory/.." && pwd -P)
output_argument=$1
mkdir -p "$output_argument"
output_directory=$(cd "$output_argument" && pwd -P)
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

started_seconds=$(date +%s)
source_revision=$(git -C "$repository_root" rev-parse --verify HEAD)
homebrew_prefix=$(brew --prefix)
temporary_directory=$(mktemp -d "${TMPDIR:-/tmp}/koreanfa-macos-test.XXXXXX")
http_server_pid=
cleanup() {
  if [[ -n $http_server_pid ]]; then
    set +e
    kill "$http_server_pid"
    wait "$http_server_pid"
    set -e
  fi
  rm -rf "$temporary_directory"
}
trap cleanup EXIT
unicode_root="$temporary_directory/설치 경로 KoreanFA 日本語"
mkdir -p "$temporary_directory/tmp" "$unicode_root"
export TMPDIR="$temporary_directory/tmp"
archive="$output_directory/koreanfa-engine-v${engine_version}-${platform}.tar.gz"
manifest="$unicode_root/engine manifest 日本語.json"
engine_home="$unicode_root/엔진 설치 日本語"
virtual_environment="$temporary_directory/venv"
runtime_workspace="$unicode_root/소스와 분리된 작업 日本語"
results="$unicode_root/런타임 결과 日本語"
port_file="$unicode_root/http-port"
http_log="$output_directory/http-install.log"
runtime_log="$output_directory/runtime-validation.log"
runtime_report="$output_directory/runtime-report.json"
verification_report="$output_directory/verification-report.json"
otool_summary="$output_directory/otool-dependencies.txt"
review_results="$output_directory/TextGrid-results-${source_revision:0:12}"
archive_reused=false

if [[ ${KOREANFA_REUSE_ARCHIVE:-0} == 1 ]]; then
  echo "[1/7] Reusing an existing development archive: ${platform} ${engine_version}"
  [[ ${KOREANFA_ALLOW_DIRTY_BUILD:-0} == 1 ]] || {
    echo "KOREANFA_REUSE_ARCHIVE is only allowed for an explicitly dirty development validation." >&2
    exit 2
  }
  [[ -f $archive && -f $archive.sha256 ]] || {
    echo "The requested reusable archive and checksum are unavailable: $archive" >&2
    exit 2
  }
  archive_reused=true
else
  echo "[1/7] Building ${platform} engine ${engine_version}"
  KOREANFA_PYTHON="$python_command" \
    bash "$script_directory/build_macos.sh" "$output_directory" "$engine_version"
fi

echo "[2/7] Validating archive structure and Mach-O dependencies"
KOREANFA_EXPECTED_SOURCE_REVISION="$source_revision" \
  KOREANFA_VERIFICATION_REPORT="$verification_report" \
  KOREANFA_OTOOL_SUMMARY="$otool_summary" \
  "$python_command" "$script_directory/verify_macos.py" "$archive"
(cd "$output_directory" && shasum -a 256 --check "$(basename "$archive.sha256")")

echo "[3/7] Creating an isolated source installation"
"$python_command" -m venv "$virtual_environment"
"$virtual_environment/bin/python" -m pip install --upgrade pip
(cd "$repository_root" && "$virtual_environment/bin/python" -m pip install .)
"$virtual_environment/bin/python" -m pip check

echo "[4/7] Installing through loopback HTTP with SHA-256 verification"
"$virtual_environment/bin/python" "$script_directory/candidate_http_server.py" \
  "$output_directory" "$port_file" >"$http_log" 2>&1 &
http_server_pid=$!
port=
for (( attempt = 1; attempt <= 100; attempt++ )); do
  if [[ -s $port_file ]]; then
    port=$(<"$port_file")
    break
  fi
  sleep 0.1
done
[[ $port =~ ^[0-9]+$ ]] || {
  echo "Candidate HTTP server did not publish a port." >&2
  exit 1
}
"$virtual_environment/bin/python" - "$archive" "$manifest" "$platform" "$engine_version" "$port" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

archive, manifest = map(Path, sys.argv[1:3])
platform, version, port = sys.argv[3:6]
manifest.write_text(
    json.dumps(
        {
            "schema_version": 1,
            "engines": {
                platform: {
                    "version": version,
                    "url": f"http://127.0.0.1:{port}/{archive.name}",
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
set +e
kill "$http_server_pid"
wait "$http_server_pid"
http_status=$?
set -e
http_server_pid=
[[ $http_status -eq 0 || $http_status -eq 143 ]] || {
  echo "Candidate HTTP server exited unexpectedly: $http_status" >&2
  exit 1
}
grep -Eq 'GET /koreanfa-engine-.*HTTP/1\.[01]" 200 ' "$http_log"

# The archive server is now offline. Runtime PATH retains only the isolated
# venv and Apple system tools, proving that no Homebrew Kaldi or MeCab is used.
export PATH="$virtual_environment/bin:/usr/bin:/bin:/usr/sbin:/sbin"
unset PYTHONPATH
echo "[5/7] Running CLI and Python API validation three times with the installed engine"
"$virtual_environment/bin/python" "$script_directory/validate_candidate_runtime.py" \
  "$repository_root" "$runtime_workspace" "$results" "$virtual_environment/bin/koreanfa" \
  "$script_directory/fixtures/alignment_labels.json" "$runtime_log" "$runtime_report"

echo "[6/7] Validating repeat counts and stable semantic label sequences"
"$virtual_environment/bin/python" - "$runtime_report" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if report["repeats"] != 3 or report["total_textgrids"] != 66:
    raise RuntimeError(f"Runtime repetition totals changed: {report}")
if any(item != {"success": 22, "failed": 2, "textgrids": 22} for item in report["counts_per_repeat"]):
    raise RuntimeError(f"Runtime success/failure counts were unstable: {report}")
print(f"Stable labels SHA-256: {report['stable_label_sequence_sha256']}")
PY

echo "[7/7] Collecting persistent review artifacts"
installed_root="$engine_home/$engine_version/$platform"
mecab="$installed_root/mecab/bin/mecab"
dictionary="$installed_root/mecab/lib/mecab/dic/ipadic"
set +e
MECABRC="$installed_root/mecab/etc/mecabrc" "$mecab" -d "$dictionary" -D \
  > "$output_directory/mecab-dictionary.txt" 2> "$output_directory/mecab-dictionary.stderr"
mecab_details_status=$?
set -e
[[ $mecab_details_status -eq 0 || $mecab_details_status -eq 1 ]]
printf '日本語の動作確認\n' | \
  MECABRC="$installed_root/mecab/etc/mecabrc" "$mecab" -d "$dictionary" \
  > "$output_directory/mecab-direct-output.txt"
[[ ! -e $review_results ]] || {
  echo "Review result directory already exists: $review_results" >&2
  exit 1
}
cp -R "$results" "$review_results"

finished_seconds=$(date +%s)
elapsed_seconds=$((finished_seconds - started_seconds))
"$virtual_environment/bin/python" - \
  "$verification_report" "$runtime_report" "$output_directory/candidate-report.json" \
  "$repository_root" "$elapsed_seconds" "$homebrew_prefix" "$archive_reused" <<'PY'
import json
import platform
import subprocess
import sys
from pathlib import Path

verification_path, runtime_path, destination, repository, elapsed, homebrew_prefix, archive_reused = sys.argv[1:]
verification = json.loads(Path(verification_path).read_text(encoding="utf-8"))
runtime = json.loads(Path(runtime_path).read_text(encoding="utf-8"))
status = subprocess.run(
    ["git", "-C", repository, "status", "--porcelain"], text=True, capture_output=True, check=True
).stdout.splitlines()
report = {
    "validation_status": "PASS" if verification["release_ready"] and not status else "PASS_DEVELOPMENT_ONLY",
    "release_ready": bool(verification["release_ready"] and not status),
    "git_head": subprocess.run(
        ["git", "-C", repository, "rev-parse", "HEAD"], text=True, capture_output=True, check=True
    ).stdout.strip(),
    "git_status_porcelain": status,
    "macos_version": platform.mac_ver()[0],
    "machine": platform.machine(),
    "python_version": platform.python_version(),
    "homebrew_prefix": homebrew_prefix,
    "elapsed_seconds": int(elapsed),
    "archive_reused": archive_reused == "true",
    "verification": verification,
    "runtime": runtime,
}
Path(destination).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
PY
{
  printf 'HEAD=%s\n' "$source_revision"
  printf 'branch=%s\n' "$(git -C "$repository_root" branch --show-current)"
  printf 'status_porcelain:\n'
  git -C "$repository_root" status --porcelain
} > "$output_directory/git-head-and-status.txt"

printf 'macOS candidate passed: %s\nArchive: %s\nChecksum: %s.sha256\n' \
  "$platform" "$archive" "$archive"
