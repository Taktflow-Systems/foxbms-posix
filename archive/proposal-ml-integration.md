# Proposal: Integrating taktflow-bms-ml with foxBMS POSIX vECU

**Date**: 2026-03-21
**Status**: PROPOSAL
**Dependencies**: foxbms-posix (BMS in NORMAL), taktflow-bms-ml (5 models trained)

---

## The Opportunity

We have two working systems that don't talk to each other:

| foxbms-posix | taktflow-bms-ml |
|---|---|
| Real BMS firmware running on Linux | 5 trained ML models (ONNX) |
| Outputs 15+ CAN messages with battery state | Inputs: pack V/I/T time series |
| Uses coulomb counting for SOC (drifts) | SOC LSTM: 1.83% RMSE |
| No degradation awareness | SOH LSTM: 0.85% RMSE |
| No predictive capability | RUL Transformer: 16% MAPE |
| Threshold-only fault detection | Thermal CNN: F1=1.000 |
| Static plant model (constant values) | Trained on real BMW i3 driving data |

Connecting them creates something neither can do alone: a **BMS with ML-augmented intelligence**, testable end-to-end without hardware.

---

## Three Integration Layers

### Layer 1: ML-Driven Plant Model (replace static data with realistic behavior)

**Problem now**: `plant_model.py` sends constant 3700mV, 0A, 25C. foxBMS reaches NORMAL but nothing interesting happens — SOC stays at 50% forever, no faults, no degradation.

**Solution**: Use the SOC LSTM model *in reverse* — instead of predicting SOC from measurements, replay the BMW i3 training data through the plant model to feed foxBMS with real driving profiles.

```
BMW i3 trip CSV ──→ plant_model.py ──→ SocketCAN ──→ foxBMS vECU
  72 real trips        encodes to           CAN         processes real
  V, I, T, SOC        foxBMS CAN format    frames      driving data
```

**What this enables**:
- foxBMS SOC changes over time (charge/discharge cycles)
- foxBMS sees realistic temperature variation
- foxBMS precharge/contactor logic exercised with real voltage profiles
- foxBMS plausibility checks tested against real cell behavior

**Implementation**:

```python
# plant_model_replay.py — new file, ~80 lines
import csv
import onnxruntime  # not needed for replay, but available

class TripReplay:
    """Replay BMW i3 trip through foxBMS CAN interface."""
    def __init__(self, trip_csv):
        self.data = load_trip(trip_csv)  # reuse prepare_soc_dataset.py loader
        self.idx = 0
        self.num_cells = 18

    def step(self):
        """Return one timestep of battery data for CAN encoding."""
        row = self.data[self.idx]
        pack_v = row[0]  # Battery Voltage [V]
        pack_i = row[1]  # Battery Current [A]
        temp   = row[2]  # Battery Temperature [C]
        # Derive cell voltages from pack voltage
        cell_v_mv = int(pack_v / self.num_cells * 1000)
        self.idx = (self.idx + 1) % len(self.data)
        return cell_v_mv, int(pack_i * 1000), int(temp * 10)
```

**Effort**: 1-2 days
**Risk**: Low — plant model changes only, no foxBMS code changes
**Value**: Immediately makes every demo and test run realistic

---

### Layer 2: ML Sidecar (run inference alongside foxBMS, compare results)

**Problem**: foxBMS uses coulomb counting for SOC. It works but drifts over time. We have a 1.83% RMSE LSTM but no way to use it.

**Solution**: A Python sidecar process that reads foxBMS CAN output, runs ONNX inference, and publishes ML predictions on a separate CAN ID or MQTT topic.

```
foxBMS vECU ──→ CAN TX ──→ ML Sidecar (Python) ──→ CAN TX (new IDs)
  0x233 pack V/I           reads SocketCAN             0x700 ML SOC
  0x250 cell V             builds 200-step window       0x701 ML SOH
  0x260 cell T             ONNX inference (5 models)    0x702 ML thermal risk
  0x235 BMS SOC            every 1 second               0x703 ML RUL
```

**What this enables**:
- Side-by-side SOC comparison: foxBMS coulomb counting vs ML LSTM
- Early degradation detection (SOH drops before capacity fades visibly)
- Thermal anomaly scoring (0-1 risk level, not just threshold)
- RUL estimation for predictive maintenance
- All observable via standard CAN tools (candump, CANape)

**Implementation**:

```python
# ml_sidecar.py — new file, ~150 lines
import onnxruntime as ort
import numpy as np
import socket, struct, collections

# Load all 5 ONNX models
soc_model = ort.InferenceSession("taktflow-bms-ml/models/bms/soc_lstm.onnx")
soh_model = ort.InferenceSession("taktflow-bms-ml/models/bms/soh_lstm.onnx")
thermal_model = ort.InferenceSession("taktflow-bms-ml/models/bms/thermal_cnn.onnx")

# Sliding window buffer (200 timesteps × 5 features)
window = collections.deque(maxlen=200)

# Read foxBMS CAN → extract V, I, T → build window → infer
while True:
    frame = read_can_frame(sock)
    if frame.id == 0x233:  # Pack Values P0: voltage + current
        pack_v, pack_i = decode_0x233(frame.data)
    if frame.id == 0x260:  # Cell Temperatures
        temp, temp_max = decode_0x260(frame.data)

    window.append([pack_v, pack_i, temp, temp_max, 0.0])  # velocity=0 for SIL

    if len(window) == 200:
        # SOC inference
        x = np.array(window, dtype=np.float32).reshape(1, 200, 5)
        x = (x - norm_mean) / norm_std  # normalize with training stats
        soc_pred = soc_model.run(None, {"bms_window": x})[0][0]

        # Publish on CAN
        can_send(0x700, encode_soc(soc_pred))  # ML SOC
```

**Input mapping** (foxBMS CAN → LSTM features):

| LSTM Feature | foxBMS CAN Source | Signal |
|---|---|---|
| pack_V (V) | 0x233 Pack Values P0 | packVoltage_mV / 1000 |
| pack_I (A) | 0x233 Pack Values P0 | packCurrent_mA / 1000 |
| T_avg (C) | 0x260 Cell Temperatures | average of decoded temps |
| T_max (C) | 0x260 Cell Temperatures | max of decoded temps |
| velocity (km/h) | not available in foxBMS | set to 0 (SIL) or inject from plant |

**Key detail**: The LSTM was trained with normalization. The sidecar must apply the same `soc_norm_mean.npy` and `soc_norm_std.npy` from `data/bms-processed/`. Without normalization, predictions will be garbage.

**Effort**: 3-5 days
**Risk**: Medium — needs CAN signal decoding to match foxBMS DBC exactly
**Value**: High — demonstrates ML+firmware co-simulation, directly portfolio-worthy

---

### Layer 3: ML-Enhanced Fault Injection (use models to generate realistic faults)

**Problem**: PLAN.md Phase 3 (fault injection) currently means manually setting one cell to 4.5V. That's unrealistic — real faults develop gradually.

**Solution**: Use the ML models to generate *realistic* fault progression scenarios based on patterns in the training data.

```
Fault Scenario Engine ──→ plant_model.py ──→ foxBMS ──→ ML Sidecar
                                                            ↓
  "thermal runaway at t=300s"     gradually increasing    detects anomaly
  "capacity fade over 500 cycles" temperature + voltage   at t=280s (20s early)
  "cell imbalance developing"     drop following NREL     triggers CAN alert
                                  failure profiles
```

**Scenarios**:

| Scenario | Data Source | Plant Model Behavior | foxBMS Expected Response | ML Expected Response |
|---|---|---|---|---|
| Thermal runaway | NREL failure profiles | Cell temp ramp 2C/min → 100C | Opens contactors at 80C threshold | Thermal CNN detects at 60C (20s earlier) |
| Capacity fade | SOH training data | Slowly reduce cell voltage range | No response (below threshold) | SOH LSTM tracks degradation trend |
| Cell imbalance | Imbalance CNN training data | 1 cell drifts 50mV/cycle | Balancing activates | Imbalance CNN predicts which cell |
| Sensor drift | Synthetic | IVT current offset +5A gradually | SOC drifts | SOC LSTM disagrees with BMS SOC |
| Fast charge stress | BMW i3 high-current profiles | High current + temp rise | SOF limits power | Thermal risk score rises |

**Effort**: 1-2 weeks
**Risk**: High — requires careful scenario design and validation
**Value**: Very high — proves ML catches faults that threshold logic misses

---

## Architecture Summary

```
                        Layer 1                Layer 2              Layer 3
                    (Plant Model)           (ML Sidecar)       (Fault Injection)
                         |                       |                    |
  BMW i3 trip data       |    foxBMS CAN output  |   NREL failure     |
  or fault scenario ─────+────────────────────── | ── profiles ───────+
                         |                       |                    |
                         v                       v                    v
              +--------------------+   +------------------+  +----------------+
              | plant_model.py     |   | ml_sidecar.py    |  | fault_engine.py|
              | (enhanced)         |   | ONNX Runtime     |  | scenario       |
              | trip replay        |   | 5 models loaded  |  | generator      |
              | fault injection    |   | reads foxBMS CAN |  | gradual faults |
              +--------+-----------+   | publishes ML CAN |  +-------+--------+
                       |               +--------+---------+          |
                       | 0x270,0x521           | 0x700-703           |
                       v                       v                     |
              +----------------------------------------+             |
              |           SocketCAN (vcan1)             | <-----------+
              +------------------+---------------------+
                                 |
                                 v
              +----------------------------------------+
              |        foxbms-vecu (C binary)           |
              |  BMS state machine + SOC counting       |
              |  15+ CAN TX messages                    |
              +----------------------------------------+
```

---

## Recommended Implementation Order

| Phase | What | Effort | Depends On | Deliverable |
|---|---|---|---|---|
| **L1.1** | Trip replay plant model | 2 days | — | `plant_model_replay.py` |
| **L1.2** | Dynamic current → SOC changes | 1 day | L1.1 | CAN 0x235 SOC changing over time |
| **L2.1** | ML sidecar skeleton (CAN read + ONNX load) | 2 days | — | `ml_sidecar.py` |
| **L2.2** | SOC LSTM inference + CAN publish | 2 days | L2.1 | CAN 0x700 with ML SOC |
| **L2.3** | SOC comparison dashboard | 1 day | L1.2 + L2.2 | foxBMS SOC vs ML SOC plot |
| **L2.4** | Thermal CNN + SOH LSTM inference | 2 days | L2.1 | CAN 0x701, 0x702 |
| **L3.1** | Thermal runaway scenario from NREL data | 3 days | L1.1 + L2.4 | Fault detected 20s early |
| **L3.2** | Cell imbalance + capacity fade scenarios | 3 days | L3.1 | Full fault test suite |
| **Docker** | Compose: foxbms-vecu + plant + sidecar | 1 day | L2.2 | `docker-compose.yml` |

**Total**: ~3 weeks for a student to deliver L1 + L2, ~5 weeks for all three layers.

---

## What Makes This Valuable

### For the foxBMS project
- Realistic test data instead of constant values → actual validation
- Predictive capability that foxBMS doesn't have natively
- Fault injection with realistic profiles instead of step functions

### For the ML project
- Real firmware to validate against (not just offline evaluation)
- CAN-based deployment pipeline (ONNX → sidecar → CAN bus)
- Cross-validation: ML SOC vs foxBMS coulomb counting vs BMW i3 ground truth

### For a student thesis
- **Claim**: "ML-augmented BMS achieves 1.83% SOC RMSE vs 5-10% coulomb counting drift"
- **Claim**: "Thermal anomaly detected 20 seconds before threshold-based detection"
- **Deliverable**: Working demo — foxBMS + ML sidecar + fault injection, all on SocketCAN
- **Comparison**: dSPACE VEOS + MATLAB = $150k+; this setup = $0 (open source + SocketCAN)

### For portfolio / interviews
- Embedded firmware + ML + CAN protocol + Docker → full-stack automotive
- Not a toy: real foxBMS (Fraunhofer), real driving data (BMW i3), production models (ONNX)
- Reproducible: clone, build, run, see CAN output in 10 minutes

---

## Technical Risks

| Risk | Impact | Mitigation |
|---|---|---|
| LSTM velocity feature missing in SIL | SOC accuracy degrades | Retrain with 4 features (drop velocity) or set to 0 |
| Normalization stats mismatch | Predictions are random | Ship `soc_norm_mean.npy` + `soc_norm_std.npy` with sidecar |
| CAN signal decoding mismatch | Wrong input to model | Use foxBMS DBC file for both plant model and sidecar |
| ONNX Runtime on ARM (future) | Won't run on embedded | CPU ONNX Runtime works on x86 and ARM64; tested |
| 200-step window = 200 seconds at 1Hz | 3+ minutes to first prediction | Use smaller window (50 steps) with reduced accuracy, or warm-start from plant data |
| foxBMS cycle rate (1ms) vs ML inference (~10ms) | Sidecar can't keep up | Run inference at 1Hz, not per CAN frame — 200x reduction |

---

## Files to Create

| File | Location | Purpose |
|---|---|---|
| `plant_model_replay.py` | foxbms-posix/src/ | Trip replay from BMW i3 CSV |
| `ml_sidecar.py` | foxbms-posix/src/ | ONNX inference from foxBMS CAN |
| `fault_engine.py` | foxbms-posix/src/ | Realistic fault scenario generator |
| `decode_foxbms_can.py` | foxbms-posix/src/ | foxBMS CAN message decoder (shared) |
| `docker-compose.yml` | foxbms-posix/ | Compose: vECU + plant + sidecar |
| `requirements.txt` | foxbms-posix/src/ | onnxruntime, python-can, numpy |
