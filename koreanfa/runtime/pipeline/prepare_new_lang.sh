#!/usr/bin/env bash
# Backwards-compatible name for the shared Kaldi language-directory builder.
set -Eeuo pipefail
runtime_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exec bash "$runtime_root/pipeline/prepare_language.sh" "$@"
	
