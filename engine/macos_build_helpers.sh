#!/usr/bin/env bash
# Shared filesystem, download, and Mach-O helpers for build_macos.sh.

copy_file() {
  local source=$1 destination=$2
  mkdir -p "$(dirname "$destination")"
  cp -pL "$source" "$destination"
}

fetch_git_revision() {
  local repository=$1 revision=$2 destination=$3 label=$4
  local attempt=1 maximum_attempts=5 retry_delay actual_revision

  mkdir -p "$destination"
  git -C "$destination" init --quiet
  git -C "$destination" remote add origin "$repository"

  while (( attempt <= maximum_attempts )); do
    if git -c http.version=HTTP/1.1 -C "$destination" fetch \
      --quiet --depth=1 --no-tags origin "$revision"; then
      git -C "$destination" checkout --quiet --detach FETCH_HEAD
      actual_revision=$(git -C "$destination" rev-parse HEAD)
      if [[ $actual_revision == "$revision" ]]; then
        return 0
      fi
      echo "Fetched unexpected ${label} revision: ${actual_revision}." >&2
      return 1
    fi

    if (( attempt == maximum_attempts )); then
      echo "Failed to fetch ${label} revision ${revision} after ${maximum_attempts} attempts." >&2
      return 1
    fi
    retry_delay=$((attempt * 5))
    echo "Retrying ${label} source download in ${retry_delay} seconds (${attempt}/${maximum_attempts})..." >&2
    sleep "$retry_delay"
    attempt=$((attempt + 1))
  done
}

download_archive() {
  local url=$1 destination=$2 label=$3
  curl --fail --location --silent --show-error \
    --connect-timeout 30 --retry 5 --retry-delay 3 --retry-all-errors \
    --output "$destination" "$url" || {
      echo "Failed to download ${label}: ${url}" >&2
      return 1
    }
}

is_system_library() {
  case $1 in
    /System/Library/*|/usr/lib/*|/Library/Apple/*) return 0 ;;
    *) return 1 ;;
  esac
}

macho_dependencies() {
  otool -L "$1" | awk 'NR > 1 { print $1 }'
}

macho_rpaths() {
  otool -l "$1" | awk '
    $1 == "cmd" && $2 == "LC_RPATH" { wanted = 1; next }
    wanted && $1 == "path" { print $2; wanted = 0 }
  '
}

ensure_macho_rpath() {
  local owner=$1 rpath=$2
  if macho_rpaths "$owner" | grep -Fxq "$rpath"; then
    return 0
  fi
  install_name_tool -add_rpath "$rpath" "$owner"
}

resolve_macho_dependency() {
  local owner=$1 dependency=$2 rpath candidate
  case $dependency in
    /*)
      [[ -f $dependency ]] && { printf '%s\n' "$dependency"; return 0; }
      ;;
    @loader_path/*)
      candidate="$(dirname "$owner")/${dependency#@loader_path/}"
      [[ -f $candidate ]] && { printf '%s\n' "$candidate"; return 0; }
      ;;
    @executable_path/*)
      candidate="$engine_root/${dependency#@executable_path/}"
      [[ -f $candidate ]] && { printf '%s\n' "$candidate"; return 0; }
      ;;
    @rpath/*)
      while IFS= read -r rpath; do
        rpath=${rpath/@loader_path/$(dirname "$owner")}
        rpath=${rpath/@executable_path/$engine_root}
        candidate="$rpath/${dependency#@rpath/}"
        [[ -f $candidate ]] && { printf '%s\n' "$candidate"; return 0; }
      done < <(macho_rpaths "$owner")
      ;;
  esac
  return 1
}

relative_path() {
  "$python_command" - "$1" "$2" <<'PY'
import os
import sys
print(os.path.relpath(sys.argv[2], os.path.dirname(sys.argv[1])))
PY
}

assert_architecture() {
  local binary=$1 actual
  actual=$(lipo -archs "$binary")
  grep -qw "$architecture" <<<"$actual" || {
    echo "Expected ${architecture} Mach-O binary, received '${actual}': $binary" >&2
    exit 1
  }
}

packaged_macho_files() {
  find "$engine_root/kaldi" -type f -perm -u+x -print
  find "$engine_root/lib" -type f -name '*.dylib*' -print
}

final_macho_files() {
  packaged_macho_files
  [[ ! -f $engine_root/mecab/bin/mecab ]] || printf '%s\n' "$engine_root/mecab/bin/mecab"
}
