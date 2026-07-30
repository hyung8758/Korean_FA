#!/usr/bin/env bash
# Build Kaldi's language directory.  Korean and Japanese only differ in their
# silence/OOV symbols; the generated files and validation are deliberately
# shared.
set -Eeuo pipefail

if [[ $# -ne 5 ]]; then
  echo "Usage: $0 <dictionary-dir> <language-dir> <oov-word> <silence-phone> <unknown-phone>" >&2
  exit 2
fi

dict_dir=$1
lang_dir=$2
oov_word=$3
silence_phone=$4
unknown_phone=$5
runtime_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

[[ -s $dict_dir/lexicon.txt ]] || { echo "Missing dictionary lexicon: $dict_dir/lexicon.txt" >&2; exit 1; }
mkdir -p "$lang_dir"
awk 'NF >= 2 { $1 = $1; print $1 " 1.0 " substr($0, length($1) + 2) }' "$dict_dir/lexicon.txt" > "$dict_dir/lexiconp.txt"
printf '%s\n%s\n' "$silence_phone" "$unknown_phone" > "$dict_dir/silence_phones.txt"
awk '{$1=""; sub(/^ /, ""); print}' "$dict_dir/lexicon.txt" | tr -s ' ' '\n' | sed '/^$/d' | LC_ALL=C sort -u > "$dict_dir/nonsilence_phones.txt"
printf '%s\n' "$silence_phone" > "$dict_dir/optional_silence.txt"
{
  awk '{printf "%s ", $1} END {print ""}' "$dict_dir/silence_phones.txt"
  # Kaldi's original recipe groups phones by their trailing stress/tone digit.
  # This is one group for the Japanese model (which has no such digits), and
  # preserves the Korean model's historical question sets.
  awk '{for (i=2; i<=NF; i++) { phone=$i; match(phone, /[0-9]*$/); suffix=substr(phone, RSTART, RLENGTH); group[suffix]=group[suffix] " " phone }} END {for (key in group) print substr(group[key], 2)}' "$dict_dir/lexicon.txt" | LC_ALL=C sort
} > "$dict_dir/extra_questions.txt"

if ! awk -v word="$oov_word" '$1 == word { found=1 } END { exit !found }' "$dict_dir/lexicon.txt"; then
  printf '%s %s\n' "$oov_word" "$unknown_phone" >> "$dict_dir/lexicon.txt"
  printf '%s 1.0 %s\n' "$oov_word" "$unknown_phone" >> "$dict_dir/lexiconp.txt"
fi
bash "$runtime_root/pipeline/core/prepare_lang.sh" "$dict_dir" "$oov_word" "$lang_dir/local/lang" "$lang_dir" >/dev/null
