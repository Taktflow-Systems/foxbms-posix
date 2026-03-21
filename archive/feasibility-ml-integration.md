# Feasibility Analysis: ML Integration with foxBMS POSIX vECU

**Date**: 2026-03-21
**Role**: System Architect — SIL/HIL Test Platform
**Scope**: Should we invest in connecting taktflow-bms-ml to foxbms-posix?

---

## Executive Summary

**Verdict: Feasible with constraints. Layer 1 is high-value/low-risk. Layer 2 is the differentiator but has validation gaps. Layer 3 is aspirational — defer.**

The integration is technically straightforward (same CAN bus, Python on both sides, ONNX models ready). The training data covers **two complementary levels** — BMS pack-level (BMW i3 driving) and battery cell-level (NASA, MIT, NREL, LiionPro) — both of which map to foxBMS subsystems. The domain gap at pack level (96S vs 18S) is real but mitigable; the cell-level data has **no topology gap** because cell physics are pack-independent. Additionally, the **FOBSS dataset is native foxBMS data** from KIT Radar (44-cell modular pack), offering a near-zero-gap validation path.

---

## 1. Technical Feasibility Assessment

### Layer 1: Trip Replay Plant Model

| Criterion | Assessment | Score |
|---|---|---|
| **Can we do it?** | Yes — CSV replay into existing plant_model.py CAN encoding | 9/10 |
| **Data available?** | 72 BMW i3 trips in `taktflow-bms-ml/data/bms-raw/bmw-i3-driving/` | 9/10 |
| **Interface compatible?** | BMW i3 gives pack V/I/T/SOC at 1Hz (pack level). NASA gives per-cell V/I/T across full charge/discharge (cell level). Combined: derive 18 cell voltages from pack_V + add per-cell variation from NASA cell curves. | 8/10 |
| **Effort estimate accurate?** | 2 days for pack-level replay. +1 day to add NASA-derived per-cell variation. Edge cases (foxBMS plausibility) may add 1 more day. | 7/10 |
| **Can it break foxBMS?** | Yes — real driving data has transients that may trigger SOA violations. But cell-level data lets us derive realistic per-cell spread (not naive pack_V/18). | 7/10 |

**Feasibility: HIGH**
**Blocker: None**
**Key risk**: foxBMS plausibility checks on cell voltage spread. Mitigated by using NASA cell data to generate realistic per-cell variation (±10-30mV based on real cell-to-cell spread in cycling data).

---

### Layer 2: ML Sidecar (ONNX Inference)

| Criterion | Assessment | Score |
|---|---|---|
| **Can we do it?** | Yes — ONNX Runtime + python-can + SocketCAN. Standard stack. | 9/10 |
| **Models ready?** | 5 ONNX models exported, tested offline. SOC LSTM verified with roundtrip. | 8/10 |
| **Interface compatible?** | Better than initially assessed — cell-level models (Thermal, Imbalance, SOH) have no topology gap. SOC LSTM needs per-cell normalization. FOBSS provides foxBMS-native validation data. | 7/10 |
| **Latency acceptable?** | ONNX inference ~5-15ms on CPU for LSTM. 1Hz inference rate vs 100Hz CAN = fine. | 9/10 |
| **Normalization data available?** | `soc_norm_mean.npy` and `soc_norm_std.npy` exist in data/bms-processed/ | 8/10 |

**Feasibility: MEDIUM-HIGH**
**Blocker: None (domain gap is mitigable — see Section 2)**
**Key risk**: SOC LSTM accuracy on foxBMS pack data is unvalidated. Cell-level models (Thermal, Imbalance) expected to transfer well. Validate all on FOBSS dataset.

---

### Layer 3: ML-Enhanced Fault Injection

| Criterion | Assessment | Score |
|---|---|---|
| **Can we do it?** | Yes — NREL thermal profiles map directly to foxBMS 0x280 cell temps (cell-level, no topology gap). MIT degradation data maps to 0x270 cell voltage fade. Scenario design is data-driven, not manual. | 7/10 |
| **DIAG_Handler ready?** | No — still fully suppressed. Fault detection paths are dead. Must implement selective DIAG first. | 3/10 |
| **Validation possible?** | No ground truth — we can't verify if foxBMS *should* have opened contactors at a given point without a physics model to say "this is actually dangerous". | 3/10 |

**Feasibility: LOW (today). MEDIUM after selective DIAG is implemented.**
**Blocker: DIAG_Handler suppression, no physics validation model**
**Recommendation: Defer to Phase 3 of PLAN.md. Don't attempt before Layer 1+2 are validated.**

---

## 2. Training Data: Two Levels, Both Useful

The taktflow-bms-ml repo contains data at two distinct levels. foxBMS operates at both levels, so both feed directly into the integration.

### foxBMS Operates at Two Levels

```
foxBMS CAN Output
|
+-- PACK LEVEL (what the BMS sees as a whole)
|   0x233  Pack voltage, pack current
|   0x235  SOC (coulomb counting)
|   0x232  Current/voltage limits (SOF)
|   0x240  Contactor state
|
+-- CELL LEVEL (what the BMS sees per cell)
    0x270  18x individual cell voltages (muxed)
    0x280  Cell temperatures (muxed)
    0x250  Cell voltage broadcast
    0x260  Cell temperature broadcast
```

### Data-to-foxBMS Mapping

| Dataset | Level | Size | foxBMS CAN Target | ML Model | Domain Gap |
|---|---|---|---|---|---|
| **BMW i3 driving** (72 trips) | Pack | 37MB | 0x233 pack V/I, 0x235 SOC | SOC LSTM | HIGH (96S vs 18S) — but normalizable to per-cell |
| **FOBSS foxBMS monitoring** (KIT) | Pack + Cell | 128MB | 0x270 cell V, 0x280 cell T, pack V/I | All models | **NEAR ZERO** — actual foxBMS hardware data |
| **NASA PCoE** (7565 cycles) | Cell | ~200MB | 0x270 cell voltages (derive per-cell V-SOC curves) | SOC LSTM (augments BMW i3) | **NONE** — cell physics are pack-independent |
| **LiionPro-DT** (5yr, 2M rows) | Cell lifecycle | 1.1GB | 0x270 cell V over time, capacity fade | SOH LSTM | **NONE** — cell-level degradation |
| **MIT degradation** (138 cells) | Cell lifecycle | ~500MB | Long-term cell V/capacity trends | RUL Transformer | **NONE** — cell-level end-of-life |
| **NREL thermal failure** (364 tests) | Cell | ~100MB | 0x280 cell temp ramp scenarios | Thermal CNN | **NONE** — thermal physics are cell-level |
| **EV pack multi-chem** | Cell groups | ~200MB | 0x270 cell voltage spread across 18 cells | Imbalance CNN | **LOW** — cell spread is topology-independent |
| **BMS fault diagnosis** (Mendeley) | BMS | ~50MB | Fault injection scenarios for 0x270/0x280 | Fault classification | LOW |

### Key Insight: Cell-Level Data Has No Domain Gap

The domain gap concern from the original analysis was about pack-level signals (360V BMW i3 vs 76V foxBMS). But **5 of 7 datasets operate at cell level**, where:
- A 3.7V NMC cell is a 3.7V NMC cell regardless of whether it's in a 96S or 18S pack
- Temperature physics (dT/dt, thermal runaway onset at ~130C) are cell-level
- Capacity degradation is per-cell
- Voltage spread / imbalance is relative (max-min), not absolute

Only the SOC LSTM has a real domain gap because it was trained on pack-level signals. Even that is mitigable: **normalize to per-cell voltage** (pack_V / N_cells) and the signal dynamics become topology-independent.

### FOBSS: The Zero-Gap Dataset

The FOBSS dataset from KIT Radar deserves special attention:
- **Source**: Actual foxBMS 2 hardware monitoring a 44-cell modular pack
- **Signals**: Cell-level voltages, temperatures, pack current — exactly what foxBMS CAN outputs
- **Format**: Archived at KIT Radar (128MB TAR), CC-BY license
- **Gap to foxBMS vECU**: Effectively zero — same firmware, same CAN protocol, different cell count (44 vs 18)

This is the **validation dataset**. Train on BMW i3 + NASA + NREL, **validate on FOBSS**. If models perform well on FOBSS foxBMS data, they will perform well on the foxBMS vECU.

### Revised Domain Gap Assessment

| Model | Pack-Level Gap | Cell-Level Gap | Overall | Mitigation |
|---|---|---|---|---|
| **SOC LSTM** | HIGH (96S vs 18S) | LOW (if retrained on per-cell V) | **MEDIUM** | Normalize to per-cell voltage; validate on FOBSS |
| **SOH LSTM** | N/A (cell-level model) | **NONE** — trained on LiionPro cell data | **LOW** | Needs cycling history; replay synthetic cycles through plant model |
| **Thermal CNN** | N/A (cell-level model) | **NONE** — trained on cell dT/dt | **LOW** | Directly applicable to foxBMS 0x280 cell temps |
| **RUL Transformer** | N/A (cell-level model) | **NONE** — trained on MIT cell cycles | **LOW** | Needs cycle history; replay through plant model |
| **Imbalance CNN** | N/A (cell-level model) | **NONE** — trained on cell voltage spread | **LOW** | Directly applicable to foxBMS 0x270 cell voltages |

### Revised Honest Assessment

The original analysis overstated the domain gap by focusing only on BMW i3 pack-level data. With the full dataset inventory:

- **3 models (Thermal CNN, Imbalance CNN, SOH LSTM)**: Cell-level training data, no topology dependency. Expected to transfer directly. Validate on FOBSS.
- **1 model (RUL Transformer)**: Cell-level but needs cycling history. Can demo with synthetic cycle replay. Not useful for single-run SIL.
- **1 model (SOC LSTM)**: Real domain gap at pack level. Three options:
  1. **Normalize to per-cell V** (pack_V/96 → pack_V/18 both give ~3.7V). Quick fix, may work.
  2. **Retrain on FOBSS data** (actual foxBMS signals). Best accuracy, 3-5 day effort.
  3. **Use NASA cell data directly** (already in combined training set). No pack topology in the data.

**The 1.83% RMSE should still not be claimed for foxBMS without validation, but the expected degradation is less severe than originally assessed.** Cell-level models are likely to transfer with <2x accuracy loss. Validate on FOBSS before making any claims.

---

## 3. Expected Value Analysis

### Layer 1: Trip Replay

| Value Dimension | Without ML Integration | With Trip Replay | Delta |
|---|---|---|---|
| Test realism | Static 0A/3700mV/25C | Real driving profiles with transients | **Transformative** |
| SOC validation | SOC=50% forever | SOC varies 20-100% over trip | **Enables algorithm testing** |
| Fault discovery | None (all values in range) | Real data may trigger edge cases | **Medium** |
| Demo quality | "BMS reaches NORMAL" (boring) | "BMS processes real BMW i3 trip" (compelling) | **High** |
| Code changes | None | ~80 lines Python, no C changes | **Minimal investment** |

**Expected value: HIGH. Best effort-to-value ratio of all three layers.**

### Layer 2: ML Sidecar

| Value Dimension | Without ML Sidecar | With ML Sidecar | Delta | Confidence |
|---|---|---|---|---|
| SOC accuracy comparison | No comparison possible | foxBMS coulomb vs ML LSTM side-by-side | **High if accurate** | MEDIUM — per-cell normalization + FOBSS validation path |
| Thermal monitoring | foxBMS: threshold at 80C | ML: risk score 0-1, early warning | **High** | HIGH — cell-level model, no topology gap, NREL-trained |
| Degradation tracking | Nothing | SOH trend over synthetic cycles | **Medium** | MEDIUM — cell-level LiionPro data, replay via plant model |
| Portfolio / thesis value | "I ported foxBMS" | "I built ML-augmented BMS" | **High** | HIGH |
| Architectural pattern | None | Sidecar + CAN + ONNX = reusable | **High** | HIGH |

**Expected value: MEDIUM-HIGH. SOC LSTM needs validation, but Thermal CNN and Imbalance CNN are expected to transfer directly (cell-level data, no topology gap).**

Honest decomposition of the "ML-augmented BMS" claim:

| Claim | Supportable? | Evidence Needed |
|---|---|---|
| "ML SOC outperforms coulomb counting" | LIKELY — normalize to per-cell V, validate on FOBSS foxBMS data | Run both on same trip, compare against ground truth SOC from CSV. FOBSS is the validation set. |
| "Thermal anomaly detected 20s early" | LIKELY — Thermal CNN trained on cell-level dT/dt (NREL), no topology gap | Implement NREL scenario on foxBMS 0x280, measure detection time vs threshold |
| "Cell imbalance detected before threshold" | LIKELY — Imbalance CNN trained on multi-chem cell spread, directly maps to foxBMS 0x270 | Inject voltage spread across 18 cells, verify CNN detects before foxBMS balancing threshold |
| "SOH tracking enables predictive maintenance" | POSSIBLE — LiionPro cell-level data is real, but needs cycling history replay | Replay 500-cycle synthetic degradation through plant model, validate SOH trend |
| "RUL predicted with 16% MAPE" | NO — that number is from MIT dataset, not foxBMS runtime | Can only demonstrate with synthetic cycle replay. Cite MIT number for model, measure separately for foxBMS |
| "5 ML models deployed on CAN bus" | YES — architecturally true, all ONNX models load | Demonstrable regardless of accuracy |

### Layer 3: Fault Injection

| Value Dimension | Without ML Faults | With ML Faults | Delta | Confidence |
|---|---|---|---|---|
| Fault realism | Step function (0→4.5V instantly) | Gradual ramp following NREL profiles | **High** | MEDIUM |
| Detection comparison | foxBMS threshold only | foxBMS threshold vs ML prediction time | **High if DIAG works** | LOW — DIAG suppressed |
| Test coverage | 6 manual scenarios | Data-driven scenario generation | **Medium** | MEDIUM |

**Expected value: MEDIUM, but BLOCKED by DIAG_Handler suppression.**

---

## 4. Cost-Benefit Summary

| Layer | Effort | Value | Risk | ROI | Recommendation |
|---|---|---|---|---|---|
| **L1: Trip Replay** | 2-3 days | HIGH | LOW | **BEST** | DO FIRST — BMW i3 pack + NASA cell data for per-cell variation |
| **L2: ML Sidecar** | 5-7 days | HIGH | LOW-MEDIUM | **HIGH** | DO SECOND — Thermal CNN + Imbalance CNN transfer directly (cell-level). SOC LSTM needs per-cell normalization + FOBSS validation |
| **L3: Fault Injection** | 1-2 weeks | HIGH | MEDIUM | **GOOD** | DO THIRD — NREL thermal + MIT degradation are cell-level, map directly to 0x270/0x280. Still blocked by DIAG suppression for foxBMS-side detection. |
| **FOBSS validation** | 2-3 days | HIGH (de-risks everything) | LOW | **BEST** | DO EARLY — download FOBSS from KIT Radar, validate all models on real foxBMS data |
| **Retrain SOC on per-cell V** | 3-5 days | HIGH (fixes pack-level gap) | LOW | HIGH | DO if SOC RMSE > 5% on FOBSS |
| **Docker compose** | 1 day | MEDIUM | LOW | GOOD | DO after L2 works |

---

## 5. What a System Architect Actually Wants

As a system architect evaluating this for a SIL test platform, I care about:

### Must-have (blocks adoption)

| Requirement | Status | Gap |
|---|---|---|
| Reproducible build + run | PARTIAL — `setup.sh` missing, manual patch steps | Create automation script |
| Deterministic test results | NO — wall-clock timing, race between plant and vECU | Need `--sim-time` mode or startup barrier |
| Automated pass/fail | NO — manual candump visual inspection | Need `test_smoke.py` with assertions |
| Known accuracy bounds | NO — ML accuracy on foxBMS data is unmeasured | Must validate before any claim |

### Should-have (enables serious use)

| Requirement | Status | Gap |
|---|---|---|
| Docker compose for multi-ECU SIL | Missing | 1 day effort after L2 works |
| CAN message period validation | Missing | foxBMS sends asynchronously, no DBC period enforcement |
| Graceful degradation if ML sidecar crashes | Not designed | foxBMS should run fine without sidecar (it does today) |
| Logging / recording for offline analysis | Missing | Need CSV or BLF logger |

### Nice-to-have (differentiators)

| Requirement | Status | Gap |
|---|---|---|
| XCP for real-time variable observation | Not started | Major effort |
| Grafana dashboard for ML vs foxBMS SOC | Not started | 2-3 days after L2 |
| CI/CD pipeline with regression tests | Not started | Needs `test_smoke.py` first |

---

## 6. Recommended Path Forward

```
Week 1:  Download FOBSS dataset from KIT Radar (foxBMS-native data)
         L1.1 Trip replay plant model (BMW i3 pack + NASA cell variation)
         setup.sh + test_smoke.py (automation)

Week 2:  Validate ALL 5 models on FOBSS data (the zero-gap dataset)
         Measure: SOC RMSE, Thermal F1, Imbalance accuracy on real foxBMS signals
         Decision gate (see below)

Week 3:  L2.1 ML sidecar skeleton (CAN read + ONNX load)
         L2.2 Deploy validated models: Thermal CNN + Imbalance CNN first (lowest risk)
         L2.2b SOC LSTM (with per-cell normalization if needed)

Week 4:  L2.3 SOC comparison dashboard (foxBMS vs ML vs ground truth)
         L2.4 SOH LSTM with synthetic cycle replay through plant model
         Docker compose

Week 5:  L3.1 Thermal fault injection (NREL profiles → foxBMS 0x280)
         L3.2 Cell imbalance injection (EV pack data → foxBMS 0x270)
         Document measured accuracy on FOBSS + foxBMS SIL
```

### Key decision gate: End of Week 2 (FOBSS validation)

After validating all models on FOBSS foxBMS data:

**SOC LSTM on FOBSS:**
- **If < 3% RMSE**: Proceed as planned. Strong thesis claim. Per-cell normalization works.
- **If 3-5% RMSE**: Still useful. "ML provides independent SOC estimate, X% RMSE on foxBMS monitoring data."
- **If > 5% RMSE**: Retrain on per-cell voltage (NASA + FOBSS combined). 3-5 day detour.
- **If > 10% RMSE**: Pack-level SOC model doesn't transfer. Not a blocker — proceed with cell-level models.

**Cell-level models on FOBSS (Thermal, Imbalance):**
- **Expected outcome**: Near-training accuracy (cell physics are pack-independent)
- **If accuracy degrades significantly**: Indicates data format mismatch, not domain gap. Debug normalization/encoding.

**Key insight**: Even if SOC LSTM fails to transfer, **3 out of 5 models operate at cell level and are expected to work**. The integration is not a single-model bet.

---

## 7. What NOT to Claim

| Tempting Claim | Why It's Wrong | What to Say Instead |
|---|---|---|
| "1.83% SOC accuracy on our BMS" | Measured on BMW i3 test split, not foxBMS | "1.83% on BMW i3; X% measured on FOBSS foxBMS data; Y% on foxBMS SIL" — cite all three |
| "ML detects faults 20s before foxBMS" | DIAG is suppressed, foxBMS can't detect faults at all right now | "ML thermal score rises while foxBMS threshold has not yet tripped" — accurate framing |
| "Cell-level models transfer directly" | Likely true but unvalidated | Validate on FOBSS first, then claim. "Validated on foxBMS monitoring data from KIT Radar" |
| "5 production ML models deployed" | SOH and RUL need cycling history | "SOC, Thermal, and Imbalance models deployed on live CAN; SOH and RUL demonstrated with synthetic cycle replay" |
| "Replaces dSPACE ($150k)" | Not real-time, not deterministic, not validated | "Open-source SIL alternative for early-stage BMS algorithm development and ML co-simulation" |
| "ASIL-D ML safety monitoring" | No FMEA, no safety case, no redundancy | "Demonstration of ML anomaly detection alongside certified BMS firmware — not safety-qualified" |

---

## 8. Bottom Line

| Question | Answer |
|---|---|
| Is it technically feasible? | **Yes** — all interfaces exist, no architectural blockers |
| Is it worth doing? | **All three layers: Yes.** Cell-level data eliminates most domain gap concerns. Layer 3 still needs selective DIAG. |
| What's the expected accuracy? | **Cell-level models (Thermal, Imbalance): likely transfer directly.** SOC LSTM: validate on FOBSS before claiming. SOH/RUL: need cycle replay. |
| What's the real differentiator? | **Two things**: (1) the architecture (firmware + ML + CAN + ONNX for $0), and (2) the dual-level data strategy (pack driving profiles + cell electrochemistry) feeding both foxBMS subsystems |
| Biggest risk? | **Overclaiming SOC accuracy** without FOBSS validation. Cell-level models are lower risk. |
| What data to prioritize? | **FOBSS first** (foxBMS-native, zero gap). Then NREL thermal (cell-level, immediate fault injection value). BMW i3 for pack-level replay. |
| What should a student focus on? | **Week 1: Download FOBSS + trip replay. Week 2: Validate models on FOBSS. Week 3: ML sidecar with validated models. Week 4+: Fault injection with NREL/MIT cell data.** |
