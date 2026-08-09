#!/usr/bin/env bash
# Build the pinned IceWM into this user's Kilix data directory, on request.
#
# "Lazily installed" is the point: the IceWM submodule is declared but NOT
# initialised by a normal clone, so nobody pays ~57 MB and a C++ build unless
# they actually choose this desktop. The first `kilix icewm` runs this.
#
# Nothing here touches system directories or needs root. The build lands under
# ~/.local/gpu_terminal/kilix-icewm/, matching the stack's storage contract.
set -euo pipefail
umask 077

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUBMODULE_PATH="third_party/icewm"
STORAGE_HOME="${KILIX_ICEWM_STORAGE_HOME:-$HOME/.local/gpu_terminal/kilix-icewm}"
PREFIX="${KILIX_ICEWM_PREFIX:-$STORAGE_HOME/prefix}"
BUILD_DIR="$STORAGE_HOME/build"
STAMP="$PREFIX/.built-from"

die() { printf 'kilix-icewm: %s\n' "$*" >&2; exit 1; }
log() { printf 'kilix-icewm: %s\n' "$*" >&2; }

print_path_only=0
force=0
for arg in "$@"; do
  case "$arg" in
    --print-path) print_path_only=1 ;;
    --force) force=1 ;;
    -h|--help)
      echo "usage: build-icewm.sh [--print-path] [--force]"
      exit 0 ;;
    *) die "unknown argument: $arg" ;;
  esac
done

session_binary() { printf '%s/bin/icewm-session' "$PREFIX"; }

# --print-path is the contract the Kilix launcher uses: it must print the path
# and build only if the binary is missing, so selecting an installed desktop
# never silently triggers a compile.
if [ "$print_path_only" = 1 ] && [ "$force" = 0 ] \
   && [ -x "$(session_binary)" ] && [ ! -L "$(session_binary)" ]; then
  session_binary
  exit 0
fi

pinned_commit() {
  git -C "$HERE" ls-tree HEAD "$SUBMODULE_PATH" 2>/dev/null | awk '{print $3}'
}

ensure_source() {
  local want; want="$(pinned_commit)"
  [ -n "$want" ] || die "no pinned IceWM commit recorded for $SUBMODULE_PATH"
  if [ ! -e "$HERE/$SUBMODULE_PATH/CMakeLists.txt" ]; then
    log "fetching pinned IceWM source (first use of this desktop)"
    git -C "$HERE" submodule update --init --recursive -- "$SUBMODULE_PATH" \
      || die "could not fetch the IceWM submodule"
  fi
  local have
  have="$(git -C "$HERE/$SUBMODULE_PATH" rev-parse HEAD 2>/dev/null || true)"
  [ "$have" = "$want" ] || log "warning: IceWM checkout $have is not the pinned $want"
  printf '%s' "$want"
}

check_build_deps() {
  local missing=()
  command -v cmake >/dev/null 2>&1 || missing+=(cmake)
  command -v pkg-config >/dev/null 2>&1 || missing+=(pkg-config)
  { command -v c++ >/dev/null 2>&1 || command -v g++ >/dev/null 2>&1; } \
    || missing+=("a C++ compiler")
  if [ "${#missing[@]}" -gt 0 ]; then
    die "missing build tools: ${missing[*]}
Install them, or use the distribution's icewm package and set
KILIX_ICEWM_PREFIX to the prefix that contains bin/icewm-session."
  fi
}

build() {
  local commit; commit="$(ensure_source)"
  check_build_deps
  log "building IceWM $commit -> $PREFIX"
  mkdir -p "$BUILD_DIR" "$PREFIX"
  # -DCONFIG_* off keeps the dependency surface to core X11: this desktop is
  # presented through a captured private display, so sound servers, tray icons
  # for a real panel, and session-manager integration have nothing to talk to.
  ( cd "$BUILD_DIR" && cmake "$HERE/$SUBMODULE_PATH" \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX="$PREFIX" \
      -DENABLE_NLS=OFF \
      -DCONFIG_XRANDR=ON \
      >/dev/null ) || die "cmake configuration failed (see $BUILD_DIR)"
  ( cd "$BUILD_DIR" && make -j"$(nproc 2>/dev/null || echo 2)" >/dev/null ) \
    || die "IceWM build failed (see $BUILD_DIR)"
  ( cd "$BUILD_DIR" && make install >/dev/null ) || die "IceWM install failed"
  printf '%s\n' "$commit" > "$STAMP"
  chmod 600 "$STAMP" 2>/dev/null || true
  log "built IceWM $commit"
}

if [ "$force" = 1 ] || [ ! -x "$(session_binary)" ]; then
  build
fi

[ -x "$(session_binary)" ] || die "build finished but $(session_binary) is missing"
session_binary
