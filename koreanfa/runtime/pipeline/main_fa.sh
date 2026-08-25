#!/usr/bin/env bash
# Align one staged WAV/TXT pair with a language profile and write one TextGrid.
# The batch runner controls file-level parallelism; this script owns one pair,
# prepares its temporary Kaldi data, retries decoding, and records its result.
set -Eeuo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: main_fa.sh <language> <job-id> <log-root> <output-textgrid> <wav> <txt> <kaldi-dir> [--no-word] [--no-phone] [--no-romanization]
EOF
}

parse_arguments() {
  [[ $# -ge 7 && $# -le 10 ]] || { usage; exit 2; }

  LANGUAGE=$1
  JOB_ID=$2
  LOG_ROOT=$3
  OUTPUT_TEXTGRID=$4
  WAV_FILE=$5
  TXT_FILE=$6
  KALDI_DIR=$7
  WORD_OPTION=${8:-}
  PHONE_OPTION=${9:-}
  ROMANIZATION_OPTION=${10:-}

  # Older callers represented an omitted option as the literal string "none".
  if [[ $WORD_OPTION == none ]]; then
    WORD_OPTION=
  fi
  if [[ $PHONE_OPTION == none ]]; then
    PHONE_OPTION=
  fi
  if [[ $ROMANIZATION_OPTION == none ]]; then
    ROMANIZATION_OPTION=
  fi
}

load_language_profile() {
  RUNTIME_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
  export KOREANFA_RUNTIME_ROOT="$RUNTIME_ROOT"

  # Kaldi-derived helpers retain historical runtime/pipeline relative paths.
  # Running from the package directory keeps those helpers unchanged.
  cd "$RUNTIME_ROOT/.."

  [[ $LANGUAGE =~ ^[a-z][a-z0-9_-]*$ ]] || { echo "Invalid language identifier: $LANGUAGE" >&2; exit 2; }
  PROFILE="$RUNTIME_ROOT/languages/$LANGUAGE/profile.sh"
  [[ -f $PROFILE ]] || { echo "No KoreanFA language profile exists for: $LANGUAGE" >&2; exit 2; }

  # shellcheck source=/dev/null
  source "$PROFILE"
  MODEL_DIR="$RUNTIME_ROOT/$model_relative"
  [[ -f $MODEL_DIR/final.mdl ]] || { echo "Language model is unavailable: $MODEL_DIR" >&2; exit 1; }
}

initialize_workspace() {
  WORK_DIR=$(dirname -- "$WAV_FILE")
  LOG_NAME=$(basename -- "${WAV_FILE%.wav}")

  JOB_LOG="$WORK_DIR/log_$JOB_ID"
  DATA_DIR="$WORK_DIR/data_$JOB_ID"
  TRANS_DIR="$WORK_DIR/trans_$JOB_ID"
  DICT_DIR="$WORK_DIR/dict_$JOB_ID"
  LANG_DIR="$WORK_DIR/lang_$JOB_ID"
  RESULT_DIR="$WORK_DIR/result_$JOB_ID"
  ALIGN_DIR="$WORK_DIR/fa_$JOB_ID"
  RAW_SENT_DIR="$WORK_DIR/raw_$JOB_ID"
  PRONUNCIATION_DIR="$WORK_DIR/prono_$JOB_ID"

  mkdir -p \
    "$JOB_LOG" "$DATA_DIR" "$TRANS_DIR" "$DICT_DIR" "$LANG_DIR" \
    "$RESULT_DIR" "$ALIGN_DIR" "$RAW_SENT_DIR" "$PRONUNCIATION_DIR"
}

record_failure() {
  local exit_code=$? failed_command=$BASH_COMMAND
  trap - ERR
  # Functions that can identify an expected input rejection set a clearer
  # reason before returning non-zero. Keep that information for batch users.
  if [[ $FAILURE_REASON == "pipeline did not finish" ]]; then
    FAILURE_REASON="command failed (exit $exit_code): ${failed_command}"
  fi
  return "$exit_code"
}

finish_job() {
  local exit_code=$?
  trap - EXIT
  mkdir -p "$LOG_ROOT"

  if [[ $exit_code -eq 0 && $JOB_STATUS == success ]]; then
    printf 'SUCCESS\t%s\t%s\n' "$JOB_ID" "$LOG_NAME" >> "$LOG_ROOT/history.tsv"
    printf 'KOREANFA_EVENT\tcompleted\t%s\t%s\n' "$JOB_ID" "$LOG_NAME"
  else
    printf 'FAIL\t%s\t%s\t%s\n' "$JOB_ID" "$LOG_NAME" "$FAILURE_REASON" >> "$LOG_ROOT/history.tsv"
    printf 'KOREANFA_EVENT\tfailed\t%s\t%s\t%s\n' "$JOB_ID" "$LOG_NAME" "$FAILURE_REASON"
    exit_code=1
  fi

  # Preserve each pair's Kaldi log after the temporary work directories leave.
  if [[ -d $JOB_LOG ]]; then
    rm -rf "$LOG_ROOT/log_$LOG_NAME"
    mv "$JOB_LOG" "$LOG_ROOT/log_$LOG_NAME"
  fi
  exit "$exit_code"
}

prepare_transcript_and_dictionary() {
  local raw_text="$RAW_SENT_DIR/$LOG_NAME.raw"
  local -a prepare_args

  cp -- "$WAV_FILE" "$DATA_DIR/$LOG_NAME.wav"
  cp -- "$TXT_FILE" "$DATA_DIR/$LOG_NAME.txt"
  printf 'KOREANFA_EVENT\tpreparing\t%s\t%s\n' "$JOB_ID" "$LOG_NAME"

  "$PYTHON_EXECUTABLE" "$RUNTIME_ROOT/pipeline/check_text.py" "$DATA_DIR"
  "$PYTHON_EXECUTABLE" "$RUNTIME_ROOT/pipeline/fa_prep_data.py" "$DATA_DIR" "$TRANS_DIR"
  "$RUNTIME_ROOT/pipeline/core/utt2spk_to_spk2utt.pl" "$TRANS_DIR/utt2spk" > "$TRANS_DIR/spk2utt"

  # check_text.py normalizes all whitespace to single spaces before tokenizing.
  tr ' ' '\n' < "$DATA_DIR/$LOG_NAME.txt" > "$raw_text"
  prepare_args=(
    "$LANGUAGE" "$PYTHON_EXECUTABLE" "$raw_text" "$TRANS_DIR" "$DICT_DIR"
    "$PRONUNCIATION_DIR" "$MODEL_DIR" "$LOG_NAME"
  )
  if [[ -n ${KOREANFA_PRONUNCIATION_DICTIONARY:-} ]]; then
    [[ -f $KOREANFA_PRONUNCIATION_DICTIONARY ]] || {
      FAILURE_REASON="Pronunciation dictionary is unavailable: $KOREANFA_PRONUNCIATION_DICTIONARY"
      return 1
    }
    prepare_args+=("$KOREANFA_PRONUNCIATION_DICTIONARY")
  fi
  if ! bash "$RUNTIME_ROOT/pipeline/prepare.sh" "${prepare_args[@]}"; then
    if [[ $LANGUAGE == jap && -s $PRONUNCIATION_DIR/mecab.txt && ! -s $PRONUNCIATION_DIR/sent_lexicon.txt ]]; then
      FAILURE_REASON="Japanese transcript produced no alignable MeCab/G2P entries."
    else
      FAILURE_REASON="Transcript preparation failed."
    fi
    return 1
  fi
  bash "$RUNTIME_ROOT/pipeline/prepare_new_lang.sh" \
    "$DICT_DIR" "$LANG_DIR" "$oov_word" "$silence_phone" "$unknown_phone"
}

prepare_features_and_aligner() {
  case "$alignment_kind" in
    gmm)
      local mfcc_dir="$DATA_DIR/mfcc"
      bash "$RUNTIME_ROOT/pipeline/core/make_mfcc.sh" --nj 1 \
        --cmd run.pl "$TRANS_DIR" "$JOB_LOG" "$mfcc_dir"
      bash "$RUNTIME_ROOT/pipeline/core/fix_data_dir.sh" "$TRANS_DIR"
      bash "$RUNTIME_ROOT/pipeline/core/compute_cmvn_stats.sh" "$TRANS_DIR" "$JOB_LOG" "$mfcc_dir"
      bash "$RUNTIME_ROOT/pipeline/core/fix_data_dir.sh" "$TRANS_DIR"
      ALIGN_SCRIPT="$RUNTIME_ROOT/pipeline/core/align_si.sh"
      ALIGN_ARGS=("$TRANS_DIR" "$LANG_DIR" "$MODEL_DIR" "$ALIGN_DIR")
      ;;
    nnet3)
      [[ -n $mfcc_config ]] || { echo "nnet3 profile requires mfcc_config" >&2; exit 2; }
      local mfcc_dir="$TRANS_DIR/mfcchires"
      bash "$RUNTIME_ROOT/pipeline/core/make_mfcc.sh" --nj 1 \
        --cmd run.pl --mfcc-config "$RUNTIME_ROOT/$mfcc_config" \
        "$TRANS_DIR" "$JOB_LOG" "$mfcc_dir"
      bash "$RUNTIME_ROOT/pipeline/core/fix_data_dir.sh" "$TRANS_DIR"
      bash "$RUNTIME_ROOT/pipeline/core/compute_cmvn_stats.sh" "$TRANS_DIR" "$JOB_LOG" "$mfcc_dir"
      bash "$RUNTIME_ROOT/pipeline/core/fix_data_dir.sh" "$TRANS_DIR"

      local ivector_dir="$TRANS_DIR/ivector"
      bash "$RUNTIME_ROOT/pipeline/core/extract_ivectors_online.sh" \
        --cmd run.pl --nj 1 \
        "$TRANS_DIR" "$MODEL_DIR/ivector_extractor" "$ivector_dir"
      ALIGN_SCRIPT="$RUNTIME_ROOT/pipeline/core/align_nnet3.sh"
      ALIGN_ARGS=("$ivector_dir" "$LANG_DIR" "$MODEL_DIR" "$ALIGN_DIR")
      ;;
    *)
      echo "Unsupported alignment_kind in $PROFILE: $alignment_kind" >&2
      exit 2
      ;;
  esac
}

decode_with_retries() {
  # Each worker owns exactly one staged pair.  Parallelism is managed by the
  # outer batch runner, so Kaldi's commands intentionally use --nj 1 here.
  local beams=(10 80 1000)
  local retry_beams=(40 100 2500)
  local index attempt align_log alignment_exit

  for index in "${!beams[@]}"; do
    attempt=$((index + 1))
    align_log="$JOB_LOG/align.$LOG_NAME.log"
    rm -f "$align_log"
    printf 'KOREANFA_EVENT\tattempt\t%s\t%s\t%s/3\n' "$JOB_ID" "$LOG_NAME" "$attempt"

    alignment_exit=0
    bash "$ALIGN_SCRIPT" --nj 1 --cmd run.pl \
      "${ALIGN_ARGS[@]}" "${beams[index]}" "${retry_beams[index]}" "$LOG_NAME" "$JOB_LOG" \
      || alignment_exit=$?

    [[ -f $align_log ]] || { FAILURE_REASON="Kaldi did not create an alignment log on attempt $attempt"; return 1; }
    if grep -q 'ERROR' "$align_log"; then
      FAILURE_REASON="Kaldi reported an error on attempt $attempt"
      return 1
    fi
    if grep -q 'Did not successfully decode file' "$align_log"; then
      FAILURE_REASON="Kaldi could not decode the audio/transcript pair on attempt $attempt"
      continue
    fi
    (( alignment_exit == 0 )) || { FAILURE_REASON="Kaldi alignment command failed on attempt $attempt"; return 1; }
    [[ -s $ALIGN_DIR/ali.1.gz ]] || { FAILURE_REASON="Kaldi did not create an alignment archive on attempt $attempt"; return 1; }
    return 0
  done
  return 1
}

write_textgrid() {
  local raw_ctm="$ALIGN_DIR/raw_ali.ctm"
  local fixed_ctm="$ALIGN_DIR/fixed_ali.ctm"
  local tagged_alignment="$RESULT_DIR/tmp_fa/tagged_final_ali.txt"
  local text_num="$RAW_SENT_DIR/text_num.raw"

  "$KALDI_DIR/src/bin/ali-to-phones" --ctm-output "$MODEL_DIR/final.mdl" \
    "ark:gunzip -c $ALIGN_DIR/ali.1.gz|" - > "$raw_ctm"
  "$PYTHON_EXECUTABLE" "$RUNTIME_ROOT/pipeline/fix_ctm_float.py" "$raw_ctm" "$fixed_ctm"

  cp "$fixed_ctm" "$RESULT_DIR/fixed_ali.txt"
  cp "$LANG_DIR/phones.txt" "$RESULT_DIR/phones.txt"
  cp "$TRANS_DIR/segments" "$RESULT_DIR/segments"
  "$PYTHON_EXECUTABLE" "$RUNTIME_ROOT/pipeline/id2phone.py" \
    "$RESULT_DIR/phones.txt" "$RESULT_DIR/segments" "$RESULT_DIR/fixed_ali.txt" "$RESULT_DIR/final_ali.txt"

  mkdir -p "$RESULT_DIR/tmp_fa"
  {
    printf 'utt_id\tfile_id\tphone_id\tutt_num\tstart_ph\tdur_ph\tphone\tstart_utt\tend_utt\tstart_real\tend_real\n'
    cat "$RESULT_DIR/final_ali.txt"
  } > "$tagged_alignment"
  wc -l < "$PRONUNCIATION_DIR/sent_lexicon.txt" > "$text_num"

  # Bash 3.2 with nounset treats an empty array expansion as an unbound
  # variable. Build the optional arguments with positional parameters instead.
  set --
  [[ -n $WORD_OPTION ]] && set -- "$@" "$WORD_OPTION"
  [[ -n $PHONE_OPTION ]] && set -- "$@" "$PHONE_OPTION"
  [[ -n $ROMANIZATION_OPTION ]] && set -- "$@" "$ROMANIZATION_OPTION"
  set -- "$@" --language "$LANGUAGE"
  case "$LANGUAGE" in
    kor) set -- "$@" --romanization-file "$PRONUNCIATION_DIR/pronunciations_hangul.txt" ;;
    jap) set -- "$@" --romanization-file "$PRONUNCIATION_DIR/romanization_readings.txt" ;;
  esac
  "$PYTHON_EXECUTABLE" "$RUNTIME_ROOT/pipeline/generate_textgrid.py" \
    "$@" "$RESULT_DIR/tmp_fa" "$PRONUNCIATION_DIR/sent_lexicon.txt" "$text_num" "$DATA_DIR"
  mv "$DATA_DIR/tagged_final_ali.TextGrid" "$OUTPUT_TEXTGRID"
}

main() {
  parse_arguments "$@"
  PYTHON_EXECUTABLE=${KOREANFA_PYTHON_EXECUTABLE:-python}
  load_language_profile
  initialize_workspace

  JOB_STATUS=failed
  FAILURE_REASON="pipeline did not finish"
  trap record_failure ERR
  trap finish_job EXIT
  exec > >(tee -a "$JOB_LOG/process.$LOG_NAME.log") 2>&1

  prepare_transcript_and_dictionary
  prepare_features_and_aligner
  # Keep the decode-specific reason instead of replacing it in the ERR trap.
  if ! decode_with_retries; then
    exit 1
  fi
  write_textgrid
  JOB_STATUS=success
}

main "$@"
