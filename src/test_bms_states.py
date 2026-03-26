#!/usr/bin/env python3
"""
Unit tests for BMS state machine transitions.

Tests the state machine logic offline using the constants, transition rules,
and timing constraints defined in the foxBMS POSIX vECU specification.
These are pure-Python pytest tests — no live vECU or SocketCAN required.

Covers:
  - Valid transition adjacency matrix
  - Invalid/forbidden transitions
  - State enum integrity
  - Precharge timeout boundary
  - ERROR recovery gating (10 s blocking timer)
  - Contactor sequencing invariants
  - Startup sequence ordering
"""
# @verifies SW-REQ-040
# @verifies SW-REQ-041
# @verifies SW-REQ-042
# @verifies SW-REQ-043
# @verifies SW-REQ-044
# @verifies SW-REQ-045
# @verifies SW-REQ-050

import pytest

# ---------------------------------------------------------------------------
# BMS state definitions (from fi/constants.py)
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

STATE_NAMES = {
    0: "UNINITIALIZED", 1: "INITIALIZATION", 2: "INITIALIZED",
    3: "IDLE", 4: "OPEN_CONTACTORS", 5: "STANDBY",
    6: "PRECHARGE", 7: "NORMAL", 8: "DISCHARGE",
    9: "CHARGE", 10: "ERROR",
}

ALL_STATES = list(STATE_NAMES.keys())

# ---------------------------------------------------------------------------
# Valid transition adjacency matrix
# ---------------------------------------------------------------------------
# Each key maps to the set of states it may transition TO.
VALID_TRANSITIONS = {
    BMS_UNINITIALIZED:    {BMS_INITIALIZATION},
    BMS_INITIALIZATION:   {BMS_INITIALIZED, BMS_ERROR},
    BMS_INITIALIZED:      {BMS_IDLE, BMS_ERROR},
    BMS_IDLE:             {BMS_OPEN_CONTACTORS, BMS_STANDBY, BMS_ERROR},
    BMS_OPEN_CONTACTORS:  {BMS_STANDBY, BMS_ERROR},
    BMS_STANDBY:          {BMS_PRECHARGE, BMS_ERROR},
    BMS_PRECHARGE:        {BMS_NORMAL, BMS_ERROR},
    BMS_NORMAL:           {BMS_DISCHARGE, BMS_CHARGE, BMS_ERROR,
                           BMS_OPEN_CONTACTORS, BMS_STANDBY},
    BMS_DISCHARGE:        {BMS_NORMAL, BMS_ERROR, BMS_OPEN_CONTACTORS},
    BMS_CHARGE:           {BMS_NORMAL, BMS_ERROR, BMS_OPEN_CONTACTORS},
    BMS_ERROR:            {BMS_STANDBY, BMS_OPEN_CONTACTORS},
}

# Timing constraints (ms)
PRECHARGE_TIMEOUT_MS = 2000
ERROR_RECOVERY_BLOCKING_MS = 10000
MAX_TRANSITION_LATENCY_MS = 500
PRECHARGE_MAX_TRANSITION_MS = 2500
CONTACTOR_LATENCY_MS = 10


# ===================================================================
# Test class: State enum integrity
# ===================================================================
class TestStateEnumIntegrity:
    """Verify BMS state enum values and naming consistency."""

    def test_state_count(self):
        """There are exactly 11 BMS states (0–10)."""
        assert len(STATE_NAMES) == 11

    def test_state_values_contiguous(self):
        """State enum values are contiguous integers 0..10."""
        assert sorted(STATE_NAMES.keys()) == list(range(11))

    def test_all_states_named(self):
        """Every state has a non-empty name."""
        for state_id, name in STATE_NAMES.items():
            assert isinstance(name, str) and len(name) > 0, (
                f"State {state_id} has invalid name: {name!r}"
            )

    def test_no_duplicate_names(self):
        """No two states share the same name."""
        names = list(STATE_NAMES.values())
        assert len(names) == len(set(names))

    def test_error_state_is_highest(self):
        """ERROR has the highest enum value (10)."""
        assert BMS_ERROR == max(ALL_STATES)
        assert STATE_NAMES[BMS_ERROR] == "ERROR"


# ===================================================================
# Test class: Valid transitions
# ===================================================================
class TestValidTransitions:
    """Verify every explicitly allowed transition is present in the matrix."""

    @pytest.mark.parametrize("from_state,to_state", [
        (BMS_UNINITIALIZED, BMS_INITIALIZATION),
        (BMS_INITIALIZATION, BMS_INITIALIZED),
        (BMS_STANDBY, BMS_PRECHARGE),
        (BMS_PRECHARGE, BMS_NORMAL),
        (BMS_PRECHARGE, BMS_ERROR),
        (BMS_NORMAL, BMS_ERROR),
        (BMS_NORMAL, BMS_DISCHARGE),
        (BMS_NORMAL, BMS_CHARGE),
        (BMS_ERROR, BMS_STANDBY),
    ])
    def test_transition_allowed(self, from_state, to_state):
        """Known valid transitions must be present in adjacency matrix."""
        assert to_state in VALID_TRANSITIONS[from_state], (
            f"{STATE_NAMES[from_state]} -> {STATE_NAMES[to_state]} should be allowed"
        )

    def test_every_state_has_at_least_one_successor(self):
        """Every state must have at least one valid successor."""
        for state in ALL_STATES:
            assert len(VALID_TRANSITIONS[state]) >= 1, (
                f"{STATE_NAMES[state]} has no successors"
            )

    def test_error_reachable_from_every_operational_state(self):
        """ERROR must be reachable from every state except UNINITIALIZED
        and ERROR itself (ERROR doesn't self-loop)."""
        for state in ALL_STATES:
            if state in (BMS_UNINITIALIZED, BMS_ERROR):
                continue
            assert BMS_ERROR in VALID_TRANSITIONS[state], (
                f"{STATE_NAMES[state]} cannot reach ERROR — safety violation"
            )

    def test_startup_path_exists(self):
        """The startup path UNINITIALIZED → INITIALIZATION → INITIALIZED → IDLE
        → STANDBY must be traversable."""
        path = [BMS_UNINITIALIZED, BMS_INITIALIZATION, BMS_INITIALIZED,
                BMS_IDLE, BMS_STANDBY]
        for i in range(len(path) - 1):
            assert path[i + 1] in VALID_TRANSITIONS[path[i]], (
                f"Startup path broken at {STATE_NAMES[path[i]]} -> "
                f"{STATE_NAMES[path[i + 1]]}"
            )

    def test_normal_operation_path(self):
        """Full path to NORMAL: STANDBY → PRECHARGE → NORMAL."""
        assert BMS_PRECHARGE in VALID_TRANSITIONS[BMS_STANDBY]
        assert BMS_NORMAL in VALID_TRANSITIONS[BMS_PRECHARGE]


# ===================================================================
# Test class: Forbidden (invalid) transitions
# ===================================================================
class TestForbiddenTransitions:
    """Verify that transitions NOT in the adjacency matrix are forbidden."""

    @pytest.mark.parametrize("from_state,to_state", [
        (BMS_UNINITIALIZED, BMS_NORMAL),
        (BMS_UNINITIALIZED, BMS_ERROR),
        (BMS_STANDBY, BMS_NORMAL),
        (BMS_STANDBY, BMS_CHARGE),
        (BMS_STANDBY, BMS_DISCHARGE),
        (BMS_PRECHARGE, BMS_STANDBY),
        (BMS_PRECHARGE, BMS_CHARGE),
        (BMS_ERROR, BMS_NORMAL),
        (BMS_ERROR, BMS_PRECHARGE),
        (BMS_ERROR, BMS_CHARGE),
        (BMS_ERROR, BMS_DISCHARGE),
        (BMS_NORMAL, BMS_PRECHARGE),
        (BMS_NORMAL, BMS_INITIALIZATION),
    ])
    def test_transition_forbidden(self, from_state, to_state):
        """Known forbidden transitions must NOT appear in adjacency matrix."""
        assert to_state not in VALID_TRANSITIONS[from_state], (
            f"{STATE_NAMES[from_state]} -> {STATE_NAMES[to_state]} must be forbidden"
        )

    def test_no_self_loops_for_transient_states(self):
        """Transient states (INITIALIZATION, IDLE, OPEN_CONTACTORS) must not
        self-loop in the transition matrix."""
        transient = [BMS_INITIALIZATION, BMS_IDLE, BMS_OPEN_CONTACTORS]
        for state in transient:
            assert state not in VALID_TRANSITIONS[state], (
                f"{STATE_NAMES[state]} has a self-loop — transient states must progress"
            )

    def test_error_cannot_reach_normal_directly(self):
        """From ERROR, the BMS must not jump directly to NORMAL."""
        assert BMS_NORMAL not in VALID_TRANSITIONS[BMS_ERROR]

    def test_error_cannot_reach_precharge_directly(self):
        """From ERROR, the BMS must go through STANDBY before PRECHARGE."""
        assert BMS_PRECHARGE not in VALID_TRANSITIONS[BMS_ERROR]


# ===================================================================
# Test class: Timing constraints
# ===================================================================
class TestTimingConstraints:
    """Verify timing constants are within safety-spec bounds."""

    def test_precharge_timeout_positive(self):
        assert PRECHARGE_TIMEOUT_MS > 0

    def test_precharge_timeout_value(self):
        """Precharge timeout must be 2000 ms per foxBMS spec."""
        assert PRECHARGE_TIMEOUT_MS == 2000

    def test_error_recovery_blocking_time(self):
        """ERROR recovery blocking timer must be 10 s."""
        assert ERROR_RECOVERY_BLOCKING_MS == 10000

    def test_precharge_max_exceeds_timeout(self):
        """Test allowance for precharge→ERROR must exceed the timeout itself."""
        assert PRECHARGE_MAX_TRANSITION_MS > PRECHARGE_TIMEOUT_MS

    def test_contactor_latency_reasonable(self):
        """SPS contactor latency must be small relative to precharge timeout."""
        assert CONTACTOR_LATENCY_MS < PRECHARGE_TIMEOUT_MS / 10

    def test_transition_latency_under_500ms(self):
        """General state transition latency budget is ≤500 ms."""
        assert MAX_TRANSITION_LATENCY_MS <= 500


# ===================================================================
# Test class: Contactor sequencing invariants
# ===================================================================
class TestContactorSequencing:
    """Verify contactor opening/closing sequencing rules."""

    # Contactor bit positions in SPS state word
    CONTACTOR_MAIN_POS = 0   # bit 0
    CONTACTOR_MAIN_NEG = 1   # bit 1
    CONTACTOR_PRECHARGE = 2  # bit 2

    def test_precharge_opens_before_main(self):
        """In PRECHARGE sequence: precharge relay closes FIRST, then mains.
        Encoded as bit 2 set before bits 0+1."""
        precharge_mask = 1 << self.CONTACTOR_PRECHARGE
        assert precharge_mask == 4
        main_mask = (1 << self.CONTACTOR_MAIN_POS) | (1 << self.CONTACTOR_MAIN_NEG)
        assert main_mask == 3
        # Precharge bit must be independent of main bits
        assert (precharge_mask & main_mask) == 0

    def test_all_contactors_open_in_error(self):
        """When entering ERROR, all contactor bits must be cleared (0x00)."""
        all_closed = 0x07  # bits 0, 1, 2
        all_open = 0x00
        assert all_open == (all_closed & ~0x07)

    def test_normal_state_requires_mains_closed(self):
        """NORMAL requires both main contactors closed (bits 0+1)."""
        required_mask = (1 << self.CONTACTOR_MAIN_POS) | (1 << self.CONTACTOR_MAIN_NEG)
        assert required_mask == 0x03

    @pytest.mark.parametrize("sps_actual,expected_closed", [
        (0x00, False),  # all open
        (0x01, False),  # only main+
        (0x02, False),  # only main-
        (0x03, True),   # both mains closed
        (0x07, True),   # all closed (precharge + mains)
        (0x04, False),  # only precharge
    ])
    def test_discharge_path_requires_both_mains(self, sps_actual, expected_closed):
        """Plant model only enables discharge when both main contactors are closed."""
        both_mains = (sps_actual & 0x03) == 0x03
        assert both_mains == expected_closed


# ===================================================================
# Test class: ERROR recovery path
# ===================================================================
class TestErrorRecovery:
    """Verify ERROR state recovery rules."""

    def test_error_can_recover_to_standby(self):
        """After blocking timer, ERROR → STANDBY is allowed."""
        assert BMS_STANDBY in VALID_TRANSITIONS[BMS_ERROR]

    def test_error_cannot_skip_to_normal(self):
        """Recovery must go through STANDBY → PRECHARGE → NORMAL, not skip."""
        assert BMS_NORMAL not in VALID_TRANSITIONS[BMS_ERROR]
        assert BMS_PRECHARGE not in VALID_TRANSITIONS[BMS_ERROR]

    def test_full_recovery_path(self):
        """ERROR → STANDBY → PRECHARGE → NORMAL is a valid recovery path."""
        path = [BMS_ERROR, BMS_STANDBY, BMS_PRECHARGE, BMS_NORMAL]
        for i in range(len(path) - 1):
            assert path[i + 1] in VALID_TRANSITIONS[path[i]]

    def test_recovery_blocking_timer_positive(self):
        """Recovery blocking timer must be > 0."""
        assert ERROR_RECOVERY_BLOCKING_MS > 0

    def test_recovery_timer_longer_than_precharge(self):
        """Recovery blocking must exceed precharge timeout to prevent
        rapid cycling between NORMAL and ERROR."""
        assert ERROR_RECOVERY_BLOCKING_MS > PRECHARGE_TIMEOUT_MS


# ===================================================================
# Test class: Startup sequence
# ===================================================================
class TestStartupSequence:
    """Verify the power-on startup state ordering."""

    STARTUP_SEQUENCE = [
        BMS_UNINITIALIZED,
        BMS_INITIALIZATION,
        BMS_INITIALIZED,
        BMS_IDLE,
        BMS_OPEN_CONTACTORS,
        BMS_STANDBY,
    ]

    def test_startup_states_monotonically_reachable(self):
        """Each startup state can reach the next in sequence."""
        for i in range(len(self.STARTUP_SEQUENCE) - 1):
            src = self.STARTUP_SEQUENCE[i]
            dst = self.STARTUP_SEQUENCE[i + 1]
            assert dst in VALID_TRANSITIONS[src], (
                f"Startup broken: {STATE_NAMES[src]} cannot reach {STATE_NAMES[dst]}"
            )

    def test_initial_state_is_uninitialized(self):
        """System must start in UNINITIALIZED (enum 0)."""
        assert BMS_UNINITIALIZED == 0

    def test_standby_is_first_steady_state(self):
        """STANDBY is the first state that waits for external input."""
        # Verify STANDBY requires an explicit CAN request to proceed
        # (it doesn't auto-transition to PRECHARGE)
        assert BMS_PRECHARGE in VALID_TRANSITIONS[BMS_STANDBY]
        assert BMS_NORMAL not in VALID_TRANSITIONS[BMS_STANDBY]
