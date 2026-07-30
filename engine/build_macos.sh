#!/usr/bin/env bash
# Build one relocatable macOS KoreanFA runtime on its native CPU architecture.
#
# Usage: engine/build_macos.sh OUTPUT_DIRECTORY ENGINE_VERSION
#
# This script deliberately does not cross-compile.  Run it once on an Intel
# Mac and once on an Apple Silicon Mac to produce darwin-x86_64 and
# darwin-arm64 archives respectively.  The final user archive contains the
# Kaldi programs, OpenFST, MeCab, IPADIC, required non-system dylibs,
# and their notices; users do not need Homebrew, Kaldi, or MeCab installed.

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
  echo "This builder must run on macOS; current host is $(uname -s)-$(uname -m)." >&2
  exit 2
fi

case $(uname -m) in
  x86_64) architecture=x86_64 ;;
  arm64) architecture=arm64 ;;
  *)
    echo "Unsupported macOS CPU architecture: $(uname -m)." >&2
    exit 2
    ;;
esac

script_directory=$(cd "$(dirname "$0")" && pwd -P)
repository_root=$(cd "$script_directory/.." && pwd -P)
source_revision=$(git -C "$repository_root" rev-parse --verify HEAD)
source_tracked_files_clean=true
if ! git -C "$repository_root" diff --quiet --ignore-submodules -- || \
   ! git -C "$repository_root" diff --cached --quiet --ignore-submodules --; then
  source_tracked_files_clean=false
fi
if [[ $source_tracked_files_clean == false && ${KOREANFA_ALLOW_DIRTY_BUILD:-0} != 1 ]]; then
  echo "Refusing to build a release engine with uncommitted changes to tracked files." >&2
  echo "Commit the reviewed source first, or set KOREANFA_ALLOW_DIRTY_BUILD=1 for a non-release development build." >&2
  exit 2
fi

python_command=${KOREANFA_PYTHON:-python3}
for command in autoconf automake brew clang clang++ codesign curl git glibtoolize install_name_tool lipo make otool shasum strip tar "$python_command"; do
  command -v "$command" >/dev/null || {
    echo "Missing required macOS build command: $command" >&2
    exit 2
  }
done
gettext_m4_directory="$(brew --prefix gettext)/share/gettext/m4"
[[ -d $gettext_m4_directory ]] || {
  echo "Homebrew gettext development files are unavailable. Run 'brew install gettext'." >&2
  exit 2
}
export ACLOCAL_PATH="$gettext_m4_directory${ACLOCAL_PATH:+:$ACLOCAL_PATH}"

mkdir -p "$1"
output_directory=$(cd "$1" && pwd -P)
platform="darwin-${architecture}"
minimum_macos=12.0
build_jobs=${KOREANFA_BUILD_JOBS:-$(sysctl -n hw.ncpu)}
kaldi_revision=e02e35f0254bb033fab73d1df99fc34123e31d56
openfst_version=1.8.4
openfst_url=https://storage.googleapis.com/rime-public/mirror/openfst-1.8.4.tar.gz
openfst_sha256=a8ebbb6f3d92d07e671500587472518cfc87cb79b9a654a5a8abb2d0eb298016
mecab_revision=cd22ce53d855a1cda1acfcb680c9e82c5de39a94
ipadic_url=https://downloads.sourceforge.net/project/mecab/mecab-ipadic/2.7.0-20070801/mecab-ipadic-2.7.0-20070801.tar.gz
ipadic_sha256=b62f527d881c504576baed9c6ef6561554658b175ce6ae0096a60307e49e3523

export MACOSX_DEPLOYMENT_TARGET="$minimum_macos"
export CC="${CC:-clang}"
export CXX="${CXX:-clang++}"
export CFLAGS="${CFLAGS:-} -mmacosx-version-min=${minimum_macos}"
export CXXFLAGS="${CXXFLAGS:-} -mmacosx-version-min=${minimum_macos}"
export LDFLAGS="${LDFLAGS:-} -mmacosx-version-min=${minimum_macos}"

mkdir -p "$output_directory"
work_directory=$(mktemp -d)
trap 'rm -rf "$work_directory"' EXIT
engine_name="koreanfa-engine-v${engine_version}-${platform}"
engine_root="$work_directory/$engine_name"
kaldi_source="$work_directory/kaldi"
openfst_archive="$work_directory/openfst-${openfst_version}.tar.gz"
openfst_source="$work_directory/openfst-${openfst_version}"
mecab_source="$work_directory/mecab"
mecab_root="$work_directory/mecab-root"
ipadic_archive="$work_directory/mecab-ipadic.tar.gz"
iconv_probe_source="$work_directory/iconv-euc-jp-probe.c"
iconv_probe="$work_directory/iconv-euc-jp-probe"

copy_file() {
  local source=$1 destination=$2
  mkdir -p "$(dirname "$destination")"
  cp -pL "$source" "$destination"
}

fetch_git_revision() {
  local repository=$1 revision=$2 destination=$3 label=$4
  local attempt=1 maximum_attempts=5 retry_delay actual_revision

  mkdir -p "$destination"
  git -C "$destination" init --quiet
  git -C "$destination" remote add origin "$repository"

  while (( attempt <= maximum_attempts )); do
    if git -c http.version=HTTP/1.1 -C "$destination" fetch \
      --quiet --depth=1 --no-tags origin "$revision"; then
      git -C "$destination" checkout --quiet --detach FETCH_HEAD
      actual_revision=$(git -C "$destination" rev-parse HEAD)
      if [[ $actual_revision == "$revision" ]]; then
        return 0
      fi
      echo "Fetched unexpected ${label} revision: ${actual_revision}." >&2
      return 1
    fi

    if (( attempt == maximum_attempts )); then
      echo "Failed to fetch ${label} revision ${revision} after ${maximum_attempts} attempts." >&2
      return 1
    fi
    retry_delay=$((attempt * 5))
    echo "Retrying ${label} source download in ${retry_delay} seconds (${attempt}/${maximum_attempts})..." >&2
    sleep "$retry_delay"
    attempt=$((attempt + 1))
  done
}

download_archive() {
  local url=$1 destination=$2 label=$3
  curl --fail --location --silent --show-error \
    --connect-timeout 30 --retry 5 --retry-delay 3 --retry-all-errors \
    --output "$destination" "$url" || {
      echo "Failed to download ${label}: ${url}" >&2
      return 1
    }
}

is_system_library() {
  case $1 in
    /System/Library/*|/usr/lib/*|/Library/Apple/*) return 0 ;;
    *) return 1 ;;
  esac
}

macho_dependencies() {
  otool -L "$1" | awk 'NR > 1 { print $1 }'
}

macho_rpaths() {
  otool -l "$1" | awk '
    $1 == "cmd" && $2 == "LC_RPATH" { wanted = 1; next }
    wanted && $1 == "path" { print $2; wanted = 0 }
  '
}

resolve_macho_dependency() {
  local owner=$1 dependency=$2 rpath candidate
  case $dependency in
    /*)
      [[ -f $dependency ]] && { printf '%s\n' "$dependency"; return 0; }
      ;;
    @loader_path/*)
      candidate="$(dirname "$owner")/${dependency#@loader_path/}"
      [[ -f $candidate ]] && { printf '%s\n' "$candidate"; return 0; }
      ;;
    @executable_path/*)
      candidate="$engine_root/${dependency#@executable_path/}"
      [[ -f $candidate ]] && { printf '%s\n' "$candidate"; return 0; }
      ;;
    @rpath/*)
      while IFS= read -r rpath; do
        rpath=${rpath/@loader_path/$(dirname "$owner")}
        rpath=${rpath/@executable_path/$engine_root}
        candidate="$rpath/${dependency#@rpath/}"
        [[ -f $candidate ]] && { printf '%s\n' "$candidate"; return 0; }
      done < <(macho_rpaths "$owner")
      ;;
  esac
  return 1
}

relative_path() {
  "$python_command" - "$1" "$2" <<'PY'
import os
import sys
print(os.path.relpath(sys.argv[2], os.path.dirname(sys.argv[1])))
PY
}

assert_architecture() {
  local binary=$1 actual
  actual=$(lipo -archs "$binary")
  grep -qw "$architecture" <<<"$actual" || {
    echo "Expected ${architecture} Mach-O binary, received '${actual}': $binary" >&2
    exit 1
  }
}

packaged_macho_files() {
  find "$engine_root/kaldi" -type f -perm -u+x -print
  find "$engine_root/lib" -type f -name '*.dylib*' -print
}

final_macho_files() {
  packaged_macho_files
  [[ ! -f $engine_root/mecab/bin/mecab ]] || printf '%s\n' "$engine_root/mecab/bin/mecab"
}

# Resolve every network dependency before starting the expensive native build.
# This prevents a transient MeCab or IPADIC download failure from discarding a
# completed Kaldi build. Exact shallow fetches also avoid cloning full history.
fetch_git_revision \
  https://github.com/kaldi-asr/kaldi.git "$kaldi_revision" "$kaldi_source" Kaldi
fetch_git_revision \
  https://github.com/shogo82148/mecab.git "$mecab_revision" "$mecab_source" MeCab
download_archive "$openfst_url" "$openfst_archive" OpenFST
printf '%s  %s\n' "$openfst_sha256" "$openfst_archive" | shasum -a 256 --check --status
download_archive "$ipadic_url" "$ipadic_archive" IPADIC
printf '%s  %s\n' "$ipadic_sha256" "$ipadic_archive" | shasum -a 256 --check --status

# Validate and build the macOS-specific MeCab path before the expensive Kaldi
# compilation. gettext's generic AM_ICONV runtime probe rejects some Apple
# iconv implementations for conversions that KoreanFA never uses. Prove the
# required EUC-JP -> UTF-8 conversion directly, then cache that targeted result
# for MeCab's configure script. The UTF-8 dictionary smoke test below remains
# the final authority and fails the build if the conversion is not usable.
cat > "$iconv_probe_source" <<'C'
#include <iconv.h>
#include <stddef.h>
#include <string.h>

int main(void) {
  unsigned char input[] = {
    0xc6, 0xfc, 0xcb, 0xdc, 0xb8, 0xec, 0xa4, 0xce,
    0xc6, 0xb0, 0xba, 0xee, 0xb3, 0xce, 0xc7, 0xa7
  };
  const unsigned char expected[] = {
    0xe6, 0x97, 0xa5, 0xe6, 0x9c, 0xac, 0xe8, 0xaa,
    0x9e, 0xe3, 0x81, 0xae, 0xe5, 0x8b, 0x95, 0xe4,
    0xbd, 0x9c, 0xe7, 0xa2, 0xba, 0xe8, 0xaa, 0x8d
  };
  char output[64] = {0};
  char *input_pointer = (char *)input;
  char *output_pointer = output;
  size_t input_left = sizeof(input);
  size_t output_left = sizeof(output);
  iconv_t converter = iconv_open("UTF-8", "EUC-JP");
  if (converter == (iconv_t)-1) return 1;
  if (iconv(converter, &input_pointer, &input_left,
            &output_pointer, &output_left) == (size_t)-1) return 2;
  if (iconv_close(converter) != 0) return 3;
  if (input_left != 0 || sizeof(output) - output_left != sizeof(expected)) return 4;
  return memcmp(output, expected, sizeof(expected)) == 0 ? 0 : 5;
}
C
"$CC" -mmacosx-version-min="$minimum_macos" "$iconv_probe_source" -o "$iconv_probe"
"$iconv_probe" || {
  echo 'macOS system iconv cannot convert the EUC-JP input required by IPADIC.' >&2
  exit 1
}

(
  cd "$mecab_source/mecab"
  ./autogen.sh
  # IPADIC sources are EUC-JP and must be converted by MeCab's iconv support.
  # Keep conversion enabled and compile UTF-8 scanning with unsigned bytes.
  am_cv_func_iconv_works=yes \
    CFLAGS="${CFLAGS:-} -funsigned-char" \
    CXXFLAGS="${CXXFLAGS:-} -funsigned-char" \
    ./configure --prefix="$mecab_root" --enable-static --disable-shared --with-charset=utf8
  grep -Eq '^#define HAVE_ICONV 1$' config.h || {
    echo 'MeCab configure did not enable the iconv conversion required for EUC-JP IPADIC.' >&2
    exit 1
  }
  make -j"$build_jobs"
  make install
)

tar --extract --gzip --file "$ipadic_archive" --directory "$work_directory"
(
  cd "$work_directory/mecab-ipadic-2.7.0-20070801"
  ./configure --prefix="$mecab_root" --with-mecab-config="$mecab_root/bin/mecab-config" --with-charset=utf8
  make -j"$build_jobs"
  make install
)

# A successful dictionary build must accept and emit strict UTF-8.  This also
# catches a partial build that leaves dictionary files but cannot convert the
# original EUC-JP source data correctly.
"$python_command" - "$mecab_root" <<'PY'
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
mecab = root / "bin" / "mecab"
dictionary = root / "lib" / "mecab" / "dic" / "ipadic"
details_result = subprocess.run([mecab, "-d", dictionary, "-D"], capture_output=True)
# This MeCab release prints valid dictionary information but returns 1 after
# -D because it then reaches EOF without a sentence. Reject only other codes.
if details_result.returncode not in (0, 1):
    raise RuntimeError(details_result.stderr.decode("utf-8", errors="strict"))
details = details_result.stdout.decode("utf-8", errors="strict")
if not re.search(r"^charset:\s*utf-?8\s*$", details, flags=re.IGNORECASE | re.MULTILINE):
    raise RuntimeError(f"IPADIC did not compile as UTF-8:\n{details}")
result = subprocess.run(
    [mecab, "-d", dictionary], input="日本語の動作確認\n".encode(), check=True, capture_output=True
).stdout.decode("utf-8", errors="strict")
if "日本語" not in result or "EOS" not in result or "\ufffd" in result:
    raise RuntimeError(f"Bundled MeCab failed its strict UTF-8 smoke test:\n{result}")
PY

tar --extract --gzip --file "$openfst_archive" --directory "$work_directory"
(
  cd "$openfst_source"
  ./configure --prefix="$kaldi_source/tools/openfst" --enable-static --enable-shared
  make -j"$build_jobs"
  make install
)

(
  cd "$kaldi_source/src"
  # Kaldi's Darwin configuration uses Apple's system Accelerate framework.
  # Do not build or bundle the Linux OpenBLAS toolchain on macOS.
  OPENFST_VER="$openfst_version" ./configure --shared
  grep -Fq -- '-framework Accelerate' kaldi.mk || {
    echo 'Kaldi did not configure the expected macOS Accelerate framework.' >&2
    exit 1
  }
  make -j"$build_jobs"
)

required_kaldi_programs=(
  src/bin/ali-to-phones
  src/bin/compile-train-graphs
  src/featbin/add-deltas
  src/featbin/apply-cmvn
  src/featbin/compute-cmvn-stats
  src/featbin/compute-mfcc-feats
  src/featbin/copy-feats
  src/featbin/extract-segments
  src/featbin/splice-feats
  src/featbin/transform-feats
  src/fstbin/fstaddselfloops
  src/gmmbin/gmm-align-compiled
  src/gmmbin/gmm-boost-silence
  src/nnet3bin/nnet3-align-compiled
  src/online2bin/ivector-extract-online2
  tools/openfst/bin/fstarcsort
  tools/openfst/bin/fstcompile
  tools/openfst/bin/fstcompose
  tools/openfst/bin/fstinfo
  tools/openfst/bin/fstprint
  tools/openfst/bin/fstproject
  tools/openfst/bin/fstrandgen
  tools/openfst/bin/fstrmepsilon
  tools/openfst/bin/fsttopsort
)

mkdir -p "$engine_root/kaldi" "$engine_root/lib"
for relative in "${required_kaldi_programs[@]}"; do
  source_program="$kaldi_source/$relative"
  target_program="$engine_root/kaldi/$relative"
  [[ -x $source_program ]] || { echo "Missing required Kaldi program: $source_program" >&2; exit 1; }
  copy_file "$source_program" "$target_program"
  strip -x "$target_program"
done

# Copy every non-system dylib required by the selected binaries.  Repeat until
# no new dylib appears so transitive compiler dependencies are
# bundled too.  Absolute Homebrew paths are rewritten below and never shipped.
changed=1
while [[ $changed -eq 1 ]]; do
  changed=0
  while IFS= read -r owner; do
    while IFS= read -r dependency; do
      is_system_library "$dependency" && continue
      dependency_path=$(resolve_macho_dependency "$owner" "$dependency") || {
        echo "Unresolved non-system Mach-O dependency '$dependency' in $owner" >&2
        exit 1
      }
      target_library="$engine_root/lib/$(basename "$dependency_path")"
      if [[ ! -f $target_library ]]; then
        copy_file "$dependency_path" "$target_library"
        strip -x "$target_library"
        changed=1
      fi
    done < <(macho_dependencies "$owner")
  done < <(packaged_macho_files)
done

# Make every bundled dylib self-contained and configure a relative rpath for
# each executable.  This avoids a runtime dependency on Homebrew locations.
while IFS= read -r dylib; do
  install_name_tool -id "@rpath/$(basename "$dylib")" "$dylib"
  install_name_tool -add_rpath '@loader_path' "$dylib" 2>/dev/null || true
done < <(find "$engine_root/lib" -type f -name '*.dylib*' -print)

while IFS= read -r owner; do
  while IFS= read -r dependency; do
    is_system_library "$dependency" && continue
    dependency_path=$(resolve_macho_dependency "$owner" "$dependency") || dependency_path=""
    target_library="$engine_root/lib/$(basename "${dependency_path:-$dependency}")"
    [[ -f $target_library ]] || {
      echo "Packaged Mach-O dependency missing for $owner: $dependency" >&2
      exit 1
    }
    install_name_tool -change "$dependency" "@rpath/$(basename "$target_library")" "$owner"
  done < <(macho_dependencies "$owner")
  if [[ $owner == "$engine_root/lib/"* ]]; then
    install_name_tool -add_rpath '@loader_path' "$owner" 2>/dev/null || true
  else
    lib_relative=$(relative_path "$owner" "$engine_root/lib")
    install_name_tool -add_rpath "@loader_path/$lib_relative" "$owner" 2>/dev/null || true
  fi
  assert_architecture "$owner"
done < <(packaged_macho_files)

# MeCab is intentionally static.  Only the executable and the UTF-8 IPADIC
# resources are included; headers and dictionary-build tools are omitted.
mkdir -p "$engine_root/mecab/bin" "$engine_root/mecab/lib/mecab/dic"
copy_file "$mecab_root/bin/mecab" "$engine_root/mecab/bin/mecab"
strip -x "$engine_root/mecab/bin/mecab"
assert_architecture "$engine_root/mecab/bin/mecab"
cp -R "$mecab_root/lib/mecab/dic/ipadic" "$engine_root/mecab/lib/mecab/dic/"
mkdir -p "$engine_root/mecab/etc"
printf '# KoreanFA supplies the dictionary with -d.\n' > "$engine_root/mecab/etc/mecabrc"

# clang applies an ad-hoc signature when linking Apple Silicon binaries, but
# strip and install_name_tool modify those binaries afterwards.  Re-sign every
# final Mach-O file so the archive runs on a different Mac as well as the build
# host.  Ad-hoc signing does not require an Apple Developer identity.
while IFS= read -r binary; do
  codesign --force --sign - "$binary"
  codesign --verify --strict "$binary"
done < <(final_macho_files)

mkdir -p "$engine_root/licenses"
copy_file "$kaldi_source/COPYING" "$engine_root/licenses/KALDI.txt"
copy_file "$openfst_source/COPYING" "$engine_root/licenses/OPENFST.txt"
{
  cat "$mecab_source/mecab/COPYING"
  printf '\n\n--- MeCab BSD License ---\n\n'
  cat "$mecab_source/mecab/BSD"
} > "$engine_root/licenses/MECAB.txt"
copy_file "$work_directory/mecab-ipadic-2.7.0-20070801/COPYING" "$engine_root/licenses/IPADIC.txt"

cat > "$engine_root/engine.json" <<EOF
{
  "schema_version": 1,
  "engine_version": "${engine_version}",
  "platform": "${platform}",
  "source_revision": "${source_revision}",
  "source_tracked_files_clean": ${source_tracked_files_clean},
  "macos_minimum_version": "${minimum_macos}",
  "kaldi_dir": "kaldi",
  "mecab_command": "mecab/bin/mecab",
  "mecab_dict": "mecab/lib/mecab/dic/ipadic",
  "mecabrc": "mecab/etc/mecabrc",
  "library_paths": ["lib"],
  "library_path_variable": "DYLD_FALLBACK_LIBRARY_PATH",
  "kaldi_revision": "${kaldi_revision}",
  "openfst_version": "${openfst_version}",
  "openfst_sha256": "${openfst_sha256}",
  "math_library": "Accelerate",
  "mecab_revision": "${mecab_revision}",
  "ipadic_sha256": "${ipadic_sha256}"
}
EOF

archive="$output_directory/${engine_name}.tar.gz"
tar --create --gzip --file "$archive" --directory "$work_directory" "$engine_name"
(
  cd "$output_directory"
  shasum -a 256 "${engine_name}.tar.gz" > "${engine_name}.tar.gz.sha256"
)
printf 'Built %s\n' "$archive"
