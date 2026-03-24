# System Qualification Test Specification

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SWE.6-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | L. Fischer | Initial release |

## 1. Purpose

This document specifies system-level qualification tests for the foxBMS 2 POSIX port,
satisfying ASPICE SWE.6 (software qualification test) and ISO 26262 Part 6 Clause 10.
Qualification tests verify end-to-end system behavior against system requirements
(SYS.2-001) in the target SIL environment.

## 2. Scope

Qualification tests exercise the full BMS software stack through its external interfaces
(SocketCAN) using realistic operational scenarios. Each test traces to one or more system
requirements.

## 3. References

| ID | Title |
|---|---|
| [SYS.2-001] | System Requirements Specification |
| [SWE.1-001] | Software Requirements Specification |
| [SWE.5-001] | Integration Test Specification |
| [ISO-SSR-001] | Software Safety Requirements |

## 4. Test Environment

| Aspect | Value |
|---|---|
| SIL binary | foxBMS POSIX build (x86-64, GCC 13) |
| CAN interface | SocketCAN (vcan0) |
| Test orchestration | pytest + python-can |
| Stimulus generation | Python test scripts simulating vehicle controller and sensors |
| Duration per scenario | 10-60 seconds |

## 5. Qualification Test Scenarios

### 5.1 Scenario QT-001: Normal Startup and Operation

**Objective**: Verify the complete startup sequence from power-on to NORMAL operation.

| Step | Action | Expected Observation | Traces To |
|---|---|---|---|
| 1 | Launch SIL binary | Process starts without error | SYS-REQ-080 |
| 2 | Wait 2 seconds | CAN 0x220 reports SYS state == RUNNING (5) | SYS-REQ-070 |
| 3 | Observe CAN 0x220 | BMS state == STANDBY (5) | SYS-REQ-071 |
| 4 | Send CAN 0x210: request NORMAL | BMS state transitions to PRECHARGE (6) | SYS-REQ-072 |
| 5 | Inject IVT voltage matching string voltage | BMS state transitions to NORMAL (7) | SYS-REQ-071 |
| 6 | Inject normal cell voltages (2500 mV) via CAN 0x270 | Cell voltages appear on CAN 0x240-0x245 | SYS-REQ-060 |
| 7 | Inject normal temperatures (25 deg C) via CAN 0x280 | Temperatures appear on CAN 0x260 | SYS-REQ-060 |
| 8 | Inject IVT current (500 mA) via CAN 0x521 | Current reflected in CAN 0x221 | SYS-REQ-062 |
| 9 | Run for 30 seconds | No ERROR, no crash, continuous CAN TX | SYS-REQ-071 |
| 10 | Send CAN 0x210: request STANDBY | BMS transitions to STANDBY | SYS-REQ-071 |

**Pass criteria**: All 10 steps observed correctly. No FATAL diagnostics triggered.

### 5.2 Scenario QT-002: Overvoltage Fault Injection and Recovery

**Objective**: Verify that an overvoltage condition triggers ERROR and that recovery
follows the dual-condition protocol.

| Step | Action | Expected Observation | Traces To |
|---|---|---|---|
| 1 | Start in NORMAL state (via QT-001 steps 1-5) | BMS == NORMAL | SYS-REQ-071 |
| 2 | Inject cell voltage 2850 mV (above MSL 2800 mV) via CAN 0x270 | SOA detects overvoltage | SYS-REQ-020 |
| 3 | Wait for DIAG threshold (50 events x 200 ms delay = ~10 seconds max) | CAN 0x220 shows BMS == ERROR (9) | SYS-REQ-053 |
| 4 | Verify contactors open | CAN 0x220 contactor flags show all open | SYS-REQ-054 |
| 5 | Send CAN 0x210: request NORMAL | BMS remains in ERROR (fault not cleared) | SYS-REQ-055 |
| 6 | Inject normal voltage (2500 mV) | Fault condition clears | SYS-REQ-055 |
| 7 | Wait for DIAG counter to decrement to zero | FATAL flag clears | SYS-REQ-055 |
| 8 | Send CAN 0x210: request STANDBY | BMS transitions to STANDBY | SYS-REQ-055 |

**Pass criteria**: ERROR entered on overvoltage. ERROR persists until both conditions met.

### 5.3 Scenario QT-003: Undervoltage and Deep Discharge

**Objective**: Verify undervoltage detection and deep discharge latching behavior.

| Step | Action | Expected Observation | Traces To |
|---|---|---|---|
| 1 | Start in NORMAL state | BMS == NORMAL | SYS-REQ-071 |
| 2 | Inject cell voltage 1450 mV (below MSL 1500 mV) | SOA detects undervoltage and deep discharge | SYS-REQ-021, SYS-REQ-022 |
| 3 | Wait for DIAG thresholds | BMS enters ERROR | SYS-REQ-053 |
| 4 | Inject normal voltage (2500 mV) | Undervoltage clears but deep discharge latched (threshold=1) | SYS-REQ-022 |
| 5 | Send CAN 0x210: request STANDBY | BMS remains in ERROR (deep discharge latched) | SYS-REQ-055 |

**Pass criteria**: Deep discharge latch prevents recovery even with normal voltage restored.

### 5.4 Scenario QT-004: Overcurrent Fault (Fast Response)

**Objective**: Verify that overcurrent is detected quickly due to low threshold (10 events).

| Step | Action | Expected Observation | Traces To |
|---|---|---|---|
| 1 | Start in NORMAL state | BMS == NORMAL | SYS-REQ-071 |
| 2 | Inject current 190000 mA via CAN 0x521 | SOA detects overcurrent | SYS-REQ-030 |
| 3 | Wait (10 events x 100 ms = ~1 second max) | BMS enters ERROR within 2 seconds | SYS-REQ-053 |
| 4 | Verify contactors open | All contactors commanded OPEN | SYS-REQ-054 |

**Pass criteria**: ERROR entered within 2 seconds of overcurrent injection.

### 5.5 Scenario QT-005: Temperature Fault (Slow Response)

**Objective**: Verify that temperature faults use the high debounce threshold (500 events).

| Step | Action | Expected Observation | Traces To |
|---|---|---|---|
| 1 | Start in NORMAL state | BMS == NORMAL | SYS-REQ-071 |
| 2 | Inject temperature 60 deg C (above discharge MSL 55 deg C) | SOA detects overtemperature | SYS-REQ-040 |
| 3 | Wait for DIAG threshold (500 events x 1000 ms delay) | BMS enters ERROR (extended debounce period) | SYS-REQ-053 |
| 4 | Verify contactors open | All contactors commanded OPEN | SYS-REQ-054 |

**Pass criteria**: ERROR entered after extended debounce period. System does not false-trip.

### 5.6 Scenario QT-006: CAN Communication Loss

**Objective**: Verify detection of CAN communication failure.

| Step | Action | Expected Observation | Traces To |
|---|---|---|---|
| 1 | Start in NORMAL state with active IVT data | BMS == NORMAL | SYS-REQ-071 |
| 2 | Stop sending IVT CAN frames | Current sensor timeout begins | SYS-REQ-063 |
| 3 | Wait for DIAG threshold (100 events x 200 ms delay) | CURRENT_SENSOR_RESPONDING triggers FATAL | SYS-REQ-063 |
| 4 | Verify BMS enters ERROR | CAN 0x220 shows ERROR (9) | SYS-REQ-053 |

**Pass criteria**: Communication loss detected and ERROR state entered.

### 5.7 Scenario QT-007: Multiple Simultaneous Faults

**Objective**: Verify correct behavior when multiple faults occur simultaneously.

| Step | Action | Expected Observation | Traces To |
|---|---|---|---|
| 1 | Start in NORMAL state | BMS == NORMAL | SYS-REQ-071 |
| 2 | Inject overvoltage (2850 mV) AND overcurrent (190000 mA) simultaneously | Both SOA checks detect violations | SYS-REQ-020, SYS-REQ-030 |
| 3 | Wait for first FATAL (overcurrent: 10 events) | BMS enters ERROR | SYS-REQ-053 |
| 4 | Verify both diagnostics are flagged | Both DIAG entries show non-zero counters | SYS-REQ-050 |
| 5 | Clear only overcurrent (inject normal current) | Overcurrent FATAL clears, overvoltage still active | SYS-REQ-055 |
| 6 | Send STANDBY request | BMS remains in ERROR (overvoltage still FATAL) | SYS-REQ-055 |
| 7 | Clear overvoltage (inject normal voltage) + send STANDBY | BMS transitions to STANDBY | SYS-REQ-055 |

**Pass criteria**: System handles multiple faults correctly. All faults must clear before recovery.

### 5.8 Scenario QT-008: Steady-State Endurance

**Objective**: Verify stable long-duration operation without degradation.

| Step | Action | Expected Observation | Traces To |
|---|---|---|---|
| 1 | Start in NORMAL state | BMS == NORMAL | SYS-REQ-071 |
| 2 | Inject normal measurements continuously | All values within SOA limits | SYS-REQ-020 to SYS-REQ-043 |
| 3 | Run for 60 seconds | No ERROR, no crash, no memory leak | SYS-REQ-080 |
| 4 | Verify CAN TX message count | Approximately 600 frames at 100 ms interval (within 10%) | SYS-REQ-060 |
| 5 | Verify no DIAG counters have incremented | All counters == 0 | SYS-REQ-050 |

**Pass criteria**: 60-second stable operation with no anomalies.

## 6. Phase 3 Planned Qualification Tests

The following tests are planned for future implementation and are documented here for
traceability completeness.

| ID | Scenario | Status | Traces To |
|---|---|---|---|
| QT-009 | Hardware fault emulation via stub injection | Planned | SYS-REQ-083 |
| QT-010 | AFE SPI failure simulation | Planned | SYS-REQ-050 |
| QT-011 | Interlock circuit break simulation | Planned | SYS-REQ-050 |
| QT-012 | SBC watchdog timeout simulation | Planned | SYS-REQ-050 |
| QT-013 | Contactor weld detection simulation | Planned | SYS-REQ-006 |
| QT-014 | Insulation monitoring failure simulation | Planned | SYS-REQ-050 |

## 7. Test Execution and Reporting

### 7.1 Execution Procedure

1. Set up virtual CAN interface: `ip link add dev vcan0 type vcan && ip link set up vcan0`
2. Launch SIL binary: `./foxbms_posix &`
3. Execute test suite: `pytest test_qualification.py -v --junitxml=report.xml`
4. Collect results and CAN trace logs.

### 7.2 Reporting

Test results shall be recorded in JUnit XML format and include:
- Test case ID and name
- Pass/fail status
- Execution duration
- Failure details (if any)
- CAN trace log reference

## 8. Pass/Fail Criteria

- All qualification tests (QT-001 through QT-008) shall pass.
- No test shall cause a crash, segfault, or unhandled exception.
- All state transitions shall occur within documented timing bounds.
- CAN communication shall be continuous throughout each scenario.

---
*End of Document*
