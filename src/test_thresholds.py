#!/usr/bin/env python3
"""
Threshold Boundary Test Catalog for foxBMS POSIX vECU.

Covers all 10 safety parameters x 3 severity levels (MOL/RSL/MSL) = 30 thresholds.
Each threshold has 4 test types: EXACT, BELOW, ABOVE, HYSTERESIS.
Plus per-cell/per-sensor individual and simultaneous tests.

Target: ~166 tests.

SIL Override Commands (via CAN ID 0x7E0):
  0x01 = cell voltage   (byte[1]=cell 0-17, byte[2-3]=value mV)
  0x02 = cell temperature (byte[1]=sensor 0-7, byte[2-3]=value ddegC)
  0x03 = pack current    (byte[1]=0, byte[2-3]=value mA signed)

Thresholds from foxBMS soa_cfg.h (approximate reference values):
  Cell Overvoltage:       MOL=2400 RSL=2600 MSL=2800 mV
  Cell Undervoltage:      MOL=2200 RSL=2000 MSL=1700 mV
  Overcurrent Disch Cell: MOL=5000 RSL=8000 MSL=10000 mA
  Overcurrent Chg Cell:   MOL=5000 RSL=8000 MSL=10000 mA
  Overcurrent Disch Str:  MOL=5000 RSL=8000 MSL=10000 mA
  Overcurrent Chg Str:    MOL=5000 RSL=8000 MSL=10000 mA
  Overtemp Discharge:     MOL=450  RSL=500  MSL=550  ddegC
  Overtemp Charge:        MOL=400  RSL=420  MSL=450  ddegC
  Undertemp Discharge:    MOL=100  RSL=50   MSL=-50  ddegC
  Undertemp Charge:       MOL=100  RSL=50   MSL=0    ddegC
"""

from __future__ import annotations

NUM_CELLS = 18
NUM_TEMP_SENSORS = 8

# ---------------------------------------------------------------------------
# Parameter definitions
# ---------------------------------------------------------------------------
# direction: "rising" means fault triggers when value >= threshold
#            "falling" means fault triggers when value <= threshold

PARAMETERS = [
    {
        "key": "cell_overvoltage",
        "short": "OV",
        "override": "cell_voltage",
        "unit": "mV",
        "direction": "rising",
        "thresholds": {"MOL": 2400, "RSL": 2600, "MSL": 2800},
        "nominal": 3700,
        "ssr_refs": ["SSR-001"],
        "sys_refs": ["SYS-REQ-020"],
        "per_element": {"type": "cell", "count": NUM_CELLS, "index_key": "cell"},
    },
    {
        "key": "cell_undervoltage",
        "short": "UV",
        "override": "cell_voltage",
        "unit": "mV",
        "direction": "falling",
        "thresholds": {"MOL": 2200, "RSL": 2000, "MSL": 1700},
        "nominal": 3700,
        "ssr_refs": ["SSR-002"],
        "sys_refs": ["SYS-REQ-021"],
        "per_element": {"type": "cell", "count": NUM_CELLS, "index_key": "cell"},
    },
    {
        "key": "overcurrent_discharge_cell",
        "short": "OCD-C",
        "override": "pack_current",
        "unit": "mA",
        "direction": "rising",
        "thresholds": {"MOL": 5000, "RSL": 8000, "MSL": 10000},
        "nominal": 0,
        "ssr_refs": ["SSR-003"],
        "sys_refs": ["SYS-REQ-022"],
        "per_element": None,
    },
    {
        "key": "overcurrent_charge_cell",
        "short": "OCC-C",
        "override": "pack_current",
        "unit": "mA",
        "direction": "falling",  # charge current is negative convention
        "thresholds": {"MOL": -5000, "RSL": -8000, "MSL": -10000},
        "nominal": 0,
        "ssr_refs": ["SSR-004"],
        "sys_refs": ["SYS-REQ-023"],
        "per_element": None,
        "_display_thresholds": {"MOL": 5000, "RSL": 8000, "MSL": 10000},
    },
    {
        "key": "overcurrent_discharge_string",
        "short": "OCD-S",
        "override": "pack_current",
        "unit": "mA",
        "direction": "rising",
        "thresholds": {"MOL": 5000, "RSL": 8000, "MSL": 10000},
        "nominal": 0,
        "ssr_refs": ["SSR-005"],
        "sys_refs": ["SYS-REQ-024"],
        "per_element": None,
    },
    {
        "key": "overcurrent_charge_string",
        "short": "OCC-S",
        "override": "pack_current",
        "unit": "mA",
        "direction": "falling",
        "thresholds": {"MOL": -5000, "RSL": -8000, "MSL": -10000},
        "nominal": 0,
        "ssr_refs": ["SSR-006"],
        "sys_refs": ["SYS-REQ-025"],
        "per_element": None,
        "_display_thresholds": {"MOL": 5000, "RSL": 8000, "MSL": 10000},
    },
    {
        "key": "overtemp_discharge",
        "short": "OTD",
        "override": "cell_temperature",
        "unit": "ddegC",
        "direction": "rising",
        "thresholds": {"MOL": 450, "RSL": 500, "MSL": 550},
        "nominal": 250,
        "ssr_refs": ["SSR-007"],
        "sys_refs": ["SYS-REQ-026"],
        "per_element": {"type": "sensor", "count": NUM_TEMP_SENSORS, "index_key": "sensor"},
    },
    {
        "key": "overtemp_charge",
        "short": "OTC",
        "override": "cell_temperature",
        "unit": "ddegC",
        "direction": "rising",
        "thresholds": {"MOL": 400, "RSL": 420, "MSL": 450},
        "nominal": 250,
        "ssr_refs": ["SSR-008"],
        "sys_refs": ["SYS-REQ-027"],
        "per_element": {"type": "sensor", "count": NUM_TEMP_SENSORS, "index_key": "sensor"},
    },
    {
        "key": "undertemp_discharge",
        "short": "UTD",
        "override": "cell_temperature",
        "unit": "ddegC",
        "direction": "falling",
        "thresholds": {"MOL": 100, "RSL": 50, "MSL": -50},
        "nominal": 250,
        "ssr_refs": ["SSR-009"],
        "sys_refs": ["SYS-REQ-028"],
        "per_element": {"type": "sensor", "count": NUM_TEMP_SENSORS, "index_key": "sensor"},
    },
    {
        "key": "undertemp_charge",
        "short": "UTC",
        "override": "cell_temperature",
        "unit": "ddegC",
        "direction": "falling",
        "thresholds": {"MOL": 100, "RSL": 50, "MSL": 0},
        "nominal": 250,
        "ssr_refs": ["SSR-010"],
        "sys_refs": ["SYS-REQ-029"],
        "per_element": {"type": "sensor", "count": NUM_TEMP_SENSORS, "index_key": "sensor"},
    },
]

# ---------------------------------------------------------------------------
# Severity-level metadata
# ---------------------------------------------------------------------------
SEVERITY_META = {
    "MOL": {"diag_severity": "MOL", "expected_state": "WARNING", "priority": "P2"},
    "RSL": {"diag_severity": "RSL", "expected_state": "ERROR", "priority": "P1"},
    "MSL": {"diag_severity": "MSL", "expected_state": "FATAL", "priority": "P1"},
}


def _lsb(param: dict) -> int:
    """Return 1 LSB in the correct sign direction."""
    if param["direction"] == "rising":
        return 1
    return -1


def _make_stimulus(param: dict, value, element_index: int = 0) -> dict:
    """Build stimulus dict for a given parameter override."""
    ovr = param["override"]
    if ovr == "cell_voltage":
        return {"override": ovr, "cell": element_index, "value_mv": value}
    elif ovr == "cell_temperature":
        return {"override": ovr, "sensor": element_index, "value_ddegC": value}
    elif ovr == "pack_current":
        return {"override": ovr, "string": 0, "value_mA": value}
    return {"override": ovr, "value": value}


def _triggered(direction: str, value, threshold) -> bool:
    """Whether a value should trigger the threshold."""
    if direction == "rising":
        return value >= threshold
    return value <= threshold


# ---------------------------------------------------------------------------
# Test generators
# ---------------------------------------------------------------------------

def _gen_boundary_tests() -> list[dict]:
    """Generate 4 boundary tests per threshold (30 thresholds = 120 tests)."""
    tests = []
    seq = {}  # per-short counter

    for param in PARAMETERS:
        short = param["short"]
        if short not in seq:
            seq[short] = 0

        for level in ("MOL", "RSL", "MSL"):
            threshold = param["thresholds"][level]
            meta = SEVERITY_META[level]
            lsb = _lsb(param)

            # Display-friendly threshold (always positive for description)
            disp_thresh = param.get("_display_thresholds", param["thresholds"]).get(level, abs(threshold))

            base_id = f"THR-{short}-{level}"
            verifies = param["ssr_refs"] + param["sys_refs"]

            # --- EXACT: value == threshold -> triggers ---
            seq[short] += 1
            tests.append({
                "id": f"{base_id}-EXACT-{seq[short]:03d}",
                "category": "THR",
                "parameter": param["key"],
                "level": level,
                "test_type": "exact_threshold",
                "description": (
                    f"{param['key']} {level}: inject exactly {threshold} {param['unit']} "
                    f"-> verify {meta['diag_severity']} triggers"
                ),
                "stimulus": _make_stimulus(param, threshold),
                "expected": {
                    "diag_triggered": True,
                    "severity": meta["diag_severity"],
                    "bms_state_contains": meta["expected_state"],
                },
                "verifies": verifies,
                "asil": "D",
                "priority": meta["priority"],
            })

            # --- BELOW: value == threshold - 1 LSB -> does NOT trigger ---
            below_val = threshold - lsb
            seq[short] += 1
            tests.append({
                "id": f"{base_id}-BELOW-{seq[short]:03d}",
                "category": "THR",
                "parameter": param["key"],
                "level": level,
                "test_type": "below_threshold",
                "description": (
                    f"{param['key']} {level}: inject {below_val} {param['unit']} "
                    f"(threshold - 1 LSB) -> verify NO trigger"
                ),
                "stimulus": _make_stimulus(param, below_val),
                "expected": {
                    "diag_triggered": False,
                    "severity": None,
                },
                "verifies": verifies,
                "asil": "D",
                "priority": meta["priority"],
            })

            # --- ABOVE: value == threshold + margin -> triggers ---
            margin = max(1, abs(threshold) // 20)  # ~5% margin
            if margin < 5:
                margin = 5
            above_val = threshold + lsb * margin
            seq[short] += 1
            tests.append({
                "id": f"{base_id}-ABOVE-{seq[short]:03d}",
                "category": "THR",
                "parameter": param["key"],
                "level": level,
                "test_type": "above_threshold",
                "description": (
                    f"{param['key']} {level}: inject {above_val} {param['unit']} "
                    f"(threshold + margin) -> verify {meta['diag_severity']} triggers"
                ),
                "stimulus": _make_stimulus(param, above_val),
                "expected": {
                    "diag_triggered": True,
                    "severity": meta["diag_severity"],
                },
                "verifies": verifies,
                "asil": "D",
                "priority": meta["priority"],
            })

            # --- HYSTERESIS: trigger then remove -> counter resets ---
            seq[short] += 1
            tests.append({
                "id": f"{base_id}-HYST-{seq[short]:03d}",
                "category": "THR",
                "parameter": param["key"],
                "level": level,
                "test_type": "hysteresis",
                "description": (
                    f"{param['key']} {level}: trigger at {threshold} {param['unit']} "
                    f"-> remove fault (return to {param['nominal']}) -> verify diag counter resets"
                ),
                "stimulus": {
                    "phase1_inject": _make_stimulus(param, threshold),
                    "phase1_hold_ms": 500,
                    "phase2_restore": _make_stimulus(param, param["nominal"]),
                    "phase2_wait_ms": 2000,
                },
                "expected": {
                    "phase1_triggered": True,
                    "phase1_severity": meta["diag_severity"],
                    "phase2_counter_reset": True,
                    "phase2_diag_cleared": True,
                },
                "verifies": verifies + ["TSR-HYST"],
                "asil": "D",
                "priority": "P2",
            })

    return tests


def _gen_per_cell_ov_tests() -> list[dict]:
    """THR-OV-CELL-xxx: Each of 18 cells triggers OV individually."""
    tests = []
    param = PARAMETERS[0]  # cell_overvoltage
    threshold = param["thresholds"]["MSL"]

    for cell in range(NUM_CELLS):
        tests.append({
            "id": f"THR-OV-CELL-{cell:03d}",
            "category": "THR",
            "parameter": "cell_overvoltage",
            "level": "MSL",
            "test_type": "per_cell",
            "description": (
                f"Cell OV per-cell: inject {threshold} mV on cell {cell} only "
                f"-> verify MSL triggers for cell {cell}"
            ),
            "stimulus": _make_stimulus(param, threshold, element_index=cell),
            "expected": {
                "diag_triggered": True,
                "severity": "MSL",
                "affected_cell": cell,
            },
            "verifies": ["SSR-001", "SYS-REQ-020", "TSR-01"],
            "asil": "D",
            "priority": "P1",
        })
    return tests


def _gen_per_cell_uv_tests() -> list[dict]:
    """THR-UV-CELL-xxx: Each of 18 cells triggers UV individually."""
    tests = []
    param = PARAMETERS[1]  # cell_undervoltage
    threshold = param["thresholds"]["MSL"]

    for cell in range(NUM_CELLS):
        tests.append({
            "id": f"THR-UV-CELL-{cell:03d}",
            "category": "THR",
            "parameter": "cell_undervoltage",
            "level": "MSL",
            "test_type": "per_cell",
            "description": (
                f"Cell UV per-cell: inject {threshold} mV on cell {cell} only "
                f"-> verify MSL triggers for cell {cell}"
            ),
            "stimulus": _make_stimulus(param, threshold, element_index=cell),
            "expected": {
                "diag_triggered": True,
                "severity": "MSL",
                "affected_cell": cell,
            },
            "verifies": ["SSR-002", "SYS-REQ-021", "TSR-02"],
            "asil": "D",
            "priority": "P1",
        })
    return tests


def _gen_per_sensor_ot_tests() -> list[dict]:
    """THR-TEMP-SENSOR-xxx: Each of 8 sensors triggers OT individually."""
    tests = []
    param = PARAMETERS[6]  # overtemp_discharge
    threshold = param["thresholds"]["MSL"]

    for sensor in range(NUM_TEMP_SENSORS):
        tests.append({
            "id": f"THR-TEMP-SENSOR-{sensor:03d}",
            "category": "THR",
            "parameter": "overtemp_discharge",
            "level": "MSL",
            "test_type": "per_sensor",
            "description": (
                f"Overtemp per-sensor: inject {threshold} ddegC on sensor {sensor} only "
                f"-> verify MSL triggers for sensor {sensor}"
            ),
            "stimulus": _make_stimulus(param, threshold, element_index=sensor),
            "expected": {
                "diag_triggered": True,
                "severity": "MSL",
                "affected_sensor": sensor,
            },
            "verifies": ["SSR-007", "SYS-REQ-026", "TSR-07"],
            "asil": "D",
            "priority": "P1",
        })
    return tests


def _gen_simultaneous_tests() -> list[dict]:
    """THR-ALL-CELLS-OV, THR-ALL-CELLS-UV: all cells simultaneously."""
    tests = []

    # All 18 cells OV
    ov_param = PARAMETERS[0]
    ov_thresh = ov_param["thresholds"]["MSL"]
    tests.append({
        "id": "THR-ALL-CELLS-OV-001",
        "category": "THR",
        "parameter": "cell_overvoltage",
        "level": "MSL",
        "test_type": "simultaneous_all",
        "description": (
            f"All 18 cells OV: inject {ov_thresh} mV on ALL cells simultaneously "
            f"-> verify MSL triggers, BMS enters FATAL"
        ),
        "stimulus": {
            "override": "cell_voltage",
            "cells": list(range(NUM_CELLS)),
            "value_mv": ov_thresh,
        },
        "expected": {
            "diag_triggered": True,
            "severity": "MSL",
            "affected_cells": list(range(NUM_CELLS)),
            "bms_state_contains": "FATAL",
        },
        "verifies": ["SSR-001", "SSR-020", "SYS-REQ-020"],
        "asil": "D",
        "priority": "P1",
    })

    # All 18 cells UV
    uv_param = PARAMETERS[1]
    uv_thresh = uv_param["thresholds"]["MSL"]
    tests.append({
        "id": "THR-ALL-CELLS-UV-001",
        "category": "THR",
        "parameter": "cell_undervoltage",
        "level": "MSL",
        "test_type": "simultaneous_all",
        "description": (
            f"All 18 cells UV: inject {uv_thresh} mV on ALL cells simultaneously "
            f"-> verify MSL triggers, BMS enters FATAL"
        ),
        "stimulus": {
            "override": "cell_voltage",
            "cells": list(range(NUM_CELLS)),
            "value_mv": uv_thresh,
        },
        "expected": {
            "diag_triggered": True,
            "severity": "MSL",
            "affected_cells": list(range(NUM_CELLS)),
            "bms_state_contains": "FATAL",
        },
        "verifies": ["SSR-002", "SSR-020", "SYS-REQ-021"],
        "asil": "D",
        "priority": "P1",
    })

    return tests


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_tests() -> list[dict]:
    """Return the complete threshold test catalog."""
    all_tests = []
    all_tests.extend(_gen_boundary_tests())
    all_tests.extend(_gen_per_cell_ov_tests())
    all_tests.extend(_gen_per_cell_uv_tests())
    all_tests.extend(_gen_per_sensor_ot_tests())
    all_tests.extend(_gen_simultaneous_tests())
    return all_tests


# ---------------------------------------------------------------------------
# CLI summary
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = get_tests()
    print(f"Threshold Test Catalog: {len(tests)} tests total")
    print("=" * 70)

    # Breakdown by category
    by_type = {}
    for t in tests:
        tt = t["test_type"]
        by_type.setdefault(tt, []).append(t)

    for tt, items in sorted(by_type.items()):
        print(f"  {tt:25s}: {len(items):4d} tests")

    print()

    # Breakdown by parameter
    by_param = {}
    for t in tests:
        p = t["parameter"]
        by_param.setdefault(p, []).append(t)

    print("By parameter:")
    for p, items in sorted(by_param.items()):
        print(f"  {p:35s}: {len(items):4d} tests")

    print()

    # Breakdown by severity level
    by_level = {}
    for t in tests:
        lv = t.get("level", "N/A")
        by_level.setdefault(lv, []).append(t)

    print("By severity level:")
    for lv in ("MOL", "RSL", "MSL"):
        print(f"  {lv}: {len(by_level.get(lv, [])):4d} tests")

    print()

    # Priority breakdown
    by_pri = {}
    for t in tests:
        pri = t.get("priority", "P3")
        by_pri.setdefault(pri, []).append(t)

    print("By priority:")
    for pri in sorted(by_pri.keys()):
        print(f"  {pri}: {len(by_pri[pri]):4d} tests")

    print()

    # ASIL breakdown
    asil_d = sum(1 for t in tests if t.get("asil") == "D")
    print(f"ASIL-D tests: {asil_d}/{len(tests)}")

    # Unique requirement coverage
    all_refs = set()
    for t in tests:
        all_refs.update(t.get("verifies", []))
    print(f"Unique requirements verified: {len(all_refs)}")
    for ref in sorted(all_refs):
        print(f"  {ref}")
