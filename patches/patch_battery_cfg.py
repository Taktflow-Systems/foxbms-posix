"""
Phase 3: Patch battery config for NMC cell chemistry.

foxBMS default is configured for a low-voltage cell (LTO/specialized):
  Nominal: 2500 mV, Range: 1500-2800 mV, String current: 2.4 A

Our plant model simulates NMC cells (3 Ah, 18650):
  Nominal: 3700 mV, Range: 2500-4200 mV, String current: up to 15 A

This patch updates voltage thresholds and current limits.

Idempotent: checks for sentinel comment before patching.
"""

import sys

SENTINEL = "/* POSIX: patched for NMC chemistry */"

# File 1: battery_cell_cfg.h — voltage thresholds
CELL_CFG = "src/app/application/config/battery_cell_cfg.h"
CELL_REPLACEMENTS = [
    # Overvoltage (mV)
    ("BC_VOLTAGE_MAX_MSL_mV", "2800", "4250"),
    ("BC_VOLTAGE_MAX_RSL_mV", "2750", "4200"),
    ("BC_VOLTAGE_MAX_MOL_mV", "2720", "4150"),
    # Nominal (mV)
    ("BC_VOLTAGE_NOMINAL_mV", "2500", "3700"),
    # Undervoltage (mV)
    ("BC_VOLTAGE_MIN_MSL_mV", "1500", "2500"),
    ("BC_VOLTAGE_MIN_RSL_mV", "1550", "2600"),
    ("BC_VOLTAGE_MIN_MOL_mV", "1580", "2700"),
]

# File 2: battery_system_cfg.h — string current limit
SYSTEM_CFG = "src/app/application/config/battery_system_cfg.h"
SYSTEM_REPLACEMENTS = [
    # String current limit (mA) — 2.4A too low for 3Ah NMC
    # Set to 15A (~5C) for our simulation
    ("BS_MAXIMUM_STRING_CURRENT_mA", "2400u", "15000u"),
    # Pack current limit (mA) — uses hardcoded 2400 * NR_STRINGS
    # Set to 15A * NR_STRINGS for consistency
    ("BS_MAXIMUM_PACK_CURRENT_mA", "2400u * BS_NR_OF_STRINGS", "15000u * BS_NR_OF_STRINGS"),
]


def patch_file(filepath, replacements):
    try:
        with open(filepath) as f:
            code = f.read()
    except FileNotFoundError:
        print(f"ERROR: {filepath} not found")
        return 0

    if SENTINEL in code:
        print(f"  {filepath}: already patched")
        return -1

    patched = 0
    for name, old_val, new_val in replacements:
        old_define = f"#define {name} ({old_val})"
        new_define = f"#define {name} ({new_val})  {SENTINEL}"
        if old_define in code:
            code = code.replace(old_define, new_define, 1)
            patched += 1
        else:
            print(f"  WARNING: '{old_define}' not found in {filepath}")

    if patched > 0:
        with open(filepath, "w") as f:
            f.write(code)

    return patched


total = 0
r1 = patch_file(CELL_CFG, CELL_REPLACEMENTS)
if r1 > 0:
    total += r1
r2 = patch_file(SYSTEM_CFG, SYSTEM_REPLACEMENTS)
if r2 > 0:
    total += r2

if r1 == -1 and r2 == -1:
    print("already patched")
    sys.exit(0)

if total == 0:
    print("WARNING: no thresholds matched")
    sys.exit(1)

print(f"patched {total} thresholds for NMC chemistry (V: 2500-4250 mV, I: 15A string)")
