#!/usr/bin/env bash
# Tokenize Japanese UTF-8 text with MeCab for KoreanFA's G2P step.
set -Eeuo pipefail

pron_opt=false
tag_opt=false
usage() {
  cat <<'EOF'
Usage: mecab.sh [options] <input-text> <output-text>
  -np, --no-pron  Omit pronunciation from each token.
  -nt, --no-tag   Emit only surface forms.
EOF
}
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help) usage; exit 0 ;;
    -np|--no-pron) pron_opt=true; shift ;;
    -nt|--no-tag) tag_opt=true; pron_opt=true; shift ;;
    -nj|--num-job) echo "$1 is no longer supported; MeCab preserves token order sequentially." >&2; exit 2 ;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    *) break ;;
  esac
done
[[ $# -eq 2 ]] || { usage >&2; exit 2; }

input_text=$1
save_file=$2
[[ -f $input_text ]] || { echo "Input text does not exist: $input_text" >&2; exit 1; }
mecab_cmd=${KOREANFA_MECAB_COMMAND:-mecab}
mecab_dict=${KOREANFA_MECAB_DICT:-}
if ! command -v "$mecab_cmd" >/dev/null 2>&1 && [[ ! -x $mecab_cmd ]]; then
  echo "MeCab command is not runnable: $mecab_cmd" >&2
  exit 1
fi
[[ -z $mecab_dict || -d $mecab_dict ]] || { echo "MeCab dictionary does not exist: $mecab_dict" >&2; exit 1; }

tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/koreanfa-japanese-mecab.XXXXXX")
trap 'rm -rf "$tmp_dir"' EXIT
: > "$save_file"
line_number=0
while IFS= read -r line || [[ -n $line ]]; do
  line_number=$((line_number + 1))
  raw="$tmp_dir/$line_number.raw"
  if [[ -n $mecab_dict ]]; then
    printf '%s\n' "$line" | "$mecab_cmd" -d "$mecab_dict" > "$raw"
  else
    printf '%s\n' "$line" | "$mecab_cmd" > "$raw"
  fi
  awk -F '\t' -v no_pron="$pron_opt" -v no_tag="$tag_opt" '
    $1 == "EOS" { next }
    {
      count = split($2, feature, ",")
      surface = $1
      if (no_tag == "true") { token = surface }
      else {
        tag = ""
        for (i = 1; i <= 4 && i <= count; i++)
          if (feature[i] != "*") tag = tag (tag == "" ? "" : "/") feature[i]
        token = surface "+" (no_pron == "true" ? "" : (count >= 9 ? feature[9] : surface) "+") tag
        sub(/\+\+/, "+", token)
      }
      output = output (output == "" ? "" : " ") token
    }
    END { print output }
  ' "$raw" >> "$save_file"
done < "$input_text"
