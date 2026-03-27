# Improvement Strategy v2 — Research Synthesis

**Date**: 2026-03-27
**Based on**: BMS company pain point research + technical improvement analysis

---

## 3 Things That Change Everything

### 1. CAN Log Quality Scoring (6 days, do FIRST)

Before running any ML, score the customer's CAN log:

```
=== CAN Log Quality Report ===
File: customer_bench_run.blf
Duration: 3h 42m | Messages: 2.8M | Score: 78/100 (Grade B)

Signal Completeness: 12/12 required     [PASS]
Message Dropout: 2.3%                    [PASS]
Stuck Signals: V_cell_7 stuck 847 msgs   [WARNING]
Current Sensor Offset: +127 mA at rest   [WARNING]

Note: Cell 7 voltage sensor may have intermittent fault.
      Current offset will cause ~0.13 Ah/hr SOC drift.
```

**Why this is the #1 priority**: It builds trust instantly. When you tell a BMS company "we found a stuck voltage sensor on cell 7 before we even ran the ML" — that's competence. It also protects us when ML results are poor because input data is bad.

**Cost**: 6 days. **Impact**: Every customer interaction starts with this.

### 2. 3-Way SOC Comparison: BMS vs ML vs Reference EKF (14 days, core differentiator)

Nobody else offers this. The output:

```
Time | BMS_SOC | ML_SOC | EKF_SOC | BMS_vs_EKF | ML_vs_EKF
0    | 85.2%   | 84.8%  | 85.0%   | +0.2%      | -0.2%
3600 | 62.1%   | 64.5%  | 61.8%   | +0.3%      | +2.7%
```

- BMS and EKF agree, ML diverges → ML domain gap (our problem)
- ML and EKF agree, BMS diverges → BMS calibration issue (their problem, we found it)
- All three diverge → data quality issue (quality score already flagged it)

**Why this matters for BMS companies**: ISO 26262 requires independent validation. The EKF is physics-based (different method from their BMS). The LSTM is data-driven (yet another method). Three independent estimates triangulate the truth.

**Killer feature**: "Your SOC drifts +3.2% vs reference EKF during aggressive discharge at -10°C. Here's where and why. Our ML and EKF both agree — your coulomb counting has a cold-temperature bias."

**Cost**: 14 days. **Impact**: This is what we demo. This is what they pay for.

### 3. Auto-Generated ISO 26262 / ASPICE Test Reports (12 days, revenue multiplier)

BMS companies spend 2-3 engineer-days per validation report. We auto-generate it:

```
foxBMS POSIX ML Pipeline — Software Qualification Test Report
Per ISO 26262-6:2018 Clause 10, ASPICE SWE.6

1. Test Environment
   Tool: Taktflow ML Pipeline v1.0 | ONNX Runtime 1.24.4
   Models: SOC LSTM (BMW i3 + NASA), EKF (1RC, Chen2020 params)
   Data: customer_bench_run.blf (3h 42m, quality score 78/100)

2. Requirements Traceability
   REQ_ID           | Test_Case    | Result | Evidence
   SWR-BMS-SOC-001  | TC-SOC-ACC   | PASS   | SOC RMSE 2.1% < 5% threshold
   SWR-BMS-SOC-002  | TC-SOC-COLD  | FAIL   | SOC error 6.3% at -10°C > 5%
   SWR-BMS-OV-001   | TC-OV-DETECT | PASS   | Contactor open in 1.5s < 2s
   ...

3. Anomaly Summary
   1 failed requirement: SWR-BMS-SOC-002 (cold temperature SOC accuracy)
   Recommendation: Retune EKF process noise for T < 0°C

4. Conclusion
   11/12 requirements PASS. 1 FAIL (cold SOC). See Section 3.
```

**Why this matters**: ISO 26262 assessment costs $150K-$500K. ASPICE assessment costs $30K-$80K. If our auto-generated report saves their engineer 2 days per variant × 20 variants = 40 engineer-days = €24K of labor. That's worth €10-15K to them.

**Cost**: 12 days. **Impact**: Direct labor savings they can quantify.

---

## Updated Numbers (from research)

### What BMS companies actually spend

| Item | Cost | Our alternative | Savings |
|---|---|---|---|
| Full validation per pack variant | €20K-80K (4-12 weeks bench) | €5-15K (1 week SIL + ML) | 4-8x cheaper |
| ISO 26262 assessment preparation | €200K-500K | We provide the test evidence they need | Saves €20-50K in report preparation |
| ASPICE SWE.6 test report | 2-3 engineer-days per variant | Auto-generated in 5 minutes | 40 days saved across 20 variants |
| dSPACE HIL rig | €100K-500K per rig | €20-40K SIL on laptop | 5-25x cheaper |
| Hiring one more test engineer | €80-120K/year (loaded, EU) | €50-100K/year service contract | Same output, no headcount |

### What BMS companies actually need validated

| Requirement | Typical spec | How we measure it |
|---|---|---|
| SOC accuracy (25°C) | < 3% RMSE | 3-way comparison: BMS vs ML vs EKF |
| SOC accuracy (-10°C) | < 5% RMSE | Same, with cold-temperature CAN log |
| SOC accuracy (EOL) | < 5% RMSE | Same, with aged cell data (FOBSS/LiionPro) |
| Fault detection (OV) | Contactor open < 2s | SIL fault injection, measure response time |
| Fault detection (OT) | Contactor open < 5s | Same |
| Cell balancing | < 30mV spread after balance | Imbalance trend analysis from CAN log |
| Communication integrity | < 0.1% message dropout | CAN log quality scoring |

### Real failure modes ML catches (from research)

| Failure mode | Threshold detection | ML detection | Annual recall cost if missed |
|---|---|---|---|
| **Cell connection resistance increase** | Misses until OV threshold | Detects load-dependent voltage spikes early | Hyundai Kona: $900M recall |
| **Current sensor drift** | SOC drifts silently | Cross-references I sensor vs V behavior | Chevy Bolt: overcharge leading to fires |
| **Gradual capacity asymmetry** | Misses (within threshold) | Trends cell-to-cell capacity over months | Warranty cost: $500-2K per pack |
| **Intermittent comms loss** | Misses if transient | Detects degrading retry/CRC patterns | ESS fires: 23+ incidents in Korea |
| **Contactor wear** | Only after welding | Detects increasing contact resistance | $10K+ per incident |

---

## Revised 30-Day Plan (incorporating improvements)

### Week 1 (Day 1-5): Foundation

| Day | Hours | What | New vs Original |
|---|---|---|---|
| 1 | 8h | Download BMW i3 data, compute real norm stats, retrain anomaly on real CAN baseline | Same |
| 2-3 | 16h | FOBSS validation, citable accuracy numbers | Same |
| 4-5 | 16h | **NEW: CAN Log Quality Scorer** — implement dropout, jitter, stuck signal, offset detection, grade system | Replaces "systemd hardening" (moved to Day 18) |

**After Week 1**: We have accuracy numbers + quality scoring. Can say: "We checked your data quality AND validated our models on foxBMS hardware data."

### Week 2 (Day 6-10): Pipeline + Quality

| Day | Hours | What | New vs Original |
|---|---|---|---|
| 6-7 | 16h | Build run_audit.py pipeline (decode → extract → infer) | Same |
| 8 | 8h | Integrate quality scorer as Stage 0 of pipeline. Every audit starts with quality report. | **NEW** |
| 9-10 | 16h | **NEW: Reference EKF implementation** — 1RC Thevenin model, parameter extraction from CAN pulse events, 3-way SOC comparison framework | Replaces "variant config testing" (moved to Week 3) |

**After Week 2**: Pipeline runs: quality score → decode → extract → 3-way SOC comparison → predictions. This is the core product.

### Week 3 (Day 11-15): Reports + Bench

| Day | Hours | What | New vs Original |
|---|---|---|---|
| 11-12 | 16h | Report generator: SOC validation (with 3-way plot), thermal risk, cell health, quality report | Enhanced with 3-way comparison |
| 13 | 8h | **NEW: ISO 26262 / ASPICE report template** — auto-generated traceability matrix, test evidence, verification conclusion | NEW |
| 14-15 | 16h | Bench sidecar (DBC-driven) + auto-DBC config + CANape DBC | Same |

**After Week 3**: Professional reports with ISO 26262 framing. Bench sidecar ready. The sales package is compelling.

### Week 4 (Day 16-20): Package + Demo + LFP

| Day | Hours | What | New vs Original |
|---|---|---|---|
| 16 | 8h | **NEW: LFP chemistry support** — flat OCV curve handling, LFP-specific EKF tuning, chemistry parameter profiles for NMC/LFP/NCA | NEW (addresses #1 BMS pain point) |
| 17 | 8h | SIL variant testing (4 configs) + fault detection matrix | Moved from Week 2 |
| 18 | 8h | Docker packaging + systemd + VPS hardening | Moved from Week 1 |
| 19 | 8h | Demo script + rehearsal + recording + pitch deck | Same |
| 20 | 8h | Dry run on real data + retrospective + plan Day 21-50 | Same |

**After Week 4**: Ready for first BMS customer meeting. LFP support (their #1 pain). Docker works. Demo polished.

---

## What We Build vs What We Sell

| We build (technical) | We sell (business value) | Price |
|---|---|---|
| CAN log quality scorer | "We check your data quality before analysis — found a stuck sensor on cell 7" | Included in every tier |
| 3-way SOC comparison (BMS vs ML vs EKF) | "Your SOC drifts 3.2% at cold temp — both ML and reference EKF agree" | Core of Tier 0 report |
| ISO 26262 auto-report | "Here's your SWE.6 verification report. 11/12 requirements PASS." | €5-10K per report |
| Anomaly detection (IsolationForest + future LSTM-AE) | "We found 2 unusual patterns in your 200 bench logs" | Tier 0 batch: €5-15K |
| SIL variant testing | "Your firmware validated on 4 pack configs in 1 day instead of 8 weeks" | Tier 2: €20-40K |
| LFP SOC handling | "We handle your LFP packs where voltage-based SOC breaks" | Differentiator (included) |
| Bench sidecar | "ML predictions live in CANape alongside your BMS signals" | Tier 1: €5-15K |
| Continuous monitoring dashboard | "SOC accuracy tracked across firmware versions — regression alert" | €50-100K/year retainer |

---

## Competitive Position (updated)

| Competitor | What they sell | Gap we fill | Our price vs theirs |
|---|---|---|---|
| **dSPACE** | HIL hardware ($100K-500K/rig) | No ML. Host-side only ONNX. | 10x cheaper |
| **AVL/FEV** | Bespoke validation ($200K-1M) | Too expensive for small BMS companies | 10-50x cheaper |
| **Twaice/Accure** | Cloud battery analytics | Don't validate BMS firmware. Focus on cells. | Different market segment |
| **Vector CANape** | Measurement tool ($5-15K/seat) | No ML inference. No automated reports. | Complementary (we plug into their tool) |
| **MathWorks** | Simulink + BMS Toolbox ($10K+ license) | EKF only, no LSTM. Code-gen is complex. | We run ONNX directly, no code-gen needed |
| **Nobody** | 3-way SOC benchmarking from CAN logs | This doesn't exist as a service | We create the category |

**Our unique position**: Only company offering automated, ML-enhanced BMS firmware validation with 3-way SOC comparison, CAN quality scoring, and ISO 26262-ready reports — targeting small-to-mid BMS companies at 10x less than traditional validation houses.

---

## First Customer: Munich Electrification (internal pilot)

| Step | What | When |
|---|---|---|
| 1 | Get DBC file + 1 CAN log from ME S-CORE bench | Day 21 |
| 2 | Run full pipeline: quality score → 3-way SOC → reports | Day 22 |
| 3 | Present findings to ME test team | Day 23 |
| 4 | If findings are actionable → propose Tier 1 engagement | Day 24 |
| 5 | Deploy bench sidecar on ME Bologna bench | Day 25-30 |

**Advantage**: We work there. We have bench access. Zero sales overhead. The findings validate the entire pipeline on real customer data before going external.
