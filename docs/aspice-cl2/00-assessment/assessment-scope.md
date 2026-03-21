# ASPICE CL2 Assessment Scope

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| ASMT-SCOPE-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | M. Weber (AI-simulated) | Initial release |

## 1. Purpose

This document defines the scope of the Automotive SPICE Capability Level 2 (CL2) assessment for the foxBMS 2 POSIX virtual ECU (vECU) project. It identifies all process areas under evaluation, delineates in-scope and out-of-scope items, and provides the project context necessary for assessors to understand the assessment boundary.

## 2. Project Description

### 2.1 Product Under Assessment

The product is a software-in-the-loop (SIL) adaptation of the open-source foxBMS 2 battery management system (BMS), version 1.10.0, originally developed by Fraunhofer IISB for the TI TMS570 microcontroller. The POSIX port compiles the foxBMS application and engine layers for x86-64 Linux using GCC 13, replacing hardware-specific drivers with POSIX HAL stubs and SocketCAN interfaces.

### 2.2 Key Technical Characteristics

| Characteristic | Value |
|---|---|
| Base software | foxBMS 2 v1.10.0 (Fraunhofer IISB) |
| Target platform | x86-64 Linux (Ubuntu 24.04) |
| Compiler | GCC 13 with -Wall -Wextra |
| Source files | 170+ C source files compiled |
| Excluded source files | 18 (TMS570-specific: spi.c, i2c.c, dma.c, sbc/*, diag.c, fassert.c) |
| Execution model | Single-threaded cooperative loop (1ms tick) |
| CAN interface | SocketCAN (vcan0) |
| Battery configuration | 18 series cells (18s1p), 3 contactors |
| Plant model | Python-based closed-loop with OCV(SOC) curve, IR drop, BMW i3 trip replay |
| Test infrastructure | test_smoke.py, test_integration.py (21 criteria), test_asil.py (50 criteria) |
| Build system | setup.sh (single-command), apply_all.sh (13 patches) |
| Python version | 3.12 |

### 2.3 Project Context

This project serves as a Model-in-the-Loop / Software-in-the-Loop (MIL-SIL) pre-validation capability for HIL test engineers at a Tier 1 BMS supplier. The vECU enables early validation of BMS logic, diagnostic paths, and state machine behavior before physical bench testing, reducing HIL bench time and enabling fault injection scenarios that are difficult or dangerous to execute on real hardware.

## 3. Assessment Target

| Parameter | Value |
|---|---|
| Assessment model | Automotive SPICE v3.1 (VDA) |
| Target capability level | Level 2 (Managed Process) |
| Assessment method | Self-assessment with evidence package |
| Assessment date | 2026-03-21 |
| Lead assessor | An Dao |

### 3.1 Capability Level Definitions

- **CL1 (Performed Process)**: The process achieves its purpose; base practices are implemented and work products are produced.
- **CL2 (Managed Process)**: The performed process is now managed (planned, monitored, adjusted) and its work products are appropriately established, controlled, and maintained.

## 4. Process Areas In Scope

The following ASPICE process areas are assessed to CL2:

### 4.1 Engineering Processes

| # | Process Area | ID | Scope Description |
|---|---|---|---|
| 1 | System Requirements Analysis | SYS.2 | System-level requirements derived from stakeholder needs |
| 2 | System Architectural Design | SYS.3 | System decomposition into software and plant model components |
| 3 | Software Requirements Analysis | SWE.1 | Software requirements with ASIL allocation and traceability |
| 4 | Software Architectural Design | SWE.2 | Layer architecture (application, engine, driver, HAL) |
| 5 | Software Detailed Design and Unit Construction | SWE.3 | Module-level design and implementation |
| 6 | Software Unit Verification | SWE.4 | Unit test specification and execution (183+ Ceedling tests) |
| 7 | Software Integration and Integration Test | SWE.5 | Integration test specification (test_integration.py, 21 criteria) |
| 8 | Software Qualification Test | SWE.6 | End-to-end qualification (test_smoke.py, test_asil.py) |

### 4.2 Supporting Processes

| # | Process Area | ID | Scope Description |
|---|---|---|---|
| 9 | Configuration Management | SUP.8 | Git workflow, patch management, build reproducibility |

### 4.3 Management Processes

| # | Process Area | ID | Scope Description |
|---|---|---|---|
| 10 | Project Management | MAN.3 | Project planning, tracking, risk management |

## 5. Process Areas Assessed but Not Primary Target

The following process areas have documentation produced but are not the primary focus of the CL2 assessment:

| # | Process Area | ID | Rationale |
|---|---|---|---|
| 1 | Stakeholder Requirements Analysis | SYS.1 | Stakeholder requirements documented but derived informally |
| 2 | System Integration Test | SYS.4 | Covered via test_integration.py but no formal SYS.4 test plan |
| 3 | System Qualification Test | SYS.5 | Covered via test_smoke.py but no formal SYS.5 acceptance plan |
| 4 | Quality Assurance | SUP.1 | QA practices exist but not yet formalized into a managed process |
| 5 | Problem Resolution Management | SUP.9 | GAP-ANALYSIS.md serves as problem register |
| 6 | Change Request Management | SUP.10 | Patch workflow exists but no formal CR process |

## 6. Process Areas Out of Scope

| # | Process Area | ID | Rationale |
|---|---|---|---|
| 1 | Supplier Monitoring | ACQ.4 | foxBMS is open-source; no supplier contract exists |
| 2 | Hardware Engineering | HWE.* | No hardware development; POSIX port is software-only |
| 3 | Reuse Management | REU.2 | Not applicable to this project scope |
| 4 | Process Improvement | PIM.3 | Not targeted for this assessment cycle |

## 7. ISO 26262 Scope

Safety work products are produced in parallel to support ASIL-D classification of the BMS function. The following ISO 26262 parts have dedicated work products:

| ISO 26262 Part | Title | Work Products |
|---|---|---|
| Part 3 | Concept Phase | HARA (Hazard Analysis and Risk Assessment) |
| Part 4 | Product Development: System Level | FSC (Functional Safety Concept), TSC (Technical Safety Concept) |
| Part 5 | Product Development: Hardware Level | HSI (Hardware-Software Interface), FMEA |
| Part 6 | Product Development: Software Level | Safety Requirements, FTTI Calculations |
| Part 8 | Supporting Processes | Bidirectional Traceability Matrix |
| Part 9 | ASIL-Oriented Analysis | ASIL Decomposition |

These safety artifacts are assessed for completeness and traceability but are not rated against ASPICE capability levels.

## 8. Evidence Base

The assessment draws upon the following evidence:

| Evidence Type | Artifact | Location |
|---|---|---|
| Gap analysis | GAP-ANALYSIS.md | Repository root |
| Feature coverage | COVERAGE.md | Repository root |
| ASPICE work products | 18 documents | docs/aspice/ |
| Test results | test_smoke.py, test_integration.py, test_asil.py | tests/ |
| Build automation | setup.sh, apply_all.sh | Repository root |
| Source code | 170+ C files, HAL stubs, plant model | src/, patches/ |
| Test criteria | 147 total (76 smoke + 21 integration + 50 ASIL) | tests/ |

## 9. Assessment Criteria

For CL2 achievement, each in-scope process area must demonstrate:

1. **CL1 base practices**: All base practices (BP.1 through BP.n) are largely or fully achieved
2. **GP 2.1 Performance Management**: The process is planned, monitored, and adjusted; responsibilities are defined; resources are adequate
3. **GP 2.2 Work Product Management**: Work products have defined requirements, are reviewed, and are controlled under configuration management

## 10. Current Status

| Metric | Value |
|---|---|
| Total ASPICE criteria tracked | 112 |
| Criteria met | 94 |
| Percentage | 84% |
| Open gaps (CRITICAL/HIGH) | 0 |
| Open gaps (MEDIUM/LOW) | 0 |
| Accepted gaps (architectural) | 10 |
