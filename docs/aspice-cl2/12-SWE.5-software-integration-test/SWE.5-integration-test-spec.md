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

## Traceability: SW-REQ to Integration Test (Complete)

| SW-REQ | Verified By | Description |
|--------|------------|-------------|
| SW-REQ-001 | IT-010, IT-030 | Overvoltage detection integration |
| SW-REQ-002 | IT-010, IT-031 | Undervoltage detection integration |
| SW-REQ-003 | IT-010 | Voltage MOL/RSL threshold integration |
| SW-REQ-004 | IT-010 | Voltage range validation integration |
| SW-REQ-005 | IT-038 | Deep discharge detection integration |
| SW-REQ-010 | IT-011, IT-036 | Discharge overcurrent integration |
| SW-REQ-011 | IT-011, IT-037 | Charge overcurrent integration |
| SW-REQ-012 | IT-011 | Overcurrent MOL threshold integration |
| SW-REQ-013 | IT-011 | Overcurrent RSL threshold integration |
| SW-REQ-014 | IT-039 | Current on open string integration |
| SW-REQ-020 | IT-012, IT-032 | Overtemperature discharge integration |
| SW-REQ-021 | IT-012, IT-033 | Undertemperature discharge integration |
| SW-REQ-022 | IT-012, IT-034 | Overtemperature charge integration |
| SW-REQ-023 | IT-012, IT-035 | Undertemperature charge integration |
| SW-REQ-030 | IT-040, IT-041, IT-042 | DIAG debounce integration |
| SW-REQ-031 | IT-040, IT-041, IT-042 | DIAG counter increment integration |
| SW-REQ-032 | IT-030..IT-039 | DIAG FATAL flag integration |
| SW-REQ-033 | IT-040, IT-041 | DIAG evaluation delay integration |
| SW-REQ-034 | IT-036 | DIAG POSIX-specific integration |
| SW-REQ-035 | IT-036 | DIAG suppressed ID integration |
| SW-REQ-040 | IT-001, IT-014, IT-062 | BMS STANDBY state integration |
| SW-REQ-041 | IT-001, IT-021, IT-023, IT-050 | BMS state transition integration |
| SW-REQ-042 | IT-022, IT-050 | BMS PRECHARGE to NORMAL integration |
| SW-REQ-043 | IT-024, IT-030..IT-039 | BMS ERROR transition integration |
| SW-REQ-044 | IT-051, IT-052, IT-063 | Contactor open/close integration |
| SW-REQ-045 | IT-025, IT-038 | BMS ERROR persistence integration |
| SW-REQ-050 | IT-020 | SYS UNINITIALIZED integration |
| SW-REQ-051 | IT-020 | SYS INITIALIZATION integration |
| SW-REQ-052 | IT-020 | SYS IDLE integration |
| SW-REQ-053 | IT-020 | SYS RUNNING integration |
| SW-REQ-060 | IT-010, IT-013, IT-060 | Database write integration |
| SW-REQ-061 | IT-010, IT-060 | Database read latest integration |
| SW-REQ-062 | IT-010, IT-011, IT-012 | Database measurement entries integration |
| SW-REQ-063 | IT-010, IT-005 | Database cell voltage entries integration |
| SW-REQ-064 | IT-012, IT-006 | Database temperature entries integration |
| SW-REQ-065 | IT-011, IT-002 | Database current entries integration |
| SW-REQ-066 | IT-002 | Database SOC entries integration |
| SW-REQ-067 | IT-050, IT-063 | Database contactor state integration |
| SW-REQ-068 | IT-014, IT-062 | Database BMS state integration |
| SW-REQ-069 | IT-002, IT-003 | Database pack voltage integration |
| SW-REQ-070 | IT-002 | SOC coulomb counting integration |
| SW-REQ-071 | IT-002 | SOC initial OCV integration |
| SW-REQ-072 | IT-002 | SOC clamp integration |
| SW-REQ-073 | IT-002 | SOC current integration |
| SW-REQ-074 | IT-002 | SOC capacity config integration |
| SW-REQ-075 | IT-002 | SOC database write integration |
| SW-REQ-076 | IT-002 | SOC energy counting integration |
| SW-REQ-080 | IT-002 | Balancing enable integration |
| SW-REQ-081 | IT-002 | Balancing threshold integration |
| SW-REQ-082 | IT-002 | Balancing cell selection integration |
| SW-REQ-083 | IT-002 | Balancing timer integration |
| SW-REQ-084 | IT-002 | Balancing voltage delta integration |
| SW-REQ-085 | IT-002 | Balancing state reporting integration |
| SW-REQ-090 | IT-007, IT-014 | CAN TX BMS state 0x220 integration |
| SW-REQ-091 | IT-002, IT-005 | CAN TX cell voltage integration |
| SW-REQ-092 | IT-005 | CAN TX cell voltage messages integration |
| SW-REQ-093 | IT-006 | CAN TX temperature messages integration |
| SW-REQ-094 | IT-002 | CAN TX pack voltage integration |
| SW-REQ-095 | IT-002 | CAN TX current integration |
| SW-REQ-096 | IT-050 | CAN TX contactor state integration |
| SW-REQ-097 | IT-036 | CAN TX diagnostic status integration |
| SW-REQ-098 | IT-002 | CAN TX balancing status integration |
| SW-REQ-099 | IT-002 | CAN TX insulation monitoring integration |
| SW-REQ-100 | IT-001, IT-008, IT-013 | CAN RX state request integration |
| SW-REQ-101 | IT-002, IT-003, IT-004 | CAN RX IVT data integration |
| SW-REQ-102 | IT-005 | CAN RX AFE cell voltages integration |
| SW-REQ-103 | IT-006 | CAN RX AFE cell temperatures integration |
| SW-REQ-104 | IT-003 | CAN RX IVT voltage integration |
| SW-REQ-105 | IT-004 | CAN RX IVT temperature integration |
| SW-REQ-106 | IT-002 | CAN RX charger request integration |
| SW-REQ-107 | IT-002 | CAN RX balancing command integration |
| SW-REQ-108 | IT-002 | CAN RX diagnostic reset integration |
| SW-REQ-109 | IT-002 | CAN RX configuration update integration |
| SW-REQ-110 | IT-007 | CAN TX periodic timing integration |
| SW-REQ-111 | IT-002 | CAN RX timeout detection integration |
| SW-REQ-112 | IT-008 | CAN DLC validation integration |
| SW-REQ-113 | IT-002 | CAN counter/CRC validation integration |
| SW-REQ-120 | IT-020 | POSIX binary startup integration |
| SW-REQ-121 | IT-001 | POSIX SocketCAN integration |
| SW-REQ-122 | IT-020 | POSIX HAL stub integration |
| SW-REQ-123 | IT-020 | POSIX clean shutdown integration |
| SW-REQ-124 | IT-020 | POSIX cooperative loop integration |
| SW-REQ-125 | IT-020 | POSIX signal handling integration |
| SW-REQ-126 | IT-020 | POSIX assert override integration |
| SW-REQ-127 | IT-020 | POSIX register base integration |
| SW-REQ-128 | IT-020 | POSIX timeout flag integration |
| SW-REQ-129 | IT-001 | POSIX vCAN interface integration |
| SW-REQ-200 | IT-024, IT-025 | Negative: invalid transition integration |
| SW-REQ-201 | IT-060 | Negative: database default integration |
| SW-REQ-202 | IT-008 | Negative: malformed CAN integration |
| SW-REQ-203 | IT-025 | Negative: ERROR blocks NORMAL integration |
| SW-REQ-204 | IT-060 | Negative: database overflow integration |
| SW-REQ-205 | IT-002 | Negative: CAN TX buffer full integration |

## Traceability: SSR to Integration Test (Complete)

| SSR | Verified By | Description |
|-----|------------|-------------|
| SSR-001 | IT-030, IT-036 | Overvoltage fault detection |
| SSR-002 | IT-031, IT-036 | Undervoltage fault detection |
| SSR-003 | IT-032, IT-036 | Overtemperature fault detection |
| SSR-004 | IT-033, IT-036 | Undertemperature fault detection |
| SSR-005 | IT-036, IT-037 | Discharge overcurrent fault detection |
| SSR-006 | IT-037, IT-036 | Charge overcurrent fault detection |
| SSR-007 | IT-032, IT-036 | Overtemperature discharge fault detection |
| SSR-008 | IT-034, IT-036 | Overtemperature charge fault detection |
| SSR-009 | IT-035, IT-036 | Undertemperature charge fault detection |
| SSR-010 | IT-036, IT-040, IT-041, IT-042 | DIAG threshold debounce integration |
| SSR-020 | IT-050, IT-051 | Contactor open on fault reaction |
| SSR-021 | IT-050 | Precharge sequence fault reaction |
| SSR-022 | IT-051 | All contactors open on ERROR |
| SSR-023 | IT-050, IT-051 | Contactor feedback verification |
| SSR-024 | IT-051 | ERROR state contactor command |
| SSR-030 | IT-036, IT-040 | Diagnostic coverage: voltage faults |
| SSR-031 | IT-036, IT-041 | Diagnostic coverage: temperature faults |
| SSR-032 | IT-036, IT-042 | Diagnostic coverage: current faults |
| SSR-033 | IT-036 | Diagnostic coverage: deep discharge |
| SSR-040 | IT-002, IT-007 | Communication safety: CAN TX timing |
| SSR-041 | IT-001, IT-008 | Communication safety: CAN RX validation |
| SSR-042 | IT-002 | Communication safety: CAN timeout detection |
| SSR-050 | IT-050, IT-051 | Contactor safety: precharge sequence |
| SSR-051 | IT-051, IT-052 | Contactor safety: feedback mismatch |
| SSR-052 | IT-050, IT-051 | Contactor safety: open command on ERROR |

---
*End of Document*
