# Bidirectional Traceability Matrix

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| ISO-TRC-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | Dr. K. Richter | Initial release |

## 1. Purpose

This document provides the bidirectional traceability matrix required by ISO 26262
Part 8 Clause 6 and ASPICE generic practices (GP 2.2.4). It traces from system
requirements through software requirements, detailed design, implementation, and test
cases, enabling complete forward and backward navigation of the requirement chain.

## 2. Scope

The matrix covers all requirements from SYS.2-001 (system requirements), SWE.1-001
(software requirements), ISO-SSR-001 (safety requirements), and their traces to design
(SWE.3-001), code modules, and test cases (SWE.4-001, SWE.5-001, SWE.6-001).

## 3. References

| ID | Title |
|---|---|
| [SYS.2-001] | System Requirements Specification |
| [SWE.1-001] | Software Requirements Specification |
| [SWE.3-001] | Software Detailed Design |
| [SWE.4-001] | Unit Test Specification |
| [SWE.5-001] | Integration Test Specification |
| [SWE.6-001] | Qualification Test Specification |
| [ISO-SSR-001] | Software Safety Requirements |

## 4. Traceability Convention

Each row traces one requirement through the full chain:

- **System Req** (SYS-REQ-xxx) -- from SYS.2-001
- **Software Req** (SW-REQ-xxx) -- from SWE.1-001
- **Safety Req** (SSR-xxx) -- from ISO-SSR-001 (where applicable)
- **Design** -- detailed design section in SWE.3-001
- **Code Module** -- implementation source file(s)
- **Unit Test** (UT-xxx) -- from SWE.4-001
- **Integration Test** (IT-xxx) -- from SWE.5-001
- **Qualification Test** (QT-xxx) -- from SWE.6-001

## 5. Forward Traceability: System Requirements to Tests

### 5.1 Battery Pack Configuration (SYS-REQ-001 to SYS-REQ-007)

| System Req | Software Req | Safety Req | Design | Code Module | Unit Test | Integration Test | Qualification Test |
|---|---|---|---|---|---|---|---|
| SYS-REQ-001 | SW-REQ-062 | -- | Sec 4.3 | database.c, battery_system_cfg.h | UT-042 | IT-010 | QT-001 |
| SYS-REQ-002 | SW-REQ-062 | -- | Sec 4.3 | database.c, battery_system_cfg.h | UT-042 | IT-010 | QT-001 |
| SYS-REQ-003 | SW-REQ-062, SW-REQ-080 | -- | Sec 4.3 | database.c, balancing.c | UT-042 | IT-010 | QT-001 |
| SYS-REQ-004 | SW-REQ-062 | -- | Sec 4.3 | battery_system_cfg.h | UT-042 | IT-010 | QT-001 |
| SYS-REQ-005 | SW-REQ-062 | -- | Sec 4.3 | database.c, battery_system_cfg.h | UT-042 | IT-012 | QT-001 |
| SYS-REQ-006 | SW-REQ-044 | SSR-051 | Sec 6.4 | contactor.c | UT-060, UT-061 | IT-050, IT-051 | QT-001 |
| SYS-REQ-007 | SW-REQ-101 | -- | Sec 4.3 | can.c, can_cfg.c | UT-052 | IT-002 | QT-001 |

### 5.2 Cell Electrical Parameters (SYS-REQ-010 to SYS-REQ-016)

| System Req | Software Req | Safety Req | Design | Code Module | Unit Test | Integration Test | Qualification Test |
|---|---|---|---|---|---|---|---|
| SYS-REQ-010 | SW-REQ-070 | -- | Sec 4.3 | algorithm.c, battery_cell_cfg.h | -- | IT-011 | QT-001 |
| SYS-REQ-011 | SW-REQ-071 | -- | Sec 4.3 | algorithm.c, battery_cell_cfg.h | -- | IT-011 | QT-001 |
| SYS-REQ-012 | SW-REQ-070 | -- | Sec 4.3 | battery_cell_cfg.h | -- | IT-011 | QT-001 |
| SYS-REQ-013 | SW-REQ-012 | SSR-003 | Sec 5.2.2 | soa.c, soa_cfg.c | UT-016 | IT-036 | QT-004 |
| SYS-REQ-014 | SW-REQ-013 | SSR-003 | Sec 5.2.2 | soa.c, soa_cfg.c | UT-016 | IT-036 | QT-004 |
| SYS-REQ-015 | SW-REQ-044 | SSR-052 | Sec 6.4 | contactor.c | UT-060 | IT-051 | QT-002 |
| SYS-REQ-016 | SW-REQ-081 | -- | Sec 5.2.2 | balancing.c | -- | IT-010 | QT-001 |

### 5.3 Voltage Safety Thresholds (SYS-REQ-020 to SYS-REQ-022)

| System Req | Software Req | Safety Req | Design | Code Module | Unit Test | Integration Test | Qualification Test |
|---|---|---|---|---|---|---|---|
| SYS-REQ-020 | SW-REQ-001, SW-REQ-003 | SSR-001 | Sec 5.2.1 | soa.c, soa_cfg.c | UT-010, UT-011, UT-012 | IT-030 | QT-002 |
| SYS-REQ-021 | SW-REQ-002, SW-REQ-004 | SSR-002 | Sec 5.2.1 | soa.c, soa_cfg.c | UT-013, UT-015 | IT-031 | QT-003 |
| SYS-REQ-022 | SW-REQ-005 | SSR-009 | Sec 5.2.1 | soa.c, diag.c | UT-014 | IT-038 | QT-003 |

### 5.4 Current Safety Thresholds (SYS-REQ-030 to SYS-REQ-031)

| System Req | Software Req | Safety Req | Design | Code Module | Unit Test | Integration Test | Qualification Test |
|---|---|---|---|---|---|---|---|
| SYS-REQ-030 | SW-REQ-010 | SSR-003 | Sec 5.2.2 | soa.c, soa_cfg.c | UT-016 | IT-036 | QT-004 |
| SYS-REQ-031 | SW-REQ-011 | SSR-004 | Sec 5.2.2 | soa.c, soa_cfg.c | UT-017 | IT-037 | QT-004 |

### 5.5 Temperature Safety Thresholds (SYS-REQ-040 to SYS-REQ-043)

| System Req | Software Req | Safety Req | Design | Code Module | Unit Test | Integration Test | Qualification Test |
|---|---|---|---|---|---|---|---|
| SYS-REQ-040 | SW-REQ-020 | SSR-005 | Sec 5.2.3 | soa.c, soa_cfg.c | UT-018 | IT-032 | QT-005 |
| SYS-REQ-041 | SW-REQ-021 | SSR-006 | Sec 5.2.3 | soa.c, soa_cfg.c | UT-019 | IT-033 | QT-005 |
| SYS-REQ-042 | SW-REQ-022 | SSR-007 | Sec 5.2.3 | soa.c, soa_cfg.c | UT-020 | IT-034 | QT-005 |
| SYS-REQ-043 | SW-REQ-023 | SSR-008 | Sec 5.2.3 | soa.c, soa_cfg.c | UT-021 | IT-035 | QT-005 |

### 5.6 Diagnostic System (SYS-REQ-050 to SYS-REQ-055)

| System Req | Software Req | Safety Req | Design | Code Module | Unit Test | Integration Test | Qualification Test |
|---|---|---|---|---|---|---|---|
| SYS-REQ-050 | SW-REQ-030 | SSR-030 | Sec 4.2, 4.3 | diag.c, diag_cfg.c | UT-001, UT-007 | IT-040 | QT-007 |
| SYS-REQ-051 | SW-REQ-031 | SSR-032 | Sec 4.2 | diag.c | UT-001, UT-003 | IT-042 | QT-004 |
| SYS-REQ-052 | SW-REQ-033 | SSR-031 | Sec 4.2 | diag.c | UT-004 | IT-040, IT-041 | QT-005 |
| SYS-REQ-053 | SW-REQ-032 | SSR-020 | Sec 4.2, 6.3 | diag.c, bms.c | UT-003, UT-005 | IT-030 to IT-039 | QT-002 to QT-005 |
| SYS-REQ-054 | SW-REQ-044 | SSR-021 | Sec 6.3, 6.4 | bms.c, contactor.c | UT-034 | IT-051 | QT-002 |
| SYS-REQ-055 | SW-REQ-045 | SSR-022, SSR-023, SSR-024 | Sec 6.2, 6.3 | bms.c | UT-035, UT-036 | IT-025 | QT-002, QT-007 |

### 5.7 Communication (SYS-REQ-060 to SYS-REQ-063)

| System Req | Software Req | Safety Req | Design | Code Module | Unit Test | Integration Test | Qualification Test |
|---|---|---|---|---|---|---|---|
| SYS-REQ-060 | SW-REQ-090 to SW-REQ-093 | -- | Sec 4.1 | can.c, can_cfg.c | UT-050 | IT-007 | QT-001 |
| SYS-REQ-061 | SW-REQ-100 | -- | Sec 4.1 | can.c, can_cfg.c | UT-051 | IT-001, IT-013 | QT-001 |
| SYS-REQ-062 | SW-REQ-101, SW-REQ-111 | SSR-041 | Sec 4.1 | can.c, can_cfg.c | UT-052 | IT-002 to IT-004 | QT-001, QT-006 |
| SYS-REQ-063 | SW-REQ-110 | SSR-040 | Sec 4.3 | can.c, diag.c | -- | IT-007 | QT-006 |

### 5.8 State Machines (SYS-REQ-070 to SYS-REQ-073)

| System Req | Software Req | Safety Req | Design | Code Module | Unit Test | Integration Test | Qualification Test |
|---|---|---|---|---|---|---|---|
| SYS-REQ-070 | SW-REQ-050 to SW-REQ-053 | -- | Sec 6.1 | sys.c | -- | IT-020 | QT-001 |
| SYS-REQ-071 | SW-REQ-040 | SSR-020, SSR-021 | Sec 6.2 | bms.c | UT-030 | IT-021 to IT-024 | QT-001 |
| SYS-REQ-072 | SW-REQ-041 | SSR-051 | Sec 6.2 | bms.c | UT-031 | IT-021 | QT-001 |
| SYS-REQ-073 | SW-REQ-043 | SSR-020 | Sec 6.2 | bms.c | UT-033 | IT-024, IT-030 to IT-039 | QT-002 to QT-005 |

### 5.9 POSIX Port (SYS-REQ-080 to SYS-REQ-086)

| System Req | Software Req | Safety Req | Design | Code Module | Unit Test | Integration Test | Qualification Test |
|---|---|---|---|---|---|---|---|
| SYS-REQ-080 | SW-REQ-123 | -- | -- | Makefile, main.c | UT-100 | -- | QT-001 |
| SYS-REQ-081 | SW-REQ-120 | -- | -- | main.c | UT-100, UT-101 | IT-020 | QT-001 |
| SYS-REQ-082 | SW-REQ-121 | -- | -- | can_posix.c | UT-103 | IT-001, IT-007 | QT-001 |
| SYS-REQ-083 | SW-REQ-034 | -- | Sec 4.4 | diag_cfg.c | UT-007 | -- | QT-008 |
| SYS-REQ-084 | SW-REQ-035 | -- | Sec 4.3, 4.4 | diag_cfg.c | UT-007 | IT-030 to IT-039 | QT-002 to QT-005 |
| SYS-REQ-085 | SW-REQ-122 | -- | -- | 80+ HAL stub files | UT-110, UT-111 | -- | QT-001 |
| SYS-REQ-086 | SW-REQ-122 | -- | -- | hal_posix.c, register_stubs.c | UT-112 | -- | QT-001 |

## 6. Reverse Traceability: Tests to System Requirements

### 6.1 Qualification Tests

| QT ID | Scenario | System Requirements Verified |
|---|---|---|
| QT-001 | Normal startup and operation | SYS-REQ-001 to SYS-REQ-007, SYS-REQ-060 to SYS-REQ-062, SYS-REQ-070 to SYS-REQ-072, SYS-REQ-080 to SYS-REQ-086 |
| QT-002 | Overvoltage fault and recovery | SYS-REQ-020, SYS-REQ-053 to SYS-REQ-055 |
| QT-003 | Undervoltage and deep discharge | SYS-REQ-021, SYS-REQ-022, SYS-REQ-053, SYS-REQ-055 |
| QT-004 | Overcurrent fault (fast response) | SYS-REQ-030, SYS-REQ-031, SYS-REQ-051, SYS-REQ-053, SYS-REQ-054 |
| QT-005 | Temperature fault (slow response) | SYS-REQ-040 to SYS-REQ-043, SYS-REQ-052, SYS-REQ-053 |
| QT-006 | CAN communication loss | SYS-REQ-063, SYS-REQ-053 |
| QT-007 | Multiple simultaneous faults | SYS-REQ-050, SYS-REQ-053, SYS-REQ-055 |
| QT-008 | Steady-state endurance | SYS-REQ-020 to SYS-REQ-043, SYS-REQ-080 to SYS-REQ-084 |

### 6.2 Integration Tests

| IT ID Range | Category | System Requirements Verified |
|---|---|---|
| IT-001 to IT-008 | CAN interface | SYS-REQ-060 to SYS-REQ-063 |
| IT-010 to IT-014 | Database data flow | SYS-REQ-001 to SYS-REQ-007, SYS-REQ-060 |
| IT-020 to IT-025 | State machine | SYS-REQ-070 to SYS-REQ-073 |
| IT-030 to IT-039 | Safety path (ASIL) | SYS-REQ-020 to SYS-REQ-043, SYS-REQ-053, SYS-REQ-054 |
| IT-040 to IT-042 | Diagnostic debounce | SYS-REQ-051, SYS-REQ-052 |
| IT-050 to IT-052 | Contactor | SYS-REQ-006, SYS-REQ-054 |
| IT-060 to IT-063 | SIL probes | SYS-REQ-050, SYS-REQ-071 |

## 7. Safety Requirements Traceability

| Safety Req | Software Req | DIAG ID | Test Cases |
|---|---|---|---|
| SSR-001 | SW-REQ-001 | CELL_VOLTAGE_OVERVOLTAGE_MSL | UT-012, IT-030, QT-002 |
| SSR-002 | SW-REQ-002 | CELL_VOLTAGE_UNDERVOLTAGE_MSL | UT-013, IT-031, QT-003 |
| SSR-003 | SW-REQ-010, SW-REQ-012, SW-REQ-013 | OVERCURRENT_*_MSL | UT-016, IT-036, QT-004 |
| SSR-004 | SW-REQ-011 | OVERCURRENT_CHARGE_CELL_MSL | UT-017, IT-037, QT-004 |
| SSR-005 | SW-REQ-020 | TEMP_OVERTEMPERATURE_DISCHARGE_MSL | UT-018, IT-032, QT-005 |
| SSR-006 | SW-REQ-021 | TEMP_UNDERTEMPERATURE_DISCHARGE_MSL | UT-019, IT-033, QT-005 |
| SSR-007 | SW-REQ-022 | TEMP_OVERTEMPERATURE_CHARGE_MSL | UT-020, IT-034, QT-005 |
| SSR-008 | SW-REQ-023 | TEMP_UNDERTEMPERATURE_CHARGE_MSL | UT-021, IT-035, QT-005 |
| SSR-009 | SW-REQ-005 | DEEP_DISCHARGE_DETECTED | UT-014, IT-038, QT-003 |
| SSR-010 | SW-REQ-014 | CURRENT_ON_OPEN_STRING | -- , IT-039, -- |
| SSR-020 | SW-REQ-032, SW-REQ-043 | (all FATAL) | UT-033, IT-024, QT-002 to QT-005 |
| SSR-021 | SW-REQ-044 | (all FATAL) | UT-034, IT-051, QT-002 |
| SSR-022 | SW-REQ-045 | (all FATAL) | UT-035, IT-025, QT-002 |
| SSR-023 | SW-REQ-045 | (all FATAL) | UT-035, IT-025, QT-002 |
| SSR-024 | SW-REQ-045 | (all FATAL) | UT-036, IT-025, QT-007 |
| SSR-030 | SW-REQ-030 | (all) | UT-007, IT-040, QT-007 |
| SSR-031 | SW-REQ-033 | (all) | UT-004, IT-040, IT-041, QT-005 |
| SSR-032 | SW-REQ-031 | (all) | UT-001, UT-003, IT-042, QT-004 |
| SSR-033 | SW-REQ-031 | (all) | UT-002, IT-040, QT-002 |
| SSR-040 | SW-REQ-110 | CAN_TIMING | -- , -- , QT-006 |
| SSR-041 | SW-REQ-111 | CURRENT_SENSOR_RESPONDING | -- , -- , QT-006 |
| SSR-042 | SW-REQ-030 | AFE_SPI, AFE_COMMUNICATION_INTEGRITY | UT-007, -- , -- |
| SSR-050 | SW-REQ-044 | *_CONTACTOR_FEEDBACK | UT-062, IT-052, -- |
| SSR-051 | SW-REQ-041 | -- | UT-031, IT-021, QT-001 |
| SSR-052 | SW-REQ-044 | -- | UT-060, IT-051, QT-002 |

## 8. Coverage Analysis

### 8.1 Forward Coverage (Requirements to Tests)

| Requirement Set | Total | Traced to SW Req | Traced to Design | Traced to Test | Coverage |
|---|---|---|---|---|---|
| System Requirements (SYS-REQ) | 36 | 36 (100%) | 36 (100%) | 36 (100%) | Complete |
| Software Requirements (SW-REQ) | 42 | -- | 42 (100%) | 40 (95%) | 2 pending (Phase 3) |
| Safety Requirements (SSR) | 24 | 24 (100%) | 24 (100%) | 22 (92%) | 2 pending (Phase 3) |

### 8.2 Backward Coverage (Tests to Requirements)

| Test Suite | Total Tests | Traced to SW Req | Traced to SYS Req | Coverage |
|---|---|---|---|---|
| Unit Tests (UT) | 45 | 45 (100%) | 45 (100%) | Complete |
| Integration Tests (IT) | 34 | 34 (100%) | 34 (100%) | Complete |
| Qualification Tests (QT) | 8 | 8 (100%) | 8 (100%) | Complete |

### 8.3 Gaps and Planned Remediation

| Gap | Requirement(s) | Planned Resolution | Target |
|---|---|---|---|
| Hardware fault injection tests | SSR-042 (AFE), SSR-050 (contactor feedback) | Phase 3: QT-009 to QT-014 | Phase 3 |
| CAN timing stress test | SSR-040 | Phase 3: extended QT-006 | Phase 3 |

## 9. Acceptance Criteria

This traceability matrix is accepted when:

1. Every system requirement (SYS-REQ-xxx) traces forward to at least one software requirement and one test case.
2. Every ASIL D software requirement (SW-REQ-xxx) traces forward to at least one test case.
3. Every safety requirement (SSR-xxx) traces forward to at least one test case.
4. Every test case (UT/IT/QT) traces backward to at least one requirement.
5. All identified gaps have documented remediation plans.

---
*End of Document*
