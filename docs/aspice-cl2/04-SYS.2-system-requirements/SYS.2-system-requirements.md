# System Requirements Specification

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SYS.2-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | -- | Initial release |

## 1. Purpose

This document specifies the system-level requirements for the foxBMS 2 POSIX port
battery management system. It serves as the primary input to the system architecture
(SYS.3-001) and is the root of the bidirectional traceability chain mandated by
ASPICE SYS.2 and ISO 26262 Part 3.

## 2. Scope

The requirements herein cover the BMS functionality as configured for one battery
string with the cell chemistry and safety parameters defined below. The POSIX port
preserves all software-checkable safety logic while replacing hardware-dependent
interfaces with validated stubs.

## 3. References

| ID | Title |
|---|---|
| [SYS.3-001] | System Architecture Description |
| [SWE.1-001] | Software Requirements Specification |
| [ISO-SSR-001] | Software Safety Requirements |
| foxBMS-DS | foxBMS 2 v1.10.0 Data Sheet |

## 4. Definitions

| Term | Definition |
|---|---|
| MOL | Maximum Operating Limit -- first warning threshold |
| RSL | Recommended Safety Limit -- elevated warning threshold |
| MSL | Maximum Safety Limit -- violation triggers FATAL diagnostic |
| FTTI | Fault Tolerant Time Interval |
| SOA | Safe Operating Area |
| DIAG | Diagnostic module |

## 5. System Requirements

### 5.1 Battery Pack Configuration

| ID | Requirement | Value | Rationale |
|---|---|---|---|
| SYS-REQ-001 | The BMS shall support the configured number of battery strings. | 1 | Single-string topology for SIL validation |
| SYS-REQ-002 | Each string shall contain the configured number of modules. | 1 | Minimum viable pack structure |
| SYS-REQ-003 | Each module shall contain the configured number of cells in series. | 18 | Matches reference cell chemistry voltage range |
| SYS-REQ-004 | Each cell block shall contain the configured number of parallel cells. | 1 | Single parallel cell per block |
| SYS-REQ-005 | Each module shall support the configured number of temperature sensors. | 8 | Sufficient thermal coverage per module |
| SYS-REQ-006 | The system shall manage the configured number of contactors. | 3 (string+, string-, precharge) | Minimum contactor set for safe operation |
| SYS-REQ-007 | The system shall accept HV voltage inputs from current sensor. | 3 inputs | Pack voltage, string voltage, and reference |

### 5.2 Cell Electrical Parameters

| ID | Requirement | Value | Rationale |
|---|---|---|---|
| SYS-REQ-010 | The BMS shall record cell nominal capacity. | 3500 mAh | Cell data sheet parameter |
| SYS-REQ-011 | The BMS shall record cell energy rating. | 10.0 Wh | Cell data sheet parameter |
| SYS-REQ-012 | The BMS shall record cell nominal voltage. | 2500 mV | Cell data sheet parameter |
| SYS-REQ-013 | The BMS shall enforce maximum string current limit. | 2400 mA | Derived from cell current rating and parallel count |
| SYS-REQ-014 | The BMS shall enforce maximum pack current limit. | 2400 mA | Single-string configuration; equals string limit |
| SYS-REQ-015 | Contactor maximum break current shall not be exceeded. | 3500 mA | Contactor derating specification |
| SYS-REQ-016 | The BMS shall detect rest current condition. | 200 mA | Threshold below which pack is considered at rest |

### 5.3 Voltage Safety Thresholds

| ID | Requirement | MOL (mV) | RSL (mV) | MSL (mV) | Action at MSL |
|---|---|---|---|---|---|
| SYS-REQ-020 | Cell overvoltage detection | 2720 | 2750 | 2800 | FATAL: open contactors |
| SYS-REQ-021 | Cell undervoltage detection | 1580 | 1550 | 1500 | FATAL: open contactors |
| SYS-REQ-022 | Deep discharge detection | -- | -- | 1500 | FATAL: open contactors, latch |

### 5.4 Current Safety Thresholds

| ID | Requirement | MOL (mA) | RSL (mA) | MSL (mA) | Action at MSL |
|---|---|---|---|---|---|
| SYS-REQ-030 | Cell discharge overcurrent | 170000 | 175000 | 180000 | FATAL: open contactors |
| SYS-REQ-031 | Cell charge overcurrent | 170000 | 175000 | 180000 | FATAL: open contactors |

### 5.5 Temperature Safety Thresholds

| ID | Requirement | MOL | RSL | MSL | Action at MSL |
|---|---|---|---|---|---|
| SYS-REQ-040 | Overtemperature during discharge | 45 deg C | 50 deg C | 55 deg C | FATAL: open contactors |
| SYS-REQ-041 | Undertemperature during discharge | -10 deg C | -15 deg C | -20 deg C | FATAL: open contactors |
| SYS-REQ-042 | Overtemperature during charge | 35 deg C | 40 deg C | 45 deg C | FATAL: open contactors |
| SYS-REQ-043 | Undertemperature during charge | -10 deg C | -15 deg C | -20 deg C | FATAL: open contactors |

### 5.6 Diagnostic System Requirements

| ID | Requirement | Rationale |
|---|---|---|
| SYS-REQ-050 | The BMS shall maintain a diagnostic module with at least 85 diagnostic identifiers. | Coverage of all monitored parameters |
| SYS-REQ-051 | Each diagnostic identifier shall have a configurable threshold counter before triggering. | Debounce transient faults |
| SYS-REQ-052 | Each diagnostic identifier shall have a configurable evaluation delay. | Allow periodic re-evaluation |
| SYS-REQ-053 | A diagnostic reaching FATAL severity shall cause the BMS to enter ERROR state. | Primary safety mechanism |
| SYS-REQ-054 | In ERROR state the BMS shall open all contactors. | Disconnect battery from load |
| SYS-REQ-055 | The BMS shall not exit ERROR state until the fault is cleared AND an explicit STANDBY request is received. | Prevent unintended re-energization |

### 5.7 Communication Requirements

| ID | Requirement | Rationale |
|---|---|---|
| SYS-REQ-060 | The BMS shall transmit state and measurement data on CAN bus. | Vehicle integration |
| SYS-REQ-061 | The BMS shall receive state requests on CAN bus at ID 0x210. | External control interface |
| SYS-REQ-062 | The BMS shall receive current sensor data on CAN IDs 0x521-0x527. | Isabellenhuette IVT protocol |
| SYS-REQ-063 | The BMS shall detect CAN timing failures within the configured threshold. | Communication integrity |

### 5.8 State Machine Requirements

| ID | Requirement | Rationale |
|---|---|---|
| SYS-REQ-070 | The system state machine shall progress through UNINITIALIZED, INITIALIZATION, INITIALIZED, IDLE, RUNNING. | Orderly system startup |
| SYS-REQ-071 | The BMS state machine shall support states STANDBY, PRECHARGE, NORMAL, ERROR. | Operational mode management |
| SYS-REQ-072 | Transition from STANDBY to PRECHARGE shall require an explicit CAN state request. | Prevent unintended energization |
| SYS-REQ-073 | Transition from any state to ERROR shall occur on any FATAL diagnostic event. | Safety requirement |

### 5.9 POSIX Port Requirements

| ID | Requirement | Rationale |
|---|---|---|
| SYS-REQ-080 | The POSIX port shall compile foxBMS 2 v1.10.0 for x86-64 using GCC 13. | SIL execution target |
| SYS-REQ-081 | The POSIX port shall replace FreeRTOS with a cooperative main loop. | No RTOS on POSIX host |
| SYS-REQ-082 | The POSIX port shall replace hardware CAN with SocketCAN. | Linux-native CAN interface |
| SYS-REQ-083 | The POSIX port shall suppress 24 hardware-absent diagnostic IDs. | Avoid false FATAL on missing hardware |
| SYS-REQ-084 | The POSIX port shall retain 61 software-checkable diagnostic IDs. | Preserve safety logic validation |
| SYS-REQ-085 | The POSIX port shall provide at least 80 HAL stub modules. | Cover all hardware abstraction points |
| SYS-REQ-086 | The POSIX port shall map 60+ TMS570 register bases to RAM buffers. | Enable register-level code to execute without hardware |

## 6. Acceptance Criteria

Each requirement in Section 5 is accepted when:

1. It is traced forward to at least one software requirement in SWE.1-001.
2. It is traced forward to at least one test case in SWE.5-001 or SWE.6-001.
3. The corresponding test case passes in the POSIX SIL environment.

## 7. Open Issues

None at initial release.

---
*End of Document*
