#!/usr/bin/env bash
# Convert MeCab tokens to KoreanFA's Japanese phone lexicon.
set -Eeuo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <mecab-text> <output-lexicon>" >&2
  exit 2
fi

input_text=$1
save_file=$2
language_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/koreanfa-japanese-g2p.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT

tr ' ' '\n' < "$input_text" | awk 'NF && $0 !~ /\+ー/ && $0 !~ /^\+\+$/ && $0 !~ /×/' > "$work_dir/word.txt"
LC_ALL=C sort -u "$work_dir/word.txt" > "$work_dir/sorted_word.txt"
if [[ ! -s $work_dir/sorted_word.txt ]]; then
  : > "$save_file"
  exit 0
fi
# Both the converter and its phone table are Japanese-specific resources.
perl "$language_dir/vocab2dic.pl" -p "$language_dir/kana2phone" \
  -e "$work_dir/error.txt" -o "$work_dir/word.txt" "$work_dir/sorted_word.txt"
cut -d'+' -f1,3- "$work_dir/word.txt" | cut -f1,3- | perl -pe 's/\t/ /g' > "$save_file"
