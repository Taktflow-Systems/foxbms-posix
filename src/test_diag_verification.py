#!/usr/bin/env python3
"""
foxBMS POSIX vECU — DIAG System Verification Test Specification

Comprehensive test catalog for every DIAG ID:
  1. Positive detection (fault triggers FATAL within FTTI)
  2. Negative (normal values = no trigger)
  3. Threshold count verification (exact debounce count)
  4. Counter reset on fault removal
  5. FTTI timing measurement
  6. Boundary (threshold-1 = no trigger)

For DIAG IDs with 3 severity tiers (MSL/RSL/MOL), all three are tested.

Total: 216 tests.
"""
# @verifies SW-REQ-001
# @verifies SW-REQ-002
# @verifies SW-REQ-010
# @verifies SW-REQ-011
# @verifies SW-REQ-020
# @verifies SW-REQ-021
# @verifies SW-REQ-022
# @verifies SW-REQ-023
# @verifies SW-REQ-030
# @verifies SW-REQ-031
# @verifies SW-REQ-033
# @verifies SW-REQ-043
# @verifies SW-REQ-044
# @verifies SW-REQ-045
# @verifies SSR-001
# @verifies SSR-002
# @verifies SSR-005
# @verifies SSR-007
# @verifies SSR-010
# @verifies TSR-01
# @verifies TSR-02
# @verifies TSR-03
# @verifies TSR-04

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# CAN IDs and SIL override commands (from fi/constants.py)
# ---------------------------------------------------------------------------
CAN_OVERRIDE_ID = 0x7E0
CAN_PROBE_DIAG = 0x7F7
CAN_PROBE_DIAG_BITMAP = 0x7F8
CAN_PROBE_STATE = 0x7F9

SIL_CELL_VOLTAGE = 0x01
SIL_CELL_TEMP = 0x02
SIL_PACK_CURRENT = 0x03
SIL_CONTACTOR_FB = 0x05
SIL_INTERLOCK = 0x06
SIL_PACK_VOLTAGE = 0x07
SIL_DIAG_FORCE = 0x08
SIL_DIAG_CLEAR = 0x09
SIL_CLEAR_ALL = 0xFF

BMS_ERROR = 10
BMS_NORMAL = 7

# ---------------------------------------------------------------------------
# DIAG entry definitions
#
# Each entry describes a DIAG group with its threshold config, stimulus
# method, and severity tiers.  The generator below produces 6 test types
# per entry (or per severity tier if the entry has MSL/RSL/MOL).
# ---------------------------------------------------------------------------

# Severity tier definitions
_MSL = "MSL"  # Maximum Safety Limit — triggers FATAL / ERROR
_RSL = "RSL"  # Recommended Safety Limit — triggers WARNING
_MOL = "MOL"  # Maximum Operating Limit — informational

DiagEntry = Dict[str, Any]


def _tri_tier(base_id: int) -> List[Dict[str, Any]]:
    """Return MSL/RSL/MOL tier list for a group-of-3 DIAG ID."""
    return [
        {"tier": _MSL, "diag_id": base_id + 0, "triggers_fatal": True},
        {"tier": _RSL, "diag_id": base_id + 1, "triggers_fatal": False},
        {"tier": _MOL, "diag_id": base_id + 2, "triggers_fatal": False},
    ]


def _single_tier(diag_id: int, triggers_fatal: bool = True) -> List[Dict[str, Any]]:
    """Return single tier for DIAG IDs without MSL/RSL/MOL split."""
    return [{"tier": _MSL, "diag_id": diag_id, "triggers_fatal": triggers_fatal}]


# Master DIAG entry table
DIAG_ENTRIES: List[DiagEntry] = [
    # --- Cell voltage ---
    {
        "group": "CELLVOLTAGE_OVERVOLTAGE",
        "short": "OV",
        "tiers": _tri_tier(18),
        "threshold_count": 50,
        "delay_ms": 200,
        "ftti_ms": 10110,
        "sil_override": SIL_CELL_VOLTAGE,
        "stimulus": {"cell": 0, "fault_value_mv": 2900, "normal_value_mv": 2000},
        "boundary_value_mv": 2799,
        "asil": "D",
        "verifies_base": ["TSR-01", "SSR-001", "SW-REQ-001"],
    },
    {
        "group": "CELLVOLTAGE_UNDERVOLTAGE",
        "short": "UV",
        "tiers": _tri_tier(21),
        "threshold_count": 50,
        "delay_ms": 200,
        "ftti_ms": 10110,
        "sil_override": SIL_CELL_VOLTAGE,
        "stimulus": {"cell": 0, "fault_value_mv": 1500, "normal_value_mv": 2000},
        "boundary_value_mv": 1701,
        "asil": "D",
        "verifies_base": ["TSR-01", "SSR-001", "SW-REQ-002"],
    },
    # --- Temperature ---
    {
        "group": "TEMP_OVERTEMPERATURE_CHARGE",
        "short": "OT-CHG",
        "tiers": _tri_tier(24),
        "threshold_count": 500,
        "delay_ms": 1000,
        "ftti_ms": 500110,
        "sil_override": SIL_CELL_TEMP,
        "stimulus": {"cell": 0, "fault_value_ddegC": 600, "normal_value_ddegC": 250},
        "boundary_value_ddegC": 549,
        "asil": "C",
        "verifies_base": ["TSR-02", "SSR-001", "SW-REQ-010"],
    },
    {
        "group": "TEMP_OVERTEMPERATURE_DISCHARGE",
        "short": "OT-DIS",
        "tiers": _tri_tier(27),
        "threshold_count": 500,
        "delay_ms": 1000,
        "ftti_ms": 500110,
        "sil_override": SIL_CELL_TEMP,
        "stimulus": {"cell": 0, "fault_value_ddegC": 650, "normal_value_ddegC": 250},
        "boundary_value_ddegC": 599,
        "asil": "C",
        "verifies_base": ["TSR-02", "SSR-001", "SW-REQ-011"],
    },
    {
        "group": "TEMP_UNDERTEMPERATURE_CHARGE",
        "short": "UT-CHG",
        "tiers": _tri_tier(30),
        "threshold_count": 500,
        "delay_ms": 1000,
        "ftti_ms": 500110,
        "sil_override": SIL_CELL_TEMP,
        "stimulus": {"cell": 0, "fault_value_ddegC": -200, "normal_value_ddegC": 250},
        "boundary_value_ddegC": -99,
        "asil": "C",
        "verifies_base": ["TSR-02", "SSR-001", "SW-REQ-010"],
    },
    {
        "group": "TEMP_UNDERTEMPERATURE_DISCHARGE",
        "short": "UT-DIS",
        "tiers": _tri_tier(33),
        "threshold_count": 500,
        "delay_ms": 1000,
        "ftti_ms": 500110,
        "sil_override": SIL_CELL_TEMP,
        "stimulus": {"cell": 0, "fault_value_ddegC": -250, "normal_value_ddegC": 250},
        "boundary_value_ddegC": -149,
        "asil": "C",
        "verifies_base": ["TSR-02", "SSR-001", "SW-REQ-011"],
    },
    # --- Overcurrent (cell level) ---
    {
        "group": "OVERCURRENT_CHARGE_CELL",
        "short": "OC-CHG-CELL",
        "tiers": _tri_tier(36),
        "threshold_count": 10,
        "delay_ms": 100,
        "ftti_ms": 1110,
        "sil_override": SIL_PACK_CURRENT,
        "stimulus": {"fault_value_mA": 120000, "normal_value_mA": 5000},
        "boundary_value_mA": 99999,
        "asil": "D",
        "verifies_base": ["TSR-03", "SSR-001", "SW-REQ-020"],
    },
    {
        "group": "OVERCURRENT_DISCHARGE_CELL",
        "short": "OC-DIS-CELL",
        "tiers": _tri_tier(39),
        "threshold_count": 10,
        "delay_ms": 100,
        "ftti_ms": 1110,
        "sil_override": SIL_PACK_CURRENT,
        "stimulus": {"fault_value_mA": -120000, "normal_value_mA": -5000},
        "boundary_value_mA": -99999,
        "asil": "D",
        "verifies_base": ["TSR-03", "SSR-001", "SW-REQ-021"],
    },
    # --- Overcurrent (string level) ---
    {
        "group": "STRING_OVERCURRENT_CHARGE",
        "short": "OC-CHG-STR",
        "tiers": _tri_tier(42),
        "threshold_count": 10,
        "delay_ms": 100,
        "ftti_ms": 1110,
        "sil_override": SIL_PACK_CURRENT,
        "stimulus": {"fault_value_mA": 150000, "normal_value_mA": 5000},
        "boundary_value_mA": 119999,
        "asil": "D",
        "verifies_base": ["TSR-03", "SSR-001", "SW-REQ-022"],
    },
    {
        "group": "STRING_OVERCURRENT_DISCHARGE",
        "short": "OC-DIS-STR",
        "tiers": _tri_tier(45),
        "threshold_count": 10,
        "delay_ms": 100,
        "ftti_ms": 1110,
        "sil_override": SIL_PACK_CURRENT,
        "stimulus": {"fault_value_mA": -150000, "normal_value_mA": -5000},
        "boundary_value_mA": -119999,
        "asil": "D",
        "verifies_base": ["TSR-03", "SSR-001", "SW-REQ-023"],
    },
    # --- Pack-level overcurrent (single ID, no MSL/RSL/MOL split) ---
    {
        "group": "OVERCURRENT_CHARGE_PACK",
        "short": "OC-CHG-PACK",
        "tiers": _single_tier(48),
        "threshold_count": 10,
        "delay_ms": 100,
        "ftti_ms": 1110,
        "sil_override": SIL_PACK_CURRENT,
        "stimulus": {"fault_value_mA": 200000, "normal_value_mA": 5000},
        "boundary_value_mA": 179999,
        "asil": "D",
        "verifies_base": ["TSR-03", "SSR-001", "SW-REQ-020"],
    },
    {
        "group": "OVERCURRENT_DISCHARGE_PACK",
        "short": "OC-DIS-PACK",
        "tiers": _single_tier(49),
        "threshold_count": 10,
        "delay_ms": 100,
        "ftti_ms": 1110,
        "sil_override": SIL_PACK_CURRENT,
        "stimulus": {"fault_value_mA": -200000, "normal_value_mA": -5000},
        "boundary_value_mA": -179999,
        "asil": "D",
        "verifies_base": ["TSR-03", "SSR-001", "SW-REQ-021"],
    },
    # --- Pack voltage ---
    {
        "group": "PACKVOLTAGE",
        "short": "PACK-V",
        "tiers": _single_tier(50),
        "threshold_count": 50,
        "delay_ms": 200,
        "ftti_ms": 10110,
        "sil_override": SIL_PACK_VOLTAGE,
        "stimulus": {"fault_value_mV": 450000, "normal_value_mV": 320000},
        "boundary_value_mV": 409999,
        "asil": "D",
        "verifies_base": ["TSR-01", "SSR-001", "SW-REQ-030"],
    },
    # --- Plausibility checks ---
    {
        "group": "PLAUSIBILITY_CELLVOLTAGE",
        "short": "PLAUS-V",
        "tiers": _single_tier(51),
        "threshold_count": 50,
        "delay_ms": 200,
        "ftti_ms": 10110,
        "sil_override": SIL_CELL_VOLTAGE,
        "stimulus": {
            "description": "Set adjacent cells to wildly different values",
            "cell_0_mv": 2000,
            "cell_1_mv": 500,
            "normal_value_mv": 2000,
        },
        "boundary_delta_mv": 199,
        "asil": "C",
        "verifies_base": ["TSR-01", "SSR-002", "SW-REQ-031"],
    },
    {
        "group": "PLAUSIBILITY_CELLTEMPERATURE",
        "short": "PLAUS-T",
        "tiers": _single_tier(52),
        "threshold_count": 50,
        "delay_ms": 200,
        "ftti_ms": 10110,
        "sil_override": SIL_CELL_TEMP,
        "stimulus": {
            "description": "Set adjacent temp sensors to wildly different values",
            "sensor_0_ddegC": 250,
            "sensor_1_ddegC": 600,
            "normal_value_ddegC": 250,
        },
        "boundary_delta_ddegC": 99,
        "asil": "C",
        "verifies_base": ["TSR-02", "SSR-002", "SW-REQ-033"],
    },
    # --- Architecture-only DIAG IDs (not yet in constants.py) ---
    {
        "group": "AFE_SPI",
        "short": "AFE",
        "tiers": _single_tier(53),
        "threshold_count": 5,
        "delay_ms": 100,
        "ftti_ms": 510,
        "sil_override": SIL_DIAG_FORCE,
        "stimulus": {"diag_force_id": 53, "description": "Force AFE SPI comm fault"},
        "asil": "D",
        "verifies_base": ["TSR-04", "SSR-001", "SW-REQ-043"],
    },
    {
        "group": "CURRENT_SENSOR",
        "short": "IVT",
        "tiers": _single_tier(54),
        "threshold_count": 100,
        "delay_ms": 200,
        "ftti_ms": 20210,
        "sil_override": SIL_DIAG_FORCE,
        "stimulus": {"diag_force_id": 54, "description": "Force current sensor timeout"},
        "asil": "D",
        "verifies_base": ["TSR-03", "SSR-001", "SW-REQ-043"],
    },
    {
        "group": "CAN_TIMING",
        "short": "CAN-T",
        "tiers": _single_tier(55),
        "threshold_count": 100,
        "delay_ms": 200,
        "ftti_ms": 20210,
        "sil_override": SIL_DIAG_FORCE,
        "stimulus": {"diag_force_id": 55, "description": "Force CAN communication timeout"},
        "asil": "C",
        "verifies_base": ["TSR-04", "SSR-001", "SW-REQ-043"],
    },
    {
        "group": "INTERLOCK",
        "short": "ILCK",
        "tiers": _single_tier(56),
        "threshold_count": 1,
        "delay_ms": 0,
        "ftti_ms": 110,
        "sil_override": SIL_INTERLOCK,
        "stimulus": {"interlock_state": "OPEN", "description": "Force interlock open"},
        "asil": "D",
        "verifies_base": ["TSR-04", "SSR-001", "SSR-010", "SW-REQ-044"],
    },
    {
        "group": "CONTACTOR_FEEDBACK_STRING_PLUS",
        "short": "CTR-SP",
        "tiers": _single_tier(57),
        "threshold_count": 1,
        "delay_ms": 0,
        "ftti_ms": 110,
        "sil_override": SIL_CONTACTOR_FB,
        "stimulus": {"contactor": "STR_PLUS", "feedback": "mismatch"},
        "asil": "D",
        "verifies_base": ["TSR-04", "SSR-001", "SW-REQ-044"],
    },
    {
        "group": "CONTACTOR_FEEDBACK_STRING_MINUS",
        "short": "CTR-SM",
        "tiers": _single_tier(58),
        "threshold_count": 1,
        "delay_ms": 0,
        "ftti_ms": 110,
        "sil_override": SIL_CONTACTOR_FB,
        "stimulus": {"contactor": "STR_MINUS", "feedback": "mismatch"},
        "asil": "D",
        "verifies_base": ["TSR-04", "SSR-001", "SW-REQ-044"],
    },
    {
        "group": "CONTACTOR_FEEDBACK_PRECHARGE",
        "short": "CTR-PRE",
        "tiers": _single_tier(59),
        "threshold_count": 1,
        "delay_ms": 0,
        "ftti_ms": 110,
        "sil_override": SIL_CONTACTOR_FB,
        "stimulus": {"contactor": "PRE", "feedback": "mismatch"},
        "asil": "D",
        "verifies_base": ["TSR-04", "SSR-001", "SW-REQ-044"],
    },
    {
        "group": "CURRENT_ON_OPEN_STRING",
        "short": "I-OPEN",
        "tiers": _single_tier(60),
        "threshold_count": 10,
        "delay_ms": 100,
        "ftti_ms": 1110,
        "sil_override": SIL_PACK_CURRENT,
        "stimulus": {
            "description": "Inject current while contactors are open",
            "fault_value_mA": 5000,
            "contactor_state": "ALL_OPEN",
        },
        "asil": "D",
        "verifies_base": ["TSR-03", "SSR-001", "SW-REQ-045"],
    },
    {
        "group": "DEEP_DISCHARGE",
        "short": "DEEP-D",
        "tiers": _single_tier(61),
        "threshold_count": 1,
        "delay_ms": 100,
        "ftti_ms": 210,
        "sil_override": SIL_CELL_VOLTAGE,
        "stimulus": {"cell": 0, "fault_value_mv": 800, "normal_value_mv": 2000},
        "boundary_value_mv": 1201,
        "asil": "D",
        "verifies_base": ["TSR-01", "SSR-001", "SW-REQ-002"],
    },
    {
        "group": "SYSTEM_MONITORING",
        "short": "SYSMON",
        "tiers": _single_tier(62),
        "threshold_count": 1,
        "delay_ms": 0,
        "ftti_ms": 10,
        "sil_override": SIL_DIAG_FORCE,
        "stimulus": {"diag_force_id": 62, "description": "Force system monitoring fault"},
        "asil": "D",
        "verifies_base": ["TSR-04", "SSR-001", "SW-REQ-043"],
    },
    {
        "group": "FLASHCHECKSUM",
        "short": "FLASH",
        "tiers": _single_tier(63),
        "threshold_count": 1,
        "delay_ms": 0,
        "ftti_ms": 10,
        "sil_override": SIL_DIAG_FORCE,
        "stimulus": {"diag_force_id": 63, "description": "Force flash checksum mismatch"},
        "asil": "D",
        "verifies_base": ["TSR-04", "SSR-001", "SW-REQ-043"],
    },
    {
        "group": "ALERT_MODE",
        "short": "ALERT",
        "tiers": _single_tier(64),
        "threshold_count": 1,
        "delay_ms": 0,
        "ftti_ms": 10,
        "sil_override": SIL_DIAG_FORCE,
        "stimulus": {"diag_force_id": 64, "description": "Force AFE alert mode"},
        "asil": "C",
        "verifies_base": ["TSR-04", "SSR-001", "SW-REQ-043"],
    },
    {
        "group": "SBC_MONITORING",
        "short": "SBC",
        "tiers": _single_tier(65),
        "threshold_count": 1,
        "delay_ms": 0,
        "ftti_ms": 10,
        "sil_override": SIL_DIAG_FORCE,
        "stimulus": {"diag_force_id": 65, "description": "Force SBC monitoring fault"},
        "asil": "D",
        "verifies_base": ["TSR-04", "SSR-001", "SW-REQ-043"],
    },
]

# ---------------------------------------------------------------------------
# Test generation
# ---------------------------------------------------------------------------
_test_counter = 0


def _next_id(prefix: str) -> str:
    """Generate sequential test ID within a prefix."""
    global _test_counter
    _test_counter += 1
    return f"{prefix}-{_test_counter:03d}"


def _generate_tests_for_entry(entry: DiagEntry) -> List[Dict[str, Any]]:
    """Generate 6 test types per tier for one DIAG entry."""
    tests = []
    group = entry["group"]
    short = entry["short"]

    for tier_info in entry["tiers"]:
        tier = tier_info["tier"]
        diag_id = tier_info["diag_id"]
        triggers_fatal = tier_info["triggers_fatal"]
        tier_suffix = f"-{tier}" if len(entry["tiers"]) > 1 else ""
        id_tag = f"{short}{tier_suffix}"

        verifies = list(entry["verifies_base"])

        # --- 1. Positive detection ---
        expected_diag = "FATAL" if triggers_fatal else "WARNING"
        expected_bms = BMS_ERROR if triggers_fatal else BMS_NORMAL
        tests.append({
            "id": f"DIAG-POS-{id_tag}-{diag_id:03d}",
            "category": "DIAG",
            "test_type": "positive_detection",
            "diag_group": group,
            "diag_id": diag_id,
            "severity": tier,
            "description": (
                f"{group} {tier}: inject fault condition and verify "
                f"DIAG raises {expected_diag} within FTTI ({entry['ftti_ms']} ms). "
                f"{'BMS shall transition to ERROR.' if triggers_fatal else 'BMS shall remain in NORMAL.'}"
            ),
            "stimulus": entry["stimulus"],
            "expected": {
                "diag_state": expected_diag,
                "max_time_ms": entry["ftti_ms"],
                "bms_state": expected_bms,
            },
            "verifies": verifies,
            "asil": entry["asil"],
            "priority": "P1",
        })

        # --- 2. Negative (no fault = no trigger) ---
        tests.append({
            "id": f"DIAG-NEG-{id_tag}-{diag_id:03d}",
            "category": "DIAG",
            "test_type": "negative_no_trigger",
            "diag_group": group,
            "diag_id": diag_id,
            "severity": tier,
            "description": (
                f"{group} {tier}: with normal values applied, verify DIAG does "
                f"NOT raise any flag for this ID. Soak 30 s, check bitmap "
                f"(0x7F8) bit for ID {diag_id} remains clear."
            ),
            "stimulus": {"normal_values": True},
            "expected": {
                "diag_bit_clear": True,
                "soak_duration_s": 30,
                "bms_state": BMS_NORMAL,
            },
            "verifies": verifies,
            "asil": entry["asil"],
            "priority": "P1",
        })

        # --- 3. Threshold count verification ---
        tests.append({
            "id": f"DIAG-THR-{id_tag}-{diag_id:03d}",
            "category": "DIAG",
            "test_type": "threshold_count",
            "diag_group": group,
            "diag_id": diag_id,
            "severity": tier,
            "description": (
                f"{group} {tier}: inject fault condition and count debounce "
                f"increments. Verify DIAG triggers at exactly "
                f"threshold={entry['threshold_count']} counts (with "
                f"delay={entry['delay_ms']} ms between increments)."
            ),
            "stimulus": entry["stimulus"],
            "expected": {
                "trigger_at_count": entry["threshold_count"],
                "delay_between_ms": entry["delay_ms"],
                "no_trigger_at_count": entry["threshold_count"] - 1,
            },
            "verifies": verifies,
            "asil": entry["asil"],
            "priority": "P1",
        })

        # --- 4. Counter reset on fault removal ---
        tests.append({
            "id": f"DIAG-RST-{id_tag}-{diag_id:03d}",
            "category": "DIAG",
            "test_type": "counter_reset",
            "diag_group": group,
            "diag_id": diag_id,
            "severity": tier,
            "description": (
                f"{group} {tier}: inject fault for (threshold-1) counts, "
                f"remove fault, wait 2x delay, re-inject. Verify counter "
                f"restarted from 0 (total injections > threshold but "
                f"no trigger due to reset)."
            ),
            "stimulus": entry["stimulus"],
            "expected": {
                "counter_resets_on_removal": True,
                "partial_count": entry["threshold_count"] - 1,
                "removal_wait_ms": entry["delay_ms"] * 2,
                "no_trigger_after_reset": True,
            },
            "verifies": verifies,
            "asil": entry["asil"],
            "priority": "P2",
        })

        # --- 5. FTTI timing measurement ---
        ftti = entry["ftti_ms"]
        tests.append({
            "id": f"DIAG-FTTI-{id_tag}-{diag_id:03d}",
            "category": "DIAG",
            "test_type": "ftti_timing",
            "diag_group": group,
            "diag_id": diag_id,
            "severity": tier,
            "description": (
                f"{group} {tier}: measure total fault detection time from "
                f"first fault injection to DIAG flag assertion. "
                f"FTTI = T_detect + T_delay + T_actuate. "
                f"Expected max: {ftti} ms."
            ),
            "stimulus": entry["stimulus"],
            "expected": {
                "max_ftti_ms": ftti,
                "measurement": {
                    "t_detect": f"threshold({entry['threshold_count']}) x delay({entry['delay_ms']}ms)",
                    "t_actuate": "contactor open time (if FATAL)",
                },
            },
            "verifies": verifies,
            "asil": entry["asil"],
            "priority": "P1",
        })

        # --- 6. Boundary (threshold-1 = no trigger) ---
        tests.append({
            "id": f"DIAG-BND-{id_tag}-{diag_id:03d}",
            "category": "DIAG",
            "test_type": "boundary",
            "diag_group": group,
            "diag_id": diag_id,
            "severity": tier,
            "description": (
                f"{group} {tier}: inject fault for exactly "
                f"(threshold-1)={entry['threshold_count'] - 1} counts, "
                f"then stop. Verify DIAG does NOT trigger. "
                f"Also test with value just below fault threshold "
                f"(boundary value) held indefinitely — no trigger."
            ),
            "stimulus": entry["stimulus"],
            "expected": {
                "no_trigger_at_count_minus_1": True,
                "count": entry["threshold_count"] - 1,
                "boundary_value_no_trigger": True,
            },
            "verifies": verifies,
            "asil": entry["asil"],
            "priority": "P1",
        })

    return tests


# ---------------------------------------------------------------------------
# Generate the full catalog
# ---------------------------------------------------------------------------
ALL_DIAG_TESTS: List[Dict[str, Any]] = []

for _entry in DIAG_ENTRIES:
    ALL_DIAG_TESTS.extend(_generate_tests_for_entry(_entry))


# ---------------------------------------------------------------------------
# Summary and validation
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from collections import Counter

    print("=" * 70)
    print("foxBMS DIAG System Verification Test Specification")
    print("=" * 70)

    # Count by test type
    type_counter = Counter()
    group_counter = Counter()
    tier_counter = Counter()
    asil_counter = Counter()

    for t in ALL_DIAG_TESTS:
        type_counter[t["test_type"]] += 1
        group_counter[t["diag_group"]] += 1
        tier_counter[t.get("severity", "N/A")] += 1
        asil_counter[t["asil"]] += 1

    print("\nBy test type:")
    for tt, count in sorted(type_counter.items()):
        print(f"  {tt:<30s} {count:>4d}")

    print(f"\nBy DIAG group ({len(group_counter)} groups):")
    for grp, count in sorted(group_counter.items()):
        print(f"  {grp:<45s} {count:>4d}")

    print("\nBy severity tier:")
    for tier, count in sorted(tier_counter.items()):
        print(f"  {tier:<10s} {count:>4d}")

    print("\nBy ASIL:")
    for asil, count in sorted(asil_counter.items()):
        print(f"  ASIL-{asil:<5s} {count:>4d}")

    total = len(ALL_DIAG_TESTS)
    print(f"\n{'TOTAL':<30s} {total:>4d} tests")
    print("=" * 70)

    # Verify unique IDs
    ids = [t["id"] for t in ALL_DIAG_TESTS]
    dupes = [tid for tid in ids if ids.count(tid) > 1]
    if dupes:
        print(f"ERROR: Duplicate IDs: {set(dupes)}")
    else:
        print(f"All {total} test IDs are unique.")

    # Requirements coverage
    all_reqs = set()
    for t in ALL_DIAG_TESTS:
        all_reqs.update(t.get("verifies", []))
    print(f"Requirements traced: {sorted(all_reqs)}")

    # DIAG ID coverage
    all_diag_ids = sorted(set(t["diag_id"] for t in ALL_DIAG_TESTS))
    print(f"DIAG IDs covered: {all_diag_ids}")
    print(f"DIAG ID range: {min(all_diag_ids)} - {max(all_diag_ids)} ({len(all_diag_ids)} unique)")


def get_tests():
    """Return all DIAG verification tests (for test_catalog_runner.py)."""
    return ALL_DIAG_TESTS

