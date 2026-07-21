#!/usr/bin/env bash
# Build the native Linux x86_64 runtime distributed by ``koreanfa engine``.
#
# Run this on an Ubuntu build host after installing the packages listed in
# .github/workflows/engine-release.yml.  Users never run this script: they
# download its verified archive through the KoreanFA CLI or Python API.

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
mecab_revision=cd22ce53d855a1cda1acfcb680c9e82c5de39a94
ipadic_url=https://downloads.sourceforge.net/project/mecab/mecab-ipadic/2.7.0-20070801/mecab-ipadic-2.7.0-20070801.tar.gz
ipadic_sha256=b62f527d881c504576baed9c6ef6561554658b175ce6ae0096a60307e49e3523

if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
  echo "This builder only produces ${platform}; current host is $(uname -s)-$(uname -m)." >&2
  exit 2
fi

mkdir -p "$output_directory"
work_directory=$(mktemp -d)
trap 'rm -rf "$work_directory"' EXIT
engine_name="koreanfa-engine-v${engine_version}-${platform}"
engine_root="$work_directory/$engine_name"
kaldi_source="$work_directory/kaldi"
mecab_source="$work_directory/mecab"
ipadic_archive="$work_directory/mecab-ipadic.tar.gz"

git clone --filter=blob:none https://github.com/kaldi-asr/kaldi.git "$kaldi_source"
git -C "$kaldi_source" checkout --detach "$kaldi_revision"
# Kaldi's Makefile still downloads OpenFST through an endpoint that rejects
# GitHub Actions' wget user agent.  Pre-seed the exact archive with curl so
# the pinned Kaldi build remains reproducible.
curl --fail --location --silent --show-error --user-agent "Mozilla/5.0" \
  --output "$kaldi_source/tools/openfst-1.8.4.tar.gz" \
  https://www.openfst.org/twiki/pub/FST/FstDownload/openfst-1.8.4.tar.gz
make -C "$kaldi_source/tools" -j"$(nproc)"
(
  cd "$kaldi_source/src"
  ./configure --mathlib=OPENBLAS --shared
  make -j"$(nproc)"
)

git clone --filter=blob:none https://github.com/shogo82148/mecab.git "$mecab_source"
git -C "$mecab_source" checkout --detach "$mecab_revision"
(
  cd "$mecab_source/mecab"
  ./autogen.sh
  ./configure --prefix="$engine_root/mecab" --enable-static --disable-shared
  make -j"$(nproc)"
  make install
)

curl --fail --location --silent --show-error --output "$ipadic_archive" "$ipadic_url"
printf '%s  %s\n' "$ipadic_sha256" "$ipadic_archive" | sha256sum --check --status
tar --extract --gzip --file "$ipadic_archive" --directory "$work_directory"
(
  cd "$work_directory/mecab-ipadic-2.7.0-20070801"
  ./configure --prefix="$engine_root/mecab" --with-mecab-config="$engine_root/mecab/bin/mecab-config" --with-charset=utf8
  make -j"$(nproc)"
  make install
)

# The pipeline invokes Kaldi binaries by PATH and uses ali-to-phones directly.
# Copy every binary directory rather than relying on a brittle hand-maintained
# executable list.
mkdir -p "$engine_root/kaldi/src" "$engine_root/kaldi/tools/openfst"
while IFS= read -r directory; do
  cp -a "$directory" "$engine_root/kaldi/src/"
done < <(find "$kaldi_source/src" -maxdepth 1 -mindepth 1 -type d -name '*bin' -print | sort)
cp -a "$kaldi_source/src/lib" "$engine_root/kaldi/src/"
cp -a "$kaldi_source/src/lm" "$engine_root/kaldi/src/"
cp -a "$kaldi_source/tools/openfst/bin" "$engine_root/kaldi/tools/openfst/"
if [[ -d $kaldi_source/tools/openfst/lib ]]; then
  cp -a "$kaldi_source/tools/openfst/lib" "$engine_root/kaldi/tools/openfst/"
fi

# Kaldi is built against OpenBLAS on the release runner.  Bundle every
# non-glibc shared object required by the selected Kaldi executables so an end
# user does not need to install OpenBLAS or compiler runtimes separately.
mkdir -p "$engine_root/lib"
while IFS= read -r executable; do
  while IFS= read -r library; do
    case "$library" in
      /lib/*/libc.so.*|/lib/*/libm.so.*|/lib/*/libpthread.so.*|/lib/*/librt.so.*|/lib/*/libdl.so.*|/lib64/ld-linux-*) continue ;;
      "$engine_root"/*) continue ;;
    esac
    cp -aL "$library" "$engine_root/lib/"
  done < <(LD_LIBRARY_PATH="$engine_root/kaldi/src/lib:$engine_root/kaldi/tools/openfst/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    ldd "$executable" 2>/dev/null | awk '/=> \/[^ ]+/ { print $3 } /^\/[^ ]+/ { print $1 }' | sort -u)
done < <(find "$engine_root/kaldi/src" -type f -perm -u+x -print)

# The legacy Japanese shell pipeline passes -d explicitly.  An empty mecabrc
# makes the bundled executable relocatable while that explicit dictionary path
# selects the bundled UTF-8 IPADIC data.
mkdir -p "$engine_root/mecab/etc"
printf '# KoreanFA supplies the dictionary with -d.\n' > "$engine_root/mecab/etc/mecabrc"

mkdir -p "$engine_root/licenses"
cp "$kaldi_source/COPYING" "$engine_root/licenses/KALDI.txt"
cp "$mecab_source/mecab/COPYING" "$engine_root/licenses/MECAB.txt"
cp "$work_directory/mecab-ipadic-2.7.0-20070801/COPYING" "$engine_root/licenses/IPADIC.txt"
cat > "$engine_root/engine.json" <<EOF
{
  "schema_version": 1,
  "kaldi_dir": "kaldi",
  "mecab_command": "mecab/bin/mecab",
  "mecab_dict": "mecab/lib/mecab/dic/ipadic",
  "mecabrc": "mecab/etc/mecabrc",
  "library_paths": ["lib", "kaldi/src/lib", "kaldi/tools/openfst/lib"],
  "kaldi_revision": "${kaldi_revision}",
  "mecab_revision": "${mecab_revision}",
  "ipadic_sha256": "${ipadic_sha256}"
}
EOF

archive="$output_directory/${engine_name}.tar.gz"
tar --create --gzip --file "$archive" --directory "$work_directory" "$engine_name"
sha256sum "$archive" > "$archive.sha256"
printf 'Built %s\n' "$archive"
