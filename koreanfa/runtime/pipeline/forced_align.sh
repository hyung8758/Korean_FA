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
      if [[ ${2:-} =~ ^(true|1|yes)$ ]]; then ignore_unmatched=true; shift 2
      elif [[ ${2:-} =~ ^(false|0|no)$ ]]; then ignore_unmatched=false; shift 2
      else ignore_unmatched=true; shift
      fi
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
data_dir=$($python_executable -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1")
[[ -d $data_dir ]] || { echo "Input directory does not exist: $data_dir" >&2; exit 2; }
export KOREANFA_RUNTIME_ROOT="$runtime_root"
source "$runtime_root/path.sh" "$kaldi"
log_dir=${KOREANFA_LOG_DIR:-"$data_dir/koreanfa-logs"}
mkdir -p "$log_dir"; : > "$log_dir/history.tsv"
tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/koreanfa-runtime.XXXXXX")
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM

# Pair files by their full relative stem, matching the Python API's directory
# behavior.  This lets shell callers opt into the same ignore_unmatched mode.
declare -A audio_by_stem=() text_by_stem=()
declare -a audio_files=() text_files=() missing_text=() missing_audio=()
while IFS= read -r -d '' audio; do
  audio_by_stem["${audio%.*}"]=$audio
done < <(find "$data_dir" -type f -iname '*.wav' -print0)
while IFS= read -r -d '' transcript; do
  text_by_stem["${transcript%.*}"]=$transcript
done < <(find "$data_dir" -type f -iname '*.txt' -print0)

for stem in "${!audio_by_stem[@]}"; do
  if [[ -z ${text_by_stem[$stem]+present} ]]; then
    missing_text+=("${stem#"$data_dir"/}")
  fi
done
for stem in "${!text_by_stem[@]}"; do
  if [[ -z ${audio_by_stem[$stem]+present} ]]; then
    missing_audio+=("${stem#"$data_dir"/}")
  fi
done

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

if (( ${#missing_text[@]} || ${#missing_audio[@]} )); then
  if [[ $ignore_unmatched == false ]]; then
    echo "Unmatched corpus files." >&2
    (( ${#missing_text[@]} )) && print_unmatched "WAV without TXT" "${missing_text[@]}"
    (( ${#missing_audio[@]} )) && print_unmatched "TXT without WAV" "${missing_audio[@]}"
    exit 2
  fi
  echo "koreanfa: warning: ignoring unmatched corpus files." >&2
  (( ${#missing_text[@]} )) && print_unmatched "WAV without TXT" "${missing_text[@]}"
  (( ${#missing_audio[@]} )) && print_unmatched "TXT without WAV" "${missing_audio[@]}"
  for stem in "${missing_text[@]}"; do
    printf 'KOREANFA_EVENT\tskipped\t-\t%s\tmissing matching TXT\n' "$stem"
  done
  for stem in "${missing_audio[@]}"; do
    printf 'KOREANFA_EVENT\tskipped\t-\t%s\tmissing matching WAV\n' "$stem"
  done
fi

# Sort matched stems so progress indices remain stable across invocations.
while IFS= read -r -d '' stem; do
  audio=${audio_by_stem[$stem]}
  transcript=${text_by_stem[$stem]}
  if [[ $skip_existing == true && -f ${audio%.*}.TextGrid ]]; then
    printf 'KOREANFA_EVENT\tskipped\t-\t%s\texisting TextGrid\n' "$(basename -- "$audio")"
    continue
  fi
  audio_files+=("$audio"); text_files+=("$transcript")
done < <(
  for stem in "${!audio_by_stem[@]}"; do
    if [[ -n ${text_by_stem[$stem]+present} ]]; then
      printf '%s\0' "$stem"
    fi
  done | LC_ALL=C sort -z
)
total=${#audio_files[@]}
(( total > 0 )) || { echo "No matched WAV/TXT pairs found in $data_dir" >&2; exit 2; }

run_pair() {
  local index=$1 audio=$2 transcript=$3 stage="$tmp_dir/pair_$1" output="${2%.*}.TextGrid"
  mkdir -p "$stage"; cp -- "$audio" "$stage/pair_$index.wav"; cp -- "$transcript" "$stage/pair_$index.txt"
  printf 'KOREANFA_EVENT\tstarted\t%s\t%s\n' "$index" "$(basename -- "$audio")"
  bash "$runtime_root/pipeline/main_fa.sh" "$language" "$index" "$log_dir" "$output" \
    "$stage/pair_$index.wav" "$stage/pair_$index.txt" "$kaldi" "$word_option" "$phone_option"
}

# Wait in batches to bound concurrent Kaldi processes to --num-jobs.
failed=0; declare -a pids=()
wait_batch() { local pid; for pid in "${pids[@]}"; do wait "$pid" || failed=$((failed + 1)); done; pids=(); }
for ((i = 0; i < total; i++)); do
  run_pair "$i" "${audio_files[i]}" "${text_files[i]}" &
  pids+=("$!")
  (( ${#pids[@]} < num_jobs )) || wait_batch
done
wait_batch
success=$(awk -F '\t' '$1 == "SUCCESS" { count++ } END { print count + 0 }' "$log_dir/history.tsv")
failure=$(awk -F '\t' '$1 == "FAIL" { count++ } END { print count + 0 }' "$log_dir/history.tsv")
if (( success + failure != total )); then failure=$((total - success)); failed=$failure; fi
printf 'total\t%s\nsuccess\t%s\nfailed\t%s\n' "$total" "$success" "$failure" > "$log_dir/summary.tsv"
printf 'KOREANFA_SUMMARY\ttotal=%s\tsuccess=%s\tfailed=%s\n' "$total" "$success" "$failure"
(( failed == 0 && failure == 0 ))
