#!/bin/bash
# GA-15: Apply all foxBMS POSIX patches in the correct order.
#
# Usage: cd foxbms-posix && ./patches/apply_all.sh
#
# This script must be run from the foxbms-posix repo root.
# foxbms-2/ submodule must be initialized (git submodule update --init).

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FOXBMS_DIR="$REPO_ROOT/foxbms-2"

# Version check
EXPECTED_VERSION="v1.10.0"
if [ -f "$FOXBMS_DIR/src/version/version_cfg.h" ]; then
    VERSION=$(grep 'VER_foxBMS_Release_' "$FOXBMS_DIR/src/version/version_cfg.h" 2>/dev/null || true)
    echo "[patches] foxBMS version info: $VERSION"
fi

if [ ! -d "$FOXBMS_DIR/src/app" ]; then
    echo "ERROR: foxbms-2/ submodule not initialized."
    echo "Run: git submodule update --init"
    exit 1
fi

echo "=== Applying foxBMS POSIX patches ==="
echo "foxBMS source: $FOXBMS_DIR"
echo ""

# Order matters: register patches first, then functional patches
PATCHES=(
    # 1. Register base redirection (must be first — patches HALCoGen headers)
    "patch_all_regs.py"
    "patch_canreg.py"
    # 2. Hardware bypass patches
    "patch_sbc.py"          # SBC_GetState returns RUNNING
    "patch_sbc2.py"         # SBC_SetStateRequest returns OK
    "patch_rtc.py"          # RTC_IsRtcModuleInitialized returns true
    "patch_can_sensor.py"   # CAN_IsCurrentSensorPresent returns true
    # 3. Database / data flow patches
    "patch_database.py"     # DATA_IterateOverDatabaseEntries made non-static
    "patch_database2.py"    # Database iterate trace
    # 4. Task / state machine patches
    "patch_ftask.py"        # Debug trace in engine/precyclic init
    "patch_sys2.py"         # SYS_Trigger state trace
    "patch_bms2.py"         # BMS_Trigger state trace
    "patch_10ms2.py"        # 10ms task trace
    "patch_precharge.py"    # Precharge trace
)

FAILED=0
# Patches use relative paths like "src/app/driver/sbc/sbc.c"
# so we must run them from inside the foxbms-2 directory
cd "$FOXBMS_DIR" || exit 1

for patch in "${PATCHES[@]}"; do
    PATCH_PATH="$SCRIPT_DIR/$patch"
    if [ ! -f "$PATCH_PATH" ]; then
        echo "  SKIP $patch (not found)"
        continue
    fi
    echo -n "  Applying $patch... "
    if python3 "$PATCH_PATH" 2>/dev/null; then
        echo "OK"
    else
        echo "FAILED"
        FAILED=$((FAILED + 1))
    fi
done

cd "$REPO_ROOT"

echo ""
if [ $FAILED -eq 0 ]; then
    echo "=== All patches applied successfully ==="
else
    echo "=== WARNING: $FAILED patch(es) failed ==="
    echo "This may happen if foxBMS source has changed from $EXPECTED_VERSION."
    echo "Check each failed patch and update line numbers if needed."
    exit 1
fi
