# ASPICE Capability Level 2 Gap Assessment

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| ASMT-CL2-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | M. Weber | Initial release |

## 1. Purpose

This document provides a detailed gap assessment of the foxBMS 2 POSIX vECU project against Automotive SPICE v3.1 Capability Level 2 (CL2). For each process area in scope, it evaluates:

1. **CL1 base practice fulfillment** -- whether each base practice is Fully (F), Largely (L), Partially (P), or Not (N) achieved
2. **CL2 generic practice fulfillment** -- whether GP 2.1 (Performance Management) and GP 2.2 (Work Product Management) are achieved
3. **Specific actions needed** to close gaps and achieve CL2
4. **Estimated effort** for each action

## 2. Assessment Methodology

- Assessment model: Automotive SPICE v3.1 (VDA)
- Rating scale: F (Fully, >85%), L (Largely, 50-85%), P (Partially, 15-50%), N (Not, <15%)
- CL1 achieved when all base practices are rated F or L (with overall process purpose achieved)
- CL2 achieved when CL1 is achieved AND GP 2.1 and GP 2.2 are both rated F or L

## 3. Summary of Current Evidence

| Evidence | Details |
|---|---|
| ASPICE work products | 18 documents (SYS.2-3, SWE.1-6, ISO 26262 parts 3-9) |
| Test suites | test_smoke.py (76 criteria), test_integration.py (21), test_asil.py (50) |
| Unit tests | 183+ Ceedling tests |
| Gap analysis | GAP-ANALYSIS.md: 33 gaps, 23 FIXED, 10 ACCEPTED, 0 open |
| Coverage matrix | COVERAGE.md: 51 features tracked |
| Source code | 170+ C files, 13 patches, HAL stubs, plant model |
| Build automation | setup.sh, apply_all.sh, Makefile |
| CL2 folder hierarchy | 24 folders with assessor-facing structure |

---

## 4. Process Area Assessments

---

### 4.1 MAN.3 -- Project Management

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Define the scope of work | **F** | Assessment scope document (ASMT-SCOPE-001); WBS in project plan | -- |
| BP.2 | Define project life cycle | **F** | Four phases defined with milestones and deliverables | -- |
| BP.3 | Evaluate feasibility of the project | **L** | Feasibility demonstrated by working Phase 1-2.5 deliverables; no formal feasibility study document | No formal feasibility report |
| BP.4 | Define and maintain project plan | **L** | Project plan (MAN.3-001) with phases, milestones, WBS, resources | Plan created late in project; not maintained iteratively from start |
| BP.5 | Define, monitor and adjust project activities | **L** | GAP-ANALYSIS.md tracks issues; milestones tracked in plan | No formal activity tracking tool (e.g., Gantt chart, burn-down) |
| BP.6 | Define, monitor and adjust project estimates | **P** | Effort estimates in WBS; no re-estimation records | No estimation method documented; no re-estimation history |
| BP.7 | Ensure required skills, knowledge and experience | **L** | Single engineer with HIL domain expertise | No skills matrix or training records |
| BP.8 | Identify, monitor and adjust project interfaces | **L** | Submodule interface (foxBMS), SocketCAN interface documented | No formal interface agreement document |
| BP.9 | Allocate responsibilities | **F** | Single resource with clear responsibility for all work packages | -- |
| BP.10 | Define, monitor and adjust project schedule | **L** | Milestone dates defined in project plan | No schedule variance tracking |

**CL1 Rating: L (Largely achieved)** -- All base practices have evidence, but several lack formal documentation rigor.

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1.1 | Identify the objectives for the performance of the process | **L** | Project objectives defined in project plan | Not stated as measurable objectives with acceptance criteria |
| GP 2.1.2 | Plan the performance of the process | **L** | Project plan exists with phases and milestones | Plan created retroactively; no evidence of ongoing planning |
| GP 2.1.3 | Monitor the performance of the process | **P** | GAP-ANALYSIS.md and ASPICE criteria count (94/112) | No regular status reports; no trend data |
| GP 2.1.4 | Adjust the performance of the process | **P** | Phase adjustments evident (Phase 2.5 added) | No documented adjustment decisions or rationale |
| GP 2.1.5 | Define responsibilities and authorities | **F** | Single resource; all responsibilities clearly assigned | -- |
| GP 2.1.6 | Identify and make available resources | **L** | Tool environment documented | No resource utilization tracking |
| GP 2.2.1 | Define the requirements for the work products | **L** | Document templates with standard fields | No explicit WP requirements document |
| GP 2.2.2 | Define the requirements for documentation and control | **P** | Git-based versioning; no formal document control procedure | No document control procedure |
| GP 2.2.3 | Identify, document and control the work products | **L** | 18 ASPICE documents under Git; INDEX.md provides mapping | No formal configuration item list with states |
| GP 2.2.4 | Review and adjust work products | **P** | Self-review performed; no review records | No review meeting minutes or sign-off records |

**CL2 Rating: P (Partially achieved)** -- Performance management lacks monitoring data and adjustment records. Work product management lacks formal review records.

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| MAN.3-A1 | Create measurable project objectives with acceptance criteria | 2h | HIGH |
| MAN.3-A2 | Generate project status reports (at least 3 retrospective reports for Phases 1, 2, 2.5) | 4h | HIGH |
| MAN.3-A3 | Document Phase 2.5 addition as a formal schedule adjustment with rationale | 1h | MEDIUM |
| MAN.3-A4 | Create estimation method description (analogy-based, per-WP) | 2h | MEDIUM |
| MAN.3-A5 | Create review records for project plan review | 1h | HIGH |

**Total estimated effort: 10h**

---

### 4.2 SYS.1 -- Stakeholder Requirements Analysis

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Identify stakeholders | **F** | Three stakeholders identified (HIL engineer, safety engineer, student) | -- |
| BP.2 | Gather stakeholder requirements | **F** | 20 requirements with STKH-REQ-xxx IDs | -- |
| BP.3 | Analyze stakeholder requirements | **L** | Prioritization (MUST/SHOULD), conflict analysis | No formal analysis criteria or acceptance criteria per requirement |
| BP.4 | Establish stakeholder requirements baseline | **P** | Document exists under Git; no formal baseline record | No baseline tag or approval record |
| BP.5 | Communicate agreed stakeholder requirements | **L** | Document available in repository | No distribution record or stakeholder acknowledgment |

**CL1 Rating: L (Largely achieved)**

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **P** | Process executed but not planned or monitored | No plan for requirements elicitation; no review schedule |
| GP 2.2 | Work Product Management | **P** | Document under Git control | No review record; no formal baseline; no change history tracking |

**CL2 Rating: P (Partially achieved)**

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SYS.1-A1 | Add acceptance criteria to each STKH-REQ | 2h | MEDIUM |
| SYS.1-A2 | Create baseline record (date, version, approval) | 1h | HIGH |
| SYS.1-A3 | Create review record for stakeholder requirements review | 1h | HIGH |
| SYS.1-A4 | Document requirements elicitation method | 1h | MEDIUM |

**Total estimated effort: 5h**

---

### 4.3 SYS.2 -- System Requirements Analysis

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Specify system requirements | **F** | SYS.2-001 with SYS-REQ-xxx IDs, ASIL allocation | -- |
| BP.2 | Analyze system requirements | **F** | Requirements categorized by function (voltage, current, temp, state) | -- |
| BP.3 | Verify system requirements | **L** | Traceability to stakeholder requirements | No formal verification review record |
| BP.4 | Establish bidirectional traceability | **F** | ISO26262-part8-traceability.md provides full chain | -- |
| BP.5 | Communicate agreed system requirements | **L** | Document in repository | No formal communication/distribution record |
| BP.6 | Ensure consistency | **L** | Cross-references between SYS.2 and SYS.3, SWE.1 | No consistency check record |

**CL1 Rating: L (Largely achieved)**

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **L** | Process produced comprehensive requirements; traceability maintained | No explicit plan for requirements analysis activities |
| GP 2.2 | Work Product Management | **L** | Document under Git; revision history present | No formal review record; no baseline approval |

**CL2 Rating: L (Largely achieved)** -- Close to CL2; needs review records and baseline.

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SYS.2-A1 | Create review record for SYS.2 document review | 1h | HIGH |
| SYS.2-A2 | Create baseline record with approval | 1h | HIGH |
| SYS.2-A3 | Document consistency check between SYS.2 and SWE.1 | 1h | MEDIUM |

**Total estimated effort: 3h**

---

### 4.4 SYS.3 -- System Architectural Design

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Develop system architectural design | **F** | SYS.3-001 with layer decomposition, block diagrams | -- |
| BP.2 | Allocate system requirements to elements | **F** | Requirements allocated to application, engine, driver layers | -- |
| BP.3 | Define interfaces of system elements | **F** | CAN interface, database interface, HAL interface documented | -- |
| BP.4 | Describe dynamic behavior | **L** | State machine descriptions present | No sequence diagrams or timing diagrams |
| BP.5 | Evaluate alternative architectures | **P** | Cooperative vs. FreeRTOS decision documented in GA-02 | No formal architecture evaluation record |
| BP.6 | Establish bidirectional traceability | **F** | Traceability to SYS.2 requirements and SWE.2 | -- |
| BP.7 | Ensure consistency | **L** | Cross-references to SWE.2, HSI | No formal consistency review |

**CL1 Rating: L (Largely achieved)**

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **L** | Architecture produced and maintained | No architecture review plan |
| GP 2.2 | Work Product Management | **L** | Under Git; revision history present | No formal review record |

**CL2 Rating: L (Largely achieved)**

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SYS.3-A1 | Create review record for architecture review | 1h | HIGH |
| SYS.3-A2 | Document architecture evaluation (cooperative vs. FreeRTOS) as formal decision record | 1h | MEDIUM |
| SYS.3-A3 | Add sequence diagram for BMS state transition flow | 2h | LOW |

**Total estimated effort: 4h**

---

### 4.5 SYS.4 -- System Integration Test

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Develop system integration test strategy | **L** | test_integration.py + test_asil.py cover integration | Strategy documented in SYS.4-001 (this assessment cycle) |
| BP.2 | Develop system integration test specification | **L** | 21 integration + 50 ASIL criteria specified | Test spec formalized during this assessment |
| BP.3 | Select test cases | **F** | Test cases derived from system requirements and architecture | -- |
| BP.4 | Test integrated system elements | **F** | All 71 criteria pass | -- |
| BP.5 | Establish bidirectional traceability | **L** | SIT-xxx traces to SYS-REQ-xxx | Traceability added during this assessment |
| BP.6 | Summarize and communicate results | **L** | Test output captured; pass/fail verdicts | No formal test report document |

**CL1 Rating: L (Largely achieved)**

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **P** | Tests executed but no test plan with schedule | No test planning document |
| GP 2.2 | Work Product Management | **L** | Test scripts under Git; test spec document created | No formal test report |

**CL2 Rating: P (Partially achieved)**

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SYS.4-A1 | Create formal system integration test report with results and verdict | 2h | HIGH |
| SYS.4-A2 | Create test plan with schedule and entry/exit criteria | 1h | HIGH |
| SYS.4-A3 | Create review record for test specification review | 1h | MEDIUM |

**Total estimated effort: 4h**

---

### 4.6 SYS.5 -- System Qualification Test

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Develop system qualification test strategy | **L** | test_smoke.py serves as acceptance test | Strategy formalized in SYS.5-001 during this assessment |
| BP.2 | Develop system qualification test specification | **L** | 23 SQT-xxx test cases specified | Formalized during this assessment |
| BP.3 | Select test cases | **F** | Cases trace to stakeholder requirements | -- |
| BP.4 | Test the integrated system | **F** | Smoke test passes; setup.sh succeeds on fresh clone | -- |
| BP.5 | Establish bidirectional traceability | **L** | SQT-xxx traces to STKH-REQ-xxx | -- |
| BP.6 | Summarize and communicate results | **L** | Smoke test output; PASS verdict | No formal qualification test report |

**CL1 Rating: L (Largely achieved)**

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **P** | Tests executed ad-hoc, not on planned schedule | No test plan |
| GP 2.2 | Work Product Management | **L** | Test script under Git; spec document created | No formal test report |

**CL2 Rating: P (Partially achieved)**

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SYS.5-A1 | Create formal system qualification test report | 2h | HIGH |
| SYS.5-A2 | Create test plan with entry/exit criteria and schedule | 1h | HIGH |
| SYS.5-A3 | Create review record for test specification | 1h | MEDIUM |

**Total estimated effort: 4h**

---

### 4.7 SWE.1 -- Software Requirements Analysis

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Specify software requirements | **F** | SWE.1-001 with SW-REQ-xxx IDs, ASIL allocation | -- |
| BP.2 | Structure software requirements | **F** | Categorized by safety, functional, interface, performance | -- |
| BP.3 | Analyze software requirements | **F** | Impact on DIAG IDs, traceability to system requirements | -- |
| BP.4 | Analyze the impact on the operating environment | **F** | POSIX-specific adaptations documented (HAL stubs, cooperative loop) | -- |
| BP.5 | Establish bidirectional traceability | **F** | SW-REQ -> SYS-REQ -> STKH-REQ; SW-REQ -> SWE.3 -> SWE.4 | -- |
| BP.6 | Ensure consistency | **L** | Cross-references consistent | No formal consistency check record |
| BP.7 | Communicate agreed software requirements | **L** | Document in repository | No distribution record |

**CL1 Rating: F (Fully achieved)**

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **L** | Process well-executed; requirements comprehensive | No explicit plan for SW requirements process |
| GP 2.2 | Work Product Management | **L** | Under Git; revision history; cross-referenced | No formal review record |

**CL2 Rating: L (Largely achieved)**

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SWE.1-A1 | Create review record for SWE.1 document review | 1h | HIGH |
| SWE.1-A2 | Create baseline record | 0.5h | HIGH |

**Total estimated effort: 1.5h**

---

### 4.8 SWE.2 -- Software Architectural Design

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Develop software architectural design | **F** | SWE.2-001 with layer decomposition, component diagrams | -- |
| BP.2 | Allocate software requirements to components | **F** | Requirements allocated to application, engine, driver, HAL | -- |
| BP.3 | Define interfaces of software components | **F** | Database API, CAN API, HAL API documented | -- |
| BP.4 | Describe dynamic behavior | **L** | Task scheduling (cooperative loop), state machine flow | No formal timing/sequence diagrams |
| BP.5 | Evaluate resource consumption objectives | **L** | Memory footprint noted; cooperative loop CPU usage managed (usleep) | No formal resource budget |
| BP.6 | Establish bidirectional traceability | **F** | SW-REQ -> SWE.2 -> SWE.3 | -- |
| BP.7 | Ensure consistency | **L** | Consistent with SYS.3 and SWE.1 | No consistency check record |

**CL1 Rating: F (Fully achieved)**

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **L** | Architecture well-documented and maintained | No architecture review plan |
| GP 2.2 | Work Product Management | **L** | Under Git; referenced by other documents | No formal review record |

**CL2 Rating: L (Largely achieved)**

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SWE.2-A1 | Create review record for architecture review | 1h | HIGH |
| SWE.2-A2 | Document resource consumption analysis (memory, CPU) | 1h | LOW |

**Total estimated effort: 2h**

---

### 4.9 SWE.3 -- Software Detailed Design and Unit Construction

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Develop detailed design | **F** | SWE.3-001 with module descriptions, data structures, algorithms | -- |
| BP.2 | Define interfaces of software units | **F** | Function signatures, data types documented | -- |
| BP.3 | Describe dynamic behavior of software units | **L** | Algorithm descriptions present | No formal state charts for individual modules |
| BP.4 | Evaluate the software detailed design | **L** | Design follows foxBMS patterns | No formal design review record |
| BP.5 | Establish bidirectional traceability | **F** | SW-REQ -> SWE.3 modules -> SWE.4 test cases | -- |
| BP.6 | Ensure consistency | **L** | Consistent with SWE.2 | No consistency check record |

**CL1 Rating: F (Fully achieved)**

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **L** | Design produced systematically | No design review plan |
| GP 2.2 | Work Product Management | **L** | Under Git control | No review record |

**CL2 Rating: L (Largely achieved)**

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SWE.3-A1 | Create review record for detailed design review | 1h | HIGH |

**Total estimated effort: 1h**

---

### 4.10 SWE.4 -- Software Unit Verification

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Develop unit verification strategy | **L** | Ceedling-based unit testing; 183+ tests | Strategy described in SWE.4-001 |
| BP.2 | Develop test specification for units | **F** | SWE.4-001 with test case specifications | -- |
| BP.3 | Select test cases | **F** | Derived from SW requirements and detailed design | -- |
| BP.4 | Test software units | **F** | 183+ tests passing | -- |
| BP.5 | Establish bidirectional traceability | **L** | Test cases reference SW-REQ-xxx | Some tests lack explicit requirement references |
| BP.6 | Summarize and communicate results | **L** | Ceedling output captured | No formal unit test report |

**CL1 Rating: L (Largely achieved)**

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **P** | Tests executed but no test plan with coverage targets | No coverage target; no test execution plan |
| GP 2.2 | Work Product Management | **L** | Tests under Git; spec document exists | No formal test report |

**CL2 Rating: P (Partially achieved)**

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SWE.4-A1 | Create unit test report with pass/fail summary | 2h | HIGH |
| SWE.4-A2 | Define code coverage target and measure with gcov/lcov | 4h | MEDIUM |
| SWE.4-A3 | Add explicit requirement traceability to all unit tests | 3h | MEDIUM |
| SWE.4-A4 | Create review record for test specification | 1h | HIGH |

**Total estimated effort: 10h**

---

### 4.11 SWE.5 -- Software Integration and Integration Test

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Develop integration strategy | **L** | Bottom-up integration (HAL -> driver -> engine -> app) | Strategy described in SWE.5-001 |
| BP.2 | Develop integration test specification | **F** | SWE.5-001 with 21 criteria | -- |
| BP.3 | Select test cases | **F** | Derived from architecture and integration points | -- |
| BP.4 | Integrate and test software modules | **F** | test_integration.py 21/21 pass | -- |
| BP.5 | Establish bidirectional traceability | **L** | Test cases reference SWE.2 components | -- |
| BP.6 | Summarize and communicate results | **L** | Test output captured | No formal integration test report |

**CL1 Rating: L (Largely achieved)**

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **P** | Tests executed but no integration test plan with schedule | No test plan |
| GP 2.2 | Work Product Management | **L** | Scripts and spec under Git | No formal test report |

**CL2 Rating: P (Partially achieved)**

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SWE.5-A1 | Create integration test report with results | 2h | HIGH |
| SWE.5-A2 | Create integration test plan with schedule | 1h | HIGH |
| SWE.5-A3 | Create review record for integration test spec | 1h | MEDIUM |

**Total estimated effort: 4h**

---

### 4.12 SWE.6 -- Software Qualification Test

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Develop qualification test strategy | **L** | test_smoke.py + test_asil.py serve as qualification | Strategy described in SWE.6-001 |
| BP.2 | Develop qualification test specification | **F** | SWE.6-001 with test cases | -- |
| BP.3 | Select test cases | **F** | Derived from SW requirements | -- |
| BP.4 | Test the integrated software | **F** | All tests passing | -- |
| BP.5 | Establish bidirectional traceability | **L** | Test cases reference SW-REQ-xxx | -- |
| BP.6 | Summarize and communicate results | **L** | Test output captured | No formal qualification test report |

**CL1 Rating: L (Largely achieved)**

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **P** | Tests executed but no qualification plan | No test plan |
| GP 2.2 | Work Product Management | **L** | Scripts and spec under Git | No formal test report |

**CL2 Rating: P (Partially achieved)**

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SWE.6-A1 | Create qualification test report with results and final verdict | 2h | HIGH |
| SWE.6-A2 | Create qualification test plan with entry/exit criteria | 1h | HIGH |
| SWE.6-A3 | Create review record | 1h | MEDIUM |

**Total estimated effort: 4h**

---

### 4.13 SUP.1 -- Quality Assurance

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Develop quality assurance strategy | **L** | QA plan (SUP.1-001) with review checklists and verification activities | Plan created during this assessment |
| BP.2 | Assure quality of project work products | **L** | Code review checklists, test suites, GAP-ANALYSIS reviews | No formal QA audit records |
| BP.3 | Assure quality of project processes | **P** | ASPICE criteria tracking (94/112) | No process audit records |
| BP.4 | Assure quality of project activities | **P** | Activities produce tested deliverables | No activity review records |
| BP.5 | Summarize and communicate QA findings | **L** | GAP-ANALYSIS.md and COVERAGE.md | No QA status reports |
| BP.6 | Ensure resolution of non-conformances | **F** | 33 gaps resolved (23 FIXED, 10 ACCEPTED, 0 open) | -- |
| BP.7 | Implement process improvement activities | **P** | Phase 2.5 was a process improvement (SIL probes) | No formal improvement register |

**CL1 Rating: L (Largely achieved)**

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **P** | QA activities performed but not systematically planned | No QA audit schedule |
| GP 2.2 | Work Product Management | **P** | QA plan under Git; no QA records | No audit records, no review records |

**CL2 Rating: P (Partially achieved)**

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SUP.1-A1 | Conduct and record QA audit of each process area | 4h | HIGH |
| SUP.1-A2 | Create QA status report summarizing findings | 2h | HIGH |
| SUP.1-A3 | Create process improvement register | 1h | MEDIUM |
| SUP.1-A4 | Define QA audit schedule | 1h | MEDIUM |

**Total estimated effort: 8h**

---

### 4.14 SUP.8 -- Configuration Management

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Develop a configuration management strategy | **L** | CM plan (SUP.8-001) with Git workflow, patch management | -- |
| BP.2 | Identify configuration items | **F** | CI table in CM plan; all items tracked in Git | -- |
| BP.3 | Establish a configuration management system | **F** | Git repository with submodules, patch files, documentation | -- |
| BP.4 | Manage the storage and handling of configuration items | **F** | Git provides versioning, history, branching | -- |
| BP.5 | Control changes to configuration items | **L** | Changes via Git commits; apply_all.sh verifies patch integrity | No formal change approval records |
| BP.6 | Establish and report the configuration management status | **P** | Git log provides history | No CM status report |
| BP.7 | Verify and ensure the completeness and consistency of CIs | **L** | setup.sh verifies build from clean state | No formal configuration audit |

**CL1 Rating: L (Largely achieved)**

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **L** | CM process well-established via Git | No CM plan review or monitoring |
| GP 2.2 | Work Product Management | **L** | CM plan documented; items identified | No formal baseline records; no configuration audit report |

**CL2 Rating: L (Largely achieved)**

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SUP.8-A1 | Create formal baseline records for Phase 1, 2, 2.5, 3 | 2h | HIGH |
| SUP.8-A2 | Perform and document configuration audit | 2h | HIGH |
| SUP.8-A3 | Create CM status report | 1h | MEDIUM |

**Total estimated effort: 5h**

---

### 4.15 SUP.9 -- Problem Resolution Management

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Develop a problem resolution management strategy | **L** | Process documented in SUP.9-001; severity classification defined | -- |
| BP.2 | Identify and record problems | **F** | 33 problems recorded in GAP-ANALYSIS.md with GA-xx IDs | -- |
| BP.3 | Analyze and assess problems | **F** | Root cause analysis; severity; "what we claim vs. what's true" | -- |
| BP.4 | Develop corrective actions | **F** | Fix or accept decisions for all 33 gaps | -- |
| BP.5 | Resolve problems | **F** | 23 FIXED, 10 ACCEPTED, 0 open | -- |
| BP.6 | Track problems to closure | **F** | GAP-ANALYSIS.md tracks through FIXED/ACCEPTED/CLOSED | -- |
| BP.7 | Analyze problem trends | **P** | Summary table with severity counts | No trend analysis over time |

**CL1 Rating: F (Fully achieved)** -- All 33 problems tracked to closure with evidence.

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **L** | Process effectively executed; all problems resolved | No formal plan for problem resolution activities |
| GP 2.2 | Work Product Management | **L** | GAP-ANALYSIS.md under Git; comprehensive | No trend analysis; no review record |

**CL2 Rating: L (Largely achieved)**

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SUP.9-A1 | Create problem trend analysis (discovery rate per phase) | 1h | MEDIUM |
| SUP.9-A2 | Create review record for GAP-ANALYSIS.md review | 1h | HIGH |

**Total estimated effort: 2h**

---

### 4.16 SUP.10 -- Change Request Management

#### CL1 Base Practices

| BP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| BP.1 | Develop a change request management strategy | **L** | Process documented in SUP.10-001 | -- |
| BP.2 | Identify and record change requests | **L** | Changes tracked via Git commits and patch register | No formal CR IDs |
| BP.3 | Analyze and assess change requests | **L** | Impact analysis performed (patches, DIAG IDs, tests) | Analysis not formally recorded per CR |
| BP.4 | Approve change requests | **P** | Approval implicit (code review + test pass) | No formal approval records |
| BP.5 | Implement change requests | **F** | Changes implemented and tested | -- |
| BP.6 | Track change requests to closure | **L** | Git history; GAP-ANALYSIS updates | No formal CR status tracking |

**CL1 Rating: L (Largely achieved)**

#### CL2 Generic Practices

| GP | Practice | Rating | Evidence | Gap |
|---|---|---|---|---|
| GP 2.1 | Performance Management | **P** | Process exists but not formally planned or monitored | No CR metrics |
| GP 2.2 | Work Product Management | **P** | Git commits serve as records | No formal CR forms or register |

**CL2 Rating: P (Partially achieved)**

#### Actions for CL2

| # | Action | Effort | Priority |
|---|---|---|---|
| SUP.10-A1 | Create CR register with formal CR-xxx IDs for the 13 major patch changes | 3h | HIGH |
| SUP.10-A2 | Create CR template (ID, description, impact, approval, status) | 1h | HIGH |
| SUP.10-A3 | Record approval decisions for existing changes retroactively | 2h | MEDIUM |

**Total estimated effort: 6h**

---

## 5. Cross-Cutting CL2 Gaps

The following gaps are systemic across multiple process areas:

### 5.1 Review Records (affects all process areas)

**Current state**: All work products are self-reviewed but no formal review records exist (no reviewer name, date, findings, disposition).

**Action**: Create a review record template and generate review records for all 18 ASPICE documents and key work products.

| Effort | 8h (30 min per document/artifact) |
|---|---|
| Priority | HIGH (blocks CL2 for GP 2.2 across all areas) |

### 5.2 Baseline Records (affects SYS.1-5, SWE.1-6, SUP.8)

**Current state**: Git tags exist for phases but no formal baseline record documents (list of CIs, versions, approval).

**Action**: Create baseline record template and document baselines for Phase 1, 2, 2.5, 3.

| Effort | 3h |
|---|---|
| Priority | HIGH |

### 5.3 Measurement Data (affects MAN.3, SUP.1)

**Current state**: ASPICE criteria count (94/112) is tracked but no regular measurement data collection (schedule variance, defect density, test coverage percentage).

**Action**: Collect and document measurement data retrospectively for each phase.

| Effort | 4h |
|---|---|
| Priority | MEDIUM |

### 5.4 Test Reports (affects SYS.4-5, SWE.4-6)

**Current state**: Test scripts produce pass/fail output but no formal test report documents exist.

**Action**: Create test report template and generate reports for unit, integration, ASIL, smoke, and qualification tests.

| Effort | 6h |
|---|---|
| Priority | HIGH |

---

## 6. Overall CL2 Readiness Summary

### 6.1 Process Area Ratings

| # | Process Area | CL1 Rating | CL2 GP 2.1 | CL2 GP 2.2 | CL2 Ready |
|---|---|---|---|---|---|
| 1 | MAN.3 | L | P | P | NO |
| 2 | SYS.1 | L | P | P | NO |
| 3 | SYS.2 | L | L | L | CLOSE |
| 4 | SYS.3 | L | L | L | CLOSE |
| 5 | SYS.4 | L | P | L | NO |
| 6 | SYS.5 | L | P | L | NO |
| 7 | SWE.1 | F | L | L | CLOSE |
| 8 | SWE.2 | F | L | L | CLOSE |
| 9 | SWE.3 | F | L | L | CLOSE |
| 10 | SWE.4 | L | P | L | NO |
| 11 | SWE.5 | L | P | L | NO |
| 12 | SWE.6 | L | P | L | NO |
| 13 | SUP.1 | L | P | P | NO |
| 14 | SUP.8 | L | L | L | CLOSE |
| 15 | SUP.9 | F | L | L | CLOSE |
| 16 | SUP.10 | L | P | P | NO |

### 6.2 Summary

| Status | Count | Process Areas |
|---|---|---|
| CL2 CLOSE (needs review records only) | 6 | SYS.2, SYS.3, SWE.1, SWE.2, SWE.3, SUP.9 |
| CL2 NOT YET (needs test reports + review records) | 4 | SYS.4, SYS.5, SWE.5, SWE.6 |
| CL2 NOT YET (needs test reports + coverage data) | 1 | SWE.4 |
| CL2 NOT YET (needs monitoring data + review records) | 3 | MAN.3, SYS.1, SUP.1 |
| CL2 NOT YET (needs formal CR register) | 1 | SUP.10 |
| CL2 CLOSE (needs baseline records + audit) | 1 | SUP.8 |

### 6.3 Total Effort to CL2

| Category | Effort |
|---|---|
| Review records (cross-cutting) | 8h |
| Test reports (cross-cutting) | 6h |
| Baseline records (cross-cutting) | 3h |
| Measurement data (cross-cutting) | 4h |
| Process-specific actions | 42h |
| **Total** | **63h** |

### 6.4 Priority Roadmap

| Priority | Actions | Effort | Impact |
|---|---|---|---|
| **Phase A (Week 1)**: Review records | Create review record template; generate records for all 18 ASPICE docs | 10h | Unblocks GP 2.2 for 6 "CLOSE" areas -> CL2 |
| **Phase B (Week 2)**: Test reports | Create test report template; generate 5 test reports (unit, smoke, integration, ASIL, qualification) | 8h | Unblocks SYS.4-5, SWE.4-6 |
| **Phase C (Week 3)**: Management evidence | Status reports, baseline records, CR register, measurement data | 15h | Unblocks MAN.3, SUP.1, SUP.8, SUP.10 |
| **Phase D (Week 4)**: Remaining items | QA audit, trend analysis, coverage measurement, remaining process-specific actions | 12h | Completes all areas |

**With 63 hours of focused effort (approximately 2 weeks full-time), the project can achieve CL2 across all 16 in-scope process areas.**

---

## 7. Strengths

The following project strengths are noted for the assessment record:

1. **Comprehensive gap analysis**: 33 problems identified through 10-role audit, all tracked to closure
2. **Strong test infrastructure**: 147 integration/ASIL criteria + 183 unit tests + 76 smoke criteria, all passing
3. **Complete traceability chain**: STKH-REQ -> SYS-REQ -> SW-REQ -> Design -> Code -> Unit Test -> Integration Test -> Qualification Test
4. **Full ASPICE document set**: All 18 work products produced with consistent format, IDs, and cross-references
5. **Robust configuration management**: Git with submodules, pinned dependency, version-checked patches, single-command build
6. **Effective problem resolution**: 33/33 gaps resolved (0 open), with clear fix/accept rationale
7. **Safety integration**: ASIL-D fault injection with 2,005-test matrix, selective DIAG_Handler (24/61 split)

## 8. Weaknesses

The following weaknesses require attention for CL2:

1. **No formal review records**: The single-engineer team has reviewed all work products but produced no review evidence
2. **No test reports**: Test scripts produce console output but no formal test report documents
3. **No baseline records**: Git tags exist but no baseline report documents
4. **No measurement data**: Process performance is not quantified beyond gap counts
5. **Retroactive documentation**: Many process documents were created during the assessment, not maintained from project start
6. **Single resource**: Bus factor of 1; no independent reviews possible without external reviewer
