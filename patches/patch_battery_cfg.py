"""
Phase 3: Patch battery_cell_cfg.h for NMC cell chemistry.

foxBMS default is configured for a low-voltage cell (LTO/specialized):
  Nominal: 2500 mV, Range: 1500-2800 mV

Our plant model simulates NMC cells:
  Nominal: 3700 mV, Range: 2500-4200 mV

This patch updates voltage thresholds to match NMC chemistry.

Idempotent: checks for sentinel comment before patching.
"""

import sys

TARGET = "src/app/application/config/battery_cell_cfg.h"
SENTINEL = "/* POSIX: patched for NMC chemistry */"

# NMC voltage thresholds (mV)
REPLACEMENTS = [
    # Overvoltage
    ("BC_VOLTAGE_MAX_MSL_mV", "2800", "4250"),
    ("BC_VOLTAGE_MAX_RSL_mV", "2750", "4200"),
    ("BC_VOLTAGE_MAX_MOL_mV", "2720", "4150"),
    # Nominal
    ("BC_VOLTAGE_NOMINAL_mV", "2500", "3700"),
    # Undervoltage
    ("BC_VOLTAGE_MIN_MSL_mV", "1500", "2500"),
    ("BC_VOLTAGE_MIN_RSL_mV", "1550", "2600"),
    ("BC_VOLTAGE_MIN_MOL_mV", "1580", "2700"),
]

try:
    with open(TARGET) as f:
        code = f.read()
except FileNotFoundError:
    print(f"ERROR: {TARGET} not found")
    sys.exit(1)

if SENTINEL in code:
    print("already patched")
    sys.exit(0)

patched = 0
for name, old_val, new_val in REPLACEMENTS:
    old_define = f"#define {name} ({old_val})"
    new_define = f"#define {name} ({new_val})  {SENTINEL}"
    if old_define in code:
        code = code.replace(old_define, new_define, 1)
        patched += 1
    else:
        print(f"WARNING: '{old_define}' not found")

if patched == 0:
    print("WARNING: no voltage thresholds matched")
    sys.exit(1)

with open(TARGET, "w") as f:
    f.write(code)

print(f"patched {patched} voltage thresholds for NMC chemistry (2500-4250 mV)")
