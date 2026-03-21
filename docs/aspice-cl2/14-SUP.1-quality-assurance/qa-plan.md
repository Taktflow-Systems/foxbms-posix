# Quality Assurance Plan

| Document ID | Rev | Date | Classification |
|---|---|---|---|
| SUP.1-001 | 1.0 | 2026-03-21 | Confidential |

## Revision History

| Rev | Date | Author | Reviewer | Description |
|---|---|---|---|---|
| 1.0 | 2026-03-21 | An Dao | L. Fischer (AI-simulated) | Initial release |

## 1. Purpose

This document defines the quality assurance plan for the foxBMS 2 POSIX vECU project in accordance with ASPICE SUP.1 (Quality Assurance). It establishes the processes, reviews, and verification activities that ensure work products and processes conform to defined standards and plans.

## 2. Scope

Quality assurance activities cover all engineering work products (requirements, architecture, design, code, test specifications, test results), all supporting process outputs (configuration items, gap analyses, change records), and the processes themselves.

## 3. References

| ID | Title |
|---|---|
| [MAN.3-001] | Project Management Plan |
| [SUP.8-001] | Configuration Management Plan |
| [ASMT-SCOPE-001] | ASPICE CL2 Assessment Scope |

## 4. Quality Objectives

| Objective | Metric | Target |
|---|---|---|
| Process compliance | ASPICE criteria met / total criteria | >= 95% (106/112) |
| Defect containment | Open CRITICAL/HIGH gaps | 0 |
| Test coverage | Test criteria passing | 147/147 (100%) |
| Unit test coverage | Ceedling unit tests passing | 183+/183+ (100%) |
| Build reproducibility | setup.sh success on fresh clone | 100% |
| Documentation completeness | ASPICE work products produced | 18/18 |

## 5. Quality Assurance Activities

### 5.1 Code Review

All code changes are subject to review before integration into the main branch.

**Review Checklist for C Source Changes**:

| # | Check Item | Verification Method |
|---|---|---|
| 1 | Code compiles with -Wall -Wextra and zero warnings | GCC build output |
| 2 | No new FAS_ASSERT violations introduced | Smoke test pass |
| 3 | DIAG_Handler selective list is correct (24 HW suppressed, 61 SW enabled) | Code inspection of diag_cfg.c |
| 4 | CAN message encoding matches DBC specification | CAN log comparison |
| 5 | Database entry access follows foxBMS patterns (DATA_Read/DATA_Write) | Code inspection |
| 6 | HAL stub functions match production function signatures | Header comparison |
| 7 | No memory leaks or buffer overflows in new code | Static analysis, code review |
| 8 | Patch applies cleanly to foxBMS v1.10.0 | apply_all.sh test |

**Review Checklist for Python Changes (Plant Model, Tests)**:

| # | Check Item | Verification Method |
|---|---|---|
| 1 | CAN message IDs match foxBMS DBC | Code inspection |
| 2 | Physical values are in correct units (mV, mA, 0.01 degC) | Code inspection |
| 3 | Test criteria have clear pass/fail conditions | Code review |
| 4 | Process lifecycle (start, monitor, stop) handles timeouts | Code review |
| 5 | No hardcoded absolute paths | Code inspection |

### 5.2 Static Analysis

| Tool | Configuration | Scope | Frequency |
|---|---|---|---|
| GCC -Wall -Wextra | All warnings enabled | All C source files | Every build |
| GCC -Werror (selective) | Critical warnings as errors | New/modified files | Every build |
| Python linting | Standard PEP 8 | Plant model, test scripts | Before commit |

### 5.3 Unit Testing

| Framework | Test Count | Scope | Frequency |
|---|---|---|---|
| Ceedling | 183+ tests | foxBMS modules (SOA, SOC, BMS, DIAG, etc.) | Before each integration |

Unit tests verify individual module behavior in isolation using mock/stub dependencies. Test results are captured as Ceedling output.

### 5.4 Integration Testing

| Script | Criteria | Scope | Frequency |
|---|---|---|---|
| test_integration.py | 21 criteria | vECU + plant model end-to-end | After code changes |
| test_asil.py | 50 criteria | ASIL-D fault injection paths | After safety-relevant changes |

### 5.5 Smoke Testing

| Script | Scope | Frequency |
|---|---|---|
| test_smoke.py | BMS NORMAL, contactors, SOC | Every build (included in setup.sh) |

### 5.6 Documentation Review

All ASPICE work products are reviewed against the following criteria:

| # | Check Item |
|---|---|
| 1 | Document has revision history with author and date |
| 2 | Document has unique document ID |
| 3 | Requirements have unique IDs and traceability references |
| 4 | Test cases trace to requirements |
| 5 | Technical content is accurate (matches current implementation) |
| 6 | ASIL classifications are consistent with HARA |
| 7 | Cross-references to other documents are valid |

### 5.7 Gap Analysis Review

The GAP-ANALYSIS.md document is the quality backbone of the project. Quality assurance activities include:

| Activity | Frequency |
|---|---|
| Review all open gaps for severity accuracy | Each phase gate |
| Verify FIXED gaps with test evidence | Upon gap closure |
| Verify ACCEPTED gaps have documented rationale | Upon acceptance |
| Update gap counts in project metrics | Weekly |

## 6. Non-Conformance Handling

### 6.1 Process

1. **Detection**: Non-conformance identified during review, testing, or gap analysis
2. **Recording**: Logged in GAP-ANALYSIS.md with GA-xx identifier and severity
3. **Analysis**: Root cause determined; impact assessed
4. **Correction**: Fix implemented and tested
5. **Verification**: Fix verified by re-running relevant tests
6. **Closure**: GAP-ANALYSIS.md updated to FIXED with evidence

### 6.2 Severity Classification

| Severity | Definition | Response Time |
|---|---|---|
| CRITICAL | Safety function incorrect or missing | Immediate (block release) |
| HIGH | Core functionality broken or significant deviation from specification | Within current phase |
| MEDIUM | Deviation from specification with workaround available | Within next phase |
| LOW | Minor deviation or cosmetic issue | Tracked for future resolution |

## 7. Quality Records

The following quality records are maintained:

| Record | Location | Purpose |
|---|---|---|
| GAP-ANALYSIS.md | Repository root | Issue tracking and resolution |
| COVERAGE.md | Repository root | Feature coverage verification |
| Test output logs | tests/ output | Test execution evidence |
| Build logs | build/ output | Compilation evidence |
| ASPICE documents (18) | docs/aspice/ | Process compliance evidence |
| CL2 gap assessment | docs/aspice-cl2/00-assessment/ | Capability level evidence |

## 8. Quality Assurance Schedule

| Activity | Trigger | Responsible |
|---|---|---|
| Code review | Every code change | An Dao (self-review + checklist) |
| Static analysis | Every build | Automated (GCC flags) |
| Unit test execution | Before integration | An Dao |
| Smoke test | Every build (setup.sh) | Automated |
| Integration test | After code changes | An Dao |
| ASIL test | After safety changes | An Dao |
| Gap analysis review | Phase gate | An Dao |
| Document review | Before CL2 assessment | An Dao |

## 9. Limitations and Improvement Actions

### 9.1 Current Limitations

| Limitation | Impact | Planned Improvement |
|---|---|---|
| Single-person team limits independent review | Reviews are self-reviews | Seek peer review for CL2 evidence |
| No automated CI pipeline yet | Tests run manually | Phase 4: Docker + CI integration |
| No formal review records (minutes, sign-off) | CL2 GP 2.2 gap | Create review record templates |
| No code coverage measurement tool | Cannot quantify unit test coverage % | Integrate gcov/lcov |

### 9.2 CL2 Actions Required

To achieve CL2 for SUP.1, the following additional evidence is needed:
1. Documented review records with reviewer name and date
2. QA audit trail showing process adherence checks
3. Escalation records for non-conformances
4. Periodic QA status reports
