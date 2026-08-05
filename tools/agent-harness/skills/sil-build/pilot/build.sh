#!/usr/bin/env bash
# S-CH-07 pilot: build the Eclipse OpenBSW referenceApp as a PC-hosted
# SIL executable (POSIX platform, FreeRTOS kernel emulation).
# Idempotent: clones only if the source tree is absent, then
# configure + build via the upstream cmake preset.
set -euo pipefail
cd "$(dirname "$0")"

REPO_URL="https://github.com/eclipse-openbsw/openbsw.git"
PINNED_COMMIT="bc8d49b58b26050bef8d3d79575b404c36750324"
SRC="openbsw"
PRESET="posix-freertos"

if [ ! -d "$SRC/.git" ]; then
    git clone --depth 1 "$REPO_URL" "$SRC"
fi

ACTUAL="$(git -C "$SRC" rev-parse HEAD)"
if [ "$ACTUAL" != "$PINNED_COMMIT" ]; then
    echo "WARNING: source at $ACTUAL, pilot was validated at $PINNED_COMMIT" >&2
fi

cd "$SRC"
cmake --preset "$PRESET"
cmake --build "build/$PRESET" -j"$(nproc)"

BIN="build/$PRESET/executables/referenceApp/application/Release/app.referenceApp.elf"
ls -la "$BIN"
echo "BUILD OK: $SRC/$BIN"
