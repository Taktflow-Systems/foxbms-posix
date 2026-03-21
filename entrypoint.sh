#!/bin/bash
# foxBMS POSIX vECU Docker entrypoint
# Sets up vcan and runs smoke test by default.
set -e

CAN_IF="${FOXBMS_CAN_IF:-vcan1}"

# Set up vcan (requires --privileged or host vcan module)
if ! ip link show "$CAN_IF" > /dev/null 2>&1; then
    ip link add "$CAN_IF" type vcan
    ip link set "$CAN_IF" up
    echo "[docker] $CAN_IF created and up"
else
    echo "[docker] $CAN_IF already exists"
fi

cd /foxbms-posix/src

# Default: run smoke test. Override with: docker run ... <command>
if [ $# -eq 0 ]; then
    echo "[docker] Running smoke test..."
    exec python3 test_smoke.py "$CAN_IF"
else
    exec "$@"
fi
