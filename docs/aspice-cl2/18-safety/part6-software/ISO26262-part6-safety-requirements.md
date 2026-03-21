# Software Safety Requirements Specification

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| ISO-SSR-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | -- | Initial release |

## 1. Purpose

This document specifies the software safety requirements for the foxBMS 2 POSIX port
per ISO 26262 Part 6 Clause 6. It defines the safety goals, derives Fault Tolerant
Time Intervals (FTTI) from the DIAG configuration, and documents the diagnostic
coverage provided by the threshold counter mechanism.

## 2. Scope

Safety requirements for all ASIL D software functions in the BMS, including voltage,
current, and temperature monitoring, contactor control, and fault management.

## 3. References

| ID | Title |
|---|---|
| [SYS.2-001] | System Requirements Specification |
| [SWE.1-001] | Software Requirements Specification |
| [SWE.3-001] | Software Detailed Design |
| ISO 26262:2018 | Part 6, Clauses 6-10 |
| ISO 26262:2018 | Part 5, Clause 7 (HSI) |

## 4. Definitions

| Term | Definition |
|---|---|
| FTTI | Fault Tolerant Time Interval -- maximum time from fault occurrence to reaching a safe state |
| Safe state | Contactors open, battery disconnected from load |
| Diagnostic coverage | Percentage of faults detectable by the diagnostic mechanism |
| Single-point fault | A fault that directly leads to a safety goal violation |

## 5. Safety Goals

The following safety goals are derived from the hazard and risk analysis for a battery
management system. Each is classified ASIL D.

| ID | Safety Goal | ASIL | Safe State |
|---|---|---|---|
| SG-001 | Prevent battery cell overvoltage leading to thermal runaway | D | Open all contactors |
| SG-002 | Prevent battery cell undervoltage leading to cell damage or reversal | D | Open all contactors |
| SG-003 | Prevent battery overcurrent leading to thermal damage | D | Open all contactors |
| SG-004 | Prevent operation outside safe temperature range | D | Open all contactors |
| SG-005 | Prevent unintended battery re-energization after fault | D | Maintain contactors open; require dual-condition exit |

## 6. Fault Tolerant Time Interval (FTTI) Analysis

The FTTI for each safety-relevant fault is derived from the DIAG configuration:
threshold count, evaluation delay, and the 100 ms BMS task cycle.

```
FTTI = (threshold x delay) + BMS_task_cycle + contactor_open_time
```

Where:
- `threshold` is the DIAG counter limit
- `delay` is the minimum re-evaluation interval
- `BMS_task_cycle` = 100 ms (worst case for BMS to read FATAL flag)
- `contactor_open_time` = 10 ms (contactor driver response)

### 6.1 FTTI Calculation Table

| Safety Goal | DIAG ID | Threshold | Delay (ms) | Max Detection Time (ms) | BMS Cycle (ms) | Contactor (ms) | FTTI (ms) |
|---|---|---|---|---|---|---|---|
| SG-001 (OV) | CELL_VOLTAGE_OVERVOLTAGE_MSL | 50 | 200 | 10000 | 100 | 10 | 10110 |
| SG-002 (UV) | CELL_VOLTAGE_UNDERVOLTAGE_MSL | 50 | 200 | 10000 | 100 | 10 | 10110 |
| SG-003 (OC discharge) | OVERCURRENT_DISCHARGE_CELL_MSL | 10 | 100 | 1000 | 100 | 10 | 1110 |
| SG-003 (OC charge) | OVERCURRENT_CHARGE_CELL_MSL | 10 | 100 | 1000 | 100 | 10 | 1110 |
| SG-003 (String OC) | STRING_OVERCURRENT_DISCHARGE_MSL | 10 | 100 | 1000 | 100 | 10 | 1110 |
| SG-003 (Pack OC) | PACK_OVERCURRENT_DISCHARGE_MSL | 10 | 100 | 1000 | 100 | 10 | 1110 |
| SG-004 (OT disch) | TEMP_OVERTEMPERATURE_DISCHARGE_MSL | 500 | 1000 | 500000 | 100 | 10 | 500110 |
| SG-004 (UT disch) | TEMP_UNDERTEMPERATURE_DISCHARGE_MSL | 500 | 1000 | 500000 | 100 | 10 | 500110 |
| SG-004 (OT charge) | TEMP_OVERTEMPERATURE_CHARGE_MSL | 500 | 1000 | 500000 | 100 | 10 | 500110 |
| SG-004 (UT charge) | TEMP_UNDERTEMPERATURE_CHARGE_MSL | 500 | 1000 | 500000 | 100 | 10 | 500110 |
| SG-005 (deep disch) | DEEP_DISCHARGE_DETECTED | 1 | 100 | 100 | 100 | 10 | 210 |

### 6.2 FTTI Justification

| Category | FTTI | Justification |
|---|---|---|
| Overcurrent | ~1.1 s | Current faults progress rapidly; low threshold (10) ensures fast detection |
| Overvoltage / Undervoltage | ~10.1 s | Voltage changes are bounded by charge/discharge rate; moderate threshold (50) balances noise rejection and response time |
| Temperature | ~500 s (~8.3 min) | Thermal events have large time constants (minutes to hours); high threshold (500) with 1 s delay appropriate for physical dynamics |
| Deep discharge | ~0.21 s | Single-event detection; immediate risk of cell reversal at very low voltage |
| System critical | 0.11 s | SYSTEM_MONITORING, FLASHCHECKSUM, ALERT_MODE have threshold=1 and delay=0; immediate detection |

## 7. Software Safety Requirements

### 7.1 Fault Detection Requirements

| ID | Requirement | Safety Goal | ASIL |
|---|---|---|---|
| SSR-001 | The software shall detect cell overvoltage above 2800 mV within the FTTI of 10.1 seconds. | SG-001 | D |
| SSR-002 | The software shall detect cell undervoltage below 1500 mV within the FTTI of 10.1 seconds. | SG-002 | D |
| SSR-003 | The software shall detect cell discharge overcurrent above 180000 mA within the FTTI of 1.1 seconds. | SG-003 | D |
| SSR-004 | The software shall detect cell charge overcurrent above 180000 mA within the FTTI of 1.1 seconds. | SG-003 | D |
| SSR-005 | The software shall detect overtemperature discharge above 55 deg C within the FTTI of 500.1 seconds. | SG-004 | D |
| SSR-006 | The software shall detect undertemperature discharge below -20 deg C within the FTTI of 500.1 seconds. | SG-004 | D |
| SSR-007 | The software shall detect overtemperature charge above 45 deg C within the FTTI of 500.1 seconds. | SG-004 | D |
| SSR-008 | The software shall detect undertemperature charge below -20 deg C within the FTTI of 500.1 seconds. | SG-004 | D |
| SSR-009 | The software shall detect deep discharge (cell voltage <= 1500 mV) within 0.21 seconds and latch the fault. | SG-002, SG-005 | D |
| SSR-010 | The software shall detect current on an open string within 1.1 seconds. | SG-003 | D |

### 7.2 Fault Reaction Requirements

| ID | Requirement | Safety Goal | ASIL |
|---|---|---|---|
| SSR-020 | Upon detection of any MSL violation (FATAL), the software shall transition the BMS to ERROR state. | SG-001 to SG-004 | D |
| SSR-021 | In ERROR state, the software shall command all three contactors (string+, string-, precharge) to open within one BMS task cycle (100 ms). | SG-001 to SG-004 | D |
| SSR-022 | The software shall not permit the BMS to exit ERROR state unless the originating fault condition has cleared. | SG-005 | D |
| SSR-023 | The software shall not permit the BMS to exit ERROR state unless an explicit STANDBY request has been received via CAN. | SG-005 | D |
| SSR-024 | SSR-022 and SSR-023 must both be satisfied simultaneously for ERROR exit (AND condition). | SG-005 | D |

### 7.3 Diagnostic Coverage Requirements

| ID | Requirement | Safety Goal | ASIL |
|---|---|---|---|
| SSR-030 | The DIAG module shall provide debounced fault detection with configurable threshold counters per diagnostic ID. | SG-001 to SG-004 | D |
| SSR-031 | The DIAG module shall prevent false FATAL triggers from transient measurement noise through threshold counting. | SG-001 to SG-004 | D |
| SSR-032 | The DIAG module shall detect persistent faults by incrementing the counter on each evaluation cycle until the threshold is reached. | SG-001 to SG-004 | D |
| SSR-033 | The DIAG module shall allow fault recovery by decrementing the counter when the fault condition clears. | SG-005 | D |

### 7.4 Communication Safety Requirements

| ID | Requirement | Safety Goal | ASIL |
|---|---|---|---|
| SSR-040 | The software shall detect loss of CAN communication within the configured FTTI (100 events x 200 ms = 20 seconds). | SG-001 to SG-004 | D |
| SSR-041 | The software shall detect loss of current sensor communication within the configured FTTI (100 events x 200 ms = 20 seconds). | SG-003 | D |
| SSR-042 | The software shall detect AFE communication failure within the configured FTTI (5 events x 100 ms = 0.5 seconds). | SG-001, SG-002, SG-004 | D |

### 7.5 Contactor Safety Requirements

| ID | Requirement | Safety Goal | ASIL |
|---|---|---|---|
| SSR-050 | The software shall monitor contactor feedback and detect mismatches within the configured FTTI (20 events x 100 ms = 2 seconds). | SG-001 to SG-005 | D |
| SSR-051 | The software shall not close contactors unless the BMS is in a state that permits contactor closure (PRECHARGE or NORMAL). | SG-005 | D |
| SSR-052 | The software shall respect the contactor maximum break current limit of 3500 mA during normal disconnect sequences. | SG-003 | C |

## 8. Diagnostic Coverage Summary

### 8.1 Coverage by Fault Category

| Fault Category | Detection Mechanism | Diagnostic Coverage | ASIL |
|---|---|---|---|
| Cell overvoltage | SOA voltage check + DIAG counter | High (99%) -- periodic comparison every 100 ms | D |
| Cell undervoltage | SOA voltage check + DIAG counter | High (99%) -- periodic comparison every 100 ms | D |
| Overcurrent | SOA current check + DIAG counter | High (99%) -- periodic comparison every 100 ms | D |
| Overtemperature | SOA temperature check + DIAG counter | High (99%) -- periodic comparison every 100 ms | D |
| Contactor failure | Feedback pin monitoring + DIAG counter | Medium (90%) -- electromechanical failure modes | D |
| CAN communication | Timing supervision + DIAG counter | Medium (90%) -- bus-level faults detectable | D |
| AFE communication | SPI integrity check + DIAG counter | Medium (90%) -- protocol-level faults | D |
| Deep discharge | Voltage comparison, single-event trigger | High (99%) -- threshold = 1 | D |

### 8.2 POSIX Port Diagnostic Coverage

In the POSIX SIL environment, 61 of 85 DIAG IDs (72%) are retained and exercisable.
The 24 suppressed IDs cover hardware-specific faults that cannot be meaningfully
triggered without physical hardware. This represents 100% coverage of all
software-checkable safety paths.

## 9. Freedom from Interference

### 9.1 Data Independence

The database module enforces single-writer-per-entry discipline, preventing data
corruption between modules of different ASIL levels.

### 9.2 Execution Independence

The cooperative main loop executes tasks sequentially. There is no preemption, so
there are no race conditions or priority inversions. Each task runs to completion
before the next begins.

### 9.3 Temporal Independence

Each DIAG entry has an independent evaluation delay and threshold counter. A fault in
one measurement category does not affect the detection timing of another category.

## 10. Acceptance Criteria

This document is accepted when:

1. All FTTI values are verified through integration testing (SWE.5-001).
2. All safety requirements (SSR-xxx) are traced to test cases.
3. Diagnostic coverage claims are supported by test evidence.
4. The safety path (SOA -> DIAG -> BMS -> Contactor) is demonstrated end-to-end.

---
*End of Document*
