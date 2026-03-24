# Stakeholder Requirements Specification

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SYS.1-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | M. Weber | Initial release |

## 1. Purpose

This document captures the stakeholder requirements for the foxBMS 2 POSIX vECU project in accordance with ASPICE SYS.1 (Stakeholder Requirements Analysis). It identifies the key stakeholders, elicits their needs, and formalizes them into traceable requirements that drive the system and software specifications.

## 2. Scope

All stakeholder requirements for the POSIX SIL adaptation of foxBMS 2 v1.10.0, covering the vECU, plant model, test infrastructure, and documentation.

## 3. References

| ID | Title |
|---|---|
| [SYS.2-001] | System Requirements Specification |
| [ASMT-SCOPE-001] | ASPICE CL2 Assessment Scope |
| [GAP-ANALYSIS] | foxBMS POSIX vECU Gap Analysis |

## 4. Stakeholder Identification

### 4.1 Stakeholder 1: HIL Test Engineer

**Role**: Primary end-user of the SIL system. Uses the vECU to pre-validate BMS test cases before executing them on the physical HIL bench.

**Context**: HIL bench time is expensive and limited. Test setup on real hardware requires physical battery simulators, power supplies, and contactor assemblies. Many BMS logic tests (state transitions, diagnostic thresholds, CAN message content) can be validated in software first.

**Needs**:
- Run BMS logic on a standard Linux workstation without hardware dependencies
- Execute the same diagnostic and state machine logic as the production ECU
- Validate CAN message content and timing before HIL bench sessions
- Automate regression testing in CI pipelines

### 4.2 Stakeholder 2: Functional Safety Engineer

**Role**: Responsible for demonstrating that the BMS meets ASIL-D safety requirements per ISO 26262. Uses fault injection to validate that diagnostic paths correctly detect anomalies and transition the BMS to a safe state.

**Context**: Inducing real faults on hardware (overvoltage, overcurrent, sensor failure) is dangerous and destructive. A SIL environment enables exhaustive fault injection without risk to equipment or personnel.

**Needs**:
- Inject faults into cell voltages, currents, and temperatures programmatically
- Verify that DIAG_Handler correctly classifies and escalates each fault
- Trace safety requirements through to test evidence
- Validate FTTI (Fault Tolerant Time Interval) behavior in software

### 4.3 Stakeholder 3: Student / New Developer

**Role**: Newcomer to the foxBMS codebase who needs to understand, build, and experiment with the BMS without access to target hardware.

**Context**: The foxBMS project is complex (170+ source files, FreeRTOS, TMS570-specific HAL). A new developer cannot easily set up the full toolchain (Code Composer Studio, HALCoGen, TMS570 LaunchPad). The POSIX port provides an accessible entry point.

**Needs**:
- Clone and build with a single command on standard Ubuntu
- Observe BMS behavior through CAN messages and log output
- Understand the architecture through clear documentation
- Modify and experiment without risk of bricking hardware

## 5. Stakeholder Requirements

### 5.1 Build and Setup

| ID | Requirement | Stakeholder | Priority | Traces To |
|---|---|---|---|---|
| STKH-REQ-001 | The system shall build from source on Ubuntu 24.04 LTS using only standard packages (GCC, Make, Python 3, SocketCAN). | S3: Student | MUST | SYS-REQ-001 |
| STKH-REQ-002 | A single setup command shall clone the repository, apply all patches, build the vECU, configure the CAN interface, and run a smoke test. | S3: Student | MUST | SYS-REQ-002 |
| STKH-REQ-003 | The build shall complete in under 60 seconds on a standard workstation. | S1: HIL Eng | SHOULD | SYS-REQ-003 |
| STKH-REQ-004 | The system shall use foxBMS v1.10.0 as a pinned, version-checked dependency to ensure reproducible builds. | S1: HIL Eng | MUST | SYS-REQ-004 |

### 5.2 BMS Functional Behavior

| ID | Requirement | Stakeholder | Priority | Traces To |
|---|---|---|---|---|
| STKH-REQ-005 | The vECU shall execute the same BMS state machine logic as the production foxBMS (SYS/BMS/CONT/BAL state machines). | S1: HIL Eng | MUST | SYS-REQ-010 |
| STKH-REQ-006 | The BMS shall reach the NORMAL operating state through the legitimate transition sequence (UNINIT, INIT, IDLE, STANDBY, PRECHARGE, NORMAL). | S1: HIL Eng | MUST | SYS-REQ-011 |
| STKH-REQ-007 | The vECU shall transmit at least 15 CAN message types on the virtual CAN bus, matching the foxBMS DBC message IDs. | S1: HIL Eng | MUST | SYS-REQ-020 |
| STKH-REQ-008 | The SOC algorithm shall reflect changes in battery state of charge when current flows (discharge or charge). | S1: HIL Eng | MUST | SYS-REQ-030 |

### 5.3 Safety and Diagnostics

| ID | Requirement | Stakeholder | Priority | Traces To |
|---|---|---|---|---|
| STKH-REQ-009 | The vECU shall execute the DIAG_Handler for all software-checkable diagnostic IDs (overvoltage, undervoltage, overcurrent, overtemperature, plausibility). | S2: Safety Eng | MUST | SYS-REQ-040 |
| STKH-REQ-010 | Hardware-absent diagnostic IDs (AFE SPI, SBC, I2C, IMD, interlock) shall be explicitly suppressed with documented rationale. | S2: Safety Eng | MUST | SYS-REQ-041 |
| STKH-REQ-011 | The system shall provide a fault injection interface that allows test scripts to override cell voltages, currents, and temperatures at runtime. | S2: Safety Eng | MUST | SYS-REQ-050 |
| STKH-REQ-012 | Injected faults shall trigger the same DIAG_Handler response as genuine sensor readings (same DIAG ID, same severity classification). | S2: Safety Eng | MUST | SYS-REQ-051 |
| STKH-REQ-013 | FAS_ASSERT violations shall terminate the vECU with a visible error message including file and line number. | S2: Safety Eng | MUST | SYS-REQ-042 |

### 5.4 Test Automation

| ID | Requirement | Stakeholder | Priority | Traces To |
|---|---|---|---|---|
| STKH-REQ-014 | An automated smoke test shall verify that the BMS reaches NORMAL state, contactors close, and SOC is non-zero. | S1: HIL Eng | MUST | SYS-REQ-060 |
| STKH-REQ-015 | The vECU shall support a timeout flag (--timeout N) for CI pipeline integration, exiting cleanly after N seconds. | S1: HIL Eng | MUST | SYS-REQ-061 |
| STKH-REQ-016 | Integration tests shall verify end-to-end CAN communication between plant model and vECU. | S1: HIL Eng | SHOULD | SYS-REQ-062 |
| STKH-REQ-017 | ASIL-D fault injection tests shall cover all safety-relevant diagnostic paths with pass/fail verdict. | S2: Safety Eng | MUST | SYS-REQ-063 |

### 5.5 Documentation and Usability

| ID | Requirement | Stakeholder | Priority | Traces To |
|---|---|---|---|---|
| STKH-REQ-018 | The project shall include a troubleshooting guide covering common failure modes with diagnosis and resolution steps. | S3: Student | SHOULD | SYS-REQ-070 |
| STKH-REQ-019 | The architecture shall be documented with block diagrams showing layer decomposition and data flow. | S3: Student | SHOULD | SYS-REQ-071 |
| STKH-REQ-020 | A feature coverage matrix shall identify which foxBMS features work on POSIX, which are suppressed, and which are not implemented. | S1: HIL Eng | MUST | SYS-REQ-072 |

## 6. Requirements Analysis

### 6.1 Prioritization

| Priority | Count | Description |
|---|---|---|
| MUST | 15 | Essential for SIL validation purpose |
| SHOULD | 5 | Important for usability and completeness |

### 6.2 Conflicts and Trade-offs

| Conflict | Resolution |
|---|---|
| STKH-REQ-005 (same logic) vs. single-threaded execution | ACCEPTED: cooperative loop preserves logic correctness; concurrency testing deferred to HIL (GA-02) |
| STKH-REQ-010 (suppress HW diag) vs. STKH-REQ-009 (execute SW diag) | Selective DIAG_Handler: 24 HW IDs suppressed, 61 SW IDs enabled |
| STKH-REQ-003 (build speed) vs. STKH-REQ-004 (reproducibility) | setup.sh caches submodule; incremental builds take <10s |

### 6.3 Traceability

All STKH-REQ-xxx requirements trace forward to SYS-REQ-xxx in the System Requirements Specification (SYS.2-001). The bidirectional traceability matrix in ISO26262-part8-traceability.md provides the complete mapping chain from stakeholder requirements through system requirements, software requirements, detailed design, and test cases.

### 5.7 Traceability: STKH-REQ → SYS-REQ (Complete)

This table provides the complete bidirectional mapping between all 20 STKH-REQs and all 100 SYS-REQs.

#### 5.7.1 Forward Trace: STKH-REQ → SYS-REQ

| STKH-REQ | Category | Traces Down To |
|---|---|---|
| STKH-REQ-001 | Build/Setup | SYS-REQ-150, SYS-REQ-151, SYS-REQ-152, SYS-REQ-153, SYS-REQ-154, SYS-REQ-155, SYS-REQ-156 |
| STKH-REQ-002 | Build/Setup | SYS-REQ-150, SYS-REQ-151, SYS-REQ-152, SYS-REQ-153, SYS-REQ-154, SYS-REQ-155, SYS-REQ-156 |
| STKH-REQ-003 | Build/Setup | SYS-REQ-150, SYS-REQ-151, SYS-REQ-152, SYS-REQ-153, SYS-REQ-154, SYS-REQ-155, SYS-REQ-156 |
| STKH-REQ-004 | Build/Setup | SYS-REQ-150, SYS-REQ-151, SYS-REQ-152, SYS-REQ-153, SYS-REQ-154, SYS-REQ-155, SYS-REQ-156 |
| STKH-REQ-005 | Same BMS logic | SYS-REQ-001..016, SYS-REQ-080..086, SYS-REQ-090..095, SYS-REQ-100..115, SYS-REQ-120..123, SYS-REQ-140..147 |
| STKH-REQ-006 | Full state transitions | SYS-REQ-080, SYS-REQ-081, SYS-REQ-082, SYS-REQ-083, SYS-REQ-090, SYS-REQ-091, SYS-REQ-092, SYS-REQ-093, SYS-REQ-094, SYS-REQ-095, SYS-REQ-100..115 |
| STKH-REQ-007 | 15+ CAN messages | SYS-REQ-060, SYS-REQ-061, SYS-REQ-062, SYS-REQ-063, SYS-REQ-064, SYS-REQ-065, SYS-REQ-066, SYS-REQ-067, SYS-REQ-068, SYS-REQ-069 |
| STKH-REQ-008 | SOC changes | SYS-REQ-130, SYS-REQ-131, SYS-REQ-132, SYS-REQ-133, SYS-REQ-134, SYS-REQ-140..147 |
| STKH-REQ-009 | DIAG software-checkable | SYS-REQ-020..043, SYS-REQ-050, SYS-REQ-051, SYS-REQ-052, SYS-REQ-053, SYS-REQ-054, SYS-REQ-055, SYS-REQ-056, SYS-REQ-057, SYS-REQ-058, SYS-REQ-059 |
| STKH-REQ-010 | HW DIAG suppressed | SYS-REQ-153, SYS-REQ-154 |
| STKH-REQ-011 | Fault injection | SYS-REQ-050, SYS-REQ-051, SYS-REQ-052, SYS-REQ-053, SYS-REQ-054, SYS-REQ-055 |
| STKH-REQ-012 | Fault same DIAG response | SYS-REQ-050, SYS-REQ-051, SYS-REQ-052, SYS-REQ-053 |
| STKH-REQ-013 | FAS_ASSERT visible | SYS-REQ-150 |
| STKH-REQ-014 | Smoke test | SYS-REQ-090, SYS-REQ-150 |
| STKH-REQ-015 | Timeout flag | SYS-REQ-150, SYS-REQ-151 |
| STKH-REQ-016 | Integration tests | SYS-REQ-060..069, SYS-REQ-070..077 |
| STKH-REQ-017 | ASIL fault tests | SYS-REQ-020..043, SYS-REQ-050..059 |
| STKH-REQ-018 | Troubleshooting guide | SYS-REQ-150 |
| STKH-REQ-019 | Architecture diagrams | SYS-REQ-080..086, SYS-REQ-090..095 |
| STKH-REQ-020 | Coverage matrix | SYS-REQ-150..156 |

#### 5.7.2 Reverse Trace: SYS-REQ → STKH-REQ

| SYS-REQ Range | Domain | STKH-REQ Parent(s) |
|---|---|---|
| SYS-REQ-001..016 | Pack configuration, cell parameters | STKH-REQ-005 (same BMS logic requires same config) |
| SYS-REQ-020..043 | Safety thresholds (MOL/RSL/MSL) | STKH-REQ-009, STKH-REQ-017 |
| SYS-REQ-050..053 | DIAG handler core | STKH-REQ-009, STKH-REQ-011, STKH-REQ-012, STKH-REQ-017 |
| SYS-REQ-054..055 | DIAG error escalation | STKH-REQ-011, STKH-REQ-013 |
| SYS-REQ-056..059 | DIAG suppression, coverage | STKH-REQ-009, STKH-REQ-017 |
| SYS-REQ-060..069 | CAN TX messages | STKH-REQ-007, STKH-REQ-016 |
| SYS-REQ-070..077 | CAN RX messages | STKH-REQ-016 |
| SYS-REQ-080..086 | SYS state machine | STKH-REQ-005, STKH-REQ-006, STKH-REQ-019 |
| SYS-REQ-090..095 | BMS state machine | STKH-REQ-005, STKH-REQ-006, STKH-REQ-014, STKH-REQ-019 |
| SYS-REQ-100..115 | Precharge, contactor control | STKH-REQ-005, STKH-REQ-006 |
| SYS-REQ-120..123 | Balancing | STKH-REQ-005 |
| SYS-REQ-130..134 | SOC estimation | STKH-REQ-008 |
| SYS-REQ-140..147 | Plant model | STKH-REQ-005, STKH-REQ-008 |
| SYS-REQ-150 | POSIX build/compile | STKH-REQ-001..004, STKH-REQ-013, STKH-REQ-014, STKH-REQ-015, STKH-REQ-018, STKH-REQ-020 |
| SYS-REQ-151 | POSIX timeout/CI | STKH-REQ-002, STKH-REQ-015, STKH-REQ-020 |
| SYS-REQ-152 | POSIX SocketCAN | STKH-REQ-001..004, STKH-REQ-020 |
| SYS-REQ-153 | POSIX HW DIAG suppress | STKH-REQ-010, STKH-REQ-020 |
| SYS-REQ-154 | POSIX HW stub rationale | STKH-REQ-010, STKH-REQ-020 |
| SYS-REQ-155 | POSIX cooperative loop | STKH-REQ-001..004, STKH-REQ-020 |
| SYS-REQ-156 | POSIX register stubs | STKH-REQ-001..004, STKH-REQ-020 |

## 7. Acceptance Criteria

Each stakeholder requirement is considered fulfilled when:

1. The corresponding system requirement(s) are implemented
2. Test evidence demonstrates the requirement is met (test_smoke.py, test_integration.py, or test_asil.py)
3. The GAP-ANALYSIS.md entry (if any) is marked FIXED or ACCEPTED with documented rationale
