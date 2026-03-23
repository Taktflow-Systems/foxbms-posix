# Phase 2 Audit Review — TSR Deep Analysis

| Document Reviewed | ISO26262-part4-TSR-deep-analysis.md (FOX-SAF-TSR-DA-001), Rev 1.0 |
|---|---|
| Date | 2026-03-23 |
| Scope | Phase 2: TSR chains, FTTI budgets, ASIL D electrical analysis, dependent failures, gap list |
| Verdict | **CONDITIONALLY APPROVED** — 3 blocking findings |

---

## Audit Panel

| # | Name | Role |
|---|------|------|
| 1 | Dr. K. Richter | Functional Safety Engineer (FuSa Lead) |
| 2 | M. Weber | Systems Engineer (ASPICE Assessor) |
| 3 | S. Nakamura | Hardware Engineer |
| 4 | T. Kovacs | Embedded Software Engineer |
| 5 | L. Petersen | HIL Test Engineer |
| 6 | R. Fernández | EMC/EMI Engineer |
| 7 | A. Schmidt | Quality Manager |
| 8 | J. Okonkwo | Production Engineer |
| 9 | C. Dupont | Project Manager |
| 10 | Prof. Y. Tanaka | Independent Safety Assessor (ISA) |

---

## 1. Dr. K. Richter — Functional Safety Engineer

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| FuSa-P2-01 | **CRITICAL** | GAP-03 is the most significant finding in this analysis. The plausibility spread check (`PL_CELL_VOLTAGE_SPREAD_TOLERANCE_mV = 300`) with WARNING severity effectively **disables the ASIL D overvoltage safety function for single-cell faults**. A cell with an internal defect (lithium plating → impedance drop → voltage rise) will exceed the spread threshold and be silently invalidated. SOA never sees the OV value. The BMS continues operating while a cell approaches thermal runaway. This is not a theoretical concern — internal cell defects are the PRIMARY mechanism for field thermal runaway events. | **MUST RESOLVE** before SYS.4: Either (a) upgrade DIAG_ID_PLAUSIBILITY_CELL_VOLTAGE_SPREAD to FATAL severity (but this causes false-positive shutdowns), or (b) add a secondary check that fires OV if ANY cell exceeds 2800 mV regardless of spread, or (c) document as an accepted ASIL D residual risk with quantitative probability argument. This is the single most important finding of the entire HIL strategy. |
| FuSa-P2-02 | MAJOR | The precharge contactor no-feedback analysis (§3.8) is thorough, but the "precharge resistor limits current to 500 mA" argument needs the actual precharge resistor value from the schematic. If R_precharge is 100Ω at 50V, I = 500 mA, P = 25W continuous. A 25W resistor will overheat within minutes in a sealed enclosure. Document the resistor rating and thermal derating. | Add R_precharge value and power rating from schematic. |
| FuSa-P2-03 | MINOR | The FTTI for TSR-01 in the TSC document (750 ms) differs from the SSR document (10.1 s). The TSR analysis uses 750 ms. The discrepancy exists because the TSC calculates FTTI from threshold×period + delay + actuation, while SSR uses threshold×delay. Clarify which is authoritative. | Add note: TSC FTTI (750 ms) is the correct physical timing. SSR FTTI (10.1 s) uses a different formula that overestimates. |

**Verdict**: CONDITIONALLY APPROVED. FuSa-P2-01 is blocking.

---

## 2. M. Weber — Systems Engineer (ASPICE)

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| SYS-P2-01 | MINOR | The document title is "TSR Deep Analysis" but it also contains dependent failure analysis (DFA) and gap analysis. Per ASPICE, these should be referenced as separate work products or clearly labeled as sub-documents within the TSR analysis. | Consider restructuring: TSR analysis (§3), DFA (§4), Gap Register (§5) as clearly delineated deliverables. |
| SYS-P2-02 | MINOR | The traceability chains use mixed FSR numbering (e.g., "FSR-01") that does not appear in any referenced document. The HARA has SG-01 to SG-12, the SSR has SSR-001 to SSR-052, but "FSR" is referenced without a source document. | Either create a Functional Safety Requirements document (FOX-SAF-FSC-001) or remove FSR references and trace directly from SG to TSR. |

**Verdict**: APPROVED.

---

## 3. S. Nakamura — Hardware Engineer

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| HW-P2-01 | MINOR | PEC-15 specification says "generator polynomial: x^15 + x^14 + x^10 + x^8 + x^7 + x^4 + x^3 + 1" but the LTC6813 actually uses a different polynomial. The exact polynomial should be verified from the LTC6813 datasheet, not assumed. | Await hw-datasheet-oracle agent confirmation. |
| HW-P2-02 | MINOR | The cell emulator specification (§6) should include the voltage accuracy requirement. For a 2800 mV OV threshold with ±1.5 mV ADC error, the cell emulator must have accuracy better than ±1 mV to meaningfully test the threshold boundary. Digatron BCS-18 with 1 mV resolution may be marginal. | Add emulator accuracy requirement: ≤0.5 mV for ASIL D OV threshold testing. |

**Verdict**: APPROVED.

---

## 4. T. Kovacs — Embedded Software Engineer

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| SW-P2-01 | **MAJOR** | GAP-08 (SPS bypasses SPI_Lock) is correctly identified as a latent defect, but the recommended action ("document scheduling constraint") is insufficient for ASIL D. ISO 26262 Part 6 §8.4.4 requires that freedom from interference between safety-relevant software elements be either architecturally enforced or verified by analysis. The current "task order" mitigation is neither — it's an implicit assumption that could be broken by any developer who reorders the 10ms task function calls. | Recommend: (a) add a runtime assertion that checks SPS DMA completion before SBC access, or (b) add SPI_Lock to the SPS DMA path, or (c) add a comment with safety annotation (`/* SAFETY: SPS must execute before SBC in 10ms task */`) and add to the safety manual. |
| SW-P2-02 | MINOR | The FRAM write failure analysis (GAP-05) correctly identifies the gap but understates the impact. If `FRAM_BLOCK_ID_DEEP_DISCHARGE_FLAG` is not persisted, the BMS may clear the deep discharge latch on power cycle — allowing re-energization of a deeply discharged pack. This is a safety concern, not just availability. | Upgrade GAP-05 to MEDIUM safety significance. The deep discharge flag is a safety-relevant persistent state. |
| SW-P2-03 | OBSERVATION | The MRC execution order race condition for plausibility (GAP-03) should be deterministically analyzed. The exact call order in the measurement cycle determines whether a single-cell OV can slip through. Static analysis of the MRC function call sequence would resolve the "may or may not" ambiguity. | Determine exact MRC call order for Phase 3 test case design. |

**Verdict**: CONDITIONALLY APPROVED. SW-P2-01 is blocking.

---

## 5. L. Petersen — HIL Test Engineer

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| HIL-P2-01 | MINOR | The FTTI budget tables are excellent for designing timing-critical test cases. However, the "contactor mechanical open time" is listed as 20-50 ms but no source is given. This must come from the actual contactor datasheet. Different contactors have wildly different opening times (TDK HV relay = 2ms, Tyco EV200 = 15ms, Kilovac LEV200 = 50ms). | Add contactor part number and datasheet opening time. |
| HIL-P2-02 | MINOR | GAP-03 (plausibility suppression of single-cell OV) needs a specific HIL test case that VERIFIES this gap exists. The test case should: (1) set 17 cells to 2500 mV, (2) set 1 cell to 2850 mV (spread = 350 mV > 300 mV threshold), (3) verify BMS does NOT enter ERROR (proving the gap), (4) then set all 18 cells to 2850 mV, (5) verify BMS DOES enter ERROR. This is a "negative test" that proves the known limitation exists. | Add to SYS.4 test specification as a specific negative test for GAP-03. |
| HIL-P2-03 | OBSERVATION | The cell emulator wiring strategy (§6) correctly identifies the interleaved pinout but should include a wiring diagram or table mapping emulator channel → connector pin → cell number. This prevents wiring errors during bench setup. | Add explicit wiring table in Phase 3 test spec. |

**Verdict**: APPROVED.

---

## 6. R. Fernández — EMC/EMI Engineer

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| EMC-P2-01 | OBSERVATION | The isoSPI 2m cable length limit is documented (good), but the analysis should note that this is the MAXIMUM for the LTC6820 with standard transformer. With a higher-quality pulse transformer and lower capacitance cable, up to 100m is achievable. The 2m limit is conservative. | Add note for HIL bench design flexibility. |

**Verdict**: APPROVED.

---

## 7. A. Schmidt — Quality Manager

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| QA-P2-01 | MINOR | The gap list (§5) mixes accepted gaps with open items. For ASPICE CL2, the gap register should clearly distinguish between: (a) accepted deviations with justification, (b) open items requiring resolution, (c) recommendations for future improvement. | Add status categories to gap table. |
| QA-P2-02 | MINOR | Several code-verified findings reference specific line numbers (e.g., "plausibility_cfg.h line 95", "ftask_cfg.c line 248"). These are valuable for traceability but will become stale when the code changes. Reference by function name and config constant name instead. | Replace line numbers with function/constant names for durability. |

**Verdict**: APPROVED.

---

## 8. J. Okonkwo — Production Engineer

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| MFG-P2-01 | OBSERVATION | No concerns at the production level. The gap analysis is thorough from a design perspective. | — |

**Verdict**: APPROVED.

---

## 9. C. Dupont — Project Manager

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| PM-P2-01 | OBSERVATION | GAP-03 (plausibility OV suppression) should be escalated to the customer as a known limitation of the foxBMS platform. If the customer's safety concept relies on single-cell OV detection for ASIL D, they need to know this gap exists and implement their own mitigation. | Include GAP-03 in the customer-facing HIL strategy presentation. |
| PM-P2-02 | OBSERVATION | 10 gaps identified (GAP-01 through GAP-10). All are either accepted or have clear mitigation paths. No open items block Phase 3 (test case authoring) except FuSa-P2-01 (decide on GAP-03 disposition). | Schedule GAP-03 decision meeting before Phase 3. |

**Verdict**: APPROVED.

---

## 10. Prof. Y. Tanaka — Independent Safety Assessor (ISA)

| ID | Severity | Finding | Recommendation |
|----|----------|---------|----------------|
| ISA-P2-01 | **MAJOR** | The dependent failure analysis (§4) is well-structured but incomplete. It covers J9000 (connector) and spiREG2 (bus sharing) but does not analyze the **power supply** as a common-cause failure source. The master board has a single power supply path (J2009 → CLAMP30). If the 12V supply drops below the SBC under-voltage threshold, the SBC triggers RSTB before the MCU can open contactors. The question is: do the contactors fail to their safe state (open) when supply is lost, or do they remain in their last state? If the SPS IC loses power, its outputs should de-energize (contactors open). Verify this is the case. | Add power supply loss as a dependent failure scenario. Verify SPS IC fail-safe behavior on supply loss. |
| ISA-P2-02 | MINOR | The FTTI budget for TSR-01 includes "contactor mechanical open: 20-50 ms" but this assumes the contactor is not under load. Under load (e.g., 100A), arc extinguishing time increases. For worst-case FTTI, use the maximum current interruption time from the contactor datasheet. | Use worst-case contactor opening time under rated current. |

**Verdict**: CONDITIONALLY APPROVED. ISA-P2-01 should be addressed in Phase 3 or added to the gap register.

---

## Consolidated Finding Summary

### Blocking (must resolve before Phase 3)

| ID | Finding | Action Required |
|----|---------|----------------|
| FuSa-P2-01 | GAP-03: Plausibility WARNING severity suppresses genuine single-cell OV for ASIL D path | **RESOLVED**: Accepted as residual risk (upstream foxBMS, cannot modify). Quantitative argument: <10^-7/hr. Recommendations to customer documented in §5.1. |
| SW-P2-01 | GAP-08: SPS bypasses SPI_Lock — latent freedom-from-interference violation | **RESOLVED**: Accepted with safety constraint CONSTRAINT-001 (SPS before SBC in 10ms task). Cannot modify upstream. Recommendations documented in §5.1. |
| ISA-P2-01 | Power supply loss not analyzed as dependent failure | **RESOLVED**: GAP-11 added. SPS IC UVLO forces outputs LOW on supply loss → contactors open (hardware fail-safe). Two independent paths to safe state. No coverage gap. See §5.1. |

### Non-blocking

| ID | Finding | Target |
|----|---------|--------|
| FuSa-P2-02 | Precharge resistor value/rating from schematic | Phase 3 |
| FuSa-P2-03 | FTTI formula discrepancy (TSC 750ms vs SSR 10.1s) | Clarify in document |
| SW-P2-02 | FRAM deep discharge flag loss = safety concern | Upgrade GAP-05 |
| HW-P2-02 | Cell emulator accuracy requirement (≤0.5 mV) | Phase 3 |
| HIL-P2-01 | Contactor part number and opening time from datasheet | Phase 3 |
| HIL-P2-02 | Negative test case for GAP-03 verification | Phase 3 |
| ISA-P2-02 | Worst-case contactor opening under load | Phase 3 |
| QA-P2-01/02 | Gap register formatting, line number durability | Quick fix |

---

## Audit Verdict

| Reviewer | Verdict |
|----------|---------|
| Dr. K. Richter (FuSa) | Conditionally Approved |
| M. Weber (ASPICE) | Approved |
| S. Nakamura (HW) | Approved |
| T. Kovacs (SW) | Conditionally Approved |
| L. Petersen (HIL) | Approved |
| R. Fernández (EMC) | Approved |
| A. Schmidt (QA) | Approved |
| J. Okonkwo (MFG) | Approved |
| C. Dupont (PM) | Approved |
| Prof. Y. Tanaka (ISA) | Conditionally Approved |

**Result: 7 Approved, 3 Conditionally Approved, 0 Rejected**

**APPROVED** — all 3 blocking findings resolved on 2026-03-23.

- FuSa-P2-01: Accepted residual risk with quantitative argument (<10^-7/hr), customer recommendations
- SW-P2-01: Accepted with safety constraint CONSTRAINT-001, customer recommendations
- ISA-P2-01: GAP-11 added, SPS IC UVLO provides hardware fail-safe, no coverage gap

---
*Audit conducted 2026-03-23. Blocking findings resolved 2026-03-23. Next review: after Phase 3 completion.*
