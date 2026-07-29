#!/usr/bin/env bash
# Dispatch transcript preparation to a language adapter with a stable contract.
# New languages add only languages/<id>/profile.sh and prepare.sh.
set -Eeuo pipefail

if [[ $# -ne 8 ]]; then
  echo "Usage: $0 <language> <python> <raw-text> <trans-dir> <dict-dir> <prono-dir> <model-dir> <utterance-id>" >&2
  exit 2
fi

language=$1
runtime_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ $language =~ ^[a-z][a-z0-9_-]*$ ]] || { echo "Invalid language identifier: $language" >&2; exit 2; }
adapter="$runtime_root/languages/$language/prepare.sh"
[[ -f $adapter ]] || { echo "No KoreanFA language adapter exists for: $language" >&2; exit 2; }
exec bash "$adapter" "${@:2}"
