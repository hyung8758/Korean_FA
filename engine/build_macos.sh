#!/usr/bin/env bash
# Build one relocatable macOS KoreanFA runtime on its native CPU architecture.
#
# Usage: engine/build_macos.sh OUTPUT_DIRECTORY ENGINE_VERSION
#
# This script deliberately does not cross-compile.  Run it once on an Intel
# Mac and once on an Apple Silicon Mac to produce darwin-x86_64 and
# darwin-arm64 archives respectively.  The final user archive contains the
# Kaldi programs, OpenFST, OpenBLAS, MeCab, IPADIC, required non-system dylibs,
# and their notices; users do not need Homebrew, Kaldi, or MeCab installed.

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 OUTPUT_DIRECTORY ENGINE_VERSION" >&2
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

python_command=${KOREANFA_PYTHON:-python3}
for command in autoconf automake brew curl gfortran git glibtoolize install_name_tool lipo make otool shasum strip tar "$python_command"; do
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

mkdir -p "$1"
output_directory=$(cd "$1" && pwd -P)
engine_version=$2
platform="darwin-${architecture}"
minimum_macos=12.0
build_jobs=${KOREANFA_BUILD_JOBS:-$(sysctl -n hw.ncpu)}
kaldi_revision=e02e35f0254bb033fab73d1df99fc34123e31d56
openfst_version=1.8.4
openfst_url=https://storage.googleapis.com/rime-public/mirror/openfst-1.8.4.tar.gz
openfst_sha256=a8ebbb6f3d92d07e671500587472518cfc87cb79b9a654a5a8abb2d0eb298016
openblas_revision=d2b11c47774b9216660e76e2fc67e87079f26fa1
mecab_revision=cd22ce53d855a1cda1acfcb680c9e82c5de39a94
ipadic_url=https://downloads.sourceforge.net/project/mecab/mecab-ipadic/2.7.0-20070801/mecab-ipadic-2.7.0-20070801.tar.gz
ipadic_sha256=b62f527d881c504576baed9c6ef6561554658b175ce6ae0096a60307e49e3523

export MACOSX_DEPLOYMENT_TARGET="$minimum_macos"
export CC="${CC:-clang}"
export CXX="${CXX:-clang++}"
export FC="${FC:-gfortran}"
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
openblas_source="$work_directory/openblas-source"
openblas_root="$work_directory/openblas"
mecab_source="$work_directory/mecab"
mecab_root="$work_directory/mecab-root"
ipadic_archive="$work_directory/mecab-ipadic.tar.gz"

copy_file() {
  local source=$1 destination=$2
  mkdir -p "$(dirname "$destination")"
  cp -pL "$source" "$destination"
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

git clone https://github.com/kaldi-asr/kaldi.git "$kaldi_source"
git -C "$kaldi_source" checkout --detach "$kaldi_revision"

curl --fail --location --silent --show-error --retry 3 --output "$openfst_archive" "$openfst_url"
printf '%s  %s\n' "$openfst_sha256" "$openfst_archive" | shasum -a 256 --check --status
tar --extract --gzip --file "$openfst_archive" --directory "$work_directory"
(
  cd "$openfst_source"
  ./configure --prefix="$kaldi_source/tools/openfst" --enable-static --enable-shared
  make -j"$build_jobs"
  make install
)

git clone https://github.com/OpenMathLib/OpenBLAS.git "$openblas_source"
git -C "$openblas_source" checkout --detach "$openblas_revision"
(
  cd "$openblas_source"
  # DYNAMIC_ARCH avoids producing an engine tuned only for the build Mac
  # (for example, an M3-only binary that fails on M1/M2 hardware).
  make -j"$build_jobs" PREFIX="$openblas_root" DYNAMIC_ARCH=1 USE_LOCKING=1 USE_OPENMP=0 NO_SHARED=0 all
  make PREFIX="$openblas_root" DYNAMIC_ARCH=1 USE_LOCKING=1 USE_OPENMP=0 NO_SHARED=0 install
)
(
  cd "$kaldi_source/src"
  OPENFST_VER="$openfst_version" ./configure --mathlib=OPENBLAS --openblas-root="$openblas_root" --shared
  make -j"$build_jobs"
)

git clone https://github.com/shogo82148/mecab.git "$mecab_source"
git -C "$mecab_source" checkout --detach "$mecab_revision"
(
  cd "$mecab_source/mecab"
  ./autogen.sh
  ./configure --prefix="$mecab_root" --enable-static --disable-shared
  make -j"$build_jobs"
  make install
)

curl --fail --location --silent --show-error --retry 3 --output "$ipadic_archive" "$ipadic_url"
printf '%s  %s\n' "$ipadic_sha256" "$ipadic_archive" | shasum -a 256 --check --status
tar --extract --gzip --file "$ipadic_archive" --directory "$work_directory"
(
  cd "$work_directory/mecab-ipadic-2.7.0-20070801"
  ./configure --prefix="$mecab_root" --with-mecab-config="$mecab_root/bin/mecab-config" --with-charset=utf8
  make -j"$build_jobs"
  make install
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
# no new dylib appears so transitive compiler and OpenBLAS dependencies are
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

mkdir -p "$engine_root/licenses"
copy_file "$kaldi_source/COPYING" "$engine_root/licenses/KALDI.txt"
copy_file "$openfst_source/COPYING" "$engine_root/licenses/OPENFST.txt"
copy_file "$openblas_source/LICENSE" "$engine_root/licenses/OPENBLAS.txt"
{
  cat "$mecab_source/mecab/COPYING"
  printf '\n\n--- MeCab BSD License ---\n\n'
  cat "$mecab_source/mecab/BSD"
} > "$engine_root/licenses/MECAB.txt"
copy_file "$work_directory/mecab-ipadic-2.7.0-20070801/COPYING" "$engine_root/licenses/IPADIC.txt"

# OpenBLAS links against GCC Fortran runtimes.  When they are bundled, retain
# their complete GPLv3 and Runtime Library Exception notice beside the archive.
if find "$engine_root/lib" -type f \( -name 'libgfortran*.dylib' -o -name 'libgcc_s*.dylib' -o -name 'libquadmath*.dylib' \) -print -quit | grep -q .; then
  gcc_prefix=$(brew --prefix gcc 2>/dev/null || true)
  [[ -n $gcc_prefix ]] || { echo 'Bundled GCC runtime found but Homebrew GCC prefix is unavailable.' >&2; exit 1; }
  gcc_runtime_notice=$(find "$gcc_prefix" -type f -name COPYING.RUNTIME -print -quit)
  [[ -n $gcc_runtime_notice ]] || { echo 'Missing GCC Runtime Library Exception notice.' >&2; exit 1; }
  gcc_notice_directory=$(dirname "$gcc_runtime_notice")
  [[ -f $gcc_notice_directory/COPYING3 ]] || { echo 'Missing GCC GPLv3 notice.' >&2; exit 1; }
  {
    cat "$gcc_notice_directory/COPYING3"
    printf '\n\n--- GCC Runtime Library Exception 3.1 ---\n\n'
    cat "$gcc_runtime_notice"
  } > "$engine_root/licenses/GCC-RUNTIME.txt"
fi

cat > "$engine_root/engine.json" <<EOF
{
  "schema_version": 1,
  "platform": "${platform}",
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
  "openblas_revision": "${openblas_revision}",
  "openblas_dynamic_arch": true,
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
