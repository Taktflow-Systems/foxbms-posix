# System Qualification Test Specification

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SYS.5-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | M. Weber | Initial release |

## 1. Purpose

This document specifies the system qualification tests for the foxBMS 2 POSIX vECU project in accordance with ASPICE SYS.5 (System Qualification Test). These tests verify that the delivered system meets the stakeholder requirements and is fit for its intended purpose as a SIL pre-validation platform for HIL test engineers.

## 2. Scope

System qualification testing demonstrates end-to-end acceptance of the system from the perspective of each stakeholder. Unlike integration tests (SYS.4), qualification tests focus on whether the system delivers its intended value, not on component interaction mechanics.

## 3. References

| ID | Title |
|---|---|
| [SYS.1-001] | Stakeholder Requirements Specification |
| [SYS.4-001] | System Integration Test Specification |
| [SYS.2-001] | System Requirements Specification |

## 4. Test Environment

Identical to SYS.4 test environment (see SYS.4-001, Section 4). All qualification tests execute on the same Ubuntu 24.04 workstation with SocketCAN.

## 5. Qualification Test Strategy

Qualification tests are the highest-level acceptance gate. They verify that:
1. A fresh clone of the repository can be built and tested with a single command
2. The BMS reaches its operational state within acceptable time
3. Core BMS functions (SOC, contactor control, diagnostics) operate correctly
4. The system meets timing requirements

The primary test vehicle is **test_smoke.py**, which serves as the end-to-end acceptance test.

## 6. Qualification Test Cases

### 6.1 Build and Deploy Acceptance

| Test ID | Description | Traces To | Pass Criteria |
|---|---|---|---|
| SQT-001 | Fresh clone: `git clone --recursive` completes without error | STKH-REQ-001 | Exit code 0 |
| SQT-002 | Setup: `./setup.sh` applies patches, builds vECU, configures vcan0, runs smoke test -- all in one command | STKH-REQ-002 | Exit code 0; "PASS" in output |
| SQT-003 | Build time is under 60 seconds on reference workstation | STKH-REQ-003 | Wall clock time < 60s |
| SQT-004 | foxBMS version check: apply_all.sh verifies v1.10.0 before patching | STKH-REQ-004 | Version check message in output |

### 6.2 BMS Operational Acceptance

| Test ID | Description | Traces To | Pass Criteria |
|---|---|---|---|
| SQT-005 | BMS reaches NORMAL state within 15 seconds of vECU start | STKH-REQ-006 | BMS state = NORMAL observed in CAN within 15 s (baseline: 6.3 s on reference workstation) |
| SQT-006 | BMS transitions through all expected states: UNINIT -> INIT -> IDLE -> STANDBY -> PRECHARGE -> NORMAL | STKH-REQ-005 | All intermediate states observed in sequence |
| SQT-007 | At least 15 distinct CAN message IDs transmitted during a 20-second run | STKH-REQ-007 | >= 15 unique CAN IDs on vcan0 |
| SQT-008 | connected_strings = 1 when BMS is in NORMAL state | STKH-REQ-005 | CAN message confirms connected_strings > 0 |

### 6.3 Battery State Acceptance

| Test ID | Description | Traces To | Pass Criteria |
|---|---|---|---|
| SQT-009 | SOC is non-zero and reported on CAN 0x235 | STKH-REQ-008 | SOC value >= 1% in CAN message (plant starts at 80% SOC) |
| SQT-010 | SOC decreases over a 20-second discharge run | STKH-REQ-008 | SOC at t=20s < SOC at t=5s by at least 0.05% (1A discharge at 3Ah capacity) |
| SQT-011 | Cell voltages are within valid range (1500 mV - 4200 mV) | STKH-REQ-005 | All 18 cell voltages within range |
| SQT-012 | Cell temperatures are within valid range (0 - 60 degC) | STKH-REQ-005 | All temperature readings within range |

### 6.4 Timing and Performance Acceptance

| Test ID | Description | Traces To | Pass Criteria |
|---|---|---|---|
| SQT-013 | Cooperative loop executes 1ms tick without deadline violations during 20-second run | STKH-REQ-005 | Zero deadline violations in timing summary |
| SQT-014 | vECU exits cleanly after --timeout 20 | STKH-REQ-015 | Process exits with code 0 within 22 seconds |
| SQT-015 | Timing summary printed at exit shows max execution times | STKH-REQ-015 | Timing summary present in stdout |

### 6.5 Safety Acceptance

| Test ID | Description | Traces To | Pass Criteria |
|---|---|---|---|
| SQT-016 | Selective DIAG_Handler is active: 61 SW-checkable IDs enabled, 24 HW IDs suppressed | STKH-REQ-009, STKH-REQ-010 | DIAG configuration log confirms counts |
| SQT-017 | FAS_ASSERT violation causes visible crash with file/line information | STKH-REQ-013 | Assert test produces error message and exit code 1 |
| SQT-018 | Software watchdog triggers if main loop stalls > 100ms | STKH-REQ-013 | Watchdog message in output when stall injected |

### 6.6 Fault Injection Acceptance

| Test ID | Description | Traces To | Pass Criteria |
|---|---|---|---|
| SQT-019 | SIL probe override (CAN 0x7E0) can inject overvoltage fault and BMS detects it | STKH-REQ-011, STKH-REQ-012 | DIAG event for CELL_VOLTAGE_OVERVOLTAGE_MSL logged |
| SQT-020 | Fault injection test suite (test_asil.py) achieves 50/50 criteria pass | STKH-REQ-017 | test_asil.py exit code 0 |

### 6.7 Documentation and Usability Acceptance

| Test ID | Description | Traces To | Pass Criteria |
|---|---|---|---|
| SQT-021 | TROUBLESHOOTING.md exists and covers >= 10 failure modes | STKH-REQ-018 | File exists; >= 10 sections |
| SQT-022 | Architecture documentation includes block diagrams | STKH-REQ-019 | SYS.3 and SWE.2 docs contain ASCII block diagrams |
| SQT-023 | COVERAGE.md tracks all features with working/suppressed/not-implemented status | STKH-REQ-020 | File exists; summary table present |

## 7. Test Execution

### 7.1 Execution Command

```bash
# Primary qualification test
python3 tests/test_smoke.py --timeout 20

# Full qualification (smoke + integration + ASIL)
./setup.sh  # Includes smoke test
python3 tests/test_integration.py --timeout 30
python3 tests/test_asil.py --timeout 60
```

### 7.2 Acceptance Verdict

The system qualification is **PASSED** when:
- test_smoke.py reports PASS
- test_integration.py reports 21/21 criteria pass
- test_asil.py reports 50/50 criteria pass
- setup.sh completes on a fresh clone without manual intervention

### 7.3 Current Results

```
[SMOKE] BMS reached NORMAL state after 6.3s (connected_strings=1)
[SMOKE] OK: connected_strings=1 when NORMAL
[SMOKE] OK: SOC non-zero seen on 0x235
[SMOKE] PASS: BMS NORMAL, connected_strings > 0, SOC > 0% confirmed
```

| Script | Result |
|---|---|
| test_smoke.py | PASS |
| test_integration.py | 21/21 PASS |
| test_asil.py | 50/50 PASS |
| setup.sh (fresh clone) | PASS |

## 8. Traceability

All SQT-xxx test cases trace back to STKH-REQ-xxx stakeholder requirements in [SYS.1-001]. This provides the final link in the traceability chain: stakeholder requirements -> system requirements -> software requirements -> design -> implementation -> unit test -> integration test -> qualification test.
