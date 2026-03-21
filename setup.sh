#!/bin/bash
# GA-19: Single-command setup for foxBMS POSIX vECU
#
# Usage: ./setup.sh [vcan_interface]
#
# Does everything needed:
# 1. Initialize foxbms-2 submodule
# 2. Apply all patches
# 3. Build foxbms-vecu
# 4. Set up virtual CAN
# 5. Run smoke test

set -e

CAN_IF="${1:-vcan1}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== foxBMS POSIX vECU Setup ==="
echo "CAN interface: $CAN_IF"
echo ""

# Step 1: Submodule
echo "--- Step 1: Initialize foxbms-2 submodule ---"
cd "$SCRIPT_DIR"
if [ ! -f "foxbms-2/src/app/main/main.c" ]; then
    git submodule update --init
    echo "Submodule initialized."
else
    echo "Submodule already present."
fi

# Step 2: Check HALCoGen headers
echo ""
echo "--- Step 2: Check HALCoGen headers ---"
if [ ! -d "foxbms-2/build/app_host_unit_test/include" ]; then
    echo "WARNING: HALCoGen headers not found at foxbms-2/build/app_host_unit_test/include/"
    echo "You need to copy them from a Windows build. See README.md for details."
    echo "Continuing anyway — build may fail."
else
    echo "HALCoGen headers found."
fi

# Step 3: Apply patches
echo ""
echo "--- Step 3: Apply patches ---"
bash "$SCRIPT_DIR/patches/apply_all.sh"

# Step 4: Build
echo ""
echo "--- Step 4: Build foxbms-vecu ---"
cd "$SCRIPT_DIR/src"
make clean
make -j$(nproc)
echo "Build complete."

# Step 5: Set up vcan
echo ""
echo "--- Step 5: Set up virtual CAN ($CAN_IF) ---"
if ip link show "$CAN_IF" > /dev/null 2>&1; then
    echo "$CAN_IF already exists."
else
    echo "Creating $CAN_IF (requires sudo)..."
    sudo ip link add "$CAN_IF" type vcan
    sudo ip link set "$CAN_IF" up
    echo "$CAN_IF created and up."
fi

# Step 6: Smoke test
echo ""
echo "--- Step 6: Smoke test ---"
echo "Starting plant model + vECU..."
python3 test_smoke.py "$CAN_IF"
RESULT=$?

echo ""
if [ $RESULT -eq 0 ]; then
    echo "=== SETUP COMPLETE — ALL PASS ==="
else
    echo "=== SETUP COMPLETE — SMOKE TEST FAILED (exit code $RESULT) ==="
fi

exit $RESULT
