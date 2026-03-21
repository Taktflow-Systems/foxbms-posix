# System Integration Test Specification

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SYS.4-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | M. Weber | Initial release |

## 1. Purpose

This document specifies the system integration tests for the foxBMS 2 POSIX vECU project in accordance with ASPICE SYS.4 (System Integration and System Integration Test). These tests verify that the system components -- the vECU binary, the Python plant model, and the SocketCAN communication layer -- integrate correctly and produce the expected end-to-end behavior.

## 2. Scope

System integration testing verifies the interactions between:
- foxbms-vecu (compiled BMS application) and plant_model.py (battery/sensor simulation)
- CAN message flow over SocketCAN (vcan0)
- State machine transitions driven by cross-component communication
- Closed-loop contactor feedback between vECU and plant model
- Fault injection via SIL probe overrides (CAN 0x7E0)

## 3. References

| ID | Title |
|---|---|
| [SYS.3-001] | System Architecture Description |
| [SWE.5-001] | Software Integration Test Specification |
| [SWE.6-001] | Software Qualification Test Specification |
| [SYS.2-001] | System Requirements Specification |

## 4. Test Environment

### 4.1 Hardware

| Component | Specification |
|---|---|
| Host machine | x86-64 Linux workstation |
| CAN interface | SocketCAN virtual CAN (vcan0) |
| Network | Loopback (no external network required) |

### 4.2 Software

| Component | Version |
|---|---|
| Operating system | Ubuntu 24.04 LTS |
| foxbms-vecu | Built from foxBMS v1.10.0 + 13 patches |
| plant_model.py | Current version with OCV(SOC), IR drop, trip replay |
| Python | 3.12 |
| python-can | Latest (SocketCAN backend) |
| can-utils | System package |

### 4.3 Prerequisites

1. vcan0 interface is up: `sudo ip link add dev vcan0 type vcan && sudo ip link set up vcan0`
2. foxbms-vecu binary is compiled: `make -C build/`
3. Plant model dependencies installed: `pip install python-can`

## 5. Test Strategy

System integration tests are implemented in two test scripts:

| Script | Focus | Criteria Count |
|---|---|---|
| test_integration.py | Component integration and CAN message flow | 21 |
| test_asil.py | Safety-critical fault injection paths | 50 |

Tests are executed automatically. Each test criterion produces a PASS/FAIL verdict. The test scripts manage process lifecycle (start plant model, start vECU, monitor CAN, stop both).

## 6. Integration Test Cases (test_integration.py)

### 6.1 Component Startup and Communication

| Test ID | Description | Traces To | Pass Criteria |
|---|---|---|---|
| SIT-001 | Plant model starts and transmits cell voltage CAN messages within 2 seconds | SYS-REQ-010 | CAN messages with cell voltage data observed on vcan0 |
| SIT-002 | vECU starts and begins transmitting BMS status CAN messages within 5 seconds | SYS-REQ-011 | CAN ID 0x220 (or BMS state message) observed on vcan0 |
| SIT-003 | vECU receives and processes plant model CAN messages | SYS-REQ-020 | Database entries updated with plant model values |

### 6.2 State Machine Integration

| Test ID | Description | Traces To | Pass Criteria |
|---|---|---|---|
| SIT-004 | BMS transitions from IDLE to STANDBY upon receiving STANDBY request from plant model | SYS-REQ-011 | BMS state CAN message shows STANDBY state |
| SIT-005 | BMS transitions from STANDBY to PRECHARGE and closes precharge contactor | SYS-REQ-011, SYS-REQ-012 | Precharge contactor state = CLOSED in CAN output |
| SIT-006 | BMS completes precharge and transitions to NORMAL | SYS-REQ-011 | BMS state CAN message shows NORMAL within 15 seconds |
| SIT-007 | String contactors (positive and negative) are closed when BMS is in NORMAL state | SYS-REQ-012 | Contactor state messages show all three contactors closed |

### 6.3 CAN Message Flow End-to-End

| Test ID | Description | Traces To | Pass Criteria |
|---|---|---|---|
| SIT-008 | Cell voltage CAN messages (0x240-0x24F) contain non-zero voltage values | SYS-REQ-020 | All 18 cell voltages > 1000 mV |
| SIT-009 | IVT current CAN message reflects plant model current injection | SYS-REQ-020 | Current value matches plant model output within 100 mA |
| SIT-010 | Pack voltage CAN message reflects sum of cell voltages | SYS-REQ-020 | Pack voltage = 18 * cell voltage (within 500 mV tolerance) |
| SIT-011 | Temperature CAN messages contain valid temperature values | SYS-REQ-020 | Temperatures in range 0-60 degC |
| SIT-012 | SOC CAN message (0x235) reports non-zero SOC when in NORMAL state | SYS-REQ-030 | SOC > 0% |

### 6.4 Closed-Loop Contactor Feedback

| Test ID | Description | Traces To | Pass Criteria |
|---|---|---|---|
| SIT-013 | Plant model receives contactor close command and updates feedback | SYS-REQ-012 | Contactor feedback CAN message reflects closed state |
| SIT-014 | vECU reads contactor feedback and proceeds with state transition | SYS-REQ-012 | BMS does not stall in PRECHARGE due to missing feedback |
| SIT-015 | Contactor delay simulation matches configured delay (10 cycles) | SYS-REQ-012 | Contactor state transitions after expected delay |

### 6.5 Diagnostic Integration

| Test ID | Description | Traces To | Pass Criteria |
|---|---|---|---|
| SIT-016 | SOA overvoltage detection triggers when plant model sends voltage > 2800 mV | SYS-REQ-040 | DIAG event logged; BMS transitions toward ERROR state |
| SIT-017 | SOA undervoltage detection triggers when plant model sends voltage < 1500 mV | SYS-REQ-040 | DIAG event logged |
| SIT-018 | SOA overcurrent detection triggers when plant model sends current > limit | SYS-REQ-040 | DIAG event logged |

### 6.6 Process Lifecycle

| Test ID | Description | Traces To | Pass Criteria |
|---|---|---|---|
| SIT-019 | vECU shuts down cleanly on SIGINT (contactors opened, timing summary printed) | SYS-REQ-061 | Exit code 0; contactor-open message in log |
| SIT-020 | vECU exits after --timeout N seconds | SYS-REQ-061 | Process terminates within N+2 seconds |
| SIT-021 | Plant model and vECU can be restarted without stale CAN state | SYS-REQ-001 | Second run produces same results as first |

## 7. ASIL Fault Injection Tests (test_asil.py)

The test_asil.py script exercises 50 safety-critical fault injection criteria using the SIL probe override system (CAN 0x7E0). These tests verify that the integrated system correctly detects and responds to injected faults.

### 7.1 Test Categories

| Category | Criteria Count | Description |
|---|---|---|
| Overvoltage faults | 8 | MSL/RSL/MOL thresholds for cell overvoltage |
| Undervoltage faults | 8 | MSL/RSL/MOL thresholds for cell undervoltage |
| Overcurrent faults | 6 | Charge/discharge current limit violations |
| Overtemperature faults | 6 | Charge/discharge temperature limit violations |
| Undertemperature faults | 6 | Charge/discharge temperature limit violations |
| Plausibility faults | 8 | Voltage spread, temperature spread, pack voltage |
| IVT redundancy faults | 4 | V1/V2/V3 mismatch scenarios |
| Interlock faults | 2 | Interlock break via probe override |
| Watchdog faults | 2 | Main loop stall detection |

### 7.2 Fault Injection Mechanism

Each test follows the pattern:
1. Start plant model and vECU; wait for BMS NORMAL state
2. Send SIL probe override message on CAN 0x7E0 with fault parameters
3. Monitor DIAG_Handler response via CAN output or log
4. Verify BMS state transition (NORMAL -> ERROR for MSL faults)
5. Restore nominal values and verify recovery (where applicable)

## 8. Test Execution and Reporting

### 8.1 Execution Command

```bash
# Integration tests
python3 tests/test_integration.py --timeout 30

# ASIL fault injection tests
python3 tests/test_asil.py --timeout 60

# Both via make
make test-integration
make test-asil
```

### 8.2 Pass/Fail Criteria

- **Overall PASS**: All criteria within a test script pass
- **Overall FAIL**: Any criterion fails
- Exit code: 0 = PASS, 1 = FAIL, 2 = ERROR (infrastructure failure)

### 8.3 Current Results

| Script | Criteria | Passing | Status |
|---|---|---|---|
| test_integration.py | 21 | 21 | PASS |
| test_asil.py | 50 | 50 | PASS |

## 9. Traceability

All SIT-xxx test cases trace back to SYS-REQ-xxx system requirements in [SYS.2-001]. The bidirectional traceability matrix in ISO26262-part8-traceability.md provides the complete chain from stakeholder requirements through system tests.
