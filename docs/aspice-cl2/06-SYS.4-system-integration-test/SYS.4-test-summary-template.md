# SYS.4 Test Summary Report — [Release Version]

| Document ID | Rev | Date | Tester | Classification |
|---|---|---|---|---|
| FOX-SIT-SUM-[VER] | 1.0 | [DATE] | [NAME] | Confidential |

## 1. Test Execution Summary

| Metric | Value |
|---|---|
| Release under test | [version/commit] |
| Test catalog version | [catalog commit hash] |
| Total tests executed | [N] of [TOTAL] |
| Passed | [N] |
| Failed | [N] |
| Blocked | [N] |
| Skipped (with rationale) | [N] |
| Pass rate | [N]% |
| Execution date | [DATE] |
| Execution duration | [TIME] |
| Test environment | SIL (POSIX vECU on [HOST]) / HIL ([BENCH]) |

## 2. Results by Category

| Category | Total | Pass | Fail | Blocked | Skip |
|---|---|---|---|---|---|
| SIG (CAN Signals) | | | | | |
| SM (State Machine) | | | | | |
| DIAG (Diagnostics) | | | | | |
| THR (Thresholds) | | | | | |
| E2E (Data Flow) | | | | | |
| HW (Interfaces) | | | | | |
| FI (Fault Injection) | | | | | |
| B2B (Back-to-Back) | | | | | |
| DFA (Dependent Failure) | | | | | |
| SSR (Safety Reqs) | | | | | |
| END (Endurance) | | | | | |
| **TOTAL** | | | | | |

## 3. Results by ASIL Level

| ASIL | Total | Pass | Fail |
|---|---|---|---|
| D | | | |
| C | | | |
| B | | | |
| QM | | | |
| — | | | |

## 4. Failed Tests

| Test ID | Category | ASIL | Description | Failure Detail | Impact Assessment |
|---|---|---|---|---|---|
| | | | | | |

## 5. Blocked Tests

| Test ID | Reason | Resolution Plan |
|---|---|---|
| | | |

## 6. FTTI Measurement Results

| Safety Function | FTTI Budget (ms) | Measured Max (ms) | Measured Mean (ms) | σ (ms) | N | Verdict |
|---|---|---|---|---|---|---|
| Cell OV → contactors | 750 | | | | | |
| Cell UV → contactors | 750 | | | | | |
| Overcurrent → contactors | 250 | | | | | |
| Overtemp → contactors | 6050 | | | | | |
| AFE loss → contactors | 200 | | | | | |

## 7. Requirement Coverage

| Requirement Type | Total Reqs | Tested | Coverage |
|---|---|---|---|
| TSR (Technical Safety) | 15 | | |
| SSR (Software Safety) | 26 | | |
| SYS-REQ (System) | 101 | | |
| SW-REQ (Software) | 96 | | |
| FM (Failure Modes) | 19 | | |

## 8. Defects Found

| Defect ID | Severity | Test ID | Description | Status |
|---|---|---|---|---|
| | | | | |

## 9. Conclusion

[ ] All ASIL D tests PASS — release approved for safety validation
[ ] Failures exist — remediation required before release

**Signed**: _________________________ Date: _____________

## 10. Traceability

This report satisfies:
- **ASPICE CL2 SYS.4-BP.5**: Test results summarized and communicated
- **ASPICE CL2 PA 2.2**: Work products documented and baselined
- **ISO 26262-4 §8.4.4**: Test results evaluated against pass/fail criteria
