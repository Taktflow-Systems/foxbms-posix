#!/usr/bin/env python3
"""
foxBMS POSIX vECU — State Machine Verification Test Specification

Comprehensive test catalog for BMS state machine transitions, rejection of
invalid inputs, state persistence, entry/exit actions, timing constraints,
contactor sequencing, startup sequence, and ERROR recovery.

This file defines test specifications as structured data.  A test runner
(not included here) consumes these dicts and executes them against the
running foxbms-vecu + plant_model.py over SocketCAN.

Total: 82 tests across 9 categories.
"""
# @verifies SW-REQ-040
# @verifies SW-REQ-041
# @verifies SW-REQ-042
# @verifies SW-REQ-043
# @verifies SW-REQ-044
# @verifies SW-REQ-045
# @verifies SW-REQ-050
# @verifies SW-REQ-060
# @verifies SW-REQ-070
# @verifies SW-REQ-071
# @verifies SW-REQ-073
# @verifies SW-REQ-074
# @verifies SSR-001
# @verifies SSR-002
# @verifies SSR-005
# @verifies SSR-007
# @verifies SSR-010

# ---------------------------------------------------------------------------
# BMS States (from fi/constants.py)
# ---------------------------------------------------------------------------
BMS_UNINITIALIZED = 0
BMS_INITIALIZATION = 1
BMS_INITIALIZED = 2
BMS_IDLE = 3
BMS_OPEN_CONTACTORS = 4
BMS_STANDBY = 5
BMS_PRECHARGE = 6
BMS_NORMAL = 7
BMS_DISCHARGE = 8
BMS_CHARGE = 9
BMS_ERROR = 10

ALL_STATES = [
    "UNINITIALIZED", "INITIALIZATION", "INITIALIZED", "IDLE",
    "OPEN_CONTACTORS", "STANDBY", "PRECHARGE", "NORMAL",
    "DISCHARGE", "CHARGE", "ERROR",
]

# Reachable steady states (states the BMS can sit in for extended time)
REACHABLE_STEADY_STATES = [
    "STANDBY", "PRECHARGE", "NORMAL", "CHARGE", "DISCHARGE", "ERROR",
]

# CAN IDs
CAN_STATE_REQUEST = 0x210
CAN_OVERRIDE = 0x7E0
CAN_PROBE_STATE = 0x7F9
CAN_PROBE_SPS = 0x7F0

# SIL override commands
SIL_CELL_VOLTAGE = 0x01
SIL_CELL_TEMP = 0x02
SIL_PACK_CURRENT = 0x03
SIL_CONTACTOR_FB = 0x05
SIL_INTERLOCK = 0x06
SIL_DIAG_FORCE = 0x08
SIL_DIAG_CLEAR = 0x09
SIL_CLEAR_ALL = 0xFF

# ---------------------------------------------------------------------------
# Category 1: SM-TRANS — Valid transitions (7 tests)
# ---------------------------------------------------------------------------
VALID_TRANSITION_TESTS = [
    {
        "id": "SM-TRANS-001",
        "category": "SM",
        "test_type": "valid_transition",
        "from_state": "STANDBY",
        "to_state": "PRECHARGE",
        "trigger": "CAN request 0x210 with CLOSE command",
        "description": (
            "From STANDBY, send CAN state request (0x210) to close contactors. "
            "BMS shall transition to PRECHARGE within 500 ms."
        ),
        "precondition": "System in STANDBY after startup; no faults active.",
        "stimulus": {"can_id": CAN_STATE_REQUEST, "command": "CLOSE"},
        "expected": {
            "new_state": BMS_PRECHARGE,
            "max_transition_ms": 500,
        },
        "verifies": ["SW-REQ-040", "SW-REQ-041"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-TRANS-002",
        "category": "SM",
        "test_type": "valid_transition",
        "from_state": "PRECHARGE",
        "to_state": "NORMAL",
        "trigger": "Voltage match: V_pack within 90% of V_dc_link",
        "description": (
            "During PRECHARGE, when pack voltage reaches within 90 %% of DC "
            "link voltage and precharge timeout has not expired, BMS shall "
            "transition to NORMAL."
        ),
        "precondition": (
            "System in PRECHARGE; STR- closed, PRE closed; "
            "plant model drives V_dc_link toward V_pack."
        ),
        "stimulus": {"condition": "V_pack >= 0.9 * V_dc_link"},
        "expected": {
            "new_state": BMS_NORMAL,
            "max_transition_ms": 200,
        },
        "verifies": ["SW-REQ-042", "SW-REQ-043"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-TRANS-003",
        "category": "SM",
        "test_type": "valid_transition",
        "from_state": "PRECHARGE",
        "to_state": "ERROR",
        "trigger": "Precharge timeout expired (>2000 ms without voltage match)",
        "description": (
            "If PRECHARGE does not achieve voltage match within the "
            "precharge timeout (2000 ms), BMS shall transition to ERROR."
        ),
        "precondition": (
            "System in PRECHARGE; plant model holds V_dc_link at 0 V "
            "(simulating open precharge relay)."
        ),
        "stimulus": {"condition": "precharge_timeout_expired"},
        "expected": {
            "new_state": BMS_ERROR,
            "max_transition_ms": 2500,
        },
        "verifies": ["SW-REQ-044", "SSR-001"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-TRANS-004",
        "category": "SM",
        "test_type": "valid_transition",
        "from_state": "PRECHARGE",
        "to_state": "ERROR",
        "trigger": "DIAG FATAL fault raised during precharge",
        "description": (
            "If a DIAG FATAL flag is raised while in PRECHARGE (e.g., cell "
            "overvoltage MSL), BMS shall transition to ERROR immediately."
        ),
        "precondition": "System in PRECHARGE; precharge ongoing.",
        "stimulus": {
            "override": SIL_DIAG_FORCE,
            "diag_id": 18,
            "description": "Force DIAG_ID_CELLVOLTAGE_OVERVOLTAGE MSL",
        },
        "expected": {
            "new_state": BMS_ERROR,
            "max_transition_ms": 1000,
        },
        "verifies": ["SW-REQ-044", "SSR-002"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-TRANS-005",
        "category": "SM",
        "test_type": "valid_transition",
        "from_state": "NORMAL",
        "to_state": "ERROR",
        "trigger": "DIAG FATAL flag from any DIAG module",
        "description": (
            "In NORMAL operation, if DIAG raises a FATAL flag, BMS shall "
            "transition to ERROR and open all contactors."
        ),
        "precondition": "System in NORMAL; contactors closed; load active.",
        "stimulus": {
            "override": SIL_CELL_VOLTAGE,
            "value_mv": 2900,
            "cell": 0,
            "description": "Inject cell overvoltage on cell 0",
        },
        "expected": {
            "new_state": BMS_ERROR,
            "max_transition_ms": 1000,
            "contactors": "ALL_OPEN",
        },
        "verifies": ["SW-REQ-045", "SSR-001", "SSR-005"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-TRANS-006",
        "category": "SM",
        "test_type": "valid_transition",
        "from_state": "ERROR",
        "to_state": "STANDBY",
        "trigger": "Dual condition: fault clear AND CAN request 0x210 OPEN",
        "description": (
            "From ERROR, BMS shall return to STANDBY only when BOTH "
            "conditions are met: (1) all DIAG faults cleared, and "
            "(2) an explicit CAN request (0x210 OPEN) is received."
        ),
        "precondition": (
            "System in ERROR due to prior fault; fault root cause removed."
        ),
        "stimulus": {
            "step1": {"override": SIL_DIAG_CLEAR, "description": "Clear all DIAG faults"},
            "step2": {"can_id": CAN_STATE_REQUEST, "command": "OPEN"},
        },
        "expected": {
            "new_state": BMS_STANDBY,
            "max_transition_ms": 1000,
        },
        "verifies": ["SW-REQ-050", "SSR-007"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-TRANS-007",
        "category": "SM",
        "test_type": "valid_transition",
        "from_state": "UNINITIALIZED",
        "to_state": "STANDBY",
        "trigger": "Power-on automatic startup sequence",
        "description": (
            "On power-on, BMS shall automatically transition through "
            "UNINITIALIZED -> INITIALIZATION -> INITIALIZED -> IDLE -> "
            "OPEN_CONTACTORS -> STANDBY without external stimulus."
        ),
        "precondition": "Fresh system start; no prior state.",
        "stimulus": {"condition": "power_on"},
        "expected": {
            "new_state": BMS_STANDBY,
            "max_transition_ms": 30000,
            "intermediate_states": [
                BMS_INITIALIZATION, BMS_INITIALIZED,
                BMS_IDLE, BMS_OPEN_CONTACTORS,
            ],
        },
        "verifies": ["SW-REQ-040", "SW-REQ-060"],
        "asil": "D",
        "priority": "P1",
    },
]

# ---------------------------------------------------------------------------
# Category 2: SM-REJECT — Invalid transition rejection (21 tests)
#
# For each reachable state, attempt every input that should NOT cause a
# transition.  The BMS must remain in the current state.
# ---------------------------------------------------------------------------
_REJECT_BASE = {
    "category": "SM",
    "test_type": "invalid_transition_rejection",
    "asil": "D",
    "priority": "P1",
}

INVALID_TRANSITION_TESTS = [
    # -- STANDBY: only valid exit is PRECHARGE via CAN CLOSE --
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-001",
        "from_state": "STANDBY",
        "invalid_input": "CAN OPEN request (0x210)",
        "description": "In STANDBY, CAN OPEN request shall be ignored; BMS stays in STANDBY.",
        "expected_state": BMS_STANDBY,
        "verifies": ["SW-REQ-040"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-002",
        "from_state": "STANDBY",
        "invalid_input": "Random CAN frame on 0x210 with invalid command byte",
        "description": "In STANDBY, malformed CAN request shall be ignored.",
        "expected_state": BMS_STANDBY,
        "verifies": ["SW-REQ-040"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-003",
        "from_state": "STANDBY",
        "invalid_input": "DIAG clear command (no fault active)",
        "description": "In STANDBY, DIAG clear with no faults shall not change state.",
        "expected_state": BMS_STANDBY,
        "verifies": ["SW-REQ-040"],
    },
    # -- PRECHARGE: only valid exits are NORMAL (voltage match) or ERROR --
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-004",
        "from_state": "PRECHARGE",
        "invalid_input": "CAN CLOSE request (0x210)",
        "description": "In PRECHARGE, duplicate CLOSE request shall be ignored.",
        "expected_state": BMS_PRECHARGE,
        "verifies": ["SW-REQ-042"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-005",
        "from_state": "PRECHARGE",
        "invalid_input": "CAN OPEN request (0x210)",
        "description": "In PRECHARGE, OPEN request shall be rejected (must complete or ERROR).",
        "expected_state": BMS_PRECHARGE,
        "verifies": ["SW-REQ-042"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-006",
        "from_state": "PRECHARGE",
        "invalid_input": "DIAG clear command",
        "description": "In PRECHARGE, DIAG clear shall not alter state machine progression.",
        "expected_state": BMS_PRECHARGE,
        "verifies": ["SW-REQ-042"],
    },
    # -- NORMAL: only valid exit is ERROR (FATAL fault) --
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-007",
        "from_state": "NORMAL",
        "invalid_input": "CAN CLOSE request (0x210)",
        "description": "In NORMAL, CLOSE request shall be ignored (already closed).",
        "expected_state": BMS_NORMAL,
        "verifies": ["SW-REQ-045"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-008",
        "from_state": "NORMAL",
        "invalid_input": "CAN OPEN request (0x210) without fault",
        "description": "In NORMAL, OPEN request without fault shall be rejected.",
        "expected_state": BMS_NORMAL,
        "verifies": ["SW-REQ-045"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-009",
        "from_state": "NORMAL",
        "invalid_input": "RSL-only DIAG flag (non-FATAL warning)",
        "description": "In NORMAL, RSL warning shall not trigger ERROR transition.",
        "expected_state": BMS_NORMAL,
        "verifies": ["SW-REQ-045", "SSR-002"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-010",
        "from_state": "NORMAL",
        "invalid_input": "MOL-only DIAG flag (informational)",
        "description": "In NORMAL, MOL informational flag shall not trigger ERROR.",
        "expected_state": BMS_NORMAL,
        "verifies": ["SW-REQ-045"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-011",
        "from_state": "NORMAL",
        "invalid_input": "DIAG clear command",
        "description": "In NORMAL, DIAG clear with no active faults is a no-op.",
        "expected_state": BMS_NORMAL,
        "verifies": ["SW-REQ-045"],
    },
    # -- ERROR: only valid exit is STANDBY (dual condition) --
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-012",
        "from_state": "ERROR",
        "invalid_input": "CAN CLOSE request (0x210)",
        "description": "In ERROR, CLOSE request shall be rejected.",
        "expected_state": BMS_ERROR,
        "verifies": ["SW-REQ-050", "SSR-007"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-013",
        "from_state": "ERROR",
        "invalid_input": "CAN OPEN request without clearing faults first",
        "description": "In ERROR, OPEN request alone (fault still active) shall not exit ERROR.",
        "expected_state": BMS_ERROR,
        "verifies": ["SW-REQ-050", "SSR-007"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-014",
        "from_state": "ERROR",
        "invalid_input": "DIAG clear alone (no CAN OPEN request)",
        "description": "In ERROR, clearing faults alone without CAN request shall not exit ERROR.",
        "expected_state": BMS_ERROR,
        "verifies": ["SW-REQ-050", "SSR-007"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-015",
        "from_state": "ERROR",
        "invalid_input": "Repeated DIAG FATAL (already in ERROR)",
        "description": "In ERROR, additional DIAG FATAL shall not cause further transition.",
        "expected_state": BMS_ERROR,
        "verifies": ["SW-REQ-050"],
    },
    # -- CHARGE: only valid exit is ERROR (FATAL) --
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-016",
        "from_state": "CHARGE",
        "invalid_input": "CAN CLOSE request",
        "description": "In CHARGE, CLOSE request shall be ignored.",
        "expected_state": BMS_CHARGE,
        "verifies": ["SW-REQ-045"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-017",
        "from_state": "CHARGE",
        "invalid_input": "CAN OPEN request without fault",
        "description": "In CHARGE, OPEN request without fault shall be rejected.",
        "expected_state": BMS_CHARGE,
        "verifies": ["SW-REQ-045"],
    },
    # -- DISCHARGE: only valid exit is ERROR (FATAL) --
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-018",
        "from_state": "DISCHARGE",
        "invalid_input": "CAN CLOSE request",
        "description": "In DISCHARGE, CLOSE request shall be ignored.",
        "expected_state": BMS_DISCHARGE,
        "verifies": ["SW-REQ-045"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-019",
        "from_state": "DISCHARGE",
        "invalid_input": "CAN OPEN request without fault",
        "description": "In DISCHARGE, OPEN request without fault shall be rejected.",
        "expected_state": BMS_DISCHARGE,
        "verifies": ["SW-REQ-045"],
    },
    # -- Startup transient states: external input shall not interfere --
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-020",
        "from_state": "INITIALIZATION",
        "invalid_input": "CAN CLOSE request during initialization",
        "description": "During INITIALIZATION, CAN requests shall be ignored.",
        "expected_state": BMS_INITIALIZATION,
        "verifies": ["SW-REQ-060"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-021",
        "from_state": "IDLE",
        "invalid_input": "CAN CLOSE request during IDLE",
        "description": "During IDLE, CAN requests shall be ignored; auto-progression continues.",
        "expected_state": BMS_IDLE,
        "verifies": ["SW-REQ-060"],
    },
    # -- Additional rejection: fault-based transitions that should NOT happen --
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-022",
        "from_state": "STANDBY",
        "invalid_input": "DIAG FATAL flag (no contactors closed)",
        "description": (
            "In STANDBY with no contactors closed, a DIAG FATAL shall "
            "transition to ERROR (this IS valid). But an RSL-only flag "
            "shall NOT cause transition."
        ),
        "stimulus": {"override": SIL_DIAG_FORCE, "tier": "RSL"},
        "expected_state": BMS_STANDBY,
        "verifies": ["SW-REQ-040", "SSR-002"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-023",
        "from_state": "NORMAL",
        "invalid_input": "Voltage fluctuation within normal range",
        "description": (
            "In NORMAL, cell voltage fluctuation within operating range "
            "(1800-2800 mV) shall not trigger any state change."
        ),
        "stimulus": {"override": SIL_CELL_VOLTAGE, "value_mv": 1900},
        "expected_state": BMS_NORMAL,
        "verifies": ["SW-REQ-045"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-024",
        "from_state": "NORMAL",
        "invalid_input": "Temperature fluctuation within normal range",
        "description": (
            "In NORMAL, temperature fluctuation within operating range "
            "shall not trigger any state change."
        ),
        "stimulus": {"override": SIL_CELL_TEMP, "value_ddegC": 350},
        "expected_state": BMS_NORMAL,
        "verifies": ["SW-REQ-045"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-025",
        "from_state": "ERROR",
        "invalid_input": "CAN CLOSE request in ERROR state",
        "description": "In ERROR, attempting to close contactors via CAN CLOSE shall be rejected.",
        "expected_state": BMS_ERROR,
        "verifies": ["SW-REQ-050", "SSR-007"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-026",
        "from_state": "CHARGE",
        "invalid_input": "RSL DIAG flag during charging",
        "description": "In CHARGE, RSL warning shall not cause state transition.",
        "stimulus": {"override": SIL_DIAG_FORCE, "tier": "RSL"},
        "expected_state": BMS_CHARGE,
        "verifies": ["SW-REQ-045"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-027",
        "from_state": "DISCHARGE",
        "invalid_input": "RSL DIAG flag during discharging",
        "description": "In DISCHARGE, RSL warning shall not cause state transition.",
        "stimulus": {"override": SIL_DIAG_FORCE, "tier": "RSL"},
        "expected_state": BMS_DISCHARGE,
        "verifies": ["SW-REQ-045"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-028",
        "from_state": "PRECHARGE",
        "invalid_input": "Normal voltage reading during precharge",
        "description": (
            "In PRECHARGE, normal cell voltages (not matching DC link yet) "
            "shall not prematurely advance to NORMAL."
        ),
        "stimulus": {"override": SIL_CELL_VOLTAGE, "value_mv": 2000},
        "expected_state": BMS_PRECHARGE,
        "verifies": ["SW-REQ-042"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-029",
        "from_state": "STANDBY",
        "invalid_input": "SIL clear all override (0xFF)",
        "description": "In STANDBY, SIL CLEAR_ALL override shall not change BMS state.",
        "stimulus": {"override": SIL_CLEAR_ALL},
        "expected_state": BMS_STANDBY,
        "verifies": ["SW-REQ-040"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-030",
        "from_state": "OPEN_CONTACTORS",
        "invalid_input": "CAN CLOSE request during OPEN_CONTACTORS phase",
        "description": "During OPEN_CONTACTORS startup phase, CAN requests shall be ignored.",
        "expected_state": BMS_OPEN_CONTACTORS,
        "verifies": ["SW-REQ-060"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-031",
        "from_state": "NORMAL",
        "invalid_input": "Current spike within operating limits",
        "description": (
            "In NORMAL, a current spike within the cell overcurrent threshold "
            "shall not trigger ERROR."
        ),
        "stimulus": {"override": SIL_PACK_CURRENT, "value_mA": 90000},
        "expected_state": BMS_NORMAL,
        "verifies": ["SW-REQ-045"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-032",
        "from_state": "ERROR",
        "invalid_input": "SIL voltage override while in ERROR",
        "description": "In ERROR, SIL voltage overrides shall not change state.",
        "stimulus": {"override": SIL_CELL_VOLTAGE, "value_mv": 2000},
        "expected_state": BMS_ERROR,
        "verifies": ["SW-REQ-050"],
    },
    {
        **_REJECT_BASE,
        "id": "SM-REJECT-033",
        "from_state": "ERROR",
        "invalid_input": "Multiple simultaneous DIAG clears without CAN request",
        "description": (
            "In ERROR, clearing multiple DIAG IDs individually (without "
            "SIL_CLEAR_ALL) and without CAN OPEN shall not exit ERROR."
        ),
        "expected_state": BMS_ERROR,
        "verifies": ["SW-REQ-050", "SSR-007"],
    },
]

# ---------------------------------------------------------------------------
# Category 3: SM-PERSIST — State persistence / soak tests (6 tests)
# ---------------------------------------------------------------------------
STATE_PERSISTENCE_TESTS = [
    {
        "id": f"SM-PERSIST-{i:03d}",
        "category": "SM",
        "test_type": "state_persistence",
        "state": state,
        "soak_duration_s": 60,
        "description": (
            f"Hold BMS in {state} for 60 seconds with no external stimulus. "
            f"Verify state does not change (probe 0x7F9 every 1 s)."
        ),
        "precondition": f"System brought to {state} via normal path.",
        "expected": {
            "state_unchanged": True,
            "sample_count": 60,
            "allowed_deviation": 0,
        },
        "verifies": ["SW-REQ-040"],
        "asil": "D",
        "priority": "P2",
    }
    for i, state in enumerate(REACHABLE_STEADY_STATES, start=1)
]

# ---------------------------------------------------------------------------
# Category 4: SM-ENTRY — Entry actions (6 tests)
# ---------------------------------------------------------------------------
ENTRY_ACTION_TESTS = [
    {
        "id": "SM-ENTRY-001",
        "category": "SM",
        "test_type": "entry_action",
        "state": "STANDBY",
        "description": (
            "On entering STANDBY, all contactors shall be OPEN. "
            "Verify SPS probe (0x7F0) shows STR+=OPEN, STR-=OPEN, PRE=OPEN."
        ),
        "expected_contactors": {"STR_PLUS": "OPEN", "STR_MINUS": "OPEN", "PRE": "OPEN"},
        "verifies": ["SW-REQ-070", "SSR-005"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-ENTRY-002",
        "category": "SM",
        "test_type": "entry_action",
        "state": "PRECHARGE",
        "description": (
            "On entering PRECHARGE, contactor sequence shall begin: "
            "STR- closes first, then PRE closes."
        ),
        "expected_contactors": {"STR_MINUS": "CLOSED", "PRE": "CLOSED", "STR_PLUS": "OPEN"},
        "verifies": ["SW-REQ-071", "SW-REQ-073"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-ENTRY-003",
        "category": "SM",
        "test_type": "entry_action",
        "state": "NORMAL",
        "description": (
            "On entering NORMAL, STR+ closes and PRE opens. "
            "Final state: STR+=CLOSED, STR-=CLOSED, PRE=OPEN."
        ),
        "expected_contactors": {"STR_PLUS": "CLOSED", "STR_MINUS": "CLOSED", "PRE": "OPEN"},
        "verifies": ["SW-REQ-074"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-ENTRY-004",
        "category": "SM",
        "test_type": "entry_action",
        "state": "ERROR",
        "description": (
            "On entering ERROR, all contactors shall be commanded OPEN "
            "immediately (safe state)."
        ),
        "expected_contactors": {"STR_PLUS": "OPEN", "STR_MINUS": "OPEN", "PRE": "OPEN"},
        "verifies": ["SW-REQ-045", "SSR-001", "SSR-005"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-ENTRY-005",
        "category": "SM",
        "test_type": "entry_action",
        "state": "CHARGE",
        "description": (
            "On entering CHARGE, contactors remain closed from NORMAL. "
            "STR+=CLOSED, STR-=CLOSED, PRE=OPEN."
        ),
        "expected_contactors": {"STR_PLUS": "CLOSED", "STR_MINUS": "CLOSED", "PRE": "OPEN"},
        "verifies": ["SW-REQ-074"],
        "asil": "D",
        "priority": "P2",
    },
    {
        "id": "SM-ENTRY-006",
        "category": "SM",
        "test_type": "entry_action",
        "state": "DISCHARGE",
        "description": (
            "On entering DISCHARGE, contactors remain closed from NORMAL. "
            "STR+=CLOSED, STR-=CLOSED, PRE=OPEN."
        ),
        "expected_contactors": {"STR_PLUS": "CLOSED", "STR_MINUS": "CLOSED", "PRE": "OPEN"},
        "verifies": ["SW-REQ-074"],
        "asil": "D",
        "priority": "P2",
    },
]

# ---------------------------------------------------------------------------
# Category 5: SM-EXIT — Exit actions (6 tests)
# ---------------------------------------------------------------------------
EXIT_ACTION_TESTS = [
    {
        "id": "SM-EXIT-001",
        "category": "SM",
        "test_type": "exit_action",
        "from_state": "STANDBY",
        "to_state": "PRECHARGE",
        "description": (
            "On exiting STANDBY, verify CAN state message (0x220) updates "
            "within one BMS cycle (10 ms) to reflect new state."
        ),
        "expected": {"state_msg_updated_within_ms": 10},
        "verifies": ["SW-REQ-040"],
        "asil": "D",
        "priority": "P2",
    },
    {
        "id": "SM-EXIT-002",
        "category": "SM",
        "test_type": "exit_action",
        "from_state": "PRECHARGE",
        "to_state": "NORMAL",
        "description": (
            "On exiting PRECHARGE to NORMAL, precharge timer is stopped and "
            "PRE contactor is opened before STR+ closes."
        ),
        "expected": {"pre_open_before_str_plus_close": True},
        "verifies": ["SW-REQ-073", "SW-REQ-074"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-EXIT-003",
        "category": "SM",
        "test_type": "exit_action",
        "from_state": "PRECHARGE",
        "to_state": "ERROR",
        "description": (
            "On exiting PRECHARGE to ERROR, all contactors are opened and "
            "precharge timer is cancelled."
        ),
        "expected": {"all_contactors_open": True},
        "verifies": ["SW-REQ-044", "SSR-001"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-EXIT-004",
        "category": "SM",
        "test_type": "exit_action",
        "from_state": "NORMAL",
        "to_state": "ERROR",
        "description": (
            "On exiting NORMAL to ERROR, all contactors shall be commanded "
            "OPEN within the FTTI budget."
        ),
        "expected": {"all_contactors_open_within_ms": 100},
        "verifies": ["SW-REQ-045", "SSR-001"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-EXIT-005",
        "category": "SM",
        "test_type": "exit_action",
        "from_state": "ERROR",
        "to_state": "STANDBY",
        "description": (
            "On exiting ERROR to STANDBY, DIAG counters and flags are "
            "confirmed clear; no latent faults remain."
        ),
        "expected": {"diag_bitmap_zero": True},
        "verifies": ["SW-REQ-050", "SSR-007"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-EXIT-006",
        "category": "SM",
        "test_type": "exit_action",
        "from_state": "CHARGE",
        "to_state": "ERROR",
        "description": (
            "On exiting CHARGE to ERROR, all contactors opened and charge "
            "current drops to 0 A within 200 ms."
        ),
        "expected": {"all_contactors_open": True, "current_zero_within_ms": 200},
        "verifies": ["SW-REQ-045", "SSR-001"],
        "asil": "D",
        "priority": "P1",
    },
]

# ---------------------------------------------------------------------------
# Category 6: SM-TIME — Transition timing (7 tests)
# ---------------------------------------------------------------------------
TRANSITION_TIMING_TESTS = [
    {
        "id": "SM-TIME-001",
        "category": "SM",
        "test_type": "transition_timing",
        "transition": "STANDBY -> PRECHARGE",
        "description": (
            "Measure time from CAN CLOSE request (0x210) to BMS state "
            "probe (0x7F9) showing PRECHARGE. Max 500 ms."
        ),
        "max_time_ms": 500,
        "verifies": ["SW-REQ-041"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-TIME-002",
        "category": "SM",
        "test_type": "transition_timing",
        "transition": "PRECHARGE -> NORMAL",
        "description": (
            "Measure time from voltage match condition to BMS state showing "
            "NORMAL. Max 200 ms."
        ),
        "max_time_ms": 200,
        "verifies": ["SW-REQ-043"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-TIME-003",
        "category": "SM",
        "test_type": "transition_timing",
        "transition": "PRECHARGE -> ERROR (timeout)",
        "description": (
            "Measure precharge timeout duration. BMS shall enter ERROR "
            "within 2000 ms + 500 ms margin = 2500 ms."
        ),
        "max_time_ms": 2500,
        "verifies": ["SW-REQ-044"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-TIME-004",
        "category": "SM",
        "test_type": "transition_timing",
        "transition": "NORMAL -> ERROR (FATAL)",
        "description": (
            "Measure time from DIAG FATAL assertion to BMS entering ERROR. "
            "Max 100 ms (within FTTI)."
        ),
        "max_time_ms": 100,
        "verifies": ["SW-REQ-045", "SSR-001"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-TIME-005",
        "category": "SM",
        "test_type": "transition_timing",
        "transition": "ERROR -> STANDBY",
        "description": (
            "Measure time from dual-condition met (fault clear + CAN OPEN) "
            "to BMS showing STANDBY. Max 1000 ms."
        ),
        "max_time_ms": 1000,
        "verifies": ["SW-REQ-050"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-TIME-006",
        "category": "SM",
        "test_type": "transition_timing",
        "transition": "Power-on -> STANDBY (full startup)",
        "description": (
            "Measure total startup time from power-on to STANDBY. "
            "Max 30 s (includes self-test and initialization)."
        ),
        "max_time_ms": 30000,
        "verifies": ["SW-REQ-060"],
        "asil": "D",
        "priority": "P2",
    },
    {
        "id": "SM-TIME-007",
        "category": "SM",
        "test_type": "transition_timing",
        "transition": "NORMAL -> ERROR (contactor open latency)",
        "description": (
            "Measure time from ERROR entry to all contactors confirmed OPEN "
            "via SPS probe (0x7F0). Max 50 ms."
        ),
        "max_time_ms": 50,
        "verifies": ["SW-REQ-045", "SSR-005"],
        "asil": "D",
        "priority": "P1",
    },
]

# ---------------------------------------------------------------------------
# Category 7: SM-CSEQ — Contactor sequence tests (9 tests)
# ---------------------------------------------------------------------------
CONTACTOR_SEQUENCE_TESTS = [
    {
        "id": "SM-CSEQ-001",
        "category": "SM",
        "test_type": "contactor_sequence",
        "description": (
            "Precharge sequence step 1: STR- closes first. Verify via SPS "
            "probe that STR- transitions to CLOSED before any other contactor."
        ),
        "sequence_step": 1,
        "expected": {"STR_MINUS": "CLOSED", "STR_PLUS": "OPEN", "PRE": "OPEN"},
        "verifies": ["SW-REQ-071"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-CSEQ-002",
        "category": "SM",
        "test_type": "contactor_sequence",
        "description": (
            "Precharge sequence step 2: PRE closes after STR-. "
            "Verify PRE transitions to CLOSED while STR- remains CLOSED."
        ),
        "sequence_step": 2,
        "expected": {"STR_MINUS": "CLOSED", "STR_PLUS": "OPEN", "PRE": "CLOSED"},
        "verifies": ["SW-REQ-071", "SW-REQ-073"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-CSEQ-003",
        "category": "SM",
        "test_type": "contactor_sequence",
        "description": (
            "Precharge sequence step 3: wait for V_pack approx V_dc_link. "
            "Verify voltage convergence within precharge timeout."
        ),
        "sequence_step": 3,
        "expected": {"voltage_match": True, "max_time_ms": 2000},
        "verifies": ["SW-REQ-042"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-CSEQ-004",
        "category": "SM",
        "test_type": "contactor_sequence",
        "description": (
            "Precharge sequence step 4: STR+ closes after voltage match. "
            "Verify STR+ goes CLOSED."
        ),
        "sequence_step": 4,
        "expected": {"STR_MINUS": "CLOSED", "STR_PLUS": "CLOSED", "PRE": "CLOSED"},
        "verifies": ["SW-REQ-074"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-CSEQ-005",
        "category": "SM",
        "test_type": "contactor_sequence",
        "description": (
            "Precharge sequence step 5: PRE opens after STR+ closes. "
            "Final state: STR+=CLOSED, STR-=CLOSED, PRE=OPEN."
        ),
        "sequence_step": 5,
        "expected": {"STR_MINUS": "CLOSED", "STR_PLUS": "CLOSED", "PRE": "OPEN"},
        "verifies": ["SW-REQ-074"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-CSEQ-006",
        "category": "SM",
        "test_type": "contactor_sequence",
        "description": (
            "Contactor sequence ordering: STR- must close BEFORE PRE. "
            "Timestamp ordering from SPS probe stream."
        ),
        "expected": {"order": ["STR_MINUS_CLOSE", "PRE_CLOSE"]},
        "verifies": ["SW-REQ-071"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-CSEQ-007",
        "category": "SM",
        "test_type": "contactor_sequence",
        "description": (
            "Contactor sequence ordering: STR+ must close AFTER voltage match "
            "and BEFORE PRE opens."
        ),
        "expected": {"order": ["VOLTAGE_MATCH", "STR_PLUS_CLOSE", "PRE_OPEN"]},
        "verifies": ["SW-REQ-074"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-CSEQ-008",
        "category": "SM",
        "test_type": "contactor_sequence",
        "description": (
            "Precharge failure: if contactor feedback for STR- does not "
            "confirm CLOSED within 200 ms, BMS shall abort to ERROR."
        ),
        "stimulus": {
            "override": SIL_CONTACTOR_FB,
            "contactor": "STR_MINUS",
            "feedback": "OPEN",
            "description": "Force STR- feedback to OPEN (stuck open fault)",
        },
        "expected": {"bms_state": BMS_ERROR, "max_time_ms": 500},
        "verifies": ["SW-REQ-071", "SSR-001"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-CSEQ-009",
        "category": "SM",
        "test_type": "contactor_sequence",
        "description": (
            "Precharge failure: if precharge relay feedback does not confirm "
            "CLOSED, BMS shall abort to ERROR and open all contactors."
        ),
        "stimulus": {
            "override": SIL_CONTACTOR_FB,
            "contactor": "PRE",
            "feedback": "OPEN",
            "description": "Force PRE feedback to OPEN (stuck open fault)",
        },
        "expected": {"bms_state": BMS_ERROR, "all_contactors_open": True},
        "verifies": ["SW-REQ-073", "SSR-001"],
        "asil": "D",
        "priority": "P1",
    },
]

# ---------------------------------------------------------------------------
# Category 8: SM-STARTUP — Startup sequence tests (3 tests)
# ---------------------------------------------------------------------------
STARTUP_SEQUENCE_TESTS = [
    {
        "id": "SM-STARTUP-001",
        "category": "SM",
        "test_type": "startup_sequence",
        "description": (
            "Cold start: verify BMS transitions through all startup states "
            "in correct order. Record timestamps for each transition from "
            "probe 0x7F9."
        ),
        "expected_sequence": [
            BMS_UNINITIALIZED, BMS_INITIALIZATION, BMS_INITIALIZED,
            BMS_IDLE, BMS_OPEN_CONTACTORS, BMS_STANDBY,
        ],
        "max_total_time_ms": 30000,
        "verifies": ["SW-REQ-060"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-STARTUP-002",
        "category": "SM",
        "test_type": "startup_sequence",
        "description": (
            "Startup with interlock OPEN: if interlock is not closed during "
            "startup, BMS shall halt at OPEN_CONTACTORS or transition to ERROR."
        ),
        "stimulus": {
            "override": SIL_INTERLOCK,
            "state": "OPEN",
            "description": "Force interlock feedback OPEN during startup",
        },
        "expected": {
            "bms_state_in": [BMS_OPEN_CONTACTORS, BMS_ERROR],
            "shall_not_reach": BMS_STANDBY,
        },
        "verifies": ["SW-REQ-060", "SSR-010"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-STARTUP-003",
        "category": "SM",
        "test_type": "startup_sequence",
        "description": (
            "Rapid restart: terminate vECU and restart within 1 s. "
            "Verify full startup sequence completes normally without "
            "stale state from previous run."
        ),
        "expected": {
            "final_state": BMS_STANDBY,
            "no_stale_faults": True,
        },
        "verifies": ["SW-REQ-060"],
        "asil": "D",
        "priority": "P2",
    },
]

# ---------------------------------------------------------------------------
# Category 9: SM-RECOVERY — ERROR exit / recovery tests (5 tests)
# ---------------------------------------------------------------------------
ERROR_RECOVERY_TESTS = [
    {
        "id": "SM-RECOVERY-001",
        "category": "SM",
        "test_type": "error_recovery",
        "description": (
            "Dual condition recovery: clear all DIAG faults via 0x7E0 "
            "(SIL_DIAG_CLEAR), then send CAN OPEN (0x210). BMS shall "
            "transition from ERROR to STANDBY."
        ),
        "stimulus_sequence": [
            {"action": "clear_diag", "override": SIL_DIAG_CLEAR},
            {"action": "can_request", "can_id": CAN_STATE_REQUEST, "command": "OPEN"},
        ],
        "expected": {"new_state": BMS_STANDBY, "max_time_ms": 1000},
        "verifies": ["SW-REQ-050", "SSR-007"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-RECOVERY-002",
        "category": "SM",
        "test_type": "error_recovery",
        "description": (
            "Single condition rejection (CAN only): send CAN OPEN while "
            "faults are still active. BMS shall remain in ERROR."
        ),
        "stimulus": {"can_id": CAN_STATE_REQUEST, "command": "OPEN"},
        "precondition": "DIAG fault still active (not cleared).",
        "expected": {"state_unchanged": BMS_ERROR},
        "verifies": ["SW-REQ-050", "SSR-007"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-RECOVERY-003",
        "category": "SM",
        "test_type": "error_recovery",
        "description": (
            "Single condition rejection (DIAG clear only): clear faults "
            "but do NOT send CAN request. BMS shall remain in ERROR."
        ),
        "stimulus": {"override": SIL_DIAG_CLEAR},
        "precondition": "No CAN OPEN request sent.",
        "expected": {"state_unchanged": BMS_ERROR},
        "verifies": ["SW-REQ-050", "SSR-007"],
        "asil": "D",
        "priority": "P1",
    },
    {
        "id": "SM-RECOVERY-004",
        "category": "SM",
        "test_type": "error_recovery",
        "description": (
            "Recovery order: send CAN OPEN first, then clear faults. "
            "Verify BMS still recovers to STANDBY (order-independent)."
        ),
        "stimulus_sequence": [
            {"action": "can_request", "can_id": CAN_STATE_REQUEST, "command": "OPEN"},
            {"action": "clear_diag", "override": SIL_DIAG_CLEAR},
        ],
        "expected": {"new_state": BMS_STANDBY, "max_time_ms": 2000},
        "verifies": ["SW-REQ-050"],
        "asil": "D",
        "priority": "P2",
    },
    {
        "id": "SM-RECOVERY-005",
        "category": "SM",
        "test_type": "error_recovery",
        "description": (
            "Re-fault during recovery: clear faults, then inject a new "
            "fault BEFORE sending CAN OPEN. BMS shall remain in ERROR "
            "(new fault re-latches)."
        ),
        "stimulus_sequence": [
            {"action": "clear_diag", "override": SIL_DIAG_CLEAR},
            {"action": "inject_fault", "override": SIL_CELL_VOLTAGE, "value_mv": 2900, "cell": 0},
            {"action": "can_request", "can_id": CAN_STATE_REQUEST, "command": "OPEN"},
        ],
        "expected": {"state_unchanged": BMS_ERROR},
        "verifies": ["SW-REQ-050", "SSR-007"],
        "asil": "D",
        "priority": "P1",
    },
]

# ---------------------------------------------------------------------------
# Aggregated catalog
# ---------------------------------------------------------------------------
ALL_STATE_MACHINE_TESTS = (
    VALID_TRANSITION_TESTS
    + INVALID_TRANSITION_TESTS
    + STATE_PERSISTENCE_TESTS
    + ENTRY_ACTION_TESTS
    + EXIT_ACTION_TESTS
    + TRANSITION_TIMING_TESTS
    + CONTACTOR_SEQUENCE_TESTS
    + STARTUP_SEQUENCE_TESTS
    + ERROR_RECOVERY_TESTS
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from collections import Counter

    prefix_counter = Counter()
    for t in ALL_STATE_MACHINE_TESTS:
        prefix = t["id"].rsplit("-", 1)[0]
        # Get category prefix like SM-TRANS, SM-REJECT, etc.
        parts = t["id"].split("-")
        cat = f"{parts[0]}-{parts[1]}"
        prefix_counter[cat] += 1

    print("=" * 60)
    print("foxBMS State Machine Test Specification")
    print("=" * 60)
    total = len(ALL_STATE_MACHINE_TESTS)
    for cat, count in sorted(prefix_counter.items()):
        print(f"  {cat:<16s} {count:>3d} tests")
    print(f"  {'TOTAL':<16s} {total:>3d} tests")
    print("=" * 60)

    # Verify unique IDs
    ids = [t["id"] for t in ALL_STATE_MACHINE_TESTS]
    dupes = [tid for tid in ids if ids.count(tid) > 1]
    if dupes:
        print(f"ERROR: Duplicate IDs: {set(dupes)}")
    else:
        print(f"All {total} test IDs are unique.")

    # Coverage summary
    reqs = set()
    for t in ALL_STATE_MACHINE_TESTS:
        reqs.update(t.get("verifies", []))
    print(f"Requirements traced: {sorted(reqs)}")


def get_tests():
    """Return all state machine tests (for test_catalog_runner.py)."""
    return ALL_STATE_MACHINE_TESTS

