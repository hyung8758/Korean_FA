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
gettext_m4_directory=
if gettext_formula_prefix=$(brew --prefix gettext 2>/dev/null); then
  gettext_formula_m4="$gettext_formula_prefix/share/gettext/m4"
  if [[ -d $gettext_formula_m4 ]]; then
    gettext_m4_directory=$gettext_formula_m4
  fi
fi
if [[ -z $gettext_m4_directory ]]; then
  gettext_homebrew_m4="$(brew --prefix)/share/gettext/m4"
  if [[ -d $gettext_homebrew_m4 ]]; then
    gettext_m4_directory=$gettext_homebrew_m4
  fi
fi
[[ -n $gettext_m4_directory ]] || {
  echo "Homebrew gettext m4 files were not found under the gettext formula or Homebrew prefix. Run 'brew install gettext'." >&2
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
ipadic_build_log="$work_directory/ipadic-build.log"
iconv_probe_source="$work_directory/iconv-euc-jp-probe.c"
iconv_probe="$work_directory/iconv-euc-jp-probe"

# shellcheck source=engine/macos_build_helpers.sh
source "$script_directory/macos_build_helpers.sh"
# shellcheck source=engine/macos_build_mecab.sh
source "$script_directory/macos_build_mecab.sh"

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

# Validate the UTF-8 MeCab/IPADIC path before the expensive Kaldi compilation.
build_macos_mecab

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
  ensure_macho_rpath "$dylib" '@loader_path'
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
    ensure_macho_rpath "$owner" '@loader_path'
  else
    lib_relative=$(relative_path "$owner" "$engine_root/lib")
    ensure_macho_rpath "$owner" "@loader_path/$lib_relative"
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
