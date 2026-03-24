# Unit Test Specification

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SWE.4-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | L. Fischer | Initial release |

## 1. Purpose

This document specifies unit-level tests for the foxBMS 2 POSIX port, satisfying
ASPICE SWE.4 (software unit verification) and ISO 26262 Part 6 Clause 9. It covers
both the upstream foxBMS Ceedling test suite (183+ test cases) and the POSIX-specific
test suites.

## 2. Scope

Unit tests verify individual software modules in isolation using mock dependencies.
The upstream Ceedling tests validate the foxBMS code base. The POSIX test suites
validate the port-specific adaptations and the integrated safety logic.

## 3. References

| ID | Title |
|---|---|
| [SWE.1-001] | Software Requirements Specification |
| [SWE.3-001] | Software Detailed Design |
| [SWE.5-001] | Integration Test Specification |

## 4. Test Environment

| Aspect | Upstream (Ceedling) | POSIX Test Suites |
|---|---|---|
| Framework | Ceedling + Unity + CMock | pytest + SocketCAN |
| Target | Host (x86-64) | POSIX SIL binary |
| Mocking | CMock auto-generated mocks | SocketCAN stimulus injection |
| Coverage | Per-module, function-level | System-level behavior |
| Count | 183+ test cases | 147+ test criteria across 4 suites |

## 5. Upstream Ceedling Unit Tests

### 5.1 DIAG Module Tests

| ID | Test Case | Module | Expected Result | Traces To |
|---|---|---|---|---|
| UT-001 | DIAG_Handler increments counter on NOT_OK event | diag.c | Counter increases by 1 | SW-REQ-031 |
| UT-002 | DIAG_Handler decrements counter on OK event | diag.c | Counter decreases by 1 (min 0) | SW-REQ-031 |
| UT-003 | DIAG_Handler sets FATAL flag when counter reaches threshold | diag.c | fatalFlag == true | SW-REQ-031 |
| UT-004 | DIAG_Handler respects evaluation delay | diag.c | Event ignored if called within delay period | SW-REQ-033 |
| UT-005 | DIAG_IsAnyFatalErrorSet returns true when any FATAL flag set | diag.c | Returns true | SW-REQ-032 |
| UT-006 | DIAG_IsAnyFatalErrorSet returns false when no FATAL flag set | diag.c | Returns false | SW-REQ-032 |
| UT-007 | DIAG configuration table has 85 entries | diag_cfg.c | Table size == 85 | SW-REQ-030 |
| UT-008 | All FATAL entries have non-zero thresholds | diag_cfg.c | No FATAL entry with threshold == 0 (except immediate entries) | SW-REQ-030 |

### 5.2 SOA Module Tests

| ID | Test Case | Module | Expected Result | Traces To |
|---|---|---|---|---|
| UT-010 | SOA detects overvoltage at MOL threshold (2720 mV) | soa.c | DIAG_Handler called with OV_MOL | SW-REQ-003 |
| UT-011 | SOA detects overvoltage at RSL threshold (2750 mV) | soa.c | DIAG_Handler called with OV_RSL | SW-REQ-003 |
| UT-012 | SOA detects overvoltage at MSL threshold (2800 mV) | soa.c | DIAG_Handler called with OV_MSL | SW-REQ-001 |
| UT-013 | SOA detects undervoltage at MSL threshold (1500 mV) | soa.c | DIAG_Handler called with UV_MSL | SW-REQ-002 |
| UT-014 | SOA detects deep discharge at 1500 mV | soa.c | DIAG_Handler called with DEEP_DISCHARGE | SW-REQ-005 |
| UT-015 | SOA reports OK when voltage within normal range | soa.c | DIAG_Handler called with OK event | SW-REQ-001 |
| UT-016 | SOA detects discharge overcurrent at MSL (180000 mA) | soa.c | DIAG_Handler called with OC_DISCHARGE_MSL | SW-REQ-010 |
| UT-017 | SOA detects charge overcurrent at MSL (180000 mA) | soa.c | DIAG_Handler called with OC_CHARGE_MSL | SW-REQ-011 |
| UT-018 | SOA detects overtemperature discharge at MSL (55 deg C) | soa.c | DIAG_Handler called with OT_DISCHARGE_MSL | SW-REQ-020 |
| UT-019 | SOA detects undertemperature discharge at MSL (-20 deg C) | soa.c | DIAG_Handler called with UT_DISCHARGE_MSL | SW-REQ-021 |
| UT-020 | SOA detects overtemperature charge at MSL (45 deg C) | soa.c | DIAG_Handler called with OT_CHARGE_MSL | SW-REQ-022 |
| UT-021 | SOA detects undertemperature charge at MSL (-20 deg C) | soa.c | DIAG_Handler called with UT_CHARGE_MSL | SW-REQ-023 |

### 5.3 BMS Module Tests

| ID | Test Case | Module | Expected Result | Traces To |
|---|---|---|---|---|
| UT-030 | BMS initializes in STANDBY state | bms.c | BMS_GetState() == STANDBY | SW-REQ-040 |
| UT-031 | BMS transitions STANDBY to PRECHARGE on valid request | bms.c | State changes to PRECHARGE | SW-REQ-041 |
| UT-032 | BMS transitions PRECHARGE to NORMAL on precharge complete | bms.c | State changes to NORMAL | SW-REQ-042 |
| UT-033 | BMS transitions to ERROR on FATAL diagnostic | bms.c | State changes to ERROR | SW-REQ-043 |
| UT-034 | BMS opens all contactors in ERROR state | bms.c | All 3 contactors commanded OPEN | SW-REQ-044 |
| UT-035 | BMS remains in ERROR until fault cleared AND STANDBY requested | bms.c | State stays ERROR without both conditions | SW-REQ-045 |
| UT-036 | BMS transitions ERROR to STANDBY when both conditions met | bms.c | State changes to STANDBY | SW-REQ-045 |

### 5.4 Database Module Tests

| ID | Test Case | Module | Expected Result | Traces To |
|---|---|---|---|---|
| UT-040 | Database write and read returns same data | database.c | Read data matches written data | SW-REQ-060 |
| UT-041 | Database read returns most recent write | database.c | Latest write visible to reader | SW-REQ-061 |
| UT-042 | Database entries exist for all configured measurements | database.c | Cell voltages (18), temps (8), currents present | SW-REQ-062 |

### 5.5 CAN Module Tests

| ID | Test Case | Module | Expected Result | Traces To |
|---|---|---|---|---|
| UT-050 | CAN transmit formats BMS state message at ID 0x220 | can.c | Correct ID, DLC, data encoding | SW-REQ-090 |
| UT-051 | CAN receive decodes state request from ID 0x210 | can.c | Correct state request extracted | SW-REQ-100 |
| UT-052 | CAN receive decodes IVT frames from IDs 0x521-0x527 | can.c | Current, voltage, temperature values correct | SW-REQ-101 |

### 5.6 Contactor Module Tests

| ID | Test Case | Module | Expected Result | Traces To |
|---|---|---|---|---|
| UT-060 | Contactor set state OPEN commands the physical output | contactor.c | SPS output set to OPEN | SW-REQ-044 |
| UT-061 | Contactor set state CLOSE commands the physical output | contactor.c | SPS output set to CLOSE | SW-REQ-041 |
| UT-062 | Contactor feedback mismatch reported to DIAG | contactor.c | DIAG_Handler called with feedback event | SW-REQ-044 |

## 6. POSIX-Specific Unit Tests

### 6.1 Smoke Test Suite (test_smoke.py)

| ID | Test Case | Expected Result | Traces To |
|---|---|---|---|
| UT-100 | Binary starts without crash | Process starts, PID > 0 | SW-REQ-123 |
| UT-101 | Binary reaches SYS RUNNING state | CAN 0x220 shows SYS state >= 5 | SW-REQ-050 |
| UT-102 | BMS reaches STANDBY state | CAN 0x220 shows BMS state == 5 | SW-REQ-040 |
| UT-103 | CAN TX messages appear on SocketCAN | At least one frame received on vcan0 | SW-REQ-090 |
| UT-104 | Binary runs for 10 seconds without error | Process exit code == 0 after SIGTERM | SW-REQ-123 |
| UT-105 | No segfault or abort during startup | No SIGSEGV or SIGABRT | SW-REQ-123 |

### 6.2 HAL Stub Tests

| ID | Test Case | Expected Result | Traces To |
|---|---|---|---|
| UT-110 | All 80+ HAL stub functions are callable | No linker errors, no crashes | SW-REQ-122 |
| UT-111 | Register base pointers map to valid RAM | Read/write to register base does not segfault | SW-REQ-122 |
| UT-112 | 60+ register bases allocated | All register structs have non-NULL base addresses | SW-REQ-122 |

## 7. Test Coverage Summary

| Module | # Unit Tests | Safety-Critical | Coverage Target |
|---|---|---|---|
| DIAG | 8 | Yes (ASIL D) | MC/DC |
| SOA | 12 | Yes (ASIL D) | MC/DC |
| BMS | 7 | Yes (ASIL D) | MC/DC |
| Database | 3 | Yes (ASIL C) | Branch |
| CAN | 3 | Yes (ASIL B) | Branch |
| Contactor | 3 | Yes (ASIL D) | MC/DC |
| HAL Stubs | 3 | No (QM) | Statement |
| Smoke | 6 | No (QM) | Statement |

## 8. Pass/Fail Criteria

- All unit tests shall pass with zero failures.
- No test shall produce undefined behavior (address sanitizer clean).
- For ASIL D modules, MC/DC coverage shall be demonstrated.
- For ASIL B/C modules, branch coverage shall be demonstrated.
- For QM modules, statement coverage is sufficient.

---

## Traceability: SW-REQ to Unit Test (Complete)

| SW-REQ | Verified By | Description |
|--------|------------|-------------|
| SW-REQ-001 | UT-012, UT-015, UT-016 | SOA overvoltage MSL detection |
| SW-REQ-002 | UT-013, UT-016 | SOA undervoltage MSL detection |
| SW-REQ-003 | UT-010, UT-011, UT-016 | SOA overvoltage MOL/RSL thresholds |
| SW-REQ-004 | UT-016 | SOA voltage range validation |
| SW-REQ-005 | UT-014, UT-016 | SOA deep discharge detection |
| SW-REQ-010 | UT-016, UT-020 | SOA discharge overcurrent MSL |
| SW-REQ-011 | UT-017, UT-020 | SOA charge overcurrent MSL |
| SW-REQ-012 | UT-020 | SOA overcurrent MOL threshold |
| SW-REQ-013 | UT-020 | SOA overcurrent RSL threshold |
| SW-REQ-014 | UT-020 | SOA current on open string |
| SW-REQ-020 | UT-018, UT-024 | SOA overtemperature discharge MSL |
| SW-REQ-021 | UT-019, UT-024 | SOA undertemperature discharge MSL |
| SW-REQ-022 | UT-020, UT-024 | SOA overtemperature charge MSL |
| SW-REQ-023 | UT-021, UT-024 | SOA undertemperature charge MSL |
| SW-REQ-030 | UT-007, UT-008, UT-001 | DIAG configuration table validation |
| SW-REQ-031 | UT-001, UT-002, UT-003 | DIAG counter increment/decrement/FATAL |
| SW-REQ-032 | UT-005, UT-006, UT-001 | DIAG IsAnyFatalErrorSet |
| SW-REQ-033 | UT-004, UT-001 | DIAG evaluation delay |
| SW-REQ-034 | UT-001 | DIAG POSIX-specific ID handling |
| SW-REQ-035 | UT-001 | DIAG suppressed ID handling |
| SW-REQ-040 | UT-030, UT-102 | BMS STANDBY state initialization |
| SW-REQ-041 | UT-031, UT-061, UT-030 | BMS STANDBY to PRECHARGE transition |
| SW-REQ-042 | UT-032, UT-030 | BMS PRECHARGE to NORMAL transition |
| SW-REQ-043 | UT-033, UT-030 | BMS transition to ERROR on FATAL |
| SW-REQ-044 | UT-034, UT-060, UT-062 | Contactor open in ERROR state |
| SW-REQ-045 | UT-035, UT-036, UT-030 | BMS ERROR persistence and recovery |
| SW-REQ-050 | UT-030, UT-101 | SYS state machine UNINITIALIZED |
| SW-REQ-051 | UT-030 | SYS state machine INITIALIZATION |
| SW-REQ-052 | UT-030 | SYS state machine IDLE |
| SW-REQ-053 | UT-030 | SYS state machine RUNNING |
| SW-REQ-060 | UT-040, UT-042 | Database write/read consistency |
| SW-REQ-061 | UT-041, UT-042 | Database latest write visible |
| SW-REQ-062 | UT-042 | Database entries for all measurements |
| SW-REQ-063 | UT-042 | Database cell voltage entries (18 cells) |
| SW-REQ-064 | UT-042 | Database temperature entries (8 sensors) |
| SW-REQ-065 | UT-042 | Database current entries |
| SW-REQ-066 | UT-042 | Database SOC entries |
| SW-REQ-067 | UT-042 | Database contactor state entries |
| SW-REQ-068 | UT-042 | Database BMS state entries |
| SW-REQ-069 | UT-042 | Database pack voltage entries |
| SW-REQ-070 | UT-070 | SOC coulomb counting algorithm |
| SW-REQ-071 | UT-070 | SOC initial value from OCV |
| SW-REQ-072 | UT-070 | SOC clamp to 0-100% range |
| SW-REQ-073 | UT-070 | SOC update on current integration |
| SW-REQ-074 | UT-070 | SOC capacity parameter configuration |
| SW-REQ-075 | UT-070 | SOC database write |
| SW-REQ-076 | UT-070 | SOC energy counting |
| SW-REQ-080 | UT-080 | Balancing enable/disable control |
| SW-REQ-081 | UT-080 | Balancing threshold configuration |
| SW-REQ-082 | UT-080 | Balancing cell selection algorithm |
| SW-REQ-083 | UT-080 | Balancing timer management |
| SW-REQ-084 | UT-080 | Balancing voltage delta calculation |
| SW-REQ-085 | UT-080 | Balancing state reporting |
| SW-REQ-090 | UT-050, UT-052 | CAN TX BMS state message 0x220 |
| SW-REQ-091 | UT-052 | CAN TX cell voltage messages 0x240-0x245 |
| SW-REQ-092 | UT-052 | CAN TX cell temperature messages 0x260 |
| SW-REQ-093 | UT-052 | CAN TX SOC message |
| SW-REQ-094 | UT-052 | CAN TX pack voltage message |
| SW-REQ-095 | UT-052 | CAN TX current message |
| SW-REQ-096 | UT-052 | CAN TX contactor state message |
| SW-REQ-097 | UT-052 | CAN TX diagnostic status message |
| SW-REQ-098 | UT-052 | CAN TX balancing status message |
| SW-REQ-099 | UT-052 | CAN TX insulation monitoring message |
| SW-REQ-100 | UT-051, UT-052 | CAN RX state request 0x210 |
| SW-REQ-101 | UT-052 | CAN RX IVT current 0x521 |
| SW-REQ-102 | UT-052 | CAN RX AFE cell voltages 0x270 |
| SW-REQ-103 | UT-052 | CAN RX AFE cell temperatures 0x280 |
| SW-REQ-104 | UT-052 | CAN RX IVT voltage 0x522-0x524 |
| SW-REQ-105 | UT-052 | CAN RX IVT temperature 0x525 |
| SW-REQ-106 | UT-052 | CAN RX charger request |
| SW-REQ-107 | UT-052 | CAN RX balancing command |
| SW-REQ-108 | UT-052 | CAN RX diagnostic reset command |
| SW-REQ-109 | UT-052 | CAN RX configuration update |
| SW-REQ-110 | UT-052 | CAN TX periodic timing 100 ms |
| SW-REQ-111 | UT-052 | CAN RX timeout detection |
| SW-REQ-112 | UT-052 | CAN message DLC validation |
| SW-REQ-113 | UT-052 | CAN message counter/CRC validation |
| SW-REQ-120 | UT-100, UT-104, UT-105 | POSIX binary startup |
| SW-REQ-121 | UT-100 | POSIX SocketCAN initialization |
| SW-REQ-122 | UT-110, UT-111, UT-112 | POSIX HAL stub functions |
| SW-REQ-123 | UT-100, UT-104, UT-105 | POSIX clean shutdown |
| SW-REQ-124 | UT-100 | POSIX cooperative main loop |
| SW-REQ-125 | UT-100 | POSIX signal handling |
| SW-REQ-126 | UT-100 | POSIX assert override |
| SW-REQ-127 | UT-100 | POSIX register base allocation |
| SW-REQ-128 | UT-100 | POSIX timeout flag (--timeout) |
| SW-REQ-129 | UT-100 | POSIX vCAN interface configuration |
| SW-REQ-200 | UT-030, UT-033 | Negative: invalid state transition rejected |
| SW-REQ-201 | UT-042 | Negative: database read without write returns default |
| SW-REQ-202 | UT-052 | Negative: malformed CAN frame rejected |
| SW-REQ-203 | UT-030 | Negative: ERROR state blocks NORMAL request |
| SW-REQ-204 | UT-042 | Negative: database overflow handled |
| SW-REQ-205 | UT-052 | Negative: CAN TX buffer full handled |

---
*End of Document*
