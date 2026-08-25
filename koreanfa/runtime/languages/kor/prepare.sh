#!/usr/bin/env bash
# Prepare one Korean transcript for the shared Kaldi alignment pipeline.
# The Python adapter converts each token to the bundled model's phone inventory.
set -Eeuo pipefail

if [[ $# -ne 7 && $# -ne 8 ]]; then
  echo "Usage: $0 <python> <raw-text> <trans-dir> <dict-dir> <prono-dir> <model-dir> <utterance-id> [pronunciation-dictionary]" >&2
  exit 2
fi

python_executable=$1
raw_text=$2
trans_dir=$3
dict_dir=$4
prono_dir=$5
model_dir=$6
utterance_id=$7
pronunciation_dictionary=${8:-}

g2p_args=(
  --input "$raw_text"
  --output "$prono_dir/pronunciations.txt"
  --pronunciation-output "$prono_dir/pronunciations_hangul.txt"
)
[[ -n $pronunciation_dictionary ]] && g2p_args+=(--pronunciation-dictionary "$pronunciation_dictionary")
"$python_executable" -m koreanfa._korean_g2p "${g2p_args[@]}"
paste -d ' ' "$raw_text" "$prono_dir/pronunciations.txt" > "$prono_dir/sent_lexicon.txt"
[[ -s $prono_dir/sent_lexicon.txt ]] || { echo "Korean transcript produced no pronunciations." >&2; exit 1; }
paste -d '\n' "$prono_dir/sent_lexicon.txt" "$model_dir/lexicon.txt" | LC_ALL=C sort -u | sed '/^[[:space:]]*$/d' > "$dict_dir/lexicon.txt"
printf '%s %s\n' "$utterance_id" "$(awk '{printf "%s%s", sep, $1; sep=" "}' "$prono_dir/sent_lexicon.txt")" > "$trans_dir/text"
