# Software Requirements Specification

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SWE.1-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | -- | Initial release |

## 1. Purpose

This document specifies the software-level requirements for the foxBMS 2 POSIX port.
Each requirement is derived from the system requirements in SYS.2-001 and is
traceable forward to detailed design (SWE.3-001) and test cases (SWE.4-001 through
SWE.6-001). This document satisfies ASPICE SWE.1 and ISO 26262 Part 6 Clause 6.

## 2. Scope

All software requirements for the BMS application, engine, and driver layers running
on the POSIX SIL target.

## 3. References

| ID | Title |
|---|---|
| [SYS.2-001] | System Requirements Specification |
| [SWE.2-001] | Software Architecture Description |
| [SWE.3-001] | Software Detailed Design |
| [ISO-SSR-001] | Software Safety Requirements |

## 4. Definitions

| Term | Definition |
|---|---|
| ASIL | Automotive Safety Integrity Level |
| FATAL | Highest DIAG severity; triggers ERROR state |
| DB entry | A typed data structure in the foxBMS database |

## 5. Safety Requirements

### 5.1 Voltage Safety

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-001 | The SOA module shall compare each cell voltage against the overvoltage MSL threshold of 2800 mV. If any cell exceeds this value, SOA shall call DIAG_Handler with the CELL_VOLTAGE_OVERVOLTAGE_MSL event. | SYS-REQ-020 | D |
| SW-REQ-002 | The SOA module shall compare each cell voltage against the undervoltage MSL threshold of 1500 mV. If any cell falls below this value, SOA shall call DIAG_Handler with the CELL_VOLTAGE_UNDERVOLTAGE_MSL event. | SYS-REQ-021 | D |
| SW-REQ-003 | The SOA module shall compare each cell voltage against the overvoltage RSL threshold of 2750 mV and MOL threshold of 2720 mV, reporting the corresponding events. | SYS-REQ-020 | B |
| SW-REQ-004 | The SOA module shall compare each cell voltage against the undervoltage RSL threshold of 1550 mV and MOL threshold of 1580 mV, reporting the corresponding events. | SYS-REQ-021 | B |
| SW-REQ-005 | The SOA module shall detect deep discharge when any cell voltage falls to or below 1500 mV and report DEEP_DISCHARGE_DETECTED. This event shall latch and not auto-clear. | SYS-REQ-022 | D |

### 5.2 Current Safety

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-010 | The SOA module shall compare cell discharge current against MSL threshold of 180000 mA. If exceeded, SOA shall report OVERCURRENT_DISCHARGE_CELL_MSL. | SYS-REQ-030 | D |
| SW-REQ-011 | The SOA module shall compare cell charge current against MSL threshold of 180000 mA. If exceeded, SOA shall report OVERCURRENT_CHARGE_CELL_MSL. | SYS-REQ-031 | D |
| SW-REQ-012 | The SOA module shall compare string current against the string overcurrent discharge and charge thresholds, reporting STRING_OVERCURRENT_DISCHARGE_MSL and STRING_OVERCURRENT_CHARGE_MSL respectively. | SYS-REQ-013 | D |
| SW-REQ-013 | The SOA module shall compare pack current against the pack overcurrent thresholds, reporting PACK_OVERCURRENT_DISCHARGE_MSL and PACK_OVERCURRENT_CHARGE_MSL. | SYS-REQ-014 | D |
| SW-REQ-014 | The SOA module shall detect current flow on an open string and report CURRENT_ON_OPEN_STRING. | SYS-REQ-013 | D |

### 5.3 Temperature Safety

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-020 | The SOA module shall compare each cell temperature against the overtemperature discharge MSL threshold of 55 deg C. If exceeded, SOA shall report TEMP_OVERTEMPERATURE_DISCHARGE_MSL. | SYS-REQ-040 | D |
| SW-REQ-021 | The SOA module shall compare each cell temperature against the undertemperature discharge MSL threshold of -20 deg C. If below, SOA shall report TEMP_UNDERTEMPERATURE_DISCHARGE_MSL. | SYS-REQ-041 | D |
| SW-REQ-022 | The SOA module shall compare each cell temperature against the overtemperature charge MSL threshold of 45 deg C. If exceeded, SOA shall report TEMP_OVERTEMPERATURE_CHARGE_MSL. | SYS-REQ-042 | D |
| SW-REQ-023 | The SOA module shall compare each cell temperature against the undertemperature charge MSL threshold of -20 deg C. If below, SOA shall report TEMP_UNDERTEMPERATURE_CHARGE_MSL. | SYS-REQ-043 | D |

### 5.4 Diagnostic Handling

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-030 | The DIAG module shall maintain a table of at least 85 diagnostic identifiers, each with a configurable threshold counter and evaluation delay. | SYS-REQ-050, SYS-REQ-051, SYS-REQ-052 | D |
| SW-REQ-031 | When DIAG_Handler is called for a diagnostic event, it shall increment the threshold counter for that event. When the counter reaches the configured threshold, the event shall be flagged as FATAL. | SYS-REQ-053 | D |
| SW-REQ-032 | A FATAL diagnostic flag shall cause the BMS state machine to transition to the ERROR state within the next 100ms task cycle. | SYS-REQ-053 | D |
| SW-REQ-033 | The DIAG module shall support a configurable evaluation delay per diagnostic ID. The handler shall not re-evaluate the same event more frequently than this delay. | SYS-REQ-052 | C |
| SW-REQ-034 | The POSIX port shall suppress 24 hardware-absent diagnostic IDs by setting their severity to non-FATAL or disabling evaluation. | SYS-REQ-083 | QM |
| SW-REQ-035 | The POSIX port shall retain 61 software-checkable diagnostic IDs with their original severity and thresholds. | SYS-REQ-084 | D |

### 5.5 BMS State Machine

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-040 | The BMS state machine shall implement the states: STANDBY (5), PRECHARGE (6), NORMAL (7), ERROR (9). | SYS-REQ-071 | D |
| SW-REQ-041 | Transition from STANDBY to PRECHARGE shall occur only upon receipt of a valid state request via CAN ID 0x210. | SYS-REQ-072 | D |
| SW-REQ-042 | Transition from PRECHARGE to NORMAL shall occur when precharge conditions are met (voltage within tolerance). | SYS-REQ-071 | C |
| SW-REQ-043 | Transition from any operational state to ERROR shall occur when any FATAL diagnostic flag is set. | SYS-REQ-073 | D |
| SW-REQ-044 | In ERROR state, the BMS shall command all three contactors (string+, string-, precharge) to open. | SYS-REQ-054 | D |
| SW-REQ-045 | The BMS shall not exit ERROR state until both conditions are met: (a) the originating fault is cleared, and (b) an explicit STANDBY request is received via CAN. | SYS-REQ-055 | D |

### 5.6 System State Machine

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-050 | The SYS state machine shall implement states: UNINITIALIZED (0), INITIALIZATION (1), INITIALIZED (2), IDLE (3), RUNNING (5). | SYS-REQ-070 | C |
| SW-REQ-051 | SYS shall transition from UNINITIALIZED to INITIALIZATION on system startup. | SYS-REQ-070 | C |
| SW-REQ-052 | SYS shall transition from INITIALIZATION to INITIALIZED after all module initialization completes successfully. | SYS-REQ-070 | C |
| SW-REQ-053 | SYS shall transition from IDLE to RUNNING when all subsystems report ready. | SYS-REQ-070 | C |

## 6. Functional Requirements

### 6.1 Database

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-060 | The database shall implement a producer/consumer pattern with single-writer per entry. | SYS-REQ-060 | C |
| SW-REQ-061 | Database read operations shall return the most recent complete write. Partial writes shall not be visible to readers. | SYS-REQ-060 | C |
| SW-REQ-062 | The database shall provide typed entries for cell voltages (18 cells), cell temperatures (8 sensors), string current, pack current, and pack voltage. | SYS-REQ-001 to SYS-REQ-007 | B |

### 6.2 SOC Estimation

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-070 | The algorithm module shall compute state of charge (SOC) using coulomb counting integrated with the current sensor data from CAN IDs 0x521-0x527. | SYS-REQ-010, SYS-REQ-062 | B |
| SW-REQ-071 | The algorithm module shall compute state of energy (SOE) based on SOC and cell voltage. | SYS-REQ-011 | B |

### 6.3 Balancing

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-080 | The balancing module shall identify cells whose voltage exceeds the mean cell voltage by more than a configurable threshold. | SYS-REQ-003 | QM |
| SW-REQ-081 | The balancing module shall activate passive balancing for identified cells when the BMS is in NORMAL state and current is below the rest current threshold (200 mA). | SYS-REQ-016 | QM |

## 7. Interface Requirements

### 7.1 CAN Transmit

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-090 | The CAN module shall transmit BMS state on CAN ID 0x220 every 100 ms. | SYS-REQ-060 | B |
| SW-REQ-091 | The CAN module shall transmit pack details on CAN ID 0x221 every 100 ms. | SYS-REQ-060 | B |
| SW-REQ-092 | The CAN module shall transmit individual cell voltages on CAN IDs 0x240 through 0x245 every 100 ms. | SYS-REQ-060 | B |
| SW-REQ-093 | The CAN module shall transmit multiplexed voltage data on CAN ID 0x250 and temperature data on 0x260 every 100 ms. | SYS-REQ-060 | B |

### 7.2 CAN Receive

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-100 | The CAN module shall receive and decode state requests from CAN ID 0x210. | SYS-REQ-061 | D |
| SW-REQ-101 | The CAN module shall receive and decode IVT current sensor frames from CAN IDs 0x521 through 0x527. | SYS-REQ-062 | C |
| SW-REQ-102 | The CAN module shall receive and decode AFE cell voltages from CAN ID 0x270 (50 mux x 4 voltages). | SYS-REQ-060 | C |
| SW-REQ-103 | The CAN module shall receive and decode AFE cell temperatures from CAN ID 0x280 (30 mux x 6 temperatures). | SYS-REQ-060 | C |

### 7.3 CAN Timing Supervision

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-110 | The CAN module shall monitor message reception timing. If CAN timing exceeds the threshold (100 events, 200 ms delay), DIAG shall flag CAN_TIMING as FATAL. | SYS-REQ-063 | D |
| SW-REQ-111 | The CAN module shall monitor current sensor response. If the current sensor stops responding (100 events, 200 ms delay), DIAG shall flag CURRENT_SENSOR_RESPONDING as FATAL. | SYS-REQ-062 | D |

## 8. POSIX Port-Specific Requirements

| ID | Requirement | Derives From | ASIL |
|---|---|---|---|
| SW-REQ-120 | The POSIX cooperative main loop shall call task functions in priority order: Engine, 1ms, AFE, 10ms, 100ms, I2C, 100ms-Algorithm. | SYS-REQ-081 | QM |
| SW-REQ-121 | The SocketCAN interface shall provide send and receive operations compatible with the foxBMS CAN driver API. | SYS-REQ-082 | QM |
| SW-REQ-122 | HAL stubs shall implement all function signatures of the TMS570 HAL with no-op or RAM-mapped behavior. | SYS-REQ-085, SYS-REQ-086 | QM |
| SW-REQ-123 | The POSIX build shall compile 170+ source files with GCC 13 for x86-64 without errors. | SYS-REQ-080 | QM |

## 9. Acceptance Criteria

Each software requirement is accepted when:

1. It is traced backward to at least one system requirement in SYS.2-001.
2. It is traced forward to detailed design in SWE.3-001.
3. It is covered by at least one test case in SWE.4-001, SWE.5-001, or SWE.6-001.
4. The covering test case passes on the POSIX SIL target.

---
*End of Document*
