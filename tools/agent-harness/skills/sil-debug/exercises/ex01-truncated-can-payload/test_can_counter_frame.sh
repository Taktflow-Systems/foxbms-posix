#!/usr/bin/env bash
# Exercise ex01 — the reproduce/prove test (step 1 and step 4 of the
# sil-debug workflow). UNCHANGED between the failing and passing run.
#
# Expected behavior (spec: DemoSystem sends its cycle counter as a
# 4-byte big-endian payload in CAN frame 0x558 once per second):
#   - SIL boots to "Run level 9" (sanity precondition)
#   - at least 3 counter frames are confirmed sent on CAN_0
#   - EVERY confirmed 0x558 frame has length=4
# Exit 0 = expected behavior observed; exit 1 = defect reproduced.
set -uo pipefail
cd "$(dirname "$0")"

BIN="../../../sil-build/pilot/openbsw/build/posix-freertos/executables/referenceApp/application/Release/app.referenceApp.elf"
LOG="${1:-test-run.log}"

if [ ! -x "$BIN" ]; then
    echo "TEST ERROR: SIL binary missing — build the sil-build pilot first" >&2
    exit 2
fi

(sleep 6; printf 'lc poweroff\n'; sleep 3) | timeout 30 "$BIN" > "$LOG" 2>&1
rc=$?
plain="$(sed 's/\x1b\[[0-9;]*m//g' "$LOG")"

if [ "$rc" -ne 0 ]; then
    echo "TEST FAIL: SIL exited nonzero ($rc) — cannot assess behavior"
    exit 1
fi
if ! grep -qF "Run level 9" <<< "$plain"; then
    echo "TEST FAIL: SIL never reached Run level 9 (precondition)"
    exit 1
fi

sent="$(grep -F "[CanDemoListener] CAN frame sent, id=0x558" <<< "$plain")"
count="$(grep -c . <<< "$sent")"
if [ "$count" -lt 3 ]; then
    echo "TEST FAIL: only $count counter frames confirmed (need >= 3)"
    exit 1
fi

bad="$(grep -vF "length=4" <<< "$sent" | grep -c .)"
if [ "$bad" -ne 0 ]; then
    echo "TEST FAIL: $bad of $count frames on 0x558 have wrong payload length (expected length=4):"
    grep -vF "length=4" <<< "$sent" | head -3
    exit 1
fi

echo "TEST PASS: $count counter frames on 0x558, all length=4 (log: $LOG)"
exit 0
