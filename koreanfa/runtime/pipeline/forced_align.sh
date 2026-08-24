#!/usr/bin/env bash
# Batch runtime entrypoint used by the Python API and optional shell users.
# It emits KOREANFA_EVENT and KOREANFA_SUMMARY records for callers that need
# progress without parsing Kaldi's human-oriented diagnostic output.
set -Eeuo pipefail

runtime_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$runtime_root/.."
kaldi=${KOREANFA_KALDI_DIR:-/home/kaldi}
language=${KOREANFA_LANG:-kor}
python_executable=${KOREANFA_PYTHON_EXECUTABLE:-python}
num_jobs=4; skip_existing=false; ignore_unmatched=true; word_option=; phone_option=

usage() {
  cat <<'EOF'
Usage: forced_align.sh [options] DIRECTORY
  -nj, --num-jobs N  Run at most N files concurrently (default: 4).
  -s, --skip         Skip pairs with an existing TextGrid.
  -iu, --ignore-unmatched [true|false]
                         Skip unmatched WAV/TXT files with a warning (default: true).
  -nw, --no-word     Do not generate the word tier.
  -np, --no-phone    Do not generate the phone tier.
EOF
}
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help) usage; exit 0 ;;
    -s|--skip) skip_existing=true; shift ;;
    -iu|--ignore-unmatched)
      case ${2:-} in
        true|1|yes) ignore_unmatched=true; shift 2 ;;
        false|0|no) ignore_unmatched=false; shift 2 ;;
        *) ignore_unmatched=true; shift ;;
      esac
      ;;
    -nj|--num-jobs|--num-job) [[ $# -ge 2 ]] || { echo "$1 requires a value" >&2; exit 2; }; num_jobs=$2; shift 2 ;;
    -nw|--no-word) word_option=--no-word; shift ;;
    -np|--no-phone) phone_option=--no-phone; shift ;;
    --) shift; break ;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    *) break ;;
  esac
done
[[ $# -eq 1 ]] || { usage >&2; exit 2; }
[[ $num_jobs =~ ^[1-9][0-9]*$ ]] || { echo "--num-jobs must be a positive integer" >&2; exit 2; }
[[ -d $kaldi ]] || { echo "Kaldi directory is not available: $kaldi" >&2; exit 1; }
[[ $language =~ ^[a-z][a-z0-9_-]*$ && -f $runtime_root/languages/$language/profile.sh ]] || {
  echo "No KoreanFA language profile exists for: $language" >&2; exit 2;
}
data_dir=$("$python_executable" -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1")
[[ -d $data_dir ]] || { echo "Input directory does not exist: $data_dir" >&2; exit 2; }
export KOREANFA_RUNTIME_ROOT="$runtime_root"
source "$runtime_root/path.sh" "$kaldi"
log_dir=${KOREANFA_LOG_DIR:-"$data_dir/koreanfa-logs"}
mkdir -p "$log_dir"; : > "$log_dir/history.tsv"
tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/koreanfa-runtime.XXXXXX")
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM

# Pair files through the package's single Python implementation.  Writing the
# NUL-delimited records to a file first preserves helper failures (unlike a
# process substitution) and remains safe for spaces and newlines in paths.
pair_records="$tmp_dir/pairs.bin"
"$python_executable" "$runtime_root/pipeline/pair_corpus.py" "$data_dir" > "$pair_records"
declare -a audio_files text_files missing_text missing_audio
pair_count=0; missing_text_count=0; missing_audio_count=0
while IFS= read -r -d '' record_type && \
      IFS= read -r -d '' relative_stem && \
      IFS= read -r -d '' audio && \
      IFS= read -r -d '' transcript; do
  case $record_type in
    PAIR)
      if [[ $skip_existing == true && -f ${audio%.*}.TextGrid ]]; then
        printf 'KOREANFA_EVENT\tskipped\t-\t%s\texisting TextGrid\n' "$(basename -- "$audio")"
        continue
      fi
      audio_files[pair_count]=$audio
      text_files[pair_count]=$transcript
      pair_count=$((pair_count + 1))
      ;;
    MISSING_TEXT)
      missing_text[missing_text_count]=$relative_stem
      missing_text_count=$((missing_text_count + 1))
      ;;
    MISSING_AUDIO)
      missing_audio[missing_audio_count]=$relative_stem
      missing_audio_count=$((missing_audio_count + 1))
      ;;
    *) echo "Invalid corpus pairing record: $record_type" >&2; exit 2 ;;
  esac
done < "$pair_records"

print_unmatched() {
  local label=$1 item separator=
  shift
  printf '%s: ' "$label" >&2
  for item in "$@"; do
    printf '%s%s' "$separator" "$item" >&2
    separator=', '
  done
  printf '\n' >&2
}

if (( missing_text_count || missing_audio_count )); then
  if [[ $ignore_unmatched == false ]]; then
    echo "Unmatched corpus files." >&2
    (( missing_text_count )) && print_unmatched "WAV without TXT" "${missing_text[@]}"
    (( missing_audio_count )) && print_unmatched "TXT without WAV" "${missing_audio[@]}"
    exit 2
  fi
  echo "koreanfa: warning: ignoring unmatched corpus files." >&2
  (( missing_text_count )) && print_unmatched "WAV without TXT" "${missing_text[@]}"
  (( missing_audio_count )) && print_unmatched "TXT without WAV" "${missing_audio[@]}"
  for ((i = 0; i < missing_text_count; i++)); do
    stem=${missing_text[i]}
    printf 'KOREANFA_EVENT\tskipped\t-\t%s\tmissing matching TXT\n' "$stem"
  done
  for ((i = 0; i < missing_audio_count; i++)); do
    stem=${missing_audio[i]}
    printf 'KOREANFA_EVENT\tskipped\t-\t%s\tmissing matching WAV\n' "$stem"
  done
fi
total=$pair_count
(( total > 0 )) || { echo "No matched WAV/TXT pairs found in $data_dir" >&2; exit 2; }

run_pair() {
  local index=$1 audio=$2 transcript=$3 stage="$tmp_dir/pair_$1" output="${2%.*}.TextGrid"
  mkdir -p "$stage"; cp -- "$audio" "$stage/pair_$index.wav"; cp -- "$transcript" "$stage/pair_$index.txt"
  printf 'KOREANFA_EVENT\tstarted\t%s\t%s\n' "$index" "$(basename -- "$audio")"
  bash "$runtime_root/pipeline/main_fa.sh" "$language" "$index" "$log_dir" "$output" \
    "$stage/pair_$index.wav" "$stage/pair_$index.txt" "$kaldi" "$word_option" "$phone_option"
}

# Keep each file worker busy until the corpus is exhausted.  This works on
# Bash 3.2 (the macOS system shell) without wait -n, while avoiding the idle
# slots caused by waiting for a whole batch of unevenly sized recordings.
worker() {
  local worker_index=$1 index worker_failed=0
  for ((index = worker_index; index < total; index += num_jobs)); do
    run_pair "$index" "${audio_files[index]}" "${text_files[index]}" || worker_failed=1
  done
  return "$worker_failed"
}

worker_count=$num_jobs
(( worker_count <= total )) || worker_count=$total
failed=0; declare -a pids
for ((i = 0; i < worker_count; i++)); do
  worker "$i" &
  pids[i]=$!
done
for ((i = 0; i < worker_count; i++)); do
  wait "${pids[i]}" || failed=$((failed + 1))
done
success=$(awk -F '\t' '$1 == "SUCCESS" { count++ } END { print count + 0 }' "$log_dir/history.tsv")
failure=$(awk -F '\t' '$1 == "FAIL" { count++ } END { print count + 0 }' "$log_dir/history.tsv")
if (( success + failure != total )); then failure=$((total - success)); failed=$failure; fi
printf 'total\t%s\nsuccess\t%s\nfailed\t%s\n' "$total" "$success" "$failure" > "$log_dir/summary.tsv"
printf 'KOREANFA_SUMMARY\ttotal=%s\tsuccess=%s\tfailed=%s\n' "$total" "$success" "$failure"
(( failed == 0 && failure == 0 ))
