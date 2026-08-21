#!/usr/bin/env bash
# UTF-8 MeCab and IPADIC build phase for build_macos.sh.

build_macos_mecab() {
  # gettext's generic AM_ICONV runtime probe rejects some Apple iconv
  # implementations. Prove the EUC-JP -> UTF-8 path KoreanFA requires.
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
  "$CC" -mmacosx-version-min="$minimum_macos" "$iconv_probe_source" -liconv -o "$iconv_probe"
  "$iconv_probe" || {
    echo 'macOS system iconv cannot convert the EUC-JP input required by IPADIC.' >&2
    exit 1
  }

  (
    cd "$mecab_source/mecab"
    ./autogen.sh
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
    # Legacy IPADIC targets invoke the same compiler; serialize its writers.
    make -j1
    make install
  ) 2>&1 | tee "$ipadic_build_log"
  if grep -Fq 'iconv_open is not supported' "$ipadic_build_log"; then
    echo 'IPADIC failed to use iconv while converting its EUC-JP sources.' >&2
    exit 1
  fi

  ipadic_dictionary="$mecab_root/lib/mecab/dic/ipadic"
  sed -i '' 's/^config-charset[[:space:]]*=.*/config-charset = UTF-8/' "$ipadic_dictionary/dicrc"

  "$python_command" - "$mecab_root" <<'PY'
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
mecab = root / "bin" / "mecab"
dictionary = root / "lib" / "mecab" / "dic" / "ipadic"
dicrc = (dictionary / "dicrc").read_text(encoding="utf-8", errors="strict")
details_result = subprocess.run([mecab, "-d", dictionary, "-D"], capture_output=True)
if details_result.returncode not in (0, 1):
    raise RuntimeError(details_result.stderr.decode("utf-8", errors="strict"))
details = details_result.stdout.decode("utf-8", errors="strict")
declared_charset = re.search(
    r"^config-charset\s*=\s*(\S+)\s*$", dicrc, flags=re.IGNORECASE | re.MULTILINE
)
dictionary_charset = re.search(
    r"^charset:\s*(\S+)\s*$", details, flags=re.IGNORECASE | re.MULTILINE
)
normalize_charset = lambda value: value.lower().replace("-", "")
if (
    declared_charset is None
    or dictionary_charset is None
    or normalize_charset(declared_charset.group(1)) != "utf8"
    or normalize_charset(dictionary_charset.group(1)) != "utf8"
    or normalize_charset(declared_charset.group(1))
    != normalize_charset(dictionary_charset.group(1))
):
    raise RuntimeError(f"IPADIC did not compile as UTF-8:\n{details}")
result = subprocess.run(
    [mecab, "-d", dictionary],
    input="日本語の動作確認\n".encode(),
    check=True,
    capture_output=True,
).stdout.decode("utf-8", errors="strict")
if "\ufffd" in result:
    raise RuntimeError(f"Bundled MeCab failed its strict UTF-8 smoke test:\n{result}")
expected = {
    "日本語": ("ニホンゴ", "ニホンゴ"),
    "の": ("ノ", "ノ"),
    "動作": ("ドウサ", "ドーサ"),
    "確認": ("カクニン", "カクニン"),
}
actual = {}
for line in result.splitlines():
    if line == "EOS":
        continue
    surface, features = line.split("\t", 1)
    actual[surface] = tuple(features.split(",")[-2:])
for surface, pronunciation in expected.items():
    if actual.get(surface) != pronunciation:
        raise RuntimeError(
            f"Bundled MeCab returned the wrong reading for {surface}: "
            f"expected {pronunciation}, received {actual.get(surface)}\n{result}"
        )
PY
}
