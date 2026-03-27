# ML Model Phase 2 Accuracy Report

**Date measured**: [fill after Day 55]
**Reference commit**: [git SHA at time of measurement]
**Measured by**: [name]
**Purpose**: Phase 2 qualification evidence — closes SW-REQ-ML-001..010 (SWE.1 Section 11).
All Phase 2+ improvement comparisons use this document as the baseline.
**DO NOT UPDATE** after Phase 3 starts. Create `baseline-metrics-phase3.md` instead.

---

## SOC LSTM v2 (BiLSTM 128→64, NMC 811 OCV, Phase 2 norm stats)

**Model file**: `models/bms/soc_lstm_v2.onnx`
**Norm stats**: `data/norm_stats/soc_lstm_mean.npy` + `soc_lstm_std.npy` (computed from BMW i3 training split)
**Key changes from v1**: NMC 811 21-point OCV table in plant_model.py; norm stats from actual training data

| Dataset | N | RMSE | MAE | Bias | Gate | Status | Δ vs Phase 1 |
|---|---|---|---|---|---|---|---|
| BMW i3 test split | 21,600 | ___.___% | ___.___% | ±___.___% | ≤ 2.0% | PASS/FAIL | ___ |
| FOBSS (real foxBMS 2) | ___ | ___.___% | ___.___% | ±___.___% | ≤ 3.0% | PASS/FAIL | ___ |
| foxBMS SIL 30-min bias | 1,800 | — | — | ±___.___% | ≤ ±3.0% | PASS/FAIL | +20.24%→___ |
| foxBMS SIL 30-min RMSE | 1,800 | ___.___% | ___.___% | — | ≤ 5.0% | PASS/FAIL | ~20%→___ |

**Additional FOBSS accuracy KPIs (SW-REQ-ML-001 Rev 2.1 — all N from FOBSS row above):**

| KPI | Measured | Gate | Status |
|---|---|---|---|
| P95 absolute error | ___.___% | ≤ 5.0% | PASS/FAIL |
| Max single-sample absolute error | ___.___% | ≤ 8.0% | PASS/FAIL |
| Plateau RMSE (20–80% SOC) | ___.___% | ≤ 4.5% | PASS/FAIL |
| Boundary RMSE (0–20% and 80–100% SOC) | ___.___% | ≤ 4.0% | PASS/FAIL |
| Inference latency — mean (VPS, ONNX Runtime ≥ 1.15) | ___ ms | ≤ 100 ms | PASS/FAIL |

---

**Improvement attribution** (Stage B → Stage C → Stage D):

| Fix | Estimated RMSE improvement (FOBSS) |
|---|---|
| OCV fix: linear → NMC 811 S-curve | −___.___% |
| Norm stats: estimated → training-computed | −___.___% |
| FOBSS partial fine-tune (if applied, Day 35–36) | −___.___% |
| **Total improvement** | **−___.___% → Phase 2 result: ___.___% RMSE** |

---

## IsolationForest v2 (200 trees, contamination=0.03, real SIL + anchored synthetic)

**Model files**: `models/bms/anomaly_model_v2.pkl` + `anomaly_scaler_v2.pkl`
**Training data**: `data/sil_anomaly_features.npz` (real SIL, 30 min) + anchored synthetic (30% of total)

| Condition | N | Mean Score | 95th %ile | Max | Gate | Status | Δ vs Phase 1 |
|---|---|---|---|---|---|---|---|
| Normal (real SIL 5-min) | 300 | ___.___| ___.___| ___.___| < 0.15 | PASS/FAIL | 0.36 → ___ |
| Overvoltage (4.6 V / cell 0) | 60 | ___.___| ___.___| ___.___| > 0.40 | PASS/FAIL | |
| Overtemperature (60°C) | 60 | ___.___| ___.___| ___.___| > 0.30 | PASS/FAIL | |
| Overcurrent (150 A) | 60 | ___.___| ___.___| ___.___| > 0.40 | PASS/FAIL | |
| Recovery after clear (30 s) | 30 | ___.___| — | — | < 0.20 | PASS/FAIL | |
| TPR across all fault types | — | — | — | — | ≥ 80% | PASS/FAIL | ~78% → ___% |
| FPR (30-min normal, threshold 0.70) | 1,800 | — | — | — | ≤ 5% | PASS/FAIL | ~6% → ___% |

---

## Thermal CNN v1 (dT/dt pipeline fixed, NMC 811 thermal model active)

**Model file**: `models/bms/thermal_cnn.onnx` (weights unchanged — pipeline fix only)
**Key change from Phase 1**: dT/dt now computed from successive T_avg samples at 1 Hz

| Condition | N | Mean Risk | 95th %ile Risk | FPR @ 0.3 | Gate | Status |
|---|---|---|---|---|---|---|
| Normal discharge (30 min) | 1,800 | ___.___| ___.___| ___% | ≤ 2% FPR | PASS/FAIL |
| OT fault onset (60°C injection, t=0) | — | — | — | — | ≤ 30 s to score > 0.3 | PASS/FAIL |
| OT fault at +30s | 30 | ___.___| ___.___| — | > 0.30 mean | PASS/FAIL |

**dT/dt operational check**:

| Metric | Value | Gate | Status |
|---|---|---|---|
| % samples with non-zero dT/dt during discharge | ___% | ≥ 90% | PASS/FAIL |
| OT detection latency (s) | ___ s | ≤ 30 s | PASS/FAIL |

---

## SOH Transformer v1 (synthetic cycle replay, 500 cycles)

**Model file**: `models/bms/soh_transformer.onnx` (weights from `taktflow-bms-ml`)
**Input source**: `data/soh_cycle_replay/cycle_features.npz` — 500 synthetic NMC 811 cycles
**Key change from Phase 1**: cycle history generated; model was NOT OPERATIONAL in Phase 1

| Dataset | N windows | RMSE | MAE | Trend inversions | Gate | Status |
|---|---|---|---|---|---|---|
| Synthetic 500 cycles | 490 | ___.___% | ___.___% | ___ | ≤ 12.0% + < 10 inv | PASS/FAIL |

**SOH trend shape verification**:

| SOC range | Observed SOH at cycle 0 | Observed SOH at cycle 499 | Expected direction | Status |
|---|---|---|---|---|
| 100% → ~90% (fade) | ___.___% | ___.___% | Monotone decreasing | PASS/FAIL |

**Additional SOH Transformer KPIs (SW-REQ-ML-006 Rev 2.1 — synthetic 500-cycle replay):**

| KPI | Measured | Gate | Status |
|---|---|---|---|
| P95 absolute error | ___.___% | ≤ 18.0% | PASS/FAIL |
| Cycle-to-cycle noise std dev (std of SOH[n] − SOH[n−1]) | ___.___% | ≤ 1.5% | PASS/FAIL |
| Predictions in physical range [65%, 100%] | ___ / 490 | 490 / 490 | PASS/FAIL |
| Inference latency — mean (VPS, ONNX Runtime ≥ 1.15) | ___ ms | ≤ 200 ms | PASS/FAIL |

---

## RUL Transformer v1 (initial deployment — CAN 0x704)

**Model file**: `models/bms/rul_transformer.onnx`
**Status**: Initial deployment — full accuracy validation deferred to Phase 5 (Day 121–150)

| Condition | Output range | CAN 0x704 active | Status |
|---|---|---|---|
| < 20 cycles history | 0 (guard) | No (correct) | PASS/FAIL |
| ≥ 20 cycles history | ___ – ___ cycles | Yes | PASS/FAIL |

**MIT dataset MAPE** (informational — full validation Phase 5):
- Published MAPE: 16%
- Phase 2 observed on available data: ___.___% (if MIT dataset accessible) or DEFERRED

---

## Cell Imbalance (direct computation — no ONNX model, for reference)

| Condition | Mean Spread | Std | Max Spread |
|---|---|---|---|
| foxBMS SIL normal (Phase 2 capture) | ___ mV | ___ mV | ___ mV |
| Imbalance injected (+50 mV cell 0) | ___ mV | ___ mV | ___ mV |

---

## ASPICE Qualification Evidence Summary (SWE.6)

All SW-REQ-ML requirements as defined in SWE.1 Section 11, Rev 2.1:

| SW-REQ-ML-ID | Requirement Summary | Phase 2 Measured Result | Gate | Verdict |
|---|---|---|---|---|
| SW-REQ-ML-001 | SOC RMSE ≤ 3.0%, MAE ≤ 2.0%, P95 ≤ 5.0%, max ≤ 8.0%, plateau RMSE ≤ 4.5%, boundary RMSE ≤ 4.0%, bias ≤ ±3.0%, latency ≤ 100 ms | See Additional FOBSS KPIs table above | 7 sub-gates — all must PASS | PASS/FAIL |
| SW-REQ-ML-002 | Norm stats from training split (N ≥ 60k) | N=___ samples, registry.json ✓ | Provenance record | PASS/FAIL |
| SW-REQ-ML-003 | NMC 811 OCV ≥ 21 pts, round-trip < 1% | 21 pts, RT=___.___% | < 1.0% RT | PASS/FAIL |
| SW-REQ-ML-004 | IsolationForest retrain, normal mean < 0.15 | Mean=___.___| < 0.15 | PASS/FAIL |
| SW-REQ-ML-005 | Thermal dT/dt non-zero in ≥ 90% discharge | ___% | ≥ 90% | PASS/FAIL |
| SW-REQ-ML-006 | SOH Transformer, ≥ 100 cycles, RMSE ≤ 12%, MAE ≤ 8%, inversions < 10, P95 ≤ 18%, noise ≤ 1.5%, range [65-100%], latency ≤ 200 ms | 500 cycles — see Additional SOH KPIs table above | 7 sub-gates — all must PASS | PASS/FAIL |
| SW-REQ-ML-007 | CI 0x705 strict 30-s assertion passes | CI green ✓ | CI pass | PASS/FAIL |
| SW-REQ-ML-008 | Registry v2 entries with provenance | registry.json updated ✓ | All fields non-null | PASS/FAIL |
| SW-REQ-ML-009 | Phase 2 accuracy report published | This document | Filed, no placeholders | PASS/FAIL |
| SW-REQ-ML-010 | Thermal FPR ≤ 2%, OT latency ≤ 30 s | FPR=___%, latency=___s | ≤ 2% FPR, ≤ 30 s | PASS/FAIL |

**Overall Phase 2 verdict**: ___/10 requirements PASS.
Phase 2 exit criteria met: YES / NO

---

## Notes for Phase 3 Planning

Models that required fine-tune (FOBSS fine-tune applied: YES/NO) are candidates for
drift monitoring in Phase 3, because a fine-tuned model's reference distribution may
shift as new FOBSS-like data arrives. Phase 3 PSI monitoring should target these models.

Models with Phase 2 RMSE within 20% of target gate are also drift candidates — they are
close to the gate and may cross it as battery ageing changes the operating distribution.
