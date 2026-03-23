#!/usr/bin/env python3
"""
Combined Safety Validation Test Catalog for foxBMS POSIX vECU.

Categories:
  SSR  - Software Safety Requirements verification (26 reqs x 2 = 52 tests)
  DFA  - Dependent Failure Analysis (10 tests)
  B2B  - Back-to-Back SIL vs HIL comparison (13 tests)
  E2E  - End-to-End data flow verification (~22 tests)
  HW   - HW interface / peripheral tests (~56 tests)
  END  - Endurance / soak / stress tests (8 tests)

Target: ~319 tests.

SIL Override Commands (via CAN ID 0x7E0):
  0x01 = cell voltage   (byte[1]=cell 0-17, byte[2-3]=value mV)
  0x02 = cell temperature (byte[1]=sensor 0-7, byte[2-3]=value ddegC)
  0x03 = pack current    (byte[1]=0, byte[2-3]=value mA signed)
"""

from __future__ import annotations


# ===========================================================================
# SSR: Software Safety Requirements (SSR-001 .. SSR-052)
# ===========================================================================

_SSR_DEFINITIONS = [
    # --- Fault Detection (SSR-001 .. SSR-010) ---
    {
        "ssr": "SSR-001", "title": "Cell overvoltage detection",
        "stimulus_pos": {"override": "cell_voltage", "cell": 0, "value_mv": 2800},
        "expected_pos": {"diag_triggered": True, "severity": "MSL", "fault": "CELL_OV"},
        "stimulus_neg": {"override": "cell_voltage", "cell": 0, "value_mv": 3700},
        "expected_neg": {"diag_triggered": False},
        "sys_refs": ["SYS-REQ-020"],
    },
    {
        "ssr": "SSR-002", "title": "Cell undervoltage detection",
        "stimulus_pos": {"override": "cell_voltage", "cell": 0, "value_mv": 1700},
        "expected_pos": {"diag_triggered": True, "severity": "MSL", "fault": "CELL_UV"},
        "stimulus_neg": {"override": "cell_voltage", "cell": 0, "value_mv": 3700},
        "expected_neg": {"diag_triggered": False},
        "sys_refs": ["SYS-REQ-021"],
    },
    {
        "ssr": "SSR-003", "title": "Overcurrent discharge (cell) detection",
        "stimulus_pos": {"override": "pack_current", "string": 0, "value_mA": 10000},
        "expected_pos": {"diag_triggered": True, "severity": "MSL", "fault": "OC_DISCHARGE_CELL"},
        "stimulus_neg": {"override": "pack_current", "string": 0, "value_mA": 2000},
        "expected_neg": {"diag_triggered": False},
        "sys_refs": ["SYS-REQ-022"],
    },
    {
        "ssr": "SSR-004", "title": "Overcurrent charge (cell) detection",
        "stimulus_pos": {"override": "pack_current", "string": 0, "value_mA": -10000},
        "expected_pos": {"diag_triggered": True, "severity": "MSL", "fault": "OC_CHARGE_CELL"},
        "stimulus_neg": {"override": "pack_current", "string": 0, "value_mA": -2000},
        "expected_neg": {"diag_triggered": False},
        "sys_refs": ["SYS-REQ-023"],
    },
    {
        "ssr": "SSR-005", "title": "Overcurrent discharge (string) detection",
        "stimulus_pos": {"override": "pack_current", "string": 0, "value_mA": 10000},
        "expected_pos": {"diag_triggered": True, "severity": "MSL", "fault": "OC_DISCHARGE_STRING"},
        "stimulus_neg": {"override": "pack_current", "string": 0, "value_mA": 2000},
        "expected_neg": {"diag_triggered": False},
        "sys_refs": ["SYS-REQ-024"],
    },
    {
        "ssr": "SSR-006", "title": "Overcurrent charge (string) detection",
        "stimulus_pos": {"override": "pack_current", "string": 0, "value_mA": -10000},
        "expected_pos": {"diag_triggered": True, "severity": "MSL", "fault": "OC_CHARGE_STRING"},
        "stimulus_neg": {"override": "pack_current", "string": 0, "value_mA": -2000},
        "expected_neg": {"diag_triggered": False},
        "sys_refs": ["SYS-REQ-025"],
    },
    {
        "ssr": "SSR-007", "title": "Overtemperature discharge detection",
        "stimulus_pos": {"override": "cell_temperature", "sensor": 0, "value_ddegC": 550},
        "expected_pos": {"diag_triggered": True, "severity": "MSL", "fault": "OVERTEMP_DISCHARGE"},
        "stimulus_neg": {"override": "cell_temperature", "sensor": 0, "value_ddegC": 250},
        "expected_neg": {"diag_triggered": False},
        "sys_refs": ["SYS-REQ-026"],
    },
    {
        "ssr": "SSR-008", "title": "Overtemperature charge detection",
        "stimulus_pos": {"override": "cell_temperature", "sensor": 0, "value_ddegC": 450},
        "expected_pos": {"diag_triggered": True, "severity": "MSL", "fault": "OVERTEMP_CHARGE"},
        "stimulus_neg": {"override": "cell_temperature", "sensor": 0, "value_ddegC": 250},
        "expected_neg": {"diag_triggered": False},
        "sys_refs": ["SYS-REQ-027"],
    },
    {
        "ssr": "SSR-009", "title": "Undertemperature discharge detection",
        "stimulus_pos": {"override": "cell_temperature", "sensor": 0, "value_ddegC": -50},
        "expected_pos": {"diag_triggered": True, "severity": "MSL", "fault": "UNDERTEMP_DISCHARGE"},
        "stimulus_neg": {"override": "cell_temperature", "sensor": 0, "value_ddegC": 250},
        "expected_neg": {"diag_triggered": False},
        "sys_refs": ["SYS-REQ-028"],
    },
    {
        "ssr": "SSR-010", "title": "Undertemperature charge detection",
        "stimulus_pos": {"override": "cell_temperature", "sensor": 0, "value_ddegC": 0},
        "expected_pos": {"diag_triggered": True, "severity": "MSL", "fault": "UNDERTEMP_CHARGE"},
        "stimulus_neg": {"override": "cell_temperature", "sensor": 0, "value_ddegC": 250},
        "expected_neg": {"diag_triggered": False},
        "sys_refs": ["SYS-REQ-029"],
    },
    # --- Fault Reaction (SSR-020 .. SSR-024) ---
    {
        "ssr": "SSR-020", "title": "FATAL state triggers ERROR transition",
        "stimulus_pos": {"override": "cell_voltage", "cell": 0, "value_mv": 2800},
        "expected_pos": {"bms_state_transition": "NORMAL->ERROR", "transition_cause": "MSL_FAULT"},
        "stimulus_neg": {"action": "no_fault_injection"},
        "expected_neg": {"bms_state": "NORMAL"},
        "sys_refs": ["SYS-REQ-030"],
    },
    {
        "ssr": "SSR-021", "title": "Contactors open within 100ms of ERROR entry",
        "stimulus_pos": {"override": "cell_voltage", "cell": 0, "value_mv": 2800},
        "expected_pos": {
            "contactor_state": "OPEN",
            "reaction_time_ms_max": 100,
            "string_plus_open": True,
            "string_minus_open": True,
            "precharge_open": True,
        },
        "stimulus_neg": {"action": "no_fault_injection"},
        "expected_neg": {"contactor_state": "CLOSED_IF_RUNNING"},
        "sys_refs": ["SYS-REQ-031"],
    },
    {
        "ssr": "SSR-022", "title": "ERROR state exit logic requires all faults cleared",
        "stimulus_pos": {
            "phase1": {"override": "cell_voltage", "cell": 0, "value_mv": 2800},
            "phase2_clear": {"override": "cell_voltage", "cell": 0, "value_mv": 3700},
            "phase2_wait_ms": 5000,
        },
        "expected_pos": {"bms_state_after_clear": "STANDBY", "all_faults_cleared": True},
        "stimulus_neg": {
            "phase1": {"override": "cell_voltage", "cell": 0, "value_mv": 2800},
            "phase2_partial_clear": True,
        },
        "expected_neg": {"bms_state": "ERROR", "exit_blocked": True},
        "sys_refs": ["SYS-REQ-032"],
    },
    {
        "ssr": "SSR-023", "title": "Deep discharge detection and permanent lockout",
        "stimulus_pos": {"override": "cell_voltage", "cell": 0, "value_mv": 1500},
        "expected_pos": {"diag_triggered": True, "fault": "DEEP_DISCHARGE", "lockout": True},
        "stimulus_neg": {"override": "cell_voltage", "cell": 0, "value_mv": 2000},
        "expected_neg": {"lockout": False},
        "sys_refs": ["SYS-REQ-033"],
    },
    {
        "ssr": "SSR-024", "title": "Current on open string detected",
        "stimulus_pos": {
            "contactor_state": "OPEN",
            "override": "pack_current", "string": 0, "value_mA": 500,
        },
        "expected_pos": {"diag_triggered": True, "fault": "CURRENT_ON_OPEN_STRING"},
        "stimulus_neg": {
            "contactor_state": "OPEN",
            "override": "pack_current", "string": 0, "value_mA": 0,
        },
        "expected_neg": {"diag_triggered": False},
        "sys_refs": ["SYS-REQ-034"],
    },
    # --- Diagnostic Coverage (SSR-030 .. SSR-033) ---
    {
        "ssr": "SSR-030", "title": "Plausibility check on redundant measurements",
        "stimulus_pos": {
            "override_primary": {"override": "cell_voltage", "cell": 0, "value_mv": 3700},
            "override_redundant": {"override": "cell_voltage_redundant", "cell": 0, "value_mv": 3200},
        },
        "expected_pos": {"plausibility_error": True, "delta_threshold_exceeded": True},
        "stimulus_neg": {
            "override_primary": {"override": "cell_voltage", "cell": 0, "value_mv": 3700},
            "override_redundant": {"override": "cell_voltage_redundant", "cell": 0, "value_mv": 3695},
        },
        "expected_neg": {"plausibility_error": False},
        "sys_refs": ["SYS-REQ-040"],
    },
    {
        "ssr": "SSR-031", "title": "60% diagnostic coverage achieved",
        "stimulus_pos": {"action": "run_full_diagnostic_suite"},
        "expected_pos": {"coverage_percent_min": 60, "all_diag_entries_exercised": True},
        "stimulus_neg": {"action": "disable_half_diagnostics"},
        "expected_neg": {"coverage_percent_below_60": True},
        "sys_refs": ["SYS-REQ-041"],
    },
    {
        "ssr": "SSR-032", "title": "FTTI (Fault Tolerant Time Interval) verified",
        "stimulus_pos": {"override": "cell_voltage", "cell": 0, "value_mv": 2800},
        "expected_pos": {
            "detection_time_ms_max": 50,
            "reaction_time_ms_max": 100,
            "total_ftti_ms_max": 150,
        },
        "stimulus_neg": {"action": "delay_diagnostic_cycle_500ms"},
        "expected_neg": {"ftti_violated": True},
        "sys_refs": ["SYS-REQ-042"],
    },
    {
        "ssr": "SSR-033", "title": "No hidden failures in diagnostic paths",
        "stimulus_pos": {"action": "inject_diag_self_test"},
        "expected_pos": {"all_diag_paths_verified": True, "hidden_failures": 0},
        "stimulus_neg": {"action": "disable_diag_self_test"},
        "expected_neg": {"hidden_failure_detected": True},
        "sys_refs": ["SYS-REQ-043"],
    },
    # --- Communication Safety (SSR-040 .. SSR-042) ---
    {
        "ssr": "SSR-040", "title": "CAN communication timeout detection",
        "stimulus_pos": {"action": "stop_can_tx", "duration_ms": 500},
        "expected_pos": {"diag_triggered": True, "fault": "CAN_TIMEOUT"},
        "stimulus_neg": {"action": "normal_can_tx"},
        "expected_neg": {"diag_triggered": False},
        "sys_refs": ["SYS-REQ-050"],
    },
    {
        "ssr": "SSR-041", "title": "IVT current sensor CAN timeout",
        "stimulus_pos": {"action": "stop_ivt_can_messages", "duration_ms": 300},
        "expected_pos": {"diag_triggered": True, "fault": "IVT_TIMEOUT"},
        "stimulus_neg": {"action": "normal_ivt_messages"},
        "expected_neg": {"diag_triggered": False},
        "sys_refs": ["SYS-REQ-051"],
    },
    {
        "ssr": "SSR-042", "title": "AFE SPI communication timeout",
        "stimulus_pos": {"action": "stop_afe_spi_response", "duration_ms": 200},
        "expected_pos": {"diag_triggered": True, "fault": "AFE_SPI_TIMEOUT"},
        "stimulus_neg": {"action": "normal_afe_spi"},
        "expected_neg": {"diag_triggered": False},
        "sys_refs": ["SYS-REQ-052"],
    },
    # --- Contactor Safety (SSR-050 .. SSR-052) ---
    {
        "ssr": "SSR-050", "title": "String+ contactor feedback verification",
        "stimulus_pos": {
            "command": "close_string_plus",
            "feedback_override": "string_plus_feedback_open",
        },
        "expected_pos": {"diag_triggered": True, "fault": "CONTACTOR_FEEDBACK_MISMATCH_PLUS"},
        "stimulus_neg": {
            "command": "close_string_plus",
            "feedback_override": "string_plus_feedback_closed",
        },
        "expected_neg": {"diag_triggered": False, "contactor_plus_state": "CLOSED"},
        "sys_refs": ["SYS-REQ-060"],
    },
    {
        "ssr": "SSR-051", "title": "String- contactor feedback verification",
        "stimulus_pos": {
            "command": "close_string_minus",
            "feedback_override": "string_minus_feedback_open",
        },
        "expected_pos": {"diag_triggered": True, "fault": "CONTACTOR_FEEDBACK_MISMATCH_MINUS"},
        "stimulus_neg": {
            "command": "close_string_minus",
            "feedback_override": "string_minus_feedback_closed",
        },
        "expected_neg": {"diag_triggered": False, "contactor_minus_state": "CLOSED"},
        "sys_refs": ["SYS-REQ-061"],
    },
    {
        "ssr": "SSR-052", "title": "Precharge timeout detection",
        "stimulus_pos": {
            "command": "start_precharge",
            "precharge_override": "block_voltage_rise",
        },
        "expected_pos": {
            "diag_triggered": True,
            "fault": "PRECHARGE_TIMEOUT",
            "precharge_aborted": True,
            "contactors_opened": True,
        },
        "stimulus_neg": {
            "command": "start_precharge",
            "precharge_override": "normal_voltage_rise",
        },
        "expected_neg": {
            "precharge_complete": True,
            "string_plus_closed": True,
        },
        "sys_refs": ["SYS-REQ-062"],
    },
]


def _gen_ssr_tests() -> list[dict]:
    """Generate positive + negative tests for each SSR."""
    tests = []
    for defn in _SSR_DEFINITIONS:
        ssr = defn["ssr"]
        title = defn["title"]
        sys_refs = defn.get("sys_refs", [])

        # Positive test: requirement is met / fault detected
        tests.append({
            "id": f"{ssr}-POS",
            "category": "SSR",
            "test_type": "positive",
            "description": f"{ssr} positive: {title} - verify requirement is satisfied",
            "stimulus": defn["stimulus_pos"],
            "expected": defn["expected_pos"],
            "verifies": [ssr] + sys_refs,
            "asil": "D",
            "priority": "P1",
        })

        # Negative test: no false trigger / violation detected
        tests.append({
            "id": f"{ssr}-NEG",
            "category": "SSR",
            "test_type": "negative",
            "description": f"{ssr} negative: {title} - verify no false positive / violation detection",
            "stimulus": defn["stimulus_neg"],
            "expected": defn["expected_neg"],
            "verifies": [ssr] + sys_refs,
            "asil": "D",
            "priority": "P1",
        })

    return tests


# ===========================================================================
# DFA: Dependent Failure Analysis
# ===========================================================================

_DFA_TESTS_RAW = [
    {
        "id": "DFA-CC-001",
        "title": "SPI2 bus failure (SPS + SBC common-cause)",
        "description": (
            "SPI2 bus failure affects both SPS driver and SBC watchdog. "
            "Verify BMS detects loss of both peripherals and enters safe state. "
            "GAP-08: common-cause on shared SPI bus."
        ),
        "stimulus": {"action": "disable_spi2_bus"},
        "expected": {
            "sps_fault_detected": True,
            "sbc_watchdog_fault": True,
            "bms_state": "ERROR",
            "contactors_open": True,
        },
        "gap_ref": "GAP-08",
        "verifies": ["SSR-042", "DFA-CC-SPI2"],
    },
    {
        "id": "DFA-CC-002",
        "title": "isoSPI failure (all voltage + temperature lost)",
        "description": (
            "isoSPI bus failure causes loss of all cell voltage and temperature "
            "measurements simultaneously. Verify BMS detects and reacts within FTTI. "
            "GAP-01: single-point isoSPI failure."
        ),
        "stimulus": {"action": "disable_isospi_bus"},
        "expected": {
            "all_voltages_stale": True,
            "all_temperatures_stale": True,
            "bms_state": "ERROR",
            "reaction_time_ms_max": 100,
        },
        "gap_ref": "GAP-01",
        "verifies": ["SSR-042", "SSR-030", "DFA-CC-ISOSPI"],
    },
    {
        "id": "DFA-CC-003",
        "title": "Power supply loss (UVLO fail-safe)",
        "description": (
            "Supply voltage drops below UVLO threshold. Verify SBC triggers "
            "hardware fail-safe (contactors open via hardware path, not software). "
            "GAP-11: power supply common-cause."
        ),
        "stimulus": {"action": "drop_supply_voltage_below_uvlo"},
        "expected": {
            "sbc_uvlo_triggered": True,
            "hardware_failsafe_active": True,
            "contactors_open": True,
        },
        "gap_ref": "GAP-11",
        "verifies": ["DFA-CC-POWER"],
    },
    {
        "id": "DFA-CASCADE-001",
        "title": "OV -> contactor open -> SPS feedback mismatch cascade",
        "description": (
            "Cell OV triggers contactor open command via SPS, but SPS feedback "
            "reports contactor still closed. Verify BMS detects the feedback "
            "mismatch as a secondary fault and does not re-close."
        ),
        "stimulus": {
            "phase1": {"override": "cell_voltage", "cell": 0, "value_mv": 2800},
            "phase2": {"override": "sps_feedback", "contactor": "plus", "state": "closed"},
        },
        "expected": {
            "primary_fault": "CELL_OV",
            "secondary_fault": "CONTACTOR_FEEDBACK_MISMATCH",
            "contactor_reclose_attempted": False,
            "bms_state": "ERROR",
        },
        "gap_ref": None,
        "verifies": ["SSR-050", "SSR-020", "DFA-CASCADE"],
    },
    {
        "id": "DFA-SI-001",
        "title": "OV + AFE loss simultaneous",
        "description": (
            "Cell overvoltage occurs simultaneously with AFE communication loss. "
            "Verify both faults are detected independently and the more severe "
            "reaction (ERROR + contactors open) takes precedence."
        ),
        "stimulus": {
            "inject_ov": {"override": "cell_voltage", "cell": 0, "value_mv": 2800},
            "inject_afe_loss": {"action": "stop_afe_spi_response"},
        },
        "expected": {
            "ov_fault_detected": True,
            "afe_timeout_detected": True,
            "bms_state": "ERROR",
            "contactors_open": True,
        },
        "gap_ref": None,
        "verifies": ["SSR-001", "SSR-042", "DFA-SI"],
    },
    {
        "id": "DFA-SI-002",
        "title": "CAN1 + CAN2 simultaneous loss",
        "description": (
            "Both CAN1 (IVT) and CAN2 (vehicle) buses fail simultaneously. "
            "Verify BMS detects both timeouts and enters safe state."
        ),
        "stimulus": {"action": "disable_can1_and_can2"},
        "expected": {
            "can1_timeout_detected": True,
            "can2_timeout_detected": True,
            "bms_state": "ERROR",
            "contactors_open": True,
        },
        "gap_ref": None,
        "verifies": ["SSR-040", "SSR-041", "DFA-SI"],
    },
    {
        "id": "DFA-SI-003",
        "title": "OT + OC + UV triple fault",
        "description": (
            "Overtemperature, overcurrent, and undervoltage all occur simultaneously. "
            "Verify all three faults are logged independently and the combined "
            "reaction is correct (ERROR, contactors open)."
        ),
        "stimulus": {
            "inject_ot": {"override": "cell_temperature", "sensor": 0, "value_ddegC": 550},
            "inject_oc": {"override": "pack_current", "string": 0, "value_mA": 10000},
            "inject_uv": {"override": "cell_voltage", "cell": 0, "value_mv": 1700},
        },
        "expected": {
            "ot_fault_detected": True,
            "oc_fault_detected": True,
            "uv_fault_detected": True,
            "fault_count": 3,
            "bms_state": "ERROR",
        },
        "gap_ref": None,
        "verifies": ["SSR-002", "SSR-003", "SSR-007", "DFA-SI"],
    },
    {
        "id": "DFA-SI-004",
        "title": "OV during precharge state",
        "description": (
            "Cell overvoltage detected while BMS is in PRECHARGE state. "
            "Verify precharge is aborted and contactors opened."
        ),
        "stimulus": {
            "initial_state": "PRECHARGE",
            "inject": {"override": "cell_voltage", "cell": 0, "value_mv": 2800},
        },
        "expected": {
            "precharge_aborted": True,
            "contactors_open": True,
            "bms_state": "ERROR",
        },
        "gap_ref": None,
        "verifies": ["SSR-001", "SSR-020", "SSR-052", "DFA-SI"],
    },
    {
        "id": "DFA-SI-005",
        "title": "IVT loss + OV simultaneous",
        "description": (
            "IVT current sensor communication lost simultaneously with cell OV. "
            "Verify both faults detected; contactors opened."
        ),
        "stimulus": {
            "inject_ov": {"override": "cell_voltage", "cell": 0, "value_mv": 2800},
            "inject_ivt_loss": {"action": "stop_ivt_can_messages"},
        },
        "expected": {
            "ov_fault_detected": True,
            "ivt_timeout_detected": True,
            "bms_state": "ERROR",
            "contactors_open": True,
        },
        "gap_ref": None,
        "verifies": ["SSR-001", "SSR-041", "DFA-SI"],
    },
    {
        "id": "DFA-CC-004",
        "title": "Task reorder SBC before SPS (GAP-08)",
        "description": (
            "SBC watchdog service task runs before SPS contactor drive task "
            "due to priority inversion. Verify system detects timing violation "
            "or operates correctly regardless of order."
        ),
        "stimulus": {"action": "reorder_tasks_sbc_before_sps"},
        "expected": {
            "timing_violation_detected": True,
            "sps_command_still_valid": True,
            "sbc_watchdog_serviced": True,
        },
        "gap_ref": "GAP-08",
        "verifies": ["DFA-CC-TASK-ORDER"],
    },
]


def _gen_dfa_tests() -> list[dict]:
    tests = []
    for raw in _DFA_TESTS_RAW:
        tests.append({
            "id": raw["id"],
            "category": "DFA",
            "test_type": "dependent_failure",
            "description": raw["description"],
            "stimulus": raw["stimulus"],
            "expected": raw["expected"],
            "gap_ref": raw.get("gap_ref"),
            "verifies": raw["verifies"],
            "asil": "D",
            "priority": "P1",
        })
    return tests


# ===========================================================================
# B2B: Back-to-Back SIL vs HIL
# ===========================================================================

_B2B_TESTS_RAW = [
    {
        "id": "B2B-001",
        "title": "Cell OV reaction timing comparison",
        "description": (
            "Inject cell OV on both SIL and HIL. Compare fault detection time "
            "and contactor open time. SIL must be within +/-10ms of HIL."
        ),
        "stimulus": {"override": "cell_voltage", "cell": 0, "value_mv": 2800},
        "expected": {
            "sil_detection_time_recorded": True,
            "hil_detection_time_recorded": True,
            "timing_delta_ms_max": 10,
        },
        "metric": "detection_time_ms",
    },
    {
        "id": "B2B-002",
        "title": "Cell UV reaction timing comparison",
        "description": (
            "Inject cell UV on both SIL and HIL. Compare detection and reaction timing."
        ),
        "stimulus": {"override": "cell_voltage", "cell": 0, "value_mv": 1700},
        "expected": {
            "sil_detection_time_recorded": True,
            "hil_detection_time_recorded": True,
            "timing_delta_ms_max": 10,
        },
        "metric": "detection_time_ms",
    },
    {
        "id": "B2B-003",
        "title": "AFE loss detection time comparison",
        "description": (
            "Disable AFE communication on both SIL and HIL. Compare timeout detection timing."
        ),
        "stimulus": {"action": "stop_afe_spi_response"},
        "expected": {
            "sil_timeout_detected": True,
            "hil_timeout_detected": True,
            "timing_delta_ms_max": 20,
        },
        "metric": "timeout_detection_ms",
    },
    {
        "id": "B2B-004",
        "title": "Overcurrent reaction timing comparison",
        "description": (
            "Inject overcurrent on both SIL and HIL. Compare reaction timing."
        ),
        "stimulus": {"override": "pack_current", "string": 0, "value_mA": 10000},
        "expected": {
            "sil_reaction_time_recorded": True,
            "hil_reaction_time_recorded": True,
            "timing_delta_ms_max": 10,
        },
        "metric": "reaction_time_ms",
    },
    {
        "id": "B2B-005",
        "title": "Overtemperature reaction timing comparison",
        "description": (
            "Inject overtemperature on both SIL and HIL. Compare timing."
        ),
        "stimulus": {"override": "cell_temperature", "sensor": 0, "value_ddegC": 550},
        "expected": {
            "timing_delta_ms_max": 10,
        },
        "metric": "reaction_time_ms",
    },
    {
        "id": "B2B-006",
        "title": "State machine full cycle transition match",
        "description": (
            "Run STANDBY -> PRECHARGE -> NORMAL -> ERROR -> STANDBY on SIL and HIL. "
            "Verify state sequence and transition timing are bit-exact."
        ),
        "stimulus": {"action": "full_state_cycle"},
        "expected": {
            "state_sequence_match": True,
            "transition_timing_match": True,
            "max_timing_delta_ms": 20,
        },
        "metric": "state_sequence",
    },
    {
        "id": "B2B-007",
        "title": "CAN TX cell voltage content bit-exact",
        "description": (
            "Compare CAN TX messages for cell voltages between SIL and HIL. "
            "All 18 cell voltage values must be bit-exact in the CAN frame."
        ),
        "stimulus": {"action": "capture_can_tx_cell_voltages", "duration_ms": 5000},
        "expected": {"bit_exact_match": True, "frames_compared_min": 50},
        "metric": "can_content",
    },
    {
        "id": "B2B-008",
        "title": "CAN TX cell temperature content bit-exact",
        "description": (
            "Compare CAN TX temperature messages between SIL and HIL."
        ),
        "stimulus": {"action": "capture_can_tx_cell_temps", "duration_ms": 5000},
        "expected": {"bit_exact_match": True, "frames_compared_min": 50},
        "metric": "can_content",
    },
    {
        "id": "B2B-009",
        "title": "CAN TX pack current content bit-exact",
        "description": (
            "Compare CAN TX pack current messages between SIL and HIL."
        ),
        "stimulus": {"action": "capture_can_tx_pack_current", "duration_ms": 5000},
        "expected": {"bit_exact_match": True, "frames_compared_min": 50},
        "metric": "can_content",
    },
    {
        "id": "B2B-010",
        "title": "CAN TX SOC/SOE content bit-exact",
        "description": (
            "Compare CAN TX SOC and SOE messages between SIL and HIL."
        ),
        "stimulus": {"action": "capture_can_tx_soc_soe", "duration_ms": 5000},
        "expected": {"bit_exact_match": True, "frames_compared_min": 50},
        "metric": "can_content",
    },
    {
        "id": "B2B-011",
        "title": "CAN TX BMS state content bit-exact",
        "description": (
            "Compare CAN TX BMS state messages between SIL and HIL."
        ),
        "stimulus": {"action": "capture_can_tx_bms_state", "duration_ms": 5000},
        "expected": {"bit_exact_match": True, "frames_compared_min": 50},
        "metric": "can_content",
    },
    {
        "id": "B2B-012",
        "title": "DIAG counter comparison after fault sequence",
        "description": (
            "Inject identical fault sequence on SIL and HIL. Compare diagnostic "
            "counter values after sequence completes."
        ),
        "stimulus": {
            "fault_sequence": [
                {"override": "cell_voltage", "cell": 0, "value_mv": 2800, "hold_ms": 200},
                {"override": "cell_voltage", "cell": 0, "value_mv": 3700, "hold_ms": 500},
                {"override": "cell_voltage", "cell": 5, "value_mv": 1700, "hold_ms": 200},
            ],
        },
        "expected": {
            "diag_counter_ov_match": True,
            "diag_counter_uv_match": True,
            "diag_counter_total_match": True,
        },
        "metric": "diag_counters",
    },
    {
        "id": "B2B-013",
        "title": "DIAG counter comparison under sustained load",
        "description": (
            "Run 60s sustained normal operation on SIL and HIL. "
            "Verify no spurious diagnostic counter increments on either platform."
        ),
        "stimulus": {"action": "sustained_normal_operation", "duration_ms": 60000},
        "expected": {
            "sil_spurious_diag_count": 0,
            "hil_spurious_diag_count": 0,
        },
        "metric": "diag_counters",
    },
]


def _gen_b2b_tests() -> list[dict]:
    tests = []
    for raw in _B2B_TESTS_RAW:
        tests.append({
            "id": raw["id"],
            "category": "B2B",
            "test_type": "back_to_back",
            "description": raw["description"],
            "stimulus": raw["stimulus"],
            "expected": raw["expected"],
            "metric": raw.get("metric"),
            "verifies": [raw["id"]],
            "asil": "D",
            "priority": "P1",
        })
    return tests


# ===========================================================================
# E2E: End-to-End data flow
# ===========================================================================

def _gen_e2e_tests() -> list[dict]:
    tests = []

    # --- Voltage path: AFE -> isoSPI -> SPI1 -> DMA -> database -> SOA -> DIAG -> BMS -> SPS ---
    volt_stages = [
        ("AFE-INJECT", "Inject voltage at AFE analog input model"),
        ("ISOSPI-CAPTURE", "Verify isoSPI frame contains correct voltage"),
        ("SPI1-RX", "Verify SPI1 DMA buffer receives isoSPI payload"),
        ("DMA-COMPLETE", "Verify DMA transfer complete flag set"),
        ("DB-WRITE", "Verify database cell voltage table updated"),
        ("SOA-EVAL", "Verify SOA module evaluates voltage against limits"),
        ("DIAG-ENTRY", "Verify DIAG module creates/clears entry based on SOA result"),
        ("BMS-STATE", "Verify BMS state machine reacts to DIAG verdict"),
    ]
    for i, (stage, desc) in enumerate(volt_stages, 1):
        tests.append({
            "id": f"E2E-VOLT-{i:03d}",
            "category": "E2E",
            "test_type": "data_flow",
            "path": "voltage",
            "stage": stage,
            "description": f"Voltage E2E stage {i}/{len(volt_stages)}: {desc}",
            "stimulus": {"override": "cell_voltage", "cell": 0, "value_mv": 3700},
            "expected": {
                "stage": stage,
                "data_present": True,
                "value_correct": True,
                "latency_ms_max": 10 * i,
            },
            "verifies": [f"E2E-VOLT-{stage}"],
            "asil": "D",
            "priority": "P1",
        })

    # --- Temperature path: NTC -> AFE MUX -> isoSPI -> database -> SOA -> DIAG ---
    temp_stages = [
        ("NTC-INJECT", "Inject temperature at NTC model input"),
        ("AFE-MUX", "Verify AFE MUX selects correct NTC channel"),
        ("ISOSPI-CAPTURE", "Verify isoSPI frame contains temperature ADC value"),
        ("DB-WRITE", "Verify database temperature table updated with converted ddegC"),
        ("SOA-EVAL", "Verify SOA evaluates temperature against OT/UT limits"),
        ("DIAG-ENTRY", "Verify DIAG creates entry on threshold violation"),
    ]
    for i, (stage, desc) in enumerate(temp_stages, 1):
        tests.append({
            "id": f"E2E-TEMP-{i:03d}",
            "category": "E2E",
            "test_type": "data_flow",
            "path": "temperature",
            "stage": stage,
            "description": f"Temperature E2E stage {i}/{len(temp_stages)}: {desc}",
            "stimulus": {"override": "cell_temperature", "sensor": 0, "value_ddegC": 250},
            "expected": {
                "stage": stage,
                "data_present": True,
                "value_correct": True,
                "latency_ms_max": 10 * i,
            },
            "verifies": [f"E2E-TEMP-{stage}"],
            "asil": "D",
            "priority": "P1",
        })

    # --- Current path: IVT -> CAN1 -> RX handler -> database -> SOA -> DIAG ---
    curr_stages = [
        ("IVT-INJECT", "Inject current at IVT CAN model output"),
        ("CAN1-RX", "Verify CAN1 RX handler receives IVT frame"),
        ("DB-WRITE", "Verify database current table updated"),
        ("SOA-EVAL", "Verify SOA evaluates current against OC limits"),
        ("DIAG-ENTRY", "Verify DIAG creates entry on overcurrent"),
    ]
    for i, (stage, desc) in enumerate(curr_stages, 1):
        tests.append({
            "id": f"E2E-CURR-{i:03d}",
            "category": "E2E",
            "test_type": "data_flow",
            "path": "current",
            "stage": stage,
            "description": f"Current E2E stage {i}/{len(curr_stages)}: {desc}",
            "stimulus": {"override": "pack_current", "string": 0, "value_mA": 2000},
            "expected": {
                "stage": stage,
                "data_present": True,
                "value_correct": True,
                "latency_ms_max": 10 * i,
            },
            "verifies": [f"E2E-CURR-{stage}"],
            "asil": "D",
            "priority": "P1",
        })

    # --- Stale data rejection (MRC timestamp > 250ms) ---
    stale_paths = [
        ("VOLT", "cell_voltage", {"override": "cell_voltage", "cell": 0, "value_mv": 3700}),
        ("TEMP", "cell_temperature", {"override": "cell_temperature", "sensor": 0, "value_ddegC": 250}),
        ("CURR", "pack_current", {"override": "pack_current", "string": 0, "value_mA": 2000}),
    ]
    for i, (path_short, param_key, stim) in enumerate(stale_paths, 1):
        tests.append({
            "id": f"E2E-STALE-{i:03d}",
            "category": "E2E",
            "test_type": "stale_data",
            "path": path_short.lower(),
            "description": (
                f"Stale {path_short} data: hold {param_key} update for >250ms, "
                f"verify MRC flags data as stale and SOA rejects it"
            ),
            "stimulus": {
                "inject_then_hold": stim,
                "hold_without_update_ms": 300,
            },
            "expected": {
                "mrc_stale_flag": True,
                "soa_data_rejected": True,
                "stale_threshold_ms": 250,
            },
            "verifies": [f"E2E-STALE-{path_short}", "SSR-030"],
            "asil": "D",
            "priority": "P1",
        })

    # --- Data freshness within timing window ---
    for i, (path_short, param_key, stim) in enumerate(stale_paths, 1):
        tests.append({
            "id": f"E2E-FRESH-{i:03d}",
            "category": "E2E",
            "test_type": "data_freshness",
            "path": path_short.lower(),
            "description": (
                f"Fresh {path_short} data: update {param_key} within 100ms cycle, "
                f"verify MRC accepts data as fresh"
            ),
            "stimulus": {
                "inject_cyclic": stim,
                "cycle_ms": 100,
                "duration_ms": 2000,
            },
            "expected": {
                "mrc_stale_flag": False,
                "soa_data_accepted": True,
                "all_cycles_fresh": True,
            },
            "verifies": [f"E2E-FRESH-{path_short}"],
            "asil": "D",
            "priority": "P2",
        })

    return tests


# ===========================================================================
# HW: Hardware Interface Tests
# ===========================================================================

def _gen_hw_tests() -> list[dict]:
    tests = []

    # --- SPI1: AFE (LTC6813 / ADBMS6815) ---
    spi1_tests = [
        ("HW-SPI1-001", "AFE SPI1 init: clock, CPOL, CPHA, CS configuration", {"action": "verify_spi1_init"}, {"spi1_configured": True, "clock_hz": 1000000}),
        ("HW-SPI1-002", "AFE SPI1 RDCVA command: read cell group A voltages", {"action": "spi1_rdcva"}, {"response_valid": True, "pec_ok": True}),
        ("HW-SPI1-003", "AFE SPI1 RDCVB command: read cell group B voltages", {"action": "spi1_rdcvb"}, {"response_valid": True, "pec_ok": True}),
        ("HW-SPI1-004", "AFE SPI1 RDCVC command: read cell group C voltages", {"action": "spi1_rdcvc"}, {"response_valid": True, "pec_ok": True}),
        ("HW-SPI1-005", "AFE SPI1 RDAUXA command: read GPIO/temp group A", {"action": "spi1_rdauxa"}, {"response_valid": True, "pec_ok": True}),
        ("HW-SPI1-006", "AFE SPI1 RDAUXB command: read GPIO/temp group B", {"action": "spi1_rdauxb"}, {"response_valid": True, "pec_ok": True}),
        ("HW-SPI1-007", "AFE SPI1 PEC error injection: corrupt 1 bit in RX", {"action": "spi1_inject_pec_error"}, {"pec_error_detected": True, "data_rejected": True}),
        ("HW-SPI1-008", "AFE SPI1 PEC error on all bytes: complete corruption", {"action": "spi1_inject_full_corruption"}, {"pec_error_detected": True, "retry_attempted": True}),
        ("HW-SPI1-009", "AFE SPI1 DMA timeout: no DMA complete within 5ms", {"action": "spi1_block_dma_complete"}, {"dma_timeout_detected": True, "diag_entry_created": True}),
        ("HW-SPI1-010", "AFE SPI1 recovery after timeout: next cycle succeeds", {"action": "spi1_timeout_then_recover"}, {"recovery_successful": True, "data_valid_after_recovery": True}),
        ("HW-SPI1-011", "AFE SPI1 WRCFGA: write configuration register A", {"action": "spi1_wrcfga"}, {"ack_valid": True, "config_applied": True}),
        ("HW-SPI1-012", "AFE SPI1 ADCV: start cell ADC conversion", {"action": "spi1_adcv"}, {"conversion_started": True, "poll_complete": True}),
    ]
    for tid, desc, stim, exp in spi1_tests:
        tests.append({
            "id": tid, "category": "HW", "test_type": "hw_interface",
            "peripheral": "SPI1_AFE",
            "description": desc, "stimulus": stim, "expected": exp,
            "verifies": [tid], "asil": "D", "priority": "P1",
        })

    # --- SPI2: SPS + SBC ---
    spi2_tests = [
        ("HW-SPI2-001", "SPS SPI2 contactor drive command: close string+", {"action": "spi2_sps_close_plus"}, {"sps_ack": True, "contactor_plus_driven": True}),
        ("HW-SPI2-002", "SPS SPI2 contactor drive command: close string-", {"action": "spi2_sps_close_minus"}, {"sps_ack": True, "contactor_minus_driven": True}),
        ("HW-SPI2-003", "SPS SPI2 contactor drive command: close precharge", {"action": "spi2_sps_close_precharge"}, {"sps_ack": True, "precharge_driven": True}),
        ("HW-SPI2-004", "SPS SPI2 contactor open all command", {"action": "spi2_sps_open_all"}, {"all_contactors_open": True}),
        ("HW-SPI2-005", "SBC SPI2 watchdog service: kick within window", {"action": "spi2_sbc_kick"}, {"watchdog_serviced": True, "sbc_state": "NORMAL"}),
        ("HW-SPI2-006", "SBC SPI2 watchdog timeout: no kick for 100ms", {"action": "spi2_sbc_no_kick_100ms"}, {"sbc_reset_triggered": True}),
        ("HW-SPI2-007", "SPI2 bus contention: SPS + SBC simultaneous access", {"action": "spi2_simultaneous_access"}, {"bus_arbitrated": True, "no_data_corruption": True}),
        ("HW-SPI2-008", "SPI2 CS glitch: verify no spurious transactions", {"action": "spi2_cs_glitch"}, {"spurious_transaction": False}),
    ]
    for tid, desc, stim, exp in spi2_tests:
        tests.append({
            "id": tid, "category": "HW", "test_type": "hw_interface",
            "peripheral": "SPI2_SPS_SBC",
            "description": desc, "stimulus": stim, "expected": exp,
            "verifies": [tid], "asil": "D", "priority": "P1",
        })

    # --- SPI3: FRAM ---
    spi3_tests = [
        ("HW-SPI3-001", "FRAM SPI3 write: store diagnostic NVM block", {"action": "fram_write_diag_block"}, {"write_complete": True, "verify_readback_ok": True}),
        ("HW-SPI3-002", "FRAM SPI3 read: retrieve diagnostic NVM block", {"action": "fram_read_diag_block"}, {"read_complete": True, "data_matches_written": True}),
        ("HW-SPI3-003", "FRAM SPI3 persistence: write, reset, read back", {"action": "fram_write_reset_read"}, {"data_persisted": True, "value_matches": True}),
        ("HW-SPI3-004", "FRAM SPI3 wear: 10000 write cycles to same address", {"action": "fram_wear_test_10k"}, {"all_writes_verified": True, "no_bit_errors": True}),
    ]
    for tid, desc, stim, exp in spi3_tests:
        tests.append({
            "id": tid, "category": "HW", "test_type": "hw_interface",
            "peripheral": "SPI3_FRAM",
            "description": desc, "stimulus": stim, "expected": exp,
            "verifies": [tid], "asil": "B", "priority": "P2",
        })

    # --- CAN1: IVT current sensor ---
    can1_tests = [
        ("HW-CAN1-001", "CAN1 init: bitrate 500kbps, filters configured", {"action": "verify_can1_init"}, {"can1_configured": True, "bitrate": 500000}),
        ("HW-CAN1-002", "CAN1 TX: send IVT trigger message", {"action": "can1_tx_ivt_trigger"}, {"tx_complete": True, "ack_received": True}),
        ("HW-CAN1-003", "CAN1 RX: receive IVT current response", {"action": "can1_rx_ivt_current"}, {"rx_received": True, "current_value_valid": True}),
        ("HW-CAN1-004", "CAN1 RX: receive IVT voltage response", {"action": "can1_rx_ivt_voltage"}, {"rx_received": True, "voltage_value_valid": True}),
        ("HW-CAN1-005", "CAN1 bus-off: inject 128+ error frames", {"action": "can1_inject_bus_off"}, {"bus_off_detected": True, "recovery_initiated": True}),
        ("HW-CAN1-006", "CAN1 bus-off recovery: auto-recover within 1s", {"action": "can1_bus_off_then_recover"}, {"recovered": True, "recovery_time_ms_max": 1000}),
        ("HW-CAN1-007", "CAN1 RX filter: reject non-IVT frames", {"action": "can1_inject_non_ivt_frame"}, {"frame_rejected": True, "rx_handler_not_called": True}),
        ("HW-CAN1-008", "CAN1 termination: verify 120ohm present", {"action": "can1_check_termination"}, {"termination_ohm": 120, "bus_quality_ok": True}),
    ]
    for tid, desc, stim, exp in can1_tests:
        tests.append({
            "id": tid, "category": "HW", "test_type": "hw_interface",
            "peripheral": "CAN1_IVT",
            "description": desc, "stimulus": stim, "expected": exp,
            "verifies": [tid], "asil": "D", "priority": "P1",
        })

    # --- CAN2: Vehicle CAN ---
    can2_tests = [
        ("HW-CAN2-001", "CAN2 init: bitrate 500kbps, vehicle CAN configured", {"action": "verify_can2_init"}, {"can2_configured": True, "bitrate": 500000}),
        ("HW-CAN2-002", "CAN2 TX: send BMS status message", {"action": "can2_tx_bms_status"}, {"tx_complete": True}),
        ("HW-CAN2-003", "CAN2 TX: send cell voltage broadcast", {"action": "can2_tx_cell_voltages"}, {"tx_complete": True, "all_cells_encoded": True}),
        ("HW-CAN2-004", "CAN2 TX: send temperature broadcast", {"action": "can2_tx_temperatures"}, {"tx_complete": True}),
        ("HW-CAN2-005", "CAN2 RX: receive vehicle ignition command", {"action": "can2_rx_ignition"}, {"rx_received": True, "command_valid": True}),
        ("HW-CAN2-006", "CAN2 isolation: CAN1 bus-off does not affect CAN2", {"action": "can1_bus_off_check_can2"}, {"can2_operational": True, "can2_error_count": 0}),
        ("HW-CAN2-007", "CAN2 bus-off: inject errors, verify recovery", {"action": "can2_inject_bus_off"}, {"bus_off_detected": True, "recovery_initiated": True}),
        ("HW-CAN2-008", "CAN2 message rate: verify 100ms cycle for status", {"action": "can2_measure_tx_rate"}, {"measured_cycle_ms": 100, "jitter_ms_max": 5}),
    ]
    for tid, desc, stim, exp in can2_tests:
        tests.append({
            "id": tid, "category": "HW", "test_type": "hw_interface",
            "peripheral": "CAN2_VEHICLE",
            "description": desc, "stimulus": stim, "expected": exp,
            "verifies": [tid], "asil": "D", "priority": "P1",
        })

    # --- I2C: PEX (port expander) for contactor feedback ---
    i2c_tests = [
        ("HW-I2C-001", "PEX I2C init: address 0x20, 100kHz", {"action": "verify_i2c_pex_init"}, {"i2c_configured": True, "address": "0x20"}),
        ("HW-I2C-002", "PEX read: string+ contactor feedback pin", {"action": "i2c_read_plus_feedback"}, {"read_ok": True, "pin_state_valid": True}),
        ("HW-I2C-003", "PEX read: string- contactor feedback pin", {"action": "i2c_read_minus_feedback"}, {"read_ok": True, "pin_state_valid": True}),
        ("HW-I2C-004", "PEX read: precharge contactor feedback pin", {"action": "i2c_read_precharge_feedback"}, {"read_ok": True, "pin_state_valid": True}),
        ("HW-I2C-005", "PEX I2C NACK: device not responding", {"action": "i2c_inject_nack"}, {"nack_detected": True, "diag_entry_created": True}),
        ("HW-I2C-006", "PEX I2C recovery: bus stuck low, reset sequence", {"action": "i2c_inject_bus_stuck"}, {"bus_recovery_attempted": True, "bus_recovered": True}),
    ]
    for tid, desc, stim, exp in i2c_tests:
        tests.append({
            "id": tid, "category": "HW", "test_type": "hw_interface",
            "peripheral": "I2C_PEX",
            "description": desc, "stimulus": stim, "expected": exp,
            "verifies": [tid], "asil": "D", "priority": "P1",
        })

    # --- GPIO: Interlock ---
    gpio_tests = [
        ("HW-GPIO-001", "Interlock GPIO: closed state read", {"action": "gpio_interlock_closed"}, {"interlock_state": "CLOSED", "gpio_level": "HIGH"}),
        ("HW-GPIO-002", "Interlock GPIO: open state triggers ERROR", {"action": "gpio_interlock_open"}, {"interlock_state": "OPEN", "bms_state": "ERROR", "contactors_open": True}),
        ("HW-GPIO-003", "Interlock GPIO: bounce rejection (10us glitch)", {"action": "gpio_interlock_glitch_10us"}, {"glitch_rejected": True, "interlock_state": "CLOSED"}),
        ("HW-GPIO-004", "Interlock GPIO: sustained open (>debounce period)", {"action": "gpio_interlock_sustained_open"}, {"interlock_state": "OPEN", "debounce_complete": True}),
    ]
    for tid, desc, stim, exp in gpio_tests:
        tests.append({
            "id": tid, "category": "HW", "test_type": "hw_interface",
            "peripheral": "GPIO_INTERLOCK",
            "description": desc, "stimulus": stim, "expected": exp,
            "verifies": [tid], "asil": "D", "priority": "P1",
        })

    # --- IMD: iso165C insulation monitoring ---
    imd_tests = [
        ("HW-IMD-001", "iso165C CAN init: IMD messages configured", {"action": "verify_imd_can_init"}, {"imd_can_configured": True}),
        ("HW-IMD-002", "iso165C insulation OK: resistance > 500kohm", {"action": "imd_inject_good_insulation"}, {"insulation_ok": True, "resistance_kohm_min": 500}),
        ("HW-IMD-003", "iso165C insulation fault: resistance < 100kohm", {"action": "imd_inject_insulation_fault"}, {"insulation_fault": True, "diag_triggered": True}),
        ("HW-IMD-004", "iso165C warning: resistance 100-500kohm", {"action": "imd_inject_warning_level"}, {"insulation_warning": True, "severity": "MOL"}),
        ("HW-IMD-005", "iso165C CAN timeout: no IMD message for 500ms", {"action": "imd_stop_can_messages"}, {"imd_timeout_detected": True, "diag_triggered": True}),
        ("HW-IMD-006", "iso165C self-test: verify IMD self-test pass", {"action": "imd_trigger_self_test"}, {"self_test_pass": True}),
    ]
    for tid, desc, stim, exp in imd_tests:
        tests.append({
            "id": tid, "category": "HW", "test_type": "hw_interface",
            "peripheral": "IMD_ISO165C",
            "description": desc, "stimulus": stim, "expected": exp,
            "verifies": [tid], "asil": "D", "priority": "P1",
        })

    return tests


# ===========================================================================
# END: Endurance / Soak / Stress
# ===========================================================================

_END_TESTS_RAW = [
    {
        "id": "END-SOAK-001",
        "title": "1-hour soak: no spurious faults",
        "description": (
            "Run BMS in NORMAL state with nominal cell voltages, temperatures, "
            "and currents for 1 hour. Verify zero spurious diagnostic entries."
        ),
        "stimulus": {
            "initial_state": "NORMAL",
            "cell_voltage_mv": 3700,
            "cell_temp_ddegC": 250,
            "pack_current_mA": 500,
            "duration_s": 3600,
        },
        "expected": {
            "spurious_diag_count": 0,
            "bms_state_changes": 0,
            "contactor_state": "CLOSED",
        },
        "duration_s": 3600,
        "priority": "P2",
    },
    {
        "id": "END-SOAK-002",
        "title": "8-hour overnight stability",
        "description": (
            "Run BMS in NORMAL state overnight (8 hours). Verify no memory leaks, "
            "no timer wraparound issues, no spurious faults."
        ),
        "stimulus": {
            "initial_state": "NORMAL",
            "cell_voltage_mv": 3700,
            "cell_temp_ddegC": 250,
            "pack_current_mA": 200,
            "duration_s": 28800,
        },
        "expected": {
            "spurious_diag_count": 0,
            "memory_leak_detected": False,
            "timer_wraparound_handled": True,
        },
        "duration_s": 28800,
        "priority": "P3",
    },
    {
        "id": "END-CYCLE-001",
        "title": "100 power cycles: clean startup each time",
        "description": (
            "Power cycle the vECU 100 times. Each cycle: verify STANDBY entry, "
            "successful PRECHARGE, transition to NORMAL, then clean shutdown."
        ),
        "stimulus": {
            "action": "power_cycle_sequence",
            "cycles": 100,
            "shutdown_wait_ms": 500,
        },
        "expected": {
            "all_cycles_clean": True,
            "failed_startups": 0,
            "failed_precharges": 0,
        },
        "duration_s": 600,
        "priority": "P2",
    },
    {
        "id": "END-CYCLE-002",
        "title": "1000 state transition cycles",
        "description": (
            "Cycle STANDBY -> PRECHARGE -> NORMAL -> ERROR -> STANDBY 1000 times. "
            "Verify no state machine deadlocks or counter overflows."
        ),
        "stimulus": {
            "action": "state_cycle_sequence",
            "cycles": 1000,
            "fault_trigger": {"override": "cell_voltage", "cell": 0, "value_mv": 2800},
            "fault_clear": {"override": "cell_voltage", "cell": 0, "value_mv": 3700},
        },
        "expected": {
            "all_cycles_complete": True,
            "deadlocks": 0,
            "counter_overflows": 0,
        },
        "duration_s": 1800,
        "priority": "P2",
    },
    {
        "id": "END-LOAD-001",
        "title": "CAN bus 80% sustained load",
        "description": (
            "Flood CAN2 with 80% bus load (additional frames) while BMS operates normally. "
            "Verify BMS TX messages maintain timing and no RX frames are lost."
        ),
        "stimulus": {
            "action": "can2_flood_80_percent",
            "duration_s": 300,
            "bms_state": "NORMAL",
        },
        "expected": {
            "bms_tx_timing_maintained": True,
            "bms_tx_jitter_ms_max": 10,
            "rx_frames_lost": 0,
            "can_error_count_max": 5,
        },
        "duration_s": 300,
        "priority": "P2",
    },
    {
        "id": "END-BROWNOUT-001",
        "title": "Supply voltage dip sequence",
        "description": (
            "Inject 10 supply voltage dips (drop to 90% for 50ms each) during NORMAL "
            "operation. Verify BMS handles brownouts gracefully."
        ),
        "stimulus": {
            "action": "supply_voltage_dip_sequence",
            "dips": 10,
            "dip_percent": 90,
            "dip_duration_ms": 50,
            "interval_ms": 2000,
        },
        "expected": {
            "bms_survived_all_dips": True,
            "spurious_resets": 0,
            "data_corruption": False,
        },
        "duration_s": 30,
        "priority": "P2",
    },
    {
        "id": "END-EMC-001",
        "title": "CAN error frame burst",
        "description": (
            "Inject 50 CAN error frames in 100ms burst on CAN1 and CAN2. "
            "Verify BMS error counters increment but bus-off recovery is handled."
        ),
        "stimulus": {
            "action": "can_error_frame_burst",
            "error_frames": 50,
            "burst_duration_ms": 100,
            "buses": ["CAN1", "CAN2"],
        },
        "expected": {
            "error_counters_incremented": True,
            "bus_off_handled": True,
            "recovery_within_ms": 2000,
        },
        "duration_s": 10,
        "priority": "P2",
    },
    {
        "id": "END-DRIFT-001",
        "title": "Slow NTC drift over 30 min",
        "description": (
            "Gradually increase temperature sensor 0 from 250 ddegC (25.0 C) to "
            "550 ddegC (55.0 C) over 30 minutes (~10 ddegC/min). Verify BMS "
            "detects each threshold crossing (MOL at 450, RSL at 500, MSL at 550)."
        ),
        "stimulus": {
            "override": "cell_temperature",
            "sensor": 0,
            "ramp_start_ddegC": 250,
            "ramp_end_ddegC": 550,
            "ramp_duration_s": 1800,
        },
        "expected": {
            "mol_triggered_at_ddegC": 450,
            "rsl_triggered_at_ddegC": 500,
            "msl_triggered_at_ddegC": 550,
            "all_thresholds_detected": True,
            "no_premature_triggers": True,
        },
        "duration_s": 1800,
        "priority": "P2",
    },
]


def _gen_end_tests() -> list[dict]:
    tests = []
    for raw in _END_TESTS_RAW:
        tests.append({
            "id": raw["id"],
            "category": "END",
            "test_type": "endurance",
            "description": raw["description"],
            "stimulus": raw["stimulus"],
            "expected": raw["expected"],
            "duration_s": raw.get("duration_s"),
            "verifies": [raw["id"]],
            "asil": "D",
            "priority": raw.get("priority", "P2"),
        })
    return tests


# ===========================================================================
# Public API
# ===========================================================================

def get_tests() -> list[dict]:
    """Return the complete safety validation test catalog."""
    all_tests = []
    all_tests.extend(_gen_ssr_tests())
    all_tests.extend(_gen_dfa_tests())
    all_tests.extend(_gen_b2b_tests())
    all_tests.extend(_gen_e2e_tests())
    all_tests.extend(_gen_hw_tests())
    all_tests.extend(_gen_end_tests())
    return all_tests


# ===========================================================================
# CLI summary
# ===========================================================================

if __name__ == "__main__":
    tests = get_tests()
    print(f"Safety Validation Test Catalog: {len(tests)} tests total")
    print("=" * 70)

    # Breakdown by category
    by_cat = {}
    for t in tests:
        cat = t["category"]
        by_cat.setdefault(cat, []).append(t)

    cat_order = ["SSR", "DFA", "B2B", "E2E", "HW", "END"]
    for cat in cat_order:
        items = by_cat.get(cat, [])
        print(f"  {cat:6s}: {len(items):4d} tests")

    print()

    # Breakdown by test type
    by_type = {}
    for t in tests:
        tt = t["test_type"]
        by_type.setdefault(tt, []).append(t)

    print("By test type:")
    for tt, items in sorted(by_type.items()):
        print(f"  {tt:25s}: {len(items):4d} tests")

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
    asil_b = sum(1 for t in tests if t.get("asil") == "B")
    print(f"ASIL-D tests: {asil_d}")
    print(f"ASIL-B tests: {asil_b}")

    print()

    # Unique requirement coverage
    all_refs = set()
    for t in tests:
        all_refs.update(t.get("verifies", []))
    print(f"Unique requirements/references verified: {len(all_refs)}")

    # HW peripheral breakdown
    hw_tests = by_cat.get("HW", [])
    by_periph = {}
    for t in hw_tests:
        p = t.get("peripheral", "UNKNOWN")
        by_periph.setdefault(p, []).append(t)

    print()
    print("HW tests by peripheral:")
    for p, items in sorted(by_periph.items()):
        print(f"  {p:20s}: {len(items):4d} tests")

    # Endurance total duration
    end_tests = by_cat.get("END", [])
    total_dur = sum(t.get("duration_s", 0) for t in end_tests)
    print(f"\nEndurance total duration: {total_dur}s ({total_dur / 3600:.1f}h)")
