# Integration Test Specification

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SWE.5-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | -- | Initial release |

## 1. Purpose

This document specifies integration-level tests for the foxBMS 2 POSIX port,
satisfying ASPICE SWE.5 (software integration and integration test) and ISO 26262
Part 6 Clause 10. Integration tests verify that modules interact correctly through
their defined interfaces.

## 2. Scope

Integration tests verify:
- CAN interface data flow (external stimulus to internal database)
- Database producer/consumer data integrity across modules
- State machine transitions driven by inter-module interactions
- Safety path: SOA to DIAG to BMS to Contactor

## 3. References

| ID | Title |
|---|---|
| [SWE.1-001] | Software Requirements Specification |
| [SWE.2-001] | Software Architecture Description |
| [SWE.4-001] | Unit Test Specification |
| [SWE.6-001] | Qualification Test Specification |

## 4. Test Environment

| Aspect | Value |
|---|---|
| Test framework | pytest 8.x |
| CAN interface | SocketCAN (vcan0) |
| SIL binary | foxBMS POSIX build (x86-64, GCC 13) |
| Stimulus | python-can library injecting CAN frames |
| Observation | python-can listener capturing TX frames |
| Timeout | Per-test configurable, default 5 seconds |

## 5. Test Suites

### 5.1 Integration Test Suite (test_integration.py)

#### 5.1.1 CAN Interface Integration

| ID | Test Case | Stimulus | Expected Result | Traces To |
|---|---|---|---|---|
| IT-001 | State request reception | Send CAN 0x210 with NORMAL request | BMS transitions from STANDBY; CAN 0x220 reflects new state | SW-REQ-100, SW-REQ-041 |
| IT-002 | IVT current data reception | Send CAN 0x521 with current value | Database[CURRENT] updated; value appears in CAN 0x221 TX | SW-REQ-101, SW-REQ-091 |
| IT-003 | IVT voltage data reception | Send CAN 0x522-0x524 with voltage values | Database entries updated; pack voltage reflected in TX | SW-REQ-101 |
| IT-004 | IVT temperature data reception | Send CAN 0x525 with temperature | Database entry updated | SW-REQ-101 |
| IT-005 | AFE cell voltage reception | Send CAN 0x270 with multiplexed voltage data | Cell voltages appear in CAN 0x240-0x245 TX messages | SW-REQ-102, SW-REQ-092 |
| IT-006 | AFE cell temperature reception | Send CAN 0x280 with multiplexed temp data | Temperature data appears in CAN 0x260 TX | SW-REQ-103, SW-REQ-093 |
| IT-007 | CAN TX periodicity | Observe CAN 0x220 timing over 2 seconds | Inter-frame interval approximately 100 ms (within 20%) | SW-REQ-090 |
| IT-008 | Unknown CAN ID rejected | Send CAN 0x999 (not in config) | No crash, no state change, frame ignored | SW-REQ-100 |

#### 5.1.2 Database Data Flow Integration

| ID | Test Case | Stimulus | Expected Result | Traces To |
|---|---|---|---|---|
| IT-010 | Cell voltage flows from AFE to SOA | Inject cell voltages via CAN 0x270 | SOA reads correct voltages from database | SW-REQ-001, SW-REQ-062 |
| IT-011 | Current flows from IVT to SOA | Inject current via CAN 0x521 | SOA reads correct current from database | SW-REQ-010, SW-REQ-062 |
| IT-012 | Temperature flows from AFE to SOA | Inject temperatures via CAN 0x280 | SOA reads correct temperatures from database | SW-REQ-020, SW-REQ-062 |
| IT-013 | State request flows from CAN to BMS | Send state request via CAN 0x210 | BMS reads correct request from database | SW-REQ-100, SW-REQ-060 |
| IT-014 | BMS state flows to CAN TX | Trigger BMS state change | CAN 0x220 reflects updated BMS state | SW-REQ-090, SW-REQ-040 |

#### 5.1.3 State Machine Integration

| ID | Test Case | Stimulus | Expected Result | Traces To |
|---|---|---|---|---|
| IT-020 | SYS startup sequence | Start binary, wait 2 seconds | SYS progresses: UNINITIALIZED -> INITIALIZATION -> INITIALIZED -> IDLE -> RUNNING | SW-REQ-050 to SW-REQ-053 |
| IT-021 | BMS STANDBY to PRECHARGE | Send CAN 0x210 NORMAL request | BMS state changes to PRECHARGE (6) | SW-REQ-041 |
| IT-022 | BMS PRECHARGE to NORMAL | Send state request + wait for precharge | BMS state changes to NORMAL (7) | SW-REQ-042 |
| IT-023 | BMS NORMAL to STANDBY | Send CAN 0x210 STANDBY request | BMS state changes to STANDBY (5) | SW-REQ-041 |
| IT-024 | BMS any-state to ERROR | Inject fault condition (e.g., overvoltage) | BMS state changes to ERROR (9) | SW-REQ-043 |
| IT-025 | BMS ERROR persistence | In ERROR, send NORMAL request | BMS remains in ERROR (dual condition required) | SW-REQ-045 |

### 5.2 ASIL Test Suite (test_asil.py)

#### 5.2.1 Safety Path Integration

| ID | Test Case | Stimulus | Expected Result | Traces To |
|---|---|---|---|---|
| IT-030 | Overvoltage MSL triggers ERROR | Inject cell voltage > 2800 mV via CAN 0x270 for 50+ evaluations | DIAG FATAL set; BMS enters ERROR; contactors open | SW-REQ-001, SW-REQ-032, SW-REQ-043, SW-REQ-044 |
| IT-031 | Undervoltage MSL triggers ERROR | Inject cell voltage < 1500 mV via CAN 0x270 for 50+ evaluations | DIAG FATAL set; BMS enters ERROR; contactors open | SW-REQ-002, SW-REQ-032, SW-REQ-043, SW-REQ-044 |
| IT-032 | Overtemperature discharge MSL triggers ERROR | Inject temperature > 55 deg C via CAN 0x280 for 500+ evaluations | DIAG FATAL set; BMS enters ERROR | SW-REQ-020, SW-REQ-032, SW-REQ-043 |
| IT-033 | Undertemperature discharge MSL triggers ERROR | Inject temperature < -20 deg C via CAN 0x280 for 500+ evaluations | DIAG FATAL set; BMS enters ERROR | SW-REQ-021, SW-REQ-032, SW-REQ-043 |
| IT-034 | Overtemperature charge MSL triggers ERROR | Inject temperature > 45 deg C during charge | DIAG FATAL set; BMS enters ERROR | SW-REQ-022, SW-REQ-032, SW-REQ-043 |
| IT-035 | Undertemperature charge MSL triggers ERROR | Inject temperature < -20 deg C during charge | DIAG FATAL set; BMS enters ERROR | SW-REQ-023, SW-REQ-032, SW-REQ-043 |
| IT-036 | Discharge overcurrent MSL triggers ERROR | Inject current > 180000 mA for 10+ evaluations | DIAG FATAL set; BMS enters ERROR | SW-REQ-010, SW-REQ-032, SW-REQ-043 |
| IT-037 | Charge overcurrent MSL triggers ERROR | Inject charge current > 180000 mA for 10+ evaluations | DIAG FATAL set; BMS enters ERROR | SW-REQ-011, SW-REQ-032, SW-REQ-043 |
| IT-038 | Deep discharge latches ERROR | Inject cell voltage <= 1500 mV | FATAL set with threshold=1; BMS enters ERROR; does not auto-clear | SW-REQ-005, SW-REQ-045 |
| IT-039 | Current on open string triggers ERROR | Inject current > 200 mA with contactors open | DIAG FATAL set; BMS enters ERROR | SW-REQ-014, SW-REQ-043 |

#### 5.2.2 Diagnostic Debounce Integration

| ID | Test Case | Stimulus | Expected Result | Traces To |
|---|---|---|---|---|
| IT-040 | Overvoltage below threshold count does not trigger ERROR | Inject overvoltage for 49 evaluations, then normal | BMS remains in current state; counter resets | SW-REQ-031, SW-REQ-033 |
| IT-041 | Temperature below threshold count does not trigger ERROR | Inject overtemp for 499 evaluations, then normal | BMS remains in current state | SW-REQ-031, SW-REQ-033 |
| IT-042 | Overcurrent reaches threshold quickly (10 events) | Inject overcurrent continuously | FATAL triggered after 10 events at 100 ms delay | SW-REQ-031 |

#### 5.2.3 Contactor Integration

| ID | Test Case | Stimulus | Expected Result | Traces To |
|---|---|---|---|---|
| IT-050 | Precharge sequence closes correct contactors | Request NORMAL via CAN | Precharge + string- close; string+ closes after precharge | SW-REQ-041, SW-REQ-042 |
| IT-051 | ERROR opens all three contactors | Trigger FATAL event | String+, string-, precharge all commanded OPEN | SW-REQ-044 |
| IT-052 | Contactor feedback mismatch detected | Simulate feedback mismatch (via stub) | DIAG reports contactor feedback event | SW-REQ-044 |

### 5.3 SIL Probe Test Suite (test_sil_probes.py)

| ID | Test Case | Stimulus | Expected Result | Traces To |
|---|---|---|---|---|
| IT-060 | Database entry write observed | Write known value to database entry | SIL probe reads matching value | SW-REQ-060 |
| IT-061 | DIAG counter observable | Trigger diagnostic event | SIL probe reads incremented counter | SW-REQ-031 |
| IT-062 | BMS state observable | Trigger state transition | SIL probe reads new state value | SW-REQ-040 |
| IT-063 | Contactor state observable | Command contactor state | SIL probe reads commanded state | SW-REQ-044 |

## 6. Integration Strategy

### 6.1 Integration Order

Integration follows a bottom-up approach:

1. **Level 1**: HAL stubs + Driver layer (CAN via SocketCAN, SPI/I2C stubs)
2. **Level 2**: Engine layer (Database, DIAG) on top of drivers
3. **Level 3**: Application layer (SOA, BMS, Algorithm) on top of engine
4. **Level 4**: Full system integration with CAN stimulus

### 6.2 Integration Criteria

| Level | Entry Criteria | Exit Criteria |
|---|---|---|
| Level 1 | HAL stubs compile, driver unit tests pass | IT-001 through IT-008 pass |
| Level 2 | Level 1 exit, engine unit tests pass | IT-010 through IT-014 pass |
| Level 3 | Level 2 exit, application unit tests pass | IT-020 through IT-025 pass |
| Level 4 | Level 3 exit | IT-030 through IT-063 all pass |

## 7. Pass/Fail Criteria

- All integration tests shall pass with zero failures.
- No test shall cause a crash, segfault, or timeout.
- CAN message timing shall be within 20% of specified periods.
- State transitions shall occur within 500 ms of stimulus injection.

---

## Traceability: SW-REQ to Integration Test

| SW-REQ | Verified By | Description |
|--------|------------|-------------|
| SW-REQ-001 | IT-036 | Voltage check integration |
| SW-REQ-010 | IT-036 | Voltage check integration |
| SW-REQ-020 | IT-036 | Voltage check integration |
| SW-REQ-040 | IT-001 | State machine integration |
| SW-REQ-044 | IT-050 | Contactor integration |
| SW-REQ-060 | IT-010 | Database integration |
| SW-REQ-070 | IT-011 | SOC integration |
| SW-REQ-090 | IT-002 | CAN TX integration |
| SW-REQ-100 | IT-002 | CAN RX integration |

---
*End of Document*
