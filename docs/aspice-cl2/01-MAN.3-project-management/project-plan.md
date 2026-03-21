# Project Management Plan

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| MAN.3-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | M. Weber (AI-simulated) | Initial release |

## 1. Purpose

This document defines the project management plan for the foxBMS 2 POSIX vECU project in accordance with ASPICE MAN.3 (Project Management). It establishes project phases, milestones, resource allocation, risk management, and monitoring mechanisms.

## 2. Scope

The plan covers the full lifecycle of the foxBMS POSIX SIL adaptation, from initial feasibility through integration with HIL test infrastructure. It encompasses all software engineering, system engineering, and supporting process activities required to achieve ASPICE CL2.

## 3. References

| ID | Title |
|---|---|
| [ASMT-SCOPE-001] | ASPICE CL2 Assessment Scope |
| [GAP-ANALYSIS] | foxBMS POSIX vECU Gap Analysis |
| [COVERAGE] | Feature Coverage Matrix |

## 4. Project Overview

### 4.1 Objective

Deliver a validated software-in-the-loop (SIL) representation of foxBMS 2 v1.10.0 that enables HIL test engineers to pre-validate BMS logic, diagnostic paths, and fault responses on a standard Linux workstation, with sufficient process maturity to satisfy ASPICE CL2.

### 4.2 Organizational Context

| Role | Person | Responsibility |
|---|---|---|
| Project Lead / Developer | An Dao | Architecture, implementation, testing, documentation |
| Organization | Tier 1 BMS OEM | HIL test laboratory |
| Role | HIL Engineer | Primary stakeholder and end-user |

## 5. Project Phases and Milestones

### Phase 1: BMS NORMAL State -- COMPLETED

| Milestone | Target Date | Actual Date | Status |
|---|---|---|---|
| M1.1 foxBMS compiles on x86-64 | 2026-02-01 | 2026-02-01 | DONE |
| M1.2 HAL stubs pass compilation | 2026-02-08 | 2026-02-08 | DONE |
| M1.3 BMS reaches NORMAL state | 2026-02-15 | 2026-02-15 | DONE |
| M1.4 CAN TX verified (15+ messages) | 2026-02-20 | 2026-02-20 | DONE |
| M1.5 Smoke test automated | 2026-02-25 | 2026-02-25 | DONE |
| M1.6 Gap analysis complete (33 gaps) | 2026-03-01 | 2026-03-01 | DONE |

**Deliverables**: foxbms-vecu binary, plant_model.py, test_smoke.py, GAP-ANALYSIS.md, COVERAGE.md, setup.sh

### Phase 2: Realistic Simulation -- COMPLETED

| Milestone | Target Date | Actual Date | Status |
|---|---|---|---|
| M2.1 Dynamic plant model (OCV curve, IR drop) | 2026-03-05 | 2026-03-05 | DONE |
| M2.2 Closed-loop contactor feedback | 2026-03-07 | 2026-03-07 | DONE |
| M2.3 SOC decreases under discharge | 2026-03-08 | 2026-03-08 | DONE |
| M2.4 BMW i3 trip replay integrated | 2026-03-10 | 2026-03-10 | DONE |

**Deliverables**: Enhanced plant model, trip replay data, updated test_smoke.py

### Phase 2.5: SIL Probes -- COMPLETED

| Milestone | Target Date | Actual Date | Status |
|---|---|---|---|
| M2.5.1 SIL probe override system (CAN 0x7E0) | 2026-03-14 | 2026-03-14 | DONE |
| M2.5.2 ASIL-D fault injection matrix (2,005 tests) | 2026-03-15 | 2026-03-15 | DONE |
| M2.5.3 test_asil.py (50 criteria) | 2026-03-16 | 2026-03-16 | DONE |
| M2.5.4 test_integration.py (21 criteria) | 2026-03-16 | 2026-03-16 | DONE |
| M2.5.5 Software watchdog implementation | 2026-03-17 | 2026-03-17 | DONE |

**Deliverables**: SIL probe system, test_asil.py, test_integration.py, ASIL fault matrix

### Phase 3: Fault Injection -- IN PROGRESS

| Milestone | Target Date | Actual Date | Status |
|---|---|---|---|
| M3.1 ASPICE document package (18 documents) | 2026-03-21 | 2026-03-21 | DONE |
| M3.2 ASPICE CL2 folder hierarchy | 2026-03-21 | 2026-03-21 | DONE |
| M3.3 CL2 gap assessment | 2026-03-21 | -- | IN PROGRESS |
| M3.4 Formal review records | 2026-04-01 | -- | PLANNED |
| M3.5 Measurement data collection | 2026-04-07 | -- | PLANNED |

**Deliverables**: CL2 evidence package, gap assessment, review records

### Phase 4: HIL Integration -- PLANNED

| Milestone | Target Date | Actual Date | Status |
|---|---|---|---|
| M4.1 Docker containerization | 2026-04-15 | -- | PLANNED |
| M4.2 XCP/A2L integration | 2026-05-01 | -- | PLANNED |
| M4.3 HIL-SIL bridge interface | 2026-05-15 | -- | PLANNED |
| M4.4 Final CL2 evidence package | 2026-06-01 | -- | PLANNED |

## 6. Work Breakdown Structure

### 6.1 Engineering Work Packages

| WP | Description | Phase | Effort (days) | Status |
|---|---|---|---|---|
| WP-01 | POSIX HAL adaptation (stubs, register buffers) | 1 | 5 | DONE |
| WP-02 | CAN TX/RX via SocketCAN | 1 | 3 | DONE |
| WP-03 | State machine validation (SYS/BMS/CONT/BAL) | 1 | 2 | DONE |
| WP-04 | Selective DIAG_Handler (24 HW suppressed, 61 SW enabled) | 1 | 3 | DONE |
| WP-05 | Plant model (dynamic, OCV, IR drop, trip replay) | 2 | 5 | DONE |
| WP-06 | SIL probe override system | 2.5 | 4 | DONE |
| WP-07 | ASIL-D test matrix | 2.5 | 3 | DONE |
| WP-08 | ASPICE documentation package | 3 | 5 | DONE |
| WP-09 | CL2 process maturity evidence | 3 | 3 | IN PROGRESS |
| WP-10 | Docker and CI pipeline | 4 | 5 | PLANNED |
| WP-11 | HIL-SIL bridge | 4 | 5 | PLANNED |

### 6.2 Test Work Packages

| WP | Description | Test Count | Status |
|---|---|---|---|
| WP-T01 | Unit tests (Ceedling) | 183+ | DONE |
| WP-T02 | Smoke test (test_smoke.py) | 76 criteria | DONE |
| WP-T03 | Integration test (test_integration.py) | 21 criteria | DONE |
| WP-T04 | ASIL test (test_asil.py) | 50 criteria | DONE |

**Total test criteria**: 147 (across integration and ASIL suites) + 183 unit tests + 76 smoke criteria

## 7. Resource Plan

### 7.1 Personnel

| Resource | Allocation | Role |
|---|---|---|
| An Dao | 100% | HIL engineer, developer, tester, process owner |

### 7.2 Infrastructure

| Resource | Description |
|---|---|
| Development machine | Ubuntu 24.04, GCC 13, Python 3.12 |
| Build tools | Make, Ceedling (unit tests) |
| Version control | Git with submodules |
| CAN tools | SocketCAN (vcan0), can-utils |
| Documentation | Markdown (assessor-portable) |

### 7.3 Tool Environment

| Tool | Version | Purpose |
|---|---|---|
| GCC | 13 | C compilation with -Wall -Wextra |
| Python | 3.12 | Plant model, test scripts |
| Ceedling | Latest | Unit test framework |
| Git | 2.43+ | Configuration management |
| SocketCAN | Linux kernel | Virtual CAN interface |
| can-utils | System | CAN monitoring and injection |

## 8. Risk Management

### 8.1 Risk Register

| Risk ID | Description | Probability | Impact | Mitigation | Status |
|---|---|---|---|---|---|
| R-01 | foxBMS upstream update breaks patches | Medium | High | Pin to v1.10.0; version check in apply_all.sh | ACTIVE |
| R-02 | Single-threaded model misses concurrency bugs | High | Medium | ACCEPTED: documented in GAP-ANALYSIS (GA-02). SIL validates logic, not threading. | ACCEPTED |
| R-03 | Insufficient evidence for CL2 | Medium | High | CL2 gap assessment identifies specific actions | ACTIVE |
| R-04 | Single resource (bus factor = 1) | High | High | Comprehensive documentation; setup.sh enables onboarding | ACTIVE |
| R-05 | HALCoGen header licensing | Low | Medium | BSD-licensed headers committed to repository | CLOSED |
| R-06 | SocketCAN timing fidelity | Medium | Low | SIL tests logic correctness, not bus timing; timing is HIL concern | ACCEPTED |

### 8.2 Risk Review Schedule

Risks are reviewed at each phase gate milestone. The GAP-ANALYSIS.md document serves as the living risk/issue register with severity classification and resolution tracking.

## 9. Monitoring and Control

### 9.1 Progress Metrics

| Metric | Current Value | Target |
|---|---|---|
| ASPICE criteria met | 94 / 112 (84%) | 112 / 112 (100%) |
| Open gaps (CRITICAL/HIGH) | 0 | 0 |
| Test criteria passing | 147 / 147 | 147 / 147 |
| Unit tests passing | 183+ / 183+ | 183+ / 183+ |
| ASPICE documents produced | 18 | 18 |
| Phase completion | 3 of 4 phases | 4 of 4 phases |

### 9.2 Status Reporting

- GAP-ANALYSIS.md is updated upon each gap discovery or resolution
- COVERAGE.md tracks feature-level status across 7 categories
- Phase gate reviews are conducted at each milestone boundary

### 9.3 Change Control

Changes to scope, schedule, or resources are documented in the change request process (SUP.10). Patches to foxBMS source are managed through the patch workflow (apply_all.sh) with version verification.

## 10. Quality Gates

| Gate | Criteria | Phase |
|---|---|---|
| G1: Build | setup.sh completes without error | 1 |
| G2: Smoke | test_smoke.py PASS (BMS NORMAL, SOC > 0%) | 1 |
| G3: Integration | test_integration.py 21/21 criteria pass | 2.5 |
| G4: ASIL | test_asil.py 50/50 criteria pass | 2.5 |
| G5: Documentation | All 18 ASPICE documents reviewed | 3 |
| G6: CL2 Evidence | CL2 gap assessment shows all actions complete | 3 |
| G7: Acceptance | HIL engineer validates SIL-to-HIL workflow | 4 |
