#!/usr/bin/env bash
# Build the native Linux x86_64 runtime distributed by ``koreanfa engine``.
#
# Run this in a glibc 2.17-compatible Linux build environment after installing
# the build dependencies listed in .github/workflows/engine-candidate.yml.
# Users never run this script: they download its verified archive through the
# KoreanFA CLI or Python API.

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 OUTPUT_DIRECTORY ENGINE_VERSION" >&2
  exit 2
fi

mkdir -p "$1"
output_directory=$(realpath "$1")
engine_version=$2
platform=linux-x86_64
kaldi_revision=e02e35f0254bb033fab73d1df99fc34123e31d56
openfst_version=1.8.4
openfst_url=https://storage.googleapis.com/rime-public/mirror/openfst-1.8.4.tar.gz
openfst_sha256=a8ebbb6f3d92d07e671500587472518cfc87cb79b9a654a5a8abb2d0eb298016
openblas_revision=d2b11c47774b9216660e76e2fc67e87079f26fa1
mecab_revision=cd22ce53d855a1cda1acfcb680c9e82c5de39a94
ipadic_url=https://downloads.sourceforge.net/project/mecab/mecab-ipadic/2.7.0-20070801/mecab-ipadic-2.7.0-20070801.tar.gz
ipadic_sha256=b62f527d881c504576baed9c6ef6561554658b175ce6ae0096a60307e49e3523
glibc_baseline=${KOREANFA_GLIBC_BASELINE:-unknown}
build_jobs=${KOREANFA_BUILD_JOBS:-$(nproc)}

if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
  echo "This builder only produces ${platform}; current host is $(uname -s)-$(uname -m)." >&2
  exit 2
fi

# The manylinux2014 image intentionally installs RPMs with ``tsflags=nodocs``.
# The workflow restores these two files from the pinned devtoolset GCC RPM
# before invoking this builder.  Fail before downloading or compiling anything
# if that preparation step changes or is omitted.
gcc_runtime_notice=$(find /opt/rh -type f -path '*/share/doc/*gcc-*/COPYING.RUNTIME' -print -quit)
if [[ -z $gcc_runtime_notice ]]; then
  echo 'Missing GCC Runtime Library Exception notice; restore devtoolset GCC documentation before building.' >&2
  exit 1
fi
gcc_notice_directory=$(dirname "$gcc_runtime_notice")
if [[ ! -f $gcc_notice_directory/COPYING3 ]]; then
  echo "Missing GCC GPLv3 notice beside $gcc_runtime_notice." >&2
  exit 1
fi

mkdir -p "$output_directory"
work_directory=$(mktemp -d)
trap 'rm -rf "$work_directory"' EXIT
engine_name="koreanfa-engine-v${engine_version}-${platform}"
engine_root="$work_directory/$engine_name"
kaldi_source="$work_directory/kaldi"
openfst_archive="$work_directory/openfst-${openfst_version}.tar.gz"
openfst_source="$work_directory/openfst-${openfst_version}"
openblas_source="$work_directory/openblas-source"
mecab_source="$work_directory/mecab"
mecab_root="$work_directory/mecab-root"
ipadic_archive="$work_directory/mecab-ipadic.tar.gz"
openblas_root="$work_directory/openblas"

# Do not use Git partial-clone flags here.  The manylinux2014 (glibc 2.17)
# build image
# deliberately carries an older, still-compatible Git client.
git clone https://github.com/kaldi-asr/kaldi.git "$kaldi_source"
git -C "$kaldi_source" checkout --detach "$kaldi_revision"

# Kaldi expects OpenFST 1.8.4.  The Rime Labs mirror is the source archive
# pinned by Bazel Central Registry because openfst.org frequently returns 403
# to CI runners.  It has the same verified SHA-256 as the official archive.
# Keep checksum verification instead of relying on Kaldi's legacy wget path.
curl --fail --location --silent --show-error --retry 3 \
  --output "$openfst_archive" "$openfst_url"
printf '%s  %s\n' "$openfst_sha256" "$openfst_archive" | sha256sum --check --status
tar --extract --gzip --file "$openfst_archive" --directory "$work_directory"
(
  cd "$openfst_source"
  ./configure --prefix="$kaldi_source/tools/openfst" --enable-static --enable-shared
  make -j"$build_jobs"
  make install
)

# Build the matching OpenBLAS headers and shared library from the version used
# by this Kaldi revision's own installer.  Do not mix distribution LAPACKE
# headers with it: their Fortran ABI declarations differ from Kaldi's wrappers.
git clone https://github.com/OpenMathLib/OpenBLAS.git "$openblas_source"
git -C "$openblas_source" checkout --detach "$openblas_revision"
(
  cd "$openblas_source"
  make -j"$build_jobs" PREFIX="$openblas_root" DYNAMIC_ARCH=1 USE_LOCKING=1 USE_THREAD=0 NO_SHARED=0 all
  make PREFIX="$openblas_root" DYNAMIC_ARCH=1 USE_LOCKING=1 USE_THREAD=0 NO_SHARED=0 install
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

curl --fail --location --silent --show-error --output "$ipadic_archive" "$ipadic_url"
printf '%s  %s\n' "$ipadic_sha256" "$ipadic_archive" | sha256sum --check --status
tar --extract --gzip --file "$ipadic_archive" --directory "$work_directory"
(
  cd "$work_directory/mecab-ipadic-2.7.0-20070801"
  ./configure --prefix="$mecab_root" --with-mecab-config="$mecab_root/bin/mecab-config" --with-charset=utf8
  make -j"$build_jobs"
  make install
)

# Ship only the programs exercised by KoreanFA's Korean and Japanese pipelines.
# Copying complete Kaldi *bin directories also copies object files and unused
# tools, inflating a user runtime by several gigabytes.  This list was derived
# from an execve trace of both bundled model pipelines and reviewed against the
# shell scripts under runtime/pipeline.
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
  mkdir -p "$(dirname "$target_program")"
  cp -aL "$source_program" "$target_program"
  strip --strip-unneeded "$target_program"
done

# Resolve all direct and transitive shared-library dependencies from the
# selected programs.  Copy each required SONAME once; omit static archives,
# object files, headers, and duplicate symlink targets.
library_search_path="$kaldi_source/src/lib:$kaldi_source/tools/openfst/lib:$openblas_root/lib"
while IFS= read -r executable; do
  ldd_output=$(LD_LIBRARY_PATH="$library_search_path${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ldd "$executable")
  if grep -q 'not found' <<<"$ldd_output"; then
    echo "Unresolved runtime dependency for $executable:" >&2
    grep 'not found' <<<"$ldd_output" >&2
    exit 1
  fi
  while IFS= read -r library; do
    case "$(basename "$library")" in
      libc.so.*|libm.so.*|libpthread.so.*|librt.so.*|libdl.so.*|ld-linux-*.so.*) continue ;;
    esac
    cp -aL "$library" "$engine_root/lib/$(basename "$library")"
  done < <(awk '/=> \/[^ ]+/ { print $3 } /^\/[^ ]+/ { print $1 }' <<<"$ldd_output" | sort -u)
done < <(find "$engine_root/kaldi" -type f -perm -u+x -print)
find "$engine_root/lib" -type f -name '*.so*' -exec strip --strip-unneeded {} +

# The archive may contain only bundled non-glibc libraries.  Loading every
# shipped executable with that library directory catches missed transitive
# dependencies before a candidate is uploaded.
while IFS= read -r executable; do
  ldd_output=$(LD_LIBRARY_PATH="$engine_root/lib" ldd "$executable")
  if grep -q 'not found' <<<"$ldd_output"; then
    echo "Packaged runtime dependency missing for $executable:" >&2
    grep 'not found' <<<"$ldd_output" >&2
    exit 1
  fi
done < <(find "$engine_root/kaldi" -type f -perm -u+x -print)

# MeCab is only needed for runtime tokenization.  Do not ship its headers,
# static library, dictionary-build tools, or development metadata.
mkdir -p "$engine_root/mecab/bin" "$engine_root/mecab/lib/mecab/dic"
cp -aL "$mecab_root/bin/mecab" "$engine_root/mecab/bin/mecab"
strip --strip-unneeded "$engine_root/mecab/bin/mecab"
cp -a "$mecab_root/lib/mecab/dic/ipadic" "$engine_root/mecab/lib/mecab/dic/"

# The legacy Japanese shell pipeline passes -d explicitly.  An empty mecabrc
# makes the bundled executable relocatable while that explicit dictionary path
# selects the bundled UTF-8 IPADIC data.
mkdir -p "$engine_root/mecab/etc"
printf '# KoreanFA supplies the dictionary with -d.\n' > "$engine_root/mecab/etc/mecabrc"

mkdir -p "$engine_root/licenses"
cp "$kaldi_source/COPYING" "$engine_root/licenses/KALDI.txt"
cp "$openfst_source/COPYING" "$engine_root/licenses/OPENFST.txt"
cp "$openblas_source/LICENSE" "$engine_root/licenses/OPENBLAS.txt"
# MeCab offers GPL, LGPL, or BSD terms.  KoreanFA distributes the bundled
# executable under MeCab's BSD option, which requires both the attribution in
# COPYING and the complete BSD terms to accompany binary redistribution.
{
  cat "$mecab_source/mecab/COPYING"
  printf '\n\n--- MeCab BSD License ---\n\n'
  cat "$mecab_source/mecab/BSD"
} > "$engine_root/licenses/MECAB.txt"
cp "$work_directory/mecab-ipadic-2.7.0-20070801/COPYING" "$engine_root/licenses/IPADIC.txt"

# The selected Kaldi programs pull the GCC runtime libraries (libgcc_s,
# libstdc++, libgfortran, and libquadmath) and zlib into the archive.  Keep
# their notices with the matching binaries instead of assuming the target
# Linux distribution provides them.
{
  cat "$gcc_notice_directory/COPYING3"
  printf '\n\n--- GCC Runtime Library Exception 3.1 ---\n\n'
  cat "$gcc_runtime_notice"
} > "$engine_root/licenses/GCC-RUNTIME.txt"

# zlib-devel provides the exact license text for the zlib shared object copied
# above.  Extract only the comment block so no unrelated header declarations
# become part of the notice file.
sed -n '/Copyright (C) 1995/,/madler@alumni.caltech.edu/p' /usr/include/zlib.h \
  > "$engine_root/licenses/ZLIB.txt"
[[ -s $engine_root/licenses/ZLIB.txt ]] || {
  echo 'Could not extract the zlib notice from /usr/include/zlib.h.' >&2
  exit 1
}
cat > "$engine_root/engine.json" <<EOF
{
  "schema_version": 1,
  "kaldi_dir": "kaldi",
  "mecab_command": "mecab/bin/mecab",
  "mecab_dict": "mecab/lib/mecab/dic/ipadic",
  "mecabrc": "mecab/etc/mecabrc",
  "library_paths": ["lib"],
  "glibc_baseline": "${glibc_baseline}",
  "kaldi_revision": "${kaldi_revision}",
  "openfst_version": "${openfst_version}",
  "openfst_sha256": "${openfst_sha256}",
  "openblas_revision": "${openblas_revision}",
  "mecab_revision": "${mecab_revision}",
  "ipadic_sha256": "${ipadic_sha256}"
}
EOF

archive="$output_directory/${engine_name}.tar.gz"
tar --create --gzip --file "$archive" --directory "$work_directory" "$engine_name"
# Keep the checksum portable: release users verify the downloaded archive from
# an arbitrary directory, so the sidecar must not contain this builder's
# temporary absolute output path.
(
  cd "$output_directory"
  sha256sum "${engine_name}.tar.gz" > "${engine_name}.tar.gz.sha256"
)
printf 'Built %s\n' "$archive"
