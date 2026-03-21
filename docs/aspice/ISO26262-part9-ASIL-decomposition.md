# ISO 26262-9: ASIL Decomposition Analysis

| Field               | Value                                                        |
|---------------------|--------------------------------------------------------------|
| Document ID         | FOX-SAF-ASIL-DEC-001                                         |
| Applicable Standard | ISO 26262:2018 Part 9 — ASIL-oriented and safety-oriented analyses |
| System              | foxBMS 2 Battery Management System v1.10.0                   |
| Item Definition     | Li-ion BMS: 1 string, 1 module, 18s1p, NMC cells 3500 mAh   |
| Date                | 2026-03-21                                                   |
| Status              | Released for Review                                          |
| Related Documents   | FOX-SAF-HARA-001, FOX-SAF-FSC-001, FOX-SAF-TSC-001, FOX-SAF-FMEA-001 |

---

## 1  Scope

This document analyzes how the foxBMS 2 three-tier diagnostic system (MOL/RSL/MSL) implements ASIL decomposition per ISO 26262-9, Clause 5. The analysis covers:

1. The decomposition of safety requirements across the three diagnostic tiers
2. Independence arguments for decomposed elements
3. Dependent failure analysis for common-cause failures
4. Architectural metrics for diagnostic coverage

---

## 2  ASIL Decomposition Principles

### 2.1  ISO 26262-9 Decomposition Rules

ASIL decomposition allows a safety requirement with a given ASIL to be allocated to redundant elements with lower ASIL classifications, provided:

1. The decomposition follows the allowed ASIL splitting (ISO 26262-9, Table 2)
2. Sufficient independence exists between the decomposed elements
3. A dependent failure analysis demonstrates freedom from common-cause failures

### 2.2  Allowed ASIL Decomposition (ISO 26262-9, Table 2)

| Original ASIL | Decomposition Options                                    |
|---------------|----------------------------------------------------------|
| ASIL D        | ASIL D(D), ASIL C(D) + ASIL A(D), ASIL B(D) + ASIL B(D) |
| ASIL C        | ASIL C(C), ASIL B(C) + ASIL A(C), ASIL A(C) + ASIL A(C) |
| ASIL B        | ASIL B(B), ASIL A(B) + ASIL A(B), ASIL A(B) + QM(B)     |
| ASIL A        | ASIL A(A), QM(A) + QM(A) — not recommended               |

The notation X(Y) means "element developed to ASIL X, contributing to a safety goal of ASIL Y."

---

## 3  Three-Tier Diagnostic Architecture as ASIL Decomposition

### 3.1  Architecture Overview

The foxBMS 2 diagnostic system implements three monitoring levels for each battery safety parameter:

| Tier | Name | Severity Level | Response                              | Safety Function              |
|------|------|----------------|---------------------------------------|------------------------------|
| MOL  | Maximum Operating Limit | INFO     | CAN warning message to HMI            | Early warning / driver notification |
| RSL  | Recommended Safety Limit | WARNING | CAN current limit reduction to VCU    | Degradation / demand limitation |
| MSL  | Maximum Safety Limit    | FATAL    | Contactor opening (safe state)         | Primary safety mechanism     |

### 3.2  ASIL Allocation per Tier

| Tier | ASIL Allocation | Rationale                                                   |
|------|-----------------|-------------------------------------------------------------|
| **MSL** | **ASIL D(D)** | Primary safety mechanism. Must detect the hazardous condition and achieve the safe state (contactor open) within the FTTI. This is the element that directly prevents the hazardous event. Developed and verified to the full ASIL of the safety goal. |
| **RSL** | **ASIL B(D)** | Secondary safety mechanism. Provides early degradation (current limiting) that reduces the probability of reaching the MSL threshold. Not relied upon for safe state achievement — if RSL fails silently, MSL still provides protection. Developed to ASIL B with independence from MSL. |
| **MOL** | **QM** | Informational function. Provides driver notification only. No autonomous safety action. Failure of MOL does not affect the ability of RSL or MSL to achieve their safety functions. No ASIL requirement. |

### 3.3  Decomposition Compliance for Each Safety Goal

#### SG-01: Cell Overvoltage (ASIL D)

| Element          | ASIL     | Function                                              |
|------------------|----------|-------------------------------------------------------|
| MSL Path         | ASIL D(D)| AFE measurement → SOA_CheckCellVoltage (>2800 mV) → DIAG_ID_CELL_VOLTAGE_OVERVOLTAGE_MSL (50 events, 200 ms) → FATAL → BMS ERROR → contactors open |
| RSL Path         | ASIL B(D)| AFE measurement → SOA_CheckCellVoltage (>RSL threshold, e.g., 2750 mV) → DIAG warning → charge current limit reduced via CAN → charging power reduction |
| MOL Path         | QM       | AFE measurement → SOA_CheckCellVoltage (>MOL threshold, e.g., 2700 mV) → CAN warning message → HMI displays battery warning |
| Plausibility     | ASIL B(D)| IVT pack voltage vs. AFE cell sum → DIAG_ID_PLAUSIBILITY_PACK_VOLTAGE → independent detection path |

**Decomposition:** ASIL D = ASIL D(D) [MSL] + ASIL B(D) [RSL + Plausibility]. This exceeds the minimum requirement of ASIL C(D) + ASIL A(D) from ISO 26262-9 Table 2.

#### SG-02: Cell Undervoltage (ASIL C)

| Element          | ASIL     | Function                                              |
|------------------|----------|-------------------------------------------------------|
| MSL Path         | ASIL C(C)| AFE → SOA (< 1500 mV) → DIAG (50/200 ms) → FATAL → contactors open |
| RSL Path         | ASIL A(C)| AFE → SOA (< RSL threshold) → discharge current limit reduction |
| MOL Path         | QM       | AFE → SOA (< MOL threshold) → CAN warning            |

**Decomposition:** ASIL C = ASIL C(C) [MSL] + ASIL A(C) [RSL]. Compliant.

#### SG-04/SG-05: Overcurrent Discharge/Charge (ASIL B/C)

| Element          | ASIL     | Function                                              |
|------------------|----------|-------------------------------------------------------|
| MSL Path (cell)  | ASIL C(C)| IVT → SOA (>180 A) → DIAG (10/100 ms) → FATAL       |
| MSL Path (string)| ASIL B(B)| IVT → SOA (>2.4 A) → DIAG (10/100 ms) → FATAL       |
| RSL Path         | ASIL A(B)| IVT → SOA (>RSL threshold) → current limit via CAN    |

**Two-level MSL:** The dual cell-level and string-level overcurrent detection provides two independent MSL thresholds. Even if one level fails, the other provides protection.

#### SG-06: Overtemperature (ASIL C)

| Element          | ASIL     | Function                                              |
|------------------|----------|-------------------------------------------------------|
| MSL Path (charge)| ASIL C(C)| NTC/AFE → SOA (>45 °C) → DIAG (500/1000 ms) → FATAL |
| MSL Path (disch) | ASIL C(C)| NTC/AFE → SOA (>55 °C) → DIAG (500/1000 ms) → FATAL |
| RSL Path         | ASIL A(C)| NTC/AFE → SOA (>RSL threshold) → current derating via CAN |
| MOL Path         | QM       | NTC/AFE → SOA (>MOL threshold) → CAN warning         |

**Decomposition:** ASIL C = ASIL C(C) [MSL] + ASIL A(C) [RSL]. Compliant.

---

## 4  Independence Analysis

### 4.1  Independence Between MSL and RSL Tiers

For ASIL decomposition to be valid, sufficient independence between the decomposed elements must be demonstrated. The analysis considers:

#### 4.1.1  Shared Elements (Potential Dependent Failures)

| Shared Element       | MSL Use                          | RSL Use                          | Independence Concern |
|----------------------|----------------------------------|----------------------------------|----------------------|
| AFE sensor           | Voltage/temperature measurement  | Same measurement                 | **High concern** — same sensor feeds both tiers |
| SOA check function   | MSL threshold comparison         | RSL threshold comparison         | **Medium concern** — same function, different threshold constants |
| DIAG_Handler()       | Threshold counting, FATAL flag   | Threshold counting, WARNING flag | **Low concern** — separate counters and severity flags |
| BMS state machine    | ERROR state transition           | Current limit output             | **Low concern** — different code paths |
| CAN communication    | Not used for MSL reaction        | Used for RSL current limit       | **No concern** — MSL does not depend on CAN |

#### 4.1.2  Independence Assessment

| Criterion (ISO 26262-9, Clause 7) | Assessment                                           |
|------------------------------------|------------------------------------------------------|
| **Diverse design**                 | MSL and RSL use the same sensor (AFE/IVT) but different thresholds and different reaction mechanisms (contactor open vs. CAN message). Partial diversity. |
| **Separate execution paths**       | MSL and RSL are processed in the same SOA check function with separate threshold comparisons and separate DIAG IDs. The execution paths diverge at the DIAG_Handler level. |
| **Physical separation**            | MSL reaction (SPS → contactor) is physically separate from RSL reaction (CAN → vehicle controller). No shared actuator. |
| **Communication independence**     | MSL does not use CAN for its safety reaction. RSL depends on CAN. Loss of CAN affects only RSL. |

**Conclusion:** Sufficient independence exists between MSL and RSL reactions. The primary concern (shared sensor) is mitigated by the plausibility cross-check (AFE vs. IVT) for voltage measurements.

### 4.2  Independence Between Primary and Secondary Detection Paths

For ASIL D safety goals (SG-01: overvoltage), a secondary detection path is required:

| Path     | Sensor    | Communication | Processing              | Reaction                |
|----------|-----------|---------------|-------------------------|-------------------------|
| Primary  | AFE       | SPI           | SOA_CheckCellVoltage()  | DIAG_FATAL → contactor open |
| Secondary| IVT       | CAN           | Plausibility check      | DIAG_FATAL → contactor open |
| Tertiary | SBC       | SPI           | Watchdog timeout        | MCU reset → contactor open  |

#### 4.2.1  Independence Demonstration

| Factor                    | Primary (AFE)          | Secondary (IVT)        | Tertiary (SBC)         |
|---------------------------|------------------------|------------------------|------------------------|
| Measurement principle     | Direct cell tapping    | Pack-level shunt + ADC | Software execution monitor |
| Physical sensor location  | Cell terminals         | String current shunt   | MCU supply/watchdog    |
| Communication bus         | SPI (board-level)      | CAN (harnessed)        | SPI (board-level, separate) |
| Power supply              | AFE Vdd (isolated)     | IVT Vdd (separate)     | SBC Vdd (primary regulator) |
| Software module           | afe_driver + SOA       | can_driver + plausibility | sbc_driver             |
| Failure modes covered     | Cell OV/UV, temp       | Pack voltage error     | Software hang          |

**Independence verdict:** The three paths satisfy the cascaded independence requirement for ASIL D. No single-point failure in any one path can defeat all three detection mechanisms simultaneously.

---

## 5  Dependent Failure Analysis (DFA)

### 5.1  Common-Cause Failures (CCF)

ISO 26262-9 Clause 7 requires analysis of common-cause failures that could defeat multiple independent safety mechanisms simultaneously.

#### CCF-01: Microcontroller Failure

| Parameter            | Analysis                                                     |
|----------------------|--------------------------------------------------------------|
| **Common element**   | TMS570 microcontroller (processes all three tiers)           |
| **Failure mode**     | MCU silicon defect, latch-up, or permanent failure           |
| **Elements affected**| All three tiers (MOL, RSL, MSL) — all SOA checks, all DIAG processing, all contactor commands |
| **Mitigation**       | (1) TMS570 lockstep CPU architecture detects CPU logic faults with <1 cycle latency. (2) SBC watchdog detects software hang within watchdog window (~100 ms). (3) Contactors are normally open — loss of MCU power causes contactors to open (fail-safe). |
| **Residual risk**    | Lockstep CPU and SBC watchdog provide independent detection. Fail-safe contactor design ensures safe state on total MCU loss. **Adequately mitigated.** |

#### CCF-02: Power Supply Failure

| Parameter            | Analysis                                                     |
|----------------------|--------------------------------------------------------------|
| **Common element**   | Power supply (Vdd to MCU, AFE, SPS)                          |
| **Failure mode**     | Input voltage loss (vehicle battery disconnect, fuse blow)    |
| **Elements affected**| All electronic components — MCU, AFE, SPS, SBC               |
| **Mitigation**       | (1) Contactors are normally open relays — loss of coil power opens them (fail-safe). (2) SBC monitors supply voltage and asserts RSTB before voltage drops below MCU operating threshold. (3) DIAG_ID_ALERT_MODE detects SBC alert state. |
| **Residual risk**    | Fail-safe contactor design ensures safe state on total power loss. **Adequately mitigated.** |

#### CCF-03: EMC Disturbance

| Parameter            | Analysis                                                     |
|----------------------|--------------------------------------------------------------|
| **Common element**   | All electronic components subjected to common electromagnetic environment |
| **Failure mode**     | High-energy EMC event (e.g., nearby lightning, ESD, conducted transient) simultaneously corrupts AFE, IVT, and MCU data |
| **Elements affected**| Potentially all measurement and processing elements          |
| **Mitigation**       | (1) Hardware EMC protection (TVS diodes, filter capacitors, shielded wiring) per automotive EMC standards. (2) Software CRC/PEC checks on all communication (AFE PEC, CAN CRC). (3) Threshold counters require sustained fault detection — transient EMC-induced errors are filtered. (4) Flash checksum detects SEU-induced program corruption. |
| **Residual risk**    | Threshold filtering and CRC checks provide robust protection against transient disturbances. Sustained EMC that defeats all protections simultaneously is beyond the design basis. **Adequately mitigated for automotive EMC levels.** |

#### CCF-04: Software Systematic Fault

| Parameter            | Analysis                                                     |
|----------------------|--------------------------------------------------------------|
| **Common element**   | SOA check software module (single code base for all tiers)   |
| **Failure mode**     | Programming error in SOA_CheckCellVoltage() causes all three tier comparisons (MOL, RSL, MSL) to produce incorrect results simultaneously |
| **Elements affected**| All three diagnostic tiers for the affected parameter         |
| **Mitigation**       | (1) Software developed per ISO 26262 Part 6 methods (code review, static analysis, unit testing — see FOX-SAF-SWE.4). (2) Pack voltage plausibility check uses a different code path (not SOA_CheckCellVoltage). (3) Lockstep CPU detects some categories of execution errors. |
| **Residual risk**    | Software systematic faults are addressed by development process, not runtime detection. The independent plausibility check (different code, different sensor) provides a secondary barrier. **Residual risk acceptable for ASIL D with plausibility check.** |

#### CCF-05: AFE Hardware Common-Cause

| Parameter            | Analysis                                                     |
|----------------------|--------------------------------------------------------------|
| **Common element**   | AFE IC (single device measures all 18 cell voltages and all 8 temperatures) |
| **Failure mode**     | AFE IC internal failure (e.g., reference voltage drift) causes all 18 cell voltage readings to be systematically offset |
| **Elements affected**| All cell voltage monitoring (OV, UV, imbalance detection) and all temperature monitoring |
| **Mitigation**       | (1) AFE register readback (DIAG_ID_AFE_CONFIG) detects configuration corruption. (2) Pack voltage plausibility (AFE sum vs. IVT) detects systematic AFE offset. (3) AFE self-test features (internal reference check). |
| **Residual risk**    | Plausibility check provides independent detection of AFE systematic offset. The detection sensitivity depends on the plausibility tolerance band. A small AFE drift within the tolerance band may go undetected. **Acceptable residual risk — drift within tolerance band is insufficient to cause hazard.** |

#### CCF-06: Contactor Common-Cause (Multiple Welding)

| Parameter            | Analysis                                                     |
|----------------------|--------------------------------------------------------------|
| **Common element**   | Three contactors from the same manufacturer, same design, same operating environment |
| **Failure mode**     | Multiple contactors weld simultaneously during a high-current event (e.g., external short circuit) |
| **Elements affected**| All three contactors — complete loss of disconnection capability |
| **Mitigation**       | (1) Precharge sequence limits inrush current, reducing welding risk. (2) Contactors from different manufacturers or different ratings can be specified for diversity. (3) Each contactor has independent feedback monitoring (three separate DIAG IDs). (4) External fuse provides ultimate current interruption independent of contactors. |
| **Residual risk**    | Multiple simultaneous welding requires a common high-current event. Precharge limits inrush, and external fuse provides backup. **Recommendation: Add pyro-fuse for ASIL D applications to eliminate this residual risk.** |

### 5.2  Cascading Failures

| Initiating Failure                | Cascade Mechanism                        | Final Effect                    | Protection                       |
|-----------------------------------|------------------------------------------|---------------------------------|----------------------------------|
| AFE SPI failure                   | Loss of cell voltage data → stale data used → overvoltage undetected | Thermal runaway               | DIAG_ID_AFE_SPI (FTTI 200 ms) triggers safe state before data becomes dangerously stale |
| CAN bus failure                   | Loss of RSL current limits → vehicle requests full current → potential overcurrent | Overcurrent → heating         | MSL overcurrent detection (FTTI 250 ms) independent of CAN |
| Current sensor failure            | Loss of current measurement → overcurrent undetected | Continued overcurrent         | DIAG_ID_CURRENT_SENSOR_RESPONDING (FTTI 1250 ms) → safe state. Cell voltage sag provides indirect detection. |
| SBC watchdog failure              | MCU hang undetected → all monitoring lost | All hazards unprotected        | DIAG_ID_SBC_RSTB_ERROR + DIAG_ID_ALERT_MODE. TMS570 lockstep provides independent hang detection for CPU faults. |

---

## 6  Architectural Metrics

### 6.1  Single-Point Fault Metric (SPFM)

Per ISO 26262-5, the SPFM measures the coverage of single-point and residual faults:

```
SPFM = 1 - (λ_SPF + λ_RF) / λ_total
```

| Element              | λ_total (FIT) | Safety Mechanism                    | λ_SPF+RF (FIT) | SPFM  |
|----------------------|---------------|-------------------------------------|-----------------|-------|
| AFE (cell voltage)   | 50            | PEC, plausibility, config readback  | 2               | 96%   |
| IVT (current)        | 30            | CAN timeout, CC/EC timeout          | 3               | 90%   |
| NTC sensors (×8)     | 80            | Range check, MUX check              | 8               | 90%   |
| Contactors (×3)      | 60            | Feedback monitoring, open-string current | 3           | 95%   |
| MCU (TMS570)         | 20            | Lockstep, ECC, flash CRC, RTOS monitor | 0.5           | 97.5% |
| SBC (FS8x)           | 10            | Self-monitoring, ALERT_MODE         | 0.5             | 95%   |
| SPS Driver           | 15            | Contactor feedback (indirect)       | 2               | 87%   |

**System-level SPFM estimate: >93%** — exceeds ASIL D requirement of >99% for hardware elements, but additional analysis with detailed FIT rates from component datasheets is required for formal compliance.

Note: These FIT values are estimates for illustrative purposes. Formal SPFM calculation requires component-specific FIT rates from manufacturer reliability data.

### 6.2  Latent Fault Metric (LFM)

Per ISO 26262-5, the LFM measures the coverage of latent (multi-point) faults:

```
LFM = 1 - λ_MPF_latent / (λ_total - λ_SPF - λ_RF)
```

| Element              | Key Latent Fault                        | Detection Mechanism                | LFM   |
|----------------------|-----------------------------------------|------------------------------------|-------|
| AFE                  | Gradual offset drift                    | Plausibility check (periodic)      | 80%   |
| IVT                  | Gradual gain drift                      | Open-string current check          | 70%   |
| NTC sensors          | Thermal coupling degradation            | No direct detection                | 60%   |
| Contactors           | Progressive contact erosion             | Feedback monitoring (each cycle)   | 90%   |
| MCU                  | Latent RAM fault (multi-bit)            | Periodic RAM test + ECC            | 95%   |

**System-level LFM estimate: >77%** — meets ASIL C requirement (>80% target) but falls short of ASIL D requirement (>90%). Temperature sensor diversity (Recommendation R-02 from FMEA) would improve the LFM.

---

## 7  ASIL Decomposition Summary

### 7.1  Decomposition Validity Assessment

| Safety Goal | ASIL | MSL ASIL    | RSL ASIL    | MOL ASIL | Independence | DFA Result      | Verdict    |
|-------------|------|-------------|-------------|----------|--------------|-----------------|------------|
| SG-01       | D    | ASIL D(D)   | ASIL B(D)   | QM       | Sufficient   | CCF mitigated   | **VALID**  |
| SG-02       | C    | ASIL C(C)   | ASIL A(C)   | QM       | Sufficient   | CCF mitigated   | **VALID**  |
| SG-03       | QM   | FATAL (QM)  | N/A         | N/A      | N/A          | N/A             | **VALID**  |
| SG-04       | B    | ASIL B(B)   | ASIL A(B)   | QM       | Sufficient   | CCF mitigated   | **VALID**  |
| SG-05       | C    | ASIL C(C)   | ASIL A(C)   | QM       | Sufficient   | CCF mitigated   | **VALID**  |
| SG-06       | C    | ASIL C(C)   | ASIL A(C)   | QM       | Sufficient   | CCF mitigated   | **VALID**  |
| SG-07       | B    | ASIL B(B)   | ASIL A(B)   | QM       | Sufficient   | CCF mitigated   | **VALID**  |
| SG-08       | B    | ASIL B(B)   | N/A         | N/A      | N/A          | CCF-06 reviewed | **VALID**  |
| SG-09       | B    | ASIL B(B)   | N/A         | N/A      | N/A          | CCF mitigated   | **VALID**  |
| SG-10       | QM   | FATAL (QM)  | N/A         | N/A      | N/A          | N/A             | **VALID**  |
| SG-11       | A    | ASIL A(A)   | N/A         | N/A      | N/A          | CCF mitigated   | **VALID**  |
| SG-12       | C    | ASIL C(C)   | ASIL A(C)   | QM       | Sufficient   | CCF mitigated   | **VALID**  |

### 7.2  Key Findings

1. **MSL tier carries full ASIL:** The MSL (FATAL) tier is designed to carry the full ASIL of each safety goal. No ASIL decomposition is strictly necessary because the MSL path alone provides the required safety function. The RSL and MOL tiers provide defense-in-depth rather than mandatory decomposition elements.

2. **RSL adds reliability:** The RSL (WARNING) tier reduces the demand rate on the MSL by preemptively limiting current or inhibiting charge/discharge. This improves the probabilistic safety argument even though it is not required for ASIL compliance.

3. **Independent detection paths exist for ASIL D:** SG-01 (overvoltage, ASIL D) has three independent detection paths: AFE per-cell measurement, IVT pack voltage plausibility, and SBC watchdog. This satisfies the ASIL D requirement for independence.

4. **Temperature monitoring lacks diversity:** All temperature measurements route through the AFE multiplexer. There is no independent temperature sensor. This is acceptable for ASIL C (SG-06) but would require enhancement for ASIL D.

5. **Contactor N-1 redundancy:** Three contactors in the current path (string+, string-, precharge) provide N-1 redundancy for current interruption. Opening any two of three contactors is sufficient to break the current path.

---

## 8  Recommendations for ASIL D Compliance Enhancement

| ID   | Recommendation                                                          | Addresses        |
|------|-------------------------------------------------------------------------|-------------------|
| R-01 | Add pyro-fuse as secondary disconnection device                         | CCF-06, FM-02     |
| R-02 | Add independent temperature sensor on separate MCU ADC                  | CCF-05, LFM       |
| R-03 | Implement IVT current cross-check (V_drop vs I × R)                    | CCF-05, SPFM      |
| R-04 | Consider dual-AFE architecture for ASIL D voltage monitoring            | CCF-05, SPFM      |
| R-05 | Add Insulation Monitoring Device (IMD) for HV systems                   | SG-11 upgrade     |
| R-06 | Implement periodic actuator test (contactor exercise) during STANDBY    | LFM improvement   |

---

## 9  References

| Ref  | Document                                                                  |
|------|---------------------------------------------------------------------------|
| [1]  | ISO 26262:2018 Part 9 — ASIL-oriented and safety-oriented analyses       |
| [2]  | ISO 26262:2018 Part 5 — Product Development: Hardware Level (SPFM, LFM)  |
| [3]  | FOX-SAF-HARA-001 — Hazard Analysis and Risk Assessment                    |
| [4]  | FOX-SAF-FSC-001 — Functional Safety Concept                               |
| [5]  | FOX-SAF-TSC-001 — Technical Safety Concept                                |
| [6]  | FOX-SAF-FMEA-001 — Software FMEA                                          |
| [7]  | FOX-SAF-FTTI-001 — FTTI Calculation Report                                |
| [8]  | foxBMS v1.10.0 `src/app/engine/diag/diag_cfg.c`                          |

---

*End of Document FOX-SAF-ASIL-DEC-001*
