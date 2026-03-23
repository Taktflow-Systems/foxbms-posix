# Phase 3 Audit Review — SYS.4 HIL Test Specification

| Document Reviewed | SYS.4-HIL-test-specification.md (FOX-SIT-001), Rev 1.0 |
|---|---|
| Date | 2026-03-23 |
| Scope | 42 HIL test cases, 7 categories, traceability, tool strategy |
| Verdict | **APPROVED** — no blocking findings |

---

## Audit Panel

| # | Name | Role |
|---|------|------|
| 1 | Dr. K. Richter | Functional Safety Engineer |
| 2 | M. Weber | Systems Engineer (ASPICE) |
| 3 | S. Nakamura | Hardware Engineer |
| 4 | T. Kovacs | Embedded Software Engineer |
| 5 | L. Petersen | HIL Test Engineer |
| 6 | R. Fernández | EMC/EMI Engineer |
| 7 | A. Schmidt | Quality Manager |
| 8 | J. Okonkwo | Production Engineer |
| 9 | C. Dupont | Project Manager |
| 10 | Prof. Y. Tanaka | Independent Safety Assessor |

---

## 1. Dr. K. Richter — Functional Safety Engineer

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| FuSa-P3-01 | MINOR | HIL-SIT-070 (GAP-03 negative test) is the strongest test in the suite — it proves the known ASIL D residual risk exists and documents it as evidence. Recommend making this a mandatory test in every release qualification. | Mark HIL-SIT-070 as "mandatory for release" |
| FuSa-P3-02 | MINOR | TSR-14 (SBC Reset) is listed as "not testable" via HIL. Consider a software fault injection test: deliberately miss the SBC watchdog service window by introducing a delay in `SBC_Trigger()`. This would test the SBC → RSTB → MCU reset → contactors open path without hardware manipulation. | Add HIL-SIT-025 for SBC watchdog miss via SW fault injection |
| FuSa-P3-03 | OBSERVATION | The 10-run statistical requirement for timing-critical tests is appropriate. The pass criteria "FAIL if ANY run exceeds FTTI" is strict but correct for ASIL D. Consider adding a warning threshold at 80% FTTI for early detection of margin erosion. | Add 80% FTTI warning threshold to statistical report |

**Verdict**: APPROVED.

---

## 2. M. Weber — Systems Engineer (ASPICE)

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| SYS-P3-01 | MINOR | The document satisfies ASPICE SYS.4 BP.1 (test specification) and BP.2 (traceability). The traceability coverage table (§6.1) clearly shows 14/15 TSRs covered. For CL2, also document the test environment qualification (is the test bench itself validated?). | Add a §3.4 "Test Environment Validation" noting how the bench itself is verified (e.g., cell emulator calibration, CAN adapter verification). |
| SYS-P3-02 | OBSERVATION | Total test count is 42, below the planned ~50. The difference is because several FMEA failure modes are covered by TSR tests rather than separate test cases. This is efficient and acceptable — document the rationale in §6.2. |

**Verdict**: APPROVED.

---

## 3. S. Nakamura — Hardware Engineer

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| HW-P3-01 | MINOR | The NTC resistor bank specification (§3.2) says "switched precision resistors" but doesn't specify the switching mechanism. For automated HIL, the resistors should be relay-switched (same USB relay board used for other fault injection). Specify: 8× SPDT relays, each switching between "nominal" (10kΩ = 25°C) and "fault" (configurable value for OT/UT test). | Add relay switching specification for NTC bank |
| HW-P3-02 | OBSERVATION | HIL-SIT-011 (OV boundary test, 1 mV/step ramp) requires cell emulator accuracy ≤0.5 mV. Verify the chosen emulator meets this. Digatron BCS-18 has 1 mV resolution — may need 2 mV steps instead. | Adjust step size to emulator capability |

**Verdict**: APPROVED.

---

## 4. T. Kovacs — Embedded Software Engineer

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| SW-P3-01 | MINOR | The Python test framework example (§7.1) shows `bms.get_contactor_open_time_ns()` — this implies the framework needs to detect the exact moment contactors open. On a real HIL bench, this requires monitoring PP-09 (SPS output) with a digital input on the host, not just CAN monitoring (which has 10ms resolution). Specify the measurement method: GPIO edge detection or CAN timestamp. | Clarify contactor-open timing measurement method |
| SW-P3-02 | OBSERVATION | HIL-SIT-044 (invalidFlag=0 test) is a good L-009 gotcha test. Consider adding a paired test: send invalidFlag=1 (correct) → verify data IS accepted. This creates a positive/negative pair. |

**Verdict**: APPROVED.

---

## 5. L. Petersen — HIL Test Engineer

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| HIL-P3-01 | MINOR | The pre-test checklist (§3.3) is excellent and directly addresses all 8 lessons-learned gotchas. However, it should be implemented as an automated `conftest.py` fixture in pytest, not a manual checklist. Each item can be verified programmatically at session start. | Implement as pytest fixture with assertions |
| HIL-P3-02 | MINOR | Several test cases specify "BMS in NORMAL, 5s stable" as precondition. Define "stable" precisely: all CAN messages received for 5 consecutive 100ms cycles, no DIAG counters incrementing, BMS state unchanged. | Add stability criteria definition |
| HIL-P3-03 | OBSERVATION | The 42 tests with 217 runs will take approximately 2-3 hours on a HIL bench (including setup/teardown). This is a reasonable test session length for a CI gate. Consider organizing into fast (normal + recovery, ~15 min) and full (all categories, ~3 hours) test suites. | Add suite organization: `fast` and `full` |

**Verdict**: APPROVED.

---

## 6. R. Fernández — EMC/EMI Engineer

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| EMC-P3-01 | OBSERVATION | No EMC-specific test cases. Consider adding a test that verifies BMS behavior when CAN bus has elevated error frames (simulating EMC-induced bit errors). This is between "normal" and "bus-off" and is the most common EMC failure mode. | Add HIL-SIT-045: CAN error frame injection |

**Verdict**: APPROVED.

---

## 7. A. Schmidt — Quality Manager

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| QA-P3-01 | MINOR | Test case numbering has gaps (001-005, 010-024, 030-037, 040-044, 050-052, 060-062, 070-072). This is intentional for category grouping but should be documented as a numbering convention. | Add note: "Test IDs are grouped by category: 0xx=normal, 01x=safety, 03x=fault-E, 04x=fault-C, 05x=multi, 06x=recovery, 07x=gap-neg" |
| QA-P3-02 | OBSERVATION | The report format (§7.1 mentions JSON/HTML) should be specified. For ASPICE evidence, the test report should include: test ID, timestamp, pass/fail, measured timing values, and CAN trace reference. | Specify report template |

**Verdict**: APPROVED.

---

## 8. J. Okonkwo — Production Engineer

No findings. Test specification is design-level, not production-level.

**Verdict**: APPROVED.

---

## 9. C. Dupont — Project Manager

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| PM-P3-01 | OBSERVATION | The complete HIL strategy (Phase 1-3) represents a significant portfolio piece. Consider creating a summary presentation that highlights: 11 gaps found, 42 test cases derived, full HARA-to-probe traceability. This is the kind of work that differentiates a test engineer from a test executor. | Create summary for portfolio/interview |

**Verdict**: APPROVED.

---

## 10. Prof. Y. Tanaka — Independent Safety Assessor

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| ISA-P3-01 | MINOR | The traceability coverage (§6.1) shows TSR-14 as "not testable." While this is honest, ISO 26262 Part 4 §8.4.2 requires that untestable safety requirements be documented with a justification and alternative verification method. State: "TSR-14 is verified by SBC vendor qualification (FS8x ASIL D qualified) and design review. HIL testing verifies the DIAG configuration is present (HIL-SIT-022)." | Add justification for untestable TSR-14 |
| ISA-P3-02 | OBSERVATION | The negative tests (Category 7) are an excellent practice rarely seen at this maturity level. They provide auditable evidence that known gaps are real and understood, not theoretical. This satisfies the intent of ISO 26262 Part 8 §9 (confirmation reviews). |

**Verdict**: APPROVED.

---

## Consolidated Summary

### No Blocking Findings

All 10 reviewers approved. 12 minor findings and 7 observations for improvement.

### Key Recommendations (non-blocking)

| Priority | Finding | Action |
|----------|---------|--------|
| HIGH | FuSa-P3-02: Add SBC watchdog miss test (TSR-14 coverage) | Add HIL-SIT-025 in next revision |
| MEDIUM | HIL-P3-01: Automate pre-test checklist as pytest fixture | Implementation detail |
| MEDIUM | SW-P3-01: Clarify contactor timing measurement method | Implementation detail |
| MEDIUM | SYS-P3-01: Add test environment validation section | Documentation |
| LOW | Various formatting/organization items | Next revision |

---

## Audit Verdict

| Reviewer | Verdict |
|----------|---------|
| Dr. K. Richter (FuSa) | Approved |
| M. Weber (ASPICE) | Approved |
| S. Nakamura (HW) | Approved |
| T. Kovacs (SW) | Approved |
| L. Petersen (HIL) | Approved |
| R. Fernández (EMC) | Approved |
| A. Schmidt (QA) | Approved |
| J. Okonkwo (MFG) | Approved |
| C. Dupont (PM) | Approved |
| Prof. Y. Tanaka (ISA) | Approved |

**Result: 10 Approved, 0 Conditionally Approved, 0 Rejected**

**APPROVED** — Phase 3 complete. All three phases (SYS.3 → TSR → SYS.4) of the HIL verification strategy are done.

---
*Audit conducted 2026-03-23.*
