"""
Phase 3: Disable hardware-absent DIAG IDs in diag_cfg.c for POSIX build.

Changes the enable_evaluate field from DIAG_EVALUATION_ENABLED (or
DIAG_CAN_TIMING / DIAG_CAN_SENSOR_PRESENT) to DIAG_EVALUATION_DISABLED
for IDs that reference hardware not present on a POSIX vECU.

Idempotent: skips lines already containing the POSIX sentinel comment.
"""

import re
import sys

TARGET = "src/app/engine/config/diag_cfg.c"

# Hardware-absent DIAG IDs that must be disabled.
# These enum names appear at the start of each config line in diag_diagnosisIdConfiguration[].
DISABLE_IDS = [
    "DIAG_ID_FLASHCHECKSUM",
    "DIAG_ID_SYSTEM_MONITORING",
    "DIAG_ID_INTERLOCK_FEEDBACK",
    "DIAG_ID_SUPPLY_VOLTAGE_CLAMP_30C_LOST",
    "DIAG_ID_AFE_SPI",
    "DIAG_ID_AFE_COMMUNICATION_INTEGRITY",
    "DIAG_ID_AFE_MUX",
    "DIAG_ID_AFE_CONFIG",
    "DIAG_ID_AFE_OPEN_WIRE",
    "DIAG_ID_CAN_TIMING",
    "DIAG_ID_CURRENT_SENSOR_CC_RESPONDING",
    "DIAG_ID_CURRENT_SENSOR_EC_RESPONDING",
    "DIAG_ID_CURRENT_SENSOR_RESPONDING",
    "DIAG_ID_SBC_FIN_ERROR",
    "DIAG_ID_SBC_RSTB_ERROR",
    "DIAG_ID_PLAUSIBILITY_PACK_VOLTAGE",
    "DIAG_ID_STRING_MINUS_CONTACTOR_FEEDBACK",
    "DIAG_ID_STRING_PLUS_CONTACTOR_FEEDBACK",
    "DIAG_ID_PRECHARGE_CONTACTOR_FEEDBACK",
    "DIAG_ID_CURRENT_MEASUREMENT_TIMEOUT",
    "DIAG_ID_CURRENT_MEASUREMENT_ERROR",
    "DIAG_ID_CURRENT_SENSOR_V1_MEASUREMENT_TIMEOUT",
    "DIAG_ID_CURRENT_SENSOR_V2_MEASUREMENT_TIMEOUT",
    "DIAG_ID_CURRENT_SENSOR_V3_MEASUREMENT_TIMEOUT",
    "DIAG_ID_CURRENT_SENSOR_POWER_MEASUREMENT_TIMEOUT",
    "DIAG_ID_POWER_MEASUREMENT_ERROR",
    "DIAG_ID_INSULATION_MEASUREMENT_VALID",
    "DIAG_ID_LOW_INSULATION_RESISTANCE_ERROR",
    "DIAG_ID_LOW_INSULATION_RESISTANCE_WARNING",
    "DIAG_ID_INSULATION_GROUND_ERROR",
    "DIAG_ID_I2C_PEX_ERROR",
    "DIAG_ID_I2C_RTC_ERROR",
    "DIAG_ID_RTC_CLOCK_INTEGRITY_ERROR",
    "DIAG_ID_RTC_BATTERY_LOW_ERROR",
    "DIAG_ID_FRAM_READ_CRC_ERROR",
    "DIAG_ID_ALERT_MODE",
    "DIAG_ID_AEROSOL_ALERT",
    "DIAG_ID_CURRENT_ON_OPEN_STRING",
    "DIAG_ID_DEEP_DISCHARGE_DETECTED",
]

SENTINEL = "/* POSIX: disabled (no hardware) */"

try:
    with open(TARGET) as f:
        lines = f.readlines()
except FileNotFoundError:
    print(f"ERROR: {TARGET} not found")
    sys.exit(1)

patched_count = 0
already_count = 0
new_lines = []

for line in lines:
    matched = False
    for diag_id in DISABLE_IDS:
        # Match lines like: {DIAG_ID_FLASHCHECKSUM, ...
        if "{" + diag_id + "," in line:
            matched = True
            if SENTINEL in line:
                already_count += 1
                new_lines.append(line)
                break

            # Replace enable_evaluate value with DIAG_EVALUATION_DISABLED
            # Handles DIAG_EVALUATION_ENABLED, DIAG_CAN_TIMING, DIAG_CAN_SENSOR_PRESENT
            new_line = re.sub(
                r'(DIAG_EVALUATION_ENABLED|DIAG_CAN_TIMING|DIAG_CAN_SENSOR_PRESENT)',
                'DIAG_EVALUATION_DISABLED',
                line,
                count=1
            )

            # Add sentinel comment before the trailing callback
            # The line ends like: DIAG_EVALUATION_DISABLED,    DIAG_SomeCallback},
            # We want to add the sentinel at the end of the line (before newline)
            new_line = new_line.rstrip('\n').rstrip()
            if not new_line.endswith(SENTINEL):
                new_line = new_line + "  " + SENTINEL
            new_line += "\n"

            new_lines.append(new_line)
            patched_count += 1
            break

    if not matched:
        new_lines.append(line)

if patched_count == 0 and already_count > 0:
    print(f"already patched ({already_count} IDs)")
    sys.exit(0)

if patched_count == 0:
    print("WARNING: no lines matched — check DIAG ID names")
    sys.exit(1)

with open(TARGET, "w") as f:
    f.writelines(new_lines)

print(f"patched {patched_count} DIAG IDs to DIAG_EVALUATION_DISABLED (already: {already_count})")
