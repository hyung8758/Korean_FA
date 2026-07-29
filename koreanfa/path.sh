# Compatibility shim for Kaldi-derived scripts that source ./path.sh.
# The actual runtime path definition remains beside the packaged resources.
. "${KOREANFA_RUNTIME_ROOT:?KOREANFA_RUNTIME_ROOT must point to koreanfa/runtime}/path.sh" "$@"
