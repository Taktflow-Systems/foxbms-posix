#!/usr/bin/env bash
# S-CH-07 pilot smoke scenario: boot the SIL to its top run level,
# execute a console command, then shut down cleanly via lc poweroff.
# Pass criteria (all required):
#   - process exits 0 (clean poweroff, not timeout/abort)
#   - lifecycle reaches "Run level 9"
#   - console command "stats cpu" is received and succeeds
#   - "Lifecycle shutdown complete" is logged
set -uo pipefail
cd "$(dirname "$0")"

BIN="openbsw/build/posix-freertos/executables/referenceApp/application/Release/app.referenceApp.elf"
LOG="smoke-run.log"

if [ ! -x "$BIN" ]; then
    echo "SMOKE FAIL: binary missing — run ./build.sh first" >&2
    exit 2
fi

(sleep 2; printf 'stats cpu\n'; sleep 2; printf 'lc poweroff\n'; sleep 3) \
    | timeout 30 "$BIN" > "$LOG" 2>&1
rc=$?

plain="$(sed 's/\x1b\[[0-9;]*m//g' "$LOG")"
fail=0
while IFS= read -r marker; do
    if ! grep -qF "$marker" <<< "$plain"; then
        echo "SMOKE: missing marker: $marker"
        fail=1
    fi
done <<'MARKERS'
Run level 9
Received console command "stats cpu"
Console command succeeded
Lifecycle shutdown complete
MARKERS

if [ "$rc" -ne 0 ]; then
    echo "SMOKE: nonzero exit code: $rc"
    fail=1
fi

if [ "$fail" -eq 0 ]; then
    echo "SMOKE PASS: exit 0, all 4 markers present (log: $LOG)"
else
    echo "SMOKE FAIL (log: $LOG)"
    exit 1
fi
