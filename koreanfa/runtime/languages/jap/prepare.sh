#!/usr/bin/env bash
# Prepare one Japanese transcript for the shared Kaldi alignment pipeline.
# MeCab supplies readings, then the Japanese G2P adapter constructs its lexicon.
set -Eeuo pipefail

if [[ $# -ne 7 ]]; then
  echo "Usage: $0 <python> <raw-text> <trans-dir> <dict-dir> <prono-dir> <model-dir> <utterance-id>" >&2
  exit 2
fi

python_executable=$1
raw_text=$2
trans_dir=$3
dict_dir=$4
prono_dir=$5
model_dir=$6
utterance_id=$7
language_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mecab_output="$prono_dir/mecab.txt"

bash "$language_dir/mecab.sh" "$raw_text" "$mecab_output"
bash "$language_dir/g2p.sh" "$mecab_output" "$prono_dir/raw_pronunciations.txt"
awk -F'+' '{print $1}' "$prono_dir/raw_pronunciations.txt" > "$prono_dir/g2p_words.txt"
awk '{$1=""; sub(/^ /, ""); print}' "$prono_dir/raw_pronunciations.txt" > "$prono_dir/g2p_phones.txt"
paste -d ' ' "$prono_dir/g2p_words.txt" "$prono_dir/g2p_phones.txt" > "$prono_dir/all_lexicon.txt"
awk 'NR == 1 { for (i = 2; i <= NF; i++) print $i }' "$model_dir/lexicon.txt" | LC_ALL=C sort -u > "$prono_dir/model_phones.txt"
awk 'NR == FNR { allowed[$1] = 1; next }
  { valid = (NF >= 2); for (i = 2; i <= NF; i++) if (!($i in allowed)) valid = 0; if (valid) print }' \
  "$prono_dir/model_phones.txt" "$prono_dir/all_lexicon.txt" > "$prono_dir/valid_lexicon.txt"

# Build the lexicon map once.  The former shell loop spawned one awk process
# for every token, which was O(tokens x lexicon entries).
tr ' ' '\n' < "$mecab_output" | awk -F'+' '{print $1}' > "$prono_dir/mecab_words.txt"
awk 'NR == FNR { if (!($1 in lexicon)) lexicon[$1] = $0; next }
  { if ($1 in lexicon) print lexicon[$1] }' \
  "$prono_dir/valid_lexicon.txt" "$prono_dir/mecab_words.txt" > "$prono_dir/sent_lexicon.txt"
[[ -s $prono_dir/sent_lexicon.txt ]] || { echo "Japanese transcript produced no alignable MeCab/G2P entries." >&2; exit 1; }
paste -d '\n' "$prono_dir/valid_lexicon.txt" "$model_dir/lexicon.txt" | LC_ALL=C sort -u | sed '/^[[:space:]]*$/d' > "$dict_dir/lexicon.txt"
printf '%s %s\n' "$utterance_id" "$(awk '{printf "%s%s", sep, $1; sep=" "}' "$prono_dir/sent_lexicon.txt")" > "$trans_dir/text"
