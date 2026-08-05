#!/usr/bin/env bash
# Exercise ex01 — mechanical replay of the full sil-debug cycle:
#   healthy baseline PASS -> inject defect.patch -> same test FAILS
#   -> fix (remove defect) -> same test PASSES -> baseline smoke green
# Leaves the pilot source tree exactly as it found it.
# Requires: sil-build pilot cloned + built (../../../sil-build/pilot/build.sh).
set -euo pipefail
cd "$(dirname "$0")"

PILOT="../../../sil-build/pilot"
SRC="$PILOT/openbsw"
TEST=./test_can_counter_frame.sh

if ! git -C "$SRC" diff --quiet; then
    echo "EXERCISE ERROR: pilot tree is dirty — refusing to patch over local changes" >&2
    exit 2
fi

build() { cmake --build "$SRC/build/posix-freertos" -j"$(nproc)" > /dev/null; }

echo "== step 0: healthy baseline must pass =="
build
"$TEST" baseline-check.log

echo "== step 1: inject defect, same test must FAIL =="
git -C "$SRC" apply "$(pwd)/defect.patch"
build
if "$TEST" failing-run.log; then
    git -C "$SRC" apply -R "$(pwd)/defect.patch"
    echo "EXERCISE FAIL: test passed despite injected defect" >&2
    exit 1
fi

echo "== step 2+3: fix at root cause (remove the injected defect), rebuild =="
git -C "$SRC" apply -R "$(pwd)/defect.patch"
build

echo "== step 4: same test must PASS, baseline smoke must stay green =="
"$TEST" passing-run.log
(cd "$PILOT" && ./smoke.sh)

echo "EXERCISE PASS: reproduce -> localize -> fix -> prove cycle complete"
echo "evidence: failing-run.log (length=3 frames), passing-run.log, $PILOT/smoke-run.log"
