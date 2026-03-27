# AI/ML Audit — foxBMS POSIX vECU

**Generated**: 2026-03-27
**Scope**: Full repository scan of ML models, datasets, pipelines, inference paths, accuracy metrics, and known gaps.
**Auditor**: Claude Sonnet 4.6 (automated catalog pass — not a safety assessment)

---

## 1. Repository ML Inventory

### 1.1 Source Files

| File | Type | Lines | Purpose |
|---|---|---|---|
| `src/ml_sidecar.py` | Inference sidecar | ~675 | SocketCAN reader + ONNX runner + anomaly detection; publishes on CAN 0x700–0x705 |
| `src/train_anomaly_bms.py` | Training script | 215 | Trains IsolationForest on synthetic BMS telemetry (4 regimes × 5 features) |
| `src/requirements-ml.txt` | Dependency spec | 12 | `onnxruntime>=1.15`, `numpy>=1.20`, `scikit-learn>=1.4`, `joblib>=1.3` |
| `tools/foxbms_constants.py` | Constants library | 283 | OCV table, CAN IDs, signal decoders — consumed by all ML tools |
| `tools/soc-drift-calc.py` | Analysis tool | 200 | Simulates SOC error under CAN message drops; benchmarks coulomb-counting vs ML RMSE |
| `tools/trend-analyze.py` | CI analysis tool | 280 | JUnit XML trend analyzer (flakiness, regressions); includes ML sidecar test stubs |
| `scripts/deploy-ml-sidecar.sh` | Deploy script | 85 | SCP + install + train + start sidecar on Netcup VPS (152.53.245.209) |

### 1.2 Documentation

| File | Content |
|---|---|
| `docs/business/feasibility-ml-integration.md` | 3-layer feasibility analysis: trip replay / ML sidecar / fault injection |
| `docs/business/ml-improvement-plan.md` | 52-item improvement backlog: P0 critical fixes, P1 accuracy, P2 usability, P3 differentiators |
| `docs/business/ml-pipeline-value.md` | End-to-end pipeline diagram; honest accuracy assessment; revenue path (Tier 0–3) |
| `docs/business/ai-testing-implementation-guide.md` | Customer implementation guide (Tier 0–3) with code snippets |
| `docs/business/proposal-ml-integration.md` | ML integration proposal |
| `docs/business/pipeline-reusable.md` | Reusability analysis |
| `docs/business/work-packages-30-days.md` + variants | 30-day work breakdown |
| `docs/project/ml-changelog.md` | Session log (2026-03-27): all files created/modified, deployment steps, known issues |

### 1.3 Deployed Artifacts (VPS `/opt/foxbms-sil/`)

| File | Size | Status |
|---|---|---|
| `models/bms/soc_lstm.onnx` | 2.2 MB | Deployed, running |
| `models/bms/thermal_cnn.onnx` | 163 KB | Deployed, running |
| `models/bms/soh_transformer.onnx` | 328 KB | Deployed, running |
| `models/bms/soc_norm_mean.npy` | 148 B | Deployed (estimated stats — see Gap 1) |
| `models/bms/soc_norm_std.npy` | 148 B | Deployed (estimated stats — see Gap 1) |
| `src/anomaly_model.pkl` | N/A | Trained on VPS from synthetic data |
| `src/anomaly_scaler.pkl` | N/A | StandardScaler for IsolationForest |

---

## 2. Models

### 2.1 SOC LSTM

| Attribute | Value |
|---|---|
| **File** | `soc_lstm.onnx` |
| **Architecture** | BiLSTM 128→64 (from `docs/business/ml-pipeline-value.md`) |
| **ONNX input shape** | `(batch, 60, 5)` — 60 timesteps × 5 features |
| **Features (5)** | `[V_per_cell_V, I_A, T_avg_degC, T_max_degC, velocity_kmh]` |
| **Output** | SOC % (0–100), clamped |
| **Inference rate** | 1 Hz (60-step window fills in 60 s) |
| **Training data** | BMW i3 72 driving trips (pack-level, 96S); NASA PCoE 7565 cycles (cell-level) |
| **Published accuracy** | 1.83% RMSE (BMW i3 test split) |
| **Normalization** | Per-cell voltage (`pack_V / 18`); mean=[3.698 V, 0.5 A, 25°C, 30°C, 35 km/h], std=[0.1875 V, 28 A, 8°C, 10°C, 30 km/h] |
| **CAN output** | 0x700 bytes 0–1 (ML SOC, ×0.01%), bytes 2–3 (BMS SOC), bytes 4–5 (diff, signed) |
| **Observed behavior** | ML_SOC=70.2% vs BMS_SOC=50.0% (steady-state SIL) — 20% domain gap |

### 2.2 SOH Transformer

| Attribute | Value |
|---|---|
| **File** | `soh_transformer.onnx` |
| **ONNX input shape** | `(batch, 10, 12)` — 10 timesteps × 12 features |
| **Features (12)** | `[V, I, T, cap, R, cycle_count, V_min, V_max, V_spread, T_min, T_max, T_spread]` |
| **Output** | SOH % (0–100), clamped |
| **Training data** | LiionPro-DT (2M rows, 5-year cell lifecycle) |
| **Published accuracy** | 9.79% RMSE |
| **Cycle count** | Placeholder `0.0` in current SIL deployment (no cycling history) |
| **CAN output** | 0x701 bytes 0–1 (SOH ×0.01%) |
| **Status** | Not producing meaningful predictions on single-run SIL (needs cycling history) |

### 2.3 Thermal CNN

| Attribute | Value |
|---|---|
| **File** | `thermal_cnn.onnx` |
| **ONNX input shape** | `(batch, 30, 4)` — 30 timesteps × 4 features |
| **Features (4)** | `[T_avg_degC, T_max_degC, dT_dt_est, I_A]` |
| **Output** | Thermal risk score 0.0–1.0, clamped |
| **Training data** | NREL 364 thermal abuse tests (cell-level) |
| **Published accuracy** | F1 = 1.000 (on NREL test set) |
| **Domain gap** | NONE at cell level; but `dT/dt` input is `0.0` (placeholder, not computed) |
| **CAN output** | 0x702 bytes 0–1 (risk ×1000, integer) |
| **Observed output** | 0.000 (constant — plant model was isothermal; thermal model added 2026-03-27) |

### 2.4 IsolationForest (Anomaly Detection)

| Attribute | Value |
|---|---|
| **File** | `anomaly_model.pkl` + `anomaly_scaler.pkl` |
| **Algorithm** | scikit-learn `IsolationForest` (n_estimators=100, contamination=0.05, seed=42) |
| **Preprocessor** | `StandardScaler` |
| **Features (5)** | `[V_mean_mV, V_std_mV, I_mA, T_ddegC, V_spread_mV]` |
| **Training data** | 5000 synthetic samples, 4 operating regimes (25% idle, 10% precharge, 10% transition, 55% normal) |
| **Published accuracy** | 78% detection rate (cited from IsolationForest baseline; LSTM-AE achieves 94% per IEEE TVT 2024) |
| **Alert threshold** | Score > 0.70 → warning log |
| **CAN output** | 0x705 bytes 0–1 (anomaly ×1000, integer) |
| **Observed output** | 0.36 at normal operation (elevated — synthetic baseline doesn't match foxBMS steady-state; see Gap 3) |
| **Score mapping** | `0.15 - (decision_function / 0.30)`, clipped 0–1 |

### 2.5 Cell Imbalance (Direct Computation — No ML Model)

| Attribute | Value |
|---|---|
| **Algorithm** | `max(cell_voltages_mv) - min(cell_voltages_mv)` across 18 cells |
| **Input** | 0x270 cell voltage frames, decoded with foxBMS big-endian table |
| **CAN output** | 0x703 bytes 0–1 (spread in mV, integer) |
| **Observed output** | 14 mV (corrected from 2403 mV after big-endian decode fix) |
| **Note** | Not an ML model — deterministic heuristic |

### 2.6 RUL (Remaining Useful Life) — Stub

| Attribute | Value |
|---|---|
| **File** | Not loaded (no `rul_transformer.onnx` in deployment) |
| **Mentioned accuracy** | 16% MAPE (from MIT cell degradation dataset) |
| **Training data** | MIT degradation dataset (138 cells) |
| **CAN output** | 0x704 (RUL cycles) — not published in current deployment |
| **Status** | Deferred; needs cycling history to produce meaningful prediction |

---

## 3. Datasets

| Dataset | Level | Size | Domain | Maps To | Gap |
|---|---|---|---|---|---|
| **BMW i3 driving** (72 trips) | Pack | 37 MB | 96S NMC, real driving | 0x233 pack V/I, 0x235 SOC | HIGH — 96S vs 18S, normalizable to per-cell |
| **NASA PCoE** (7565 cycles) | Cell | ~200 MB | Cell V/I/T across full cycles | 0x270 cell voltages (V-SOC) | NONE — cell physics pack-independent |
| **LiionPro-DT** (2M rows, 5yr) | Cell lifecycle | 1.1 GB | Cell capacity fade | 0x270 cell V over time | NONE |
| **MIT degradation** (138 cells) | Cell lifecycle | ~500 MB | End-of-life cell trends | RUL estimation | NONE |
| **NREL thermal failure** (364 tests) | Cell | ~100 MB | Thermal abuse, runaway | 0x280 cell temps | NONE — thermal physics cell-level |
| **EV pack multi-chemistry** | Cell groups | ~200 MB | Cell voltage spread | 0x270 imbalance patterns | LOW |
| **BMS fault diagnosis** (Mendeley) | BMS | ~50 MB | Fault scenarios | 0x270/0x280 fault injection | LOW |
| **FOBSS** (KIT Radar, foxBMS hw) | Pack + Cell | 128 MB | Actual foxBMS 2 hardware, 44-cell pack | All models | **NEAR ZERO** — same firmware |

**Note**: All datasets are referenced from `taktflow-bms-ml` (external repo, not present in this repo). No raw data files exist in `foxbms-posix`.

---

## 4. Pipelines

### 4.1 Live SIL Inference Pipeline

```
plant_model.py (18S NMC sim)
    │
    ├─ CAN 0x270  (cell voltages, muxed, big-endian)
    ├─ CAN 0x280  (cell temperatures)
    ├─ CAN 0x521  (IVT current)
    ├─ CAN 0x233  (pack voltage + current)
    ├─ CAN 0x7F2  (SIL SOC probe, float32 LE)
    └─ CAN 0x7F0  (contactor state)
              │
              ▼ SocketCAN vcan1
    ml_sidecar.py
    ├─ BMSSensorBuffers.update_from_can()    [per-frame, non-blocking]
    ├─ BMSSensorBuffers.append_to_windows()  [every 1s]
    │       ├─ soc_window   deque(60)   → SOC LSTM
    │       ├─ soh_window   deque(10)   → SOH Transformer
    │       ├─ thermal_window deque(30) → Thermal CNN
    │       └─ anomaly_buffer deque(10) → IsolationForest
    ├─ ModelManager.predict_soc()            → CAN 0x700
    ├─ ModelManager.predict_soh()            → CAN 0x701
    ├─ ModelManager.predict_thermal()        → CAN 0x702
    ├─ BMSSensorBuffers.compute_imbalance()  → CAN 0x703
    └─ ModelManager.predict_anomaly()        → CAN 0x705
              │
              ▼ SocketCAN vcan1
    web/server.py (WebSocket)
    └─ web/index.html (ML Intelligence panel, 6 gauges)
```

### 4.2 Model Loading and Fallback

1. ONNX models load from `--models-dir` (e.g. `taktflow-bms-ml/models/bms/`)
2. Normalization stats `.npy` searched in `models_dir/` first, then `../data/bms-processed/`
3. If `onnxruntime` unavailable → ONNX disabled, anomaly detection continues
4. IsolationForest: loads from `anomaly_model.pkl` if present; trains on synthetic data otherwise
5. VPS deployment starts sidecar with `--no-onnx` by default (ONNX enabled separately after model upload)

### 4.3 Offline Audit Pipeline (Documented, Not Yet Implemented)

```
customer.dbc + bench_test.blf
    │
    ▼
pack_config.json  (15 min signal mapping, one-time)
    │
    ▼
pipeline/run_audit.py  [PLANNED — not yet in repo]
    ├─ Decode BLF → CSV
    ├─ Extract V, I, T, SOC per pack_config
    ├─ Normalize to per-cell
    ├─ Run 5 ONNX models in batch
    └─ Generate PDF reports
           ├─ soc_audit.pdf
           ├─ thermal_risk.pdf
           └─ cell_health.pdf
```

### 4.4 Training Pipeline

```
train_anomaly_bms.py
    │
    ├─ generate_normal_bms_data(n=5000, seed=42)
    │       ├─ Idle    (25%): V∈[3680,3720]mV, I∈[-50,50]mA, T∈[200,300]ddegC
    │       ├─ Precharge(10%): V∈[3600,3750]mV, I∈[50,500]mA
    │       ├─ Transition(10%): V∈[3500,3800]mV, I∈[100,2000]mA
    │       └─ Normal  (55%): V∈[3400,4100]mV, I∈[500,3000]mA
    ├─ StandardScaler.fit_transform()
    ├─ IsolationForest(n_estimators=100, contamination=0.05).fit()
    └─ joblib.dump() → anomaly_model.pkl + anomaly_scaler.pkl
```

### 4.5 CI Pipeline (`.github/workflows/ci.yml`)

```
push/PR → ubuntu-24.04
    ├─ Build foxBMS POSIX vECU (gcc, make)
    ├─ Run test_smoke.py (BMS reaches NORMAL state)
    ├─ Run test_fault_injection.py --priority P1 --max 10
    └─ ML sidecar smoke test:
           ├─ pip install numpy scikit-learn joblib
           ├─ python3 train_anomaly_bms.py (synthetic training)
           ├─ Start plant_model.py + ml_sidecar.py --no-onnx
           └─ candump CAN 0x705 for 8s → PASS if frame received
              (non-blocking: also PASS if frame not captured in time)
```

---

## 5. Inference Paths

### 5.1 SOC LSTM Inference Path

```
CAN 0x233   → pack_voltage_mv, pack_current_ma
CAN 0x7F2   → bms_soc_pct (float32 LE from SIL probe)
CAN 0x280   → cell_temps_ddegc[]

append_to_windows():
    v_per_cell = pack_voltage_mv / 1000.0 / 18    # V
    t_avg = mean(temps) / 10.0                    # degC
    t_max = max(temps) / 10.0                     # degC
    soc_window.append([v_per_cell, I_A, t_avg, t_max, 0.0])  # velocity=0

predict_soc():
    x = np.array(soc_window[-60:]).reshape(1, 60, 5)
    x = (x - soc_norm_mean) / (soc_norm_std + 1e-8)          # normalize
    result = soc_model.run(None, {"input": x})
    return clip(float(result[0][0]), 0, 100)
```

### 5.2 Anomaly Detection Inference Path

```
CAN frames → anomaly_buffer.append([V_mean, V_std, I_mA, T_ddegC, V_spread])
                                  (rolling 10-sample window)

compute_anomaly_features():
    arr = np.array(anomaly_buffer)          # (10, 5)
    return [[mean(V_mean), std(V_mean), mean(I), arr[-1,T], max(V_spread)]]

predict_anomaly():
    features_scaled = scaler.transform(features)
    raw = model.decision_function(features_scaled)[0]
    score = 0.15 - (raw / 0.30)            # map to 0-1
    return clip(score, 0, 1)
```

### 5.3 CAN Output Encoding

| CAN ID | Format | Scale |
|---|---|---|
| 0x700 | `>HHh2x` (ML_SOC, BMS_SOC, diff) | ×100 (0.01% units) |
| 0x701 | `>H6x` (SOH) | ×100 |
| 0x702 | `>H6x` (thermal risk) | ×1000 (0.001 units) |
| 0x703 | `>H6x` (imbalance) | mV integer |
| 0x705 | `>H6x` (anomaly) | ×1000 |

---

## 6. Accuracy Metrics

| Model | Metric | Value | Dataset | Validity for foxBMS |
|---|---|---|---|---|
| SOC LSTM | RMSE | **1.83%** | BMW i3 test split | UNVALIDATED — measured on 96S pack, not foxBMS 18S |
| SOC LSTM | RMSE on foxBMS SIL | **~20% gap** (observed) | foxBMS SIL steady-state | Domain mismatch; expected to improve with FOBSS validation |
| SOH Transformer | RMSE | **9.79%** | LiionPro-DT | UNVALIDATED on foxBMS; needs cycling history |
| Thermal CNN | F1 | **1.000** | NREL abuse test set | Likely valid at cell level; `dT/dt` input currently 0.0 |
| IsolationForest | Detection rate | **~78%** (literature baseline) | Synthetic BMS data | UNVALIDATED on real foxBMS CAN; FPR unknown |
| IsolationForest | Training FPR | **~6%** | Synthetic normal validation (100 samples) | Expected ~5%; slight overfit |
| RUL Transformer | MAPE | **16%** | MIT degradation dataset | NOT DEPLOYED |
| Normalization stats | N/A | Estimated | BMW i3 specs (not training data) | UNVERIFIED — should be recomputed from actual training split |

---

## 7. Known Gaps

### GAP-ML-001: SOC accuracy unvalidated on foxBMS data [CRITICAL]

- **Problem**: The 1.83% RMSE figure is from BMW i3 (96S). foxBMS is 18S. The sidecar produced ML_SOC=70.2% vs BMS_SOC=50.0% on steady-state SIL (20% gap).
- **Impact**: Cannot claim ML SOC is more accurate than coulomb counting without FOBSS validation.
- **Fix**: Download FOBSS dataset (KIT Radar, 128 MB, foxBMS hardware, CC-BY). Validate all 5 models. Gate claim: if RMSE < 3%, proceed; if > 5%, retrain on per-cell voltage.
- **Effort**: 2–3 days.

### GAP-ML-002: Normalization stats are estimated, not computed from training data [HIGH]

- **Problem**: `soc_norm_mean.npy` and `soc_norm_std.npy` were generated from BMW i3 specification values (e.g. `mean=[355/96=3.698, 0.5, 25, 30, 35]`), not from the actual training data distribution.
- **Impact**: SOC LSTM predictions may be systematically biased even if the domain gap is bridged.
- **Fix**: Run `prepare_soc_dataset.py` from `taktflow-bms-ml` on BMW i3 raw data to compute exact per-feature mean/std from training split.
- **Effort**: 2 hours if BMW i3 data is available locally.

### GAP-ML-003: Anomaly baseline trained on synthetic data [HIGH]

- **Problem**: IsolationForest was trained on synthetic BMS regimes, not real foxBMS CAN output. The score at normal operation is 0.36 (should be <0.1). High false-positive rate is expected.
- **Impact**: Customers will see anomaly scores that don't reflect their pack behavior.
- **Fix**: Record 30 minutes of normal foxBMS SIL CAN traffic, retrain anomaly model on real baseline. Also add V-I Ohm's law correlation to synthetic generation.
- **Effort**: 8 hours.

### GAP-ML-004: Thermal CNN gets zero dT/dt signal [HIGH]

- **Problem**: The `dT/dt` feature in the thermal window is always `0.0` (placeholder). Plant model now has I²R heating but the sidecar doesn't compute dT/dt from successive temperature samples.
- **Impact**: Thermal CNN receives incomplete input; risk scores may underestimate gradual thermal events.
- **Fix**: Track previous temperature in `thermal_window` and compute `dT = T_now - T_prev` at each step.
- **Effort**: 1 hour.

### GAP-ML-005: SOH Transformer produces no meaningful output on single-run SIL [MEDIUM]

- **Problem**: SOH estimation requires cycling history (capacity fade over cycles). The SIL demo is one continuous run. `cycle_count` feature is hardcoded to `0.0`. `cap_est` is hardcoded to `3.0 Ah`.
- **Impact**: SOH predictions are not useful on the current SIL without synthetic multi-cycle replay.
- **Fix**: Implement synthetic cycle replay (plant model replays 500 discharge-charge cycles, tracking Ah throughput). Or: use SOH Transformer output only as "current-cycle SOH estimate" with appropriate caveats.
- **Effort**: 2–5 days.

### GAP-ML-006: RUL model not deployed [MEDIUM]

- **Problem**: `docs/business/ml-pipeline-value.md` mentions RUL Transformer (16% MAPE on MIT dataset) but no `rul_transformer.onnx` file exists in the repo or deployment. CAN ID 0x704 publishes nothing.
- **Impact**: RUL is listed in the CAN protocol and web dashboard but produces no output.
- **Fix**: Export `rul_transformer.onnx` from `taktflow-bms-ml`, define input shape, implement `predict_rul()`. Requires cycle history (same dependency as GAP-ML-005).
- **Effort**: 1 day (export + integration) + cycle replay (shared with GAP-ML-005).

### GAP-ML-007: IsolationForest misses temporal anomalies [MEDIUM]

- **Problem**: IsolationForest is a point-wise anomaly detector. It scores each 1-second window independently, missing drift patterns (e.g. cell voltage declining 1 mV/cycle over 200 cycles). LSTM-Autoencoder achieves 94% detection vs 78% for IF (IEEE TVT 2024).
- **Impact**: Slow thermal degradation and cell voltage drift go undetected.
- **Fix**: Add LSTM-Autoencoder as Tier 2 detector (60-second window, run every 60 s). Keep IF for instant point anomalies.
- **Effort**: 2 weeks (train + integrate + tune threshold).

### GAP-ML-008: No model drift monitoring [MEDIUM]

- **Problem**: No Population Stability Index (PSI) or equivalent monitoring. As cells age, the "normal" distribution shifts, silently degrading anomaly detection accuracy.
- **Impact**: Model accuracy degrades over battery lifetime without any alert.
- **Fix**: Implement `ModelMonitor` class with PSI tracking (described in `ml-improvement-plan.md` §P2.2). Dashboard shows green/yellow/red per model.
- **Effort**: 3 days.

### GAP-ML-009: No explainability for anomaly scores [LOW]

- **Problem**: CAN 0x705 publishes a scalar 0–1. No breakdown of which feature drove the score.
- **Impact**: Customer cannot act on an anomaly alert without knowing whether it's voltage, current, or temperature.
- **Fix**: Implement SHAP for IsolationForest; LSTM-AE provides per-feature reconstruction error natively.
- **Effort**: 1 week.

### GAP-ML-010: Offline audit pipeline not implemented [LOW]

- **Problem**: `docs/business/ai-testing-implementation-guide.md` describes `pipeline/run_audit.py` generating SOC/thermal/cell-health PDF reports from customer BLF files. This tool does not exist in the repo.
- **Impact**: Customer-facing Tier 0 deliverable is documented but not buildable.
- **Fix**: Implement `pipeline/run_audit.py`, `auto_config.py`, and report generation (~300 lines Python).
- **Effort**: 3–5 days.

### GAP-ML-011: No FOBSS validation pass performed [CRITICAL]

- **Problem**: FOBSS dataset (actual foxBMS 2 hardware monitoring, 44-cell pack, CC-BY license) is identified as the "zero-gap validation set" in the feasibility doc but has not been downloaded or used.
- **Impact**: None of the 5 models have been validated on any foxBMS hardware data. All accuracy claims are from external datasets.
- **Fix**: Download FOBSS from KIT Radar (128 MB TAR). Run all models on FOBSS signals. Record per-model RMSE/F1 on actual foxBMS data. This single step would de-risk the entire integration.
- **Effort**: 2–3 days.

### GAP-ML-012: CI ML test is non-blocking [LOW]

- **Problem**: `ci.yml` marks the ML sidecar smoke test as PASS even if CAN 0x705 is not captured in the 8-second window ("non-blocking"). This means CI can green with ML sidecar effectively broken.
- **Impact**: Regression in ML output may go undetected in CI.
- **Fix**: Make 0x705 capture mandatory after plant model stabilizes (30-second window, strict assertion).
- **Effort**: 30 minutes.

---

## 8. Architecture Summary

```
                    ┌───────────────────────────────┐
                    │   foxBMS POSIX vECU            │
                    │   (firmware, RTOS, C)          │
                    └──────────────┬────────────────┘
                                   │ CAN TX 0x220–0x301
                                   ▼
                              vcan1 (SocketCAN)
                    ┌──────────────┴────────────────┐
                    │   plant_model.py               │
                    │   (simulated 18S NMC, 3Ah)    │
                    │   OCV: NMC 811 16-point curve  │
                    │   Thermal: I²R + Newton cool   │
                    └──────────────┬────────────────┘
                                   │ CAN RX 0x270/0x280/0x521
                                   ▼
                              vcan1 (shared bus)
                    ┌──────────────┴────────────────┐
                    │   ml_sidecar.py               │
                    │   ┌─────────────────────────┐ │
                    │   │ BMSSensorBuffers         │ │
                    │   │ (rolling deques, 1 Hz)  │ │
                    │   └────────────┬────────────┘ │
                    │                │               │
                    │   ┌────────────▼────────────┐ │
                    │   │ ModelManager             │ │
                    │   │ ├ SOC LSTM (ONNX)        │ │
                    │   │ ├ SOH Transformer (ONNX) │ │
                    │   │ ├ Thermal CNN (ONNX)     │ │
                    │   │ └ IsolationForest (pkl)  │ │
                    │   └────────────┬────────────┘ │
                    └──────────────┬──────────────────┘
                                   │ CAN TX 0x700–0x705
                                   ▼
                              vcan1
                    ┌──────────────┴────────────────┐
                    │   web/server.py (WebSocket)    │
                    │   web/index.html (dashboard)   │
                    │   ML Intelligence Panel        │
                    │   (6 gauges + CAN monitor)     │
                    └───────────────────────────────┘
```

**Deployment**: Live 24/7 at Netcup VPS (152.53.245.209), `/opt/foxbms-sil/`.
**CI**: GitHub Actions — build + smoke + fault injection + ML sidecar test.
**Docker**: `docker-compose.yml` defines `vecu`, `ml-sidecar`, and `test` services.

---

## 9. What Is and Is Not Claimed

| Claim | Supportable Now | Condition |
|---|---|---|
| "ML inference pipeline runs on CAN bus end-to-end" | YES | Live, observed |
| "5 ML models deployed, 1 Hz inference, <15ms latency" | PARTIAL — 3 ONNX + IF active; RUL not deployed | Fix GAP-ML-006 |
| "SOC LSTM 1.83% RMSE" | NO for foxBMS | BMW i3 number only; cite separately (GAP-ML-001) |
| "Thermal CNN F1=1.000" | CONDITIONAL | Cell-level metric; dT/dt input is 0 (GAP-ML-004) |
| "Anomaly detection catches overvoltage/overcurrent" | YES | IsolationForest scores these far from normal distribution |
| "ML detects faults 20s before foxBMS" | NO | DIAG_Handler suppressed; foxBMS can't detect faults to compare |
| "SOH tracking over lifetime" | NO | Single-run SIL (GAP-ML-005) |
| "Architecture is production-grade" | YES | Docker, CI, WebSocket, CAN protocol — all functional |

---

## 10. Recommended Priority Actions

| Priority | Action | Effort | Gap |
|---|---|---|---|
| **P0** | Download FOBSS dataset, validate all 5 models | 2–3 days | GAP-ML-001, GAP-ML-011 |
| **P0** | Compute normalization stats from actual training data | 2 hours | GAP-ML-002 |
| **P0** | Retrain anomaly model on real foxBMS SIL CAN baseline (30 min recording) | 8 hours | GAP-ML-003 |
| **P1** | Add dT/dt computation in `append_to_windows()` | 1 hour | GAP-ML-004 |
| **P1** | Make CI ML test assertion strict (not non-blocking) | 30 min | GAP-ML-012 |
| **P2** | Implement synthetic cycle replay for SOH/RUL | 2–5 days | GAP-ML-005, GAP-ML-006 |
| **P2** | Implement `pipeline/run_audit.py` (offline customer audit) | 3–5 days | GAP-ML-010 |
| **P3** | LSTM-Autoencoder for temporal anomaly detection | 2 weeks | GAP-ML-007 |
| **P3** | Model drift monitoring (PSI) | 3 days | GAP-ML-008 |
| **P3** | SHAP explainability for anomaly scores | 1 week | GAP-ML-009 |
