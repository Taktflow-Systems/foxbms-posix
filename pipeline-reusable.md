# Reusable BMS ML-SIL-HIL Pipeline

**What this is**: The complete pipeline that works across any BMS customer. Only the DBC file changes.

---

## Pipeline Overview

```
INPUT (per customer)              PIPELINE (reusable)                OUTPUT (deliverables)
──────────────────                ───────────────────                ─────────────────────

CAN logs (.blf/.asc)  ──→  1. DECODE  ──→  2. ANALYZE  ──→  3. REPORT
DBC file                       cantools       5 ONNX models       PDF / dashboard
Pack specs                     → CSV/numpy    → predictions        findings + numbers
                                                   │
                                                   v
                                        4. DEPLOY (optional)
                                           ML sidecar on CAN
                                           SIL plant model
                                           fault injection
```

---

## Stage 1: Decode (reusable, 1 hour per log)

**Input**: Customer CAN log + their DBC file
**Output**: Time-aligned CSV with all BMS signals

```python
# decode_customer_can.py — works with ANY BMS

import cantools
import can

def decode_log(dbc_path, log_path, output_csv):
    db = cantools.database.load_file(dbc_path)
    log = can.BLFReader(log_path)  # or ASCReader, CSVReader

    signals = {}
    for msg in log:
        try:
            decoded = db.decode_message(msg.arbitration_id, msg.data)
            for name, value in decoded.items():
                signals.setdefault(name, []).append((msg.timestamp, value))
        except:
            pass

    # Align to common timebase, write CSV
    write_aligned_csv(signals, output_csv)
```

**What changes per customer**: Only `dbc_path`. The decode logic is universal.

**Dependencies**: `pip install cantools python-can`

---

## Stage 2: Extract Features (reusable, config-driven)

**Input**: Decoded CSV
**Output**: Numpy arrays ready for ML inference

```python
# extract_features.py — parameterized by pack_config.json

import json
import numpy as np

def extract(csv_path, config_path):
    config = json.load(open(config_path))

    # Config maps customer signal names to model inputs
    # {
    #   "pack_voltage": "BMS_PackVoltage",     ← changes per customer
    #   "pack_current": "BMS_PackCurrent",     ← changes per customer
    #   "cell_temp_signals": ["CellT_01", "CellT_02", ...],
    #   "cell_voltage_signals": ["CellV_01", "CellV_02", ...],
    #   "soc_signal": "BMS_SOC",
    #   "cells_in_series": 96,
    #   "nominal_cell_voltage": 3.7
    # }

    data = load_csv(csv_path)

    # Normalize pack voltage to per-cell (makes models topology-independent)
    pack_v = data[config["pack_voltage"]]
    cell_v = pack_v / config["cells_in_series"]

    pack_i = data[config["pack_current"]]
    temp_avg = np.mean([data[s] for s in config["cell_temp_signals"]], axis=0)
    temp_max = np.max([data[s] for s in config["cell_temp_signals"]], axis=0)

    # Build feature matrix: [V_cell, I, T_avg, T_max, 0]
    # velocity=0 for bench data (model trained with this feature, set to 0)
    features = np.column_stack([cell_v, pack_i, temp_avg, temp_max,
                                np.zeros(len(cell_v))])

    return features, data.get(config.get("soc_signal"), None)
```

**What changes per customer**: `pack_config.json` — signal name mapping + cell count. ~15 minutes to create from their DBC.

---

## Stage 3: ML Inference (fully reusable, zero changes)

**Input**: Feature numpy arrays
**Output**: Predictions for all 5 models

```python
# ml_inference.py — same code for every customer

import onnxruntime as ort
import numpy as np
from pathlib import Path

MODEL_DIR = Path(__file__).parent.parent / "taktflow-bms-ml" / "models" / "bms"
NORM_DIR = Path(__file__).parent.parent / "taktflow-bms-ml" / "data" / "bms-processed"

class BMSInference:
    def __init__(self):
        self.soc = ort.InferenceSession(str(MODEL_DIR / "soc_lstm.onnx"))
        self.soh = ort.InferenceSession(str(MODEL_DIR / "soh_lstm.onnx"))
        self.thermal = ort.InferenceSession(str(MODEL_DIR / "thermal_cnn.onnx"))
        self.imbalance = ort.InferenceSession(str(MODEL_DIR / "imbalance_cnn.onnx"))
        self.rul = ort.InferenceSession(str(MODEL_DIR / "rul_transformer.onnx"))

        # Normalization stats from training
        self.soc_mean = np.load(NORM_DIR / "soc_norm_mean.npy")
        self.soc_std = np.load(NORM_DIR / "soc_norm_std.npy")

    def predict_soc(self, features, window=200):
        """Sliding window SOC prediction.
        features: (N, 5) array [V_cell, I, T_avg, T_max, velocity]
        Returns: (M,) SOC predictions, one per window
        """
        predictions = []
        for i in range(window, len(features)):
            window_data = features[i-window:i]
            x = (window_data - self.soc_mean) / self.soc_std
            x = x.astype(np.float32).reshape(1, window, 5)
            soc = self.soc.run(None, {"bms_window": x})[0][0]
            predictions.append(soc)
        return np.array(predictions)

    def predict_thermal_risk(self, features, window=30):
        """Sliding window thermal anomaly scoring.
        features: (N, 4) array [V, I, T, dT/dt]
        Returns: (M,) risk scores 0-1
        """
        risks = []
        for i in range(window, len(features)):
            x = features[i-window:i].astype(np.float32).reshape(1, window, 4)
            risk = self.thermal.run(None, {"bms_window": x})[0][0]
            risks.append(risk)
        return np.array(risks)

    def predict_imbalance(self, cell_voltages, window=20):
        """Cell imbalance detection.
        cell_voltages: (N, num_cells) array
        Returns: per-window binary (0=healthy, 1=imbalanced)
        """
        predictions = []
        for i in range(window, len(cell_voltages)):
            x = cell_voltages[i-window:i].astype(np.float32)
            x = x.reshape(1, window, -1)
            pred = self.imbalance.run(None, {"bms_window": x})[0][0]
            predictions.append(pred)
        return np.array(predictions)

    def predict_soh(self, cycle_features, window=30):
        """SOH from cycle-level features.
        cycle_features: (N_cycles, 6) [V, I, T, capacity, resistance, cycle]
        Returns: SOH %
        """
        if len(cycle_features) < window:
            return None  # need cycling history
        x = cycle_features[-window:].astype(np.float32).reshape(1, window, -1)
        return self.soh.run(None, {"bms_window": x})[0][0]
```

**What changes per customer**: Nothing. Models are trained on per-cell-normalized data. Any BMS, any topology.

---

## Stage 4: Report Generation (reusable template)

```python
# generate_report.py — parameterized by customer name + results

def generate_soc_report(customer, test_name, ml_soc, bms_soc, timestamps):
    rmse = np.sqrt(np.mean((ml_soc - bms_soc)**2))
    max_drift = np.max(np.abs(ml_soc - bms_soc))
    drift_at_end = ml_soc[-1] - bms_soc[-1]

    report = f"""
    # SOC Audit Report — {customer}
    ## Test: {test_name}

    | Metric | Value |
    |--------|-------|
    | ML SOC RMSE vs BMS | {rmse:.2f}% |
    | Max instantaneous difference | {max_drift:.2f}% |
    | End-of-test drift | {drift_at_end:+.2f}% |
    | ML model | SOC LSTM (BiLSTM 128→64, trained BMW i3 + NASA) |
    | Confidence | Based on {len(ml_soc)} prediction windows |

    ## Interpretation
    {"BMS SOC tracking is within industry standard (<2%)." if rmse < 2
     else f"BMS SOC shows {rmse:.1f}% RMSE — investigate coulomb counting drift."}

    [SOC comparison plot attached]
    """
    return report

def generate_thermal_report(customer, test_name, risk_scores, temps, timestamps):
    peak_risk = np.max(risk_scores)
    high_risk_periods = np.sum(risk_scores > 0.5)

    report = f"""
    # Thermal Risk Report — {customer}
    ## Test: {test_name}

    | Metric | Value |
    |--------|-------|
    | Peak thermal risk score | {peak_risk:.3f} |
    | Periods with risk > 0.5 | {high_risk_periods} ({high_risk_periods*100/len(risk_scores):.1f}%) |
    | Max cell temperature | {np.max(temps):.1f}°C |
    | ML model | Thermal CNN (trained NREL 364 abuse tests) |

    ## Findings
    {"No thermal anomalies detected." if peak_risk < 0.3
     else f"Elevated thermal risk detected. {high_risk_periods} windows scored above 0.5."}

    [Thermal risk overlay plot attached]
    """
    return report

def generate_cell_health_report(customer, cell_voltages_at_rest):
    n_cells = cell_voltages_at_rest.shape[1]
    mean_v = np.mean(cell_voltages_at_rest, axis=0)
    spread = np.max(mean_v) - np.min(mean_v)
    weakest = np.argmin(mean_v)
    deviation = mean_v[weakest] - np.mean(mean_v)

    report = f"""
    # Cell Health Report — {customer}

    | Metric | Value |
    |--------|-------|
    | Cells monitored | {n_cells} |
    | Voltage spread at rest | {spread*1000:.1f} mV |
    | Weakest cell | Cell {weakest+1} ({deviation*1000:+.1f} mV from mean) |
    | Imbalance threshold | >30mV = investigate |

    ## Cell Voltage Bar Chart
    [attached]

    ## Recommendation
    {"Cell voltages are well balanced." if spread < 0.020
     else f"Cell {weakest+1} shows {abs(deviation)*1000:.0f}mV deviation — monitor for further degradation."}
    """
    return report
```

**What changes per customer**: Customer name string. Everything else is data-driven.

---

## Stage 5: Live CAN Sidecar (reusable, config-driven)

For bench deployment — reads CAN in real-time, publishes ML predictions.

```python
# ml_sidecar.py — runs on bench laptop, reads CAN, publishes ML predictions

import can
import cantools
import json
import collections
import numpy as np
import onnxruntime as ort
import time

class MLSidecar:
    def __init__(self, dbc_path, config_path, can_interface="can0"):
        self.db = cantools.database.load_file(dbc_path)
        self.config = json.load(open(config_path))
        self.bus = can.interface.Bus(can_interface, bustype="socketcan")
        self.inference = BMSInference()  # from Stage 3

        # Sliding window buffers
        self.soc_window = collections.deque(maxlen=200)
        self.thermal_window = collections.deque(maxlen=30)

        # Latest decoded values
        self.pack_v = 0.0
        self.pack_i = 0.0
        self.temp_avg = 25.0
        self.temp_max = 25.0
        self.last_inference = 0

    def run(self):
        """Main loop: read CAN → decode → infer → publish."""
        while True:
            msg = self.bus.recv(timeout=0.1)
            if msg is None:
                continue

            # Decode
            try:
                decoded = self.db.decode_message(msg.arbitration_id, msg.data)
                self.update_state(decoded)
            except:
                continue

            # Infer at 1Hz (not per frame)
            now = time.monotonic()
            if now - self.last_inference >= 1.0:
                self.last_inference = now
                self.do_inference()

    def update_state(self, decoded):
        """Update internal state from decoded CAN signals."""
        cfg = self.config
        if cfg["pack_voltage"] in decoded:
            self.pack_v = decoded[cfg["pack_voltage"]]
        if cfg["pack_current"] in decoded:
            self.pack_i = decoded[cfg["pack_current"]]
        # ... temperature signals similarly

        cell_v = self.pack_v / self.config["cells_in_series"]
        self.soc_window.append([cell_v, self.pack_i, self.temp_avg,
                                self.temp_max, 0.0])

    def do_inference(self):
        """Run all models, publish results on CAN."""
        if len(self.soc_window) >= 200:
            features = np.array(self.soc_window, dtype=np.float32)
            x = (features - self.inference.soc_mean) / self.inference.soc_std
            x = x.reshape(1, 200, 5)
            soc = self.inference.soc.run(None, {"bms_window": x})[0][0]

            # Publish ML SOC on CAN ID 0x700
            soc_bytes = int(soc * 100).to_bytes(2, "big")
            self.bus.send(can.Message(arbitration_id=0x700,
                                     data=soc_bytes + bytes(6)))

    def publish(self, can_id, data):
        self.bus.send(can.Message(arbitration_id=can_id, data=data))
```

**What changes per customer**: `dbc_path` and `config_path` (signal name mapping). Same sidecar binary.

---

## Stage 6: SIL Plant Model (reusable, parameter-driven)

For customers who want simulation without the bench.

```python
# plant_model_calibrated.py — parameterized from real bench data

import json
import numpy as np

class CalibratedPlantModel:
    def __init__(self, config_path):
        cfg = json.load(open(config_path))
        self.n_cells = cfg["cells_in_series"]
        self.n_parallel = cfg["cells_in_parallel"]
        self.capacity_ah = cfg["nominal_capacity_ah"]
        self.r_internal = cfg["r_internal_ohm"]       # from bench data
        self.ocv_soc_table = np.array(cfg["ocv_curve"])  # from bench rest periods
        self.thermal_mass = cfg["thermal_mass_j_per_k"]
        self.cell_spread_mv = cfg["cell_spread_mv"]   # from bench OCV measurement
        self.soc = cfg.get("initial_soc", 0.5)
        self.temp = cfg.get("initial_temp_c", 25.0)

    def step(self, dt, current_a):
        """Advance one timestep. Returns cell voltages, pack voltage, temperature."""
        # SOC update (coulomb counting)
        self.soc -= (current_a * dt) / (self.capacity_ah * 3600)
        self.soc = np.clip(self.soc, 0, 1)

        # OCV from SOC (interpolate table from bench data)
        ocv = np.interp(self.soc, self.ocv_soc_table[:, 0], self.ocv_soc_table[:, 1])

        # Per-cell voltage with IR drop + cell-to-cell spread
        cell_v_base = ocv - current_a * self.r_internal / self.n_parallel
        cell_voltages = cell_v_base + np.random.normal(0, self.cell_spread_mv/1000,
                                                        self.n_cells)

        # Temperature (simple thermal model)
        power_dissipated = current_a**2 * self.r_internal
        self.temp += (power_dissipated * dt) / self.thermal_mass
        self.temp -= 0.1 * (self.temp - 25.0) * dt  # ambient cooling

        pack_v = np.sum(cell_voltages)
        return cell_voltages, pack_v, current_a, self.temp, self.soc
```

**What changes per customer**: `plant_config.json` — extracted from their bench data. The plant model code is identical.

**Config extraction script** (run once on their CAN logs):

```python
# calibrate_plant.py — extract plant parameters from customer CAN logs

def calibrate(decoded_csv, config):
    data = load_csv(decoded_csv)

    params = {}
    params["cells_in_series"] = config["cells_in_series"]
    params["cells_in_parallel"] = config["cells_in_parallel"]

    # OCV curve: voltage at rest periods (|current| < 0.5A for >60s)
    rest_mask = find_rest_periods(data[config["pack_current"]],
                                  threshold=0.5, min_duration=60)
    params["ocv_curve"] = extract_ocv_soc(
        data[config["pack_voltage"]][rest_mask] / config["cells_in_series"],
        data[config["soc_signal"]][rest_mask]
    )

    # Internal resistance: dV/dI at load steps
    params["r_internal_ohm"] = estimate_resistance(
        data[config["pack_voltage"]],
        data[config["pack_current"]],
        config["cells_in_series"]
    )

    # Cell spread: std of cell voltages at rest
    cell_vs = [data[s] for s in config["cell_voltage_signals"]]
    params["cell_spread_mv"] = float(np.std(np.array(cell_vs), axis=0).mean() * 1000)

    # Thermal mass: from temperature rise during known power
    params["thermal_mass_j_per_k"] = estimate_thermal_mass(
        data[config["cell_temp_signals"][0]],
        data[config["pack_current"]],
        params["r_internal_ohm"]
    )

    params["nominal_capacity_ah"] = config["nominal_capacity_ah"]

    return params
```

---

## Per-Customer Config File (the only thing that changes)

```json
{
    "customer": "Example BMS GmbH",
    "pack_voltage": "BMS_HV_Voltage",
    "pack_current": "BMS_HV_Current",
    "soc_signal": "BMS_SOC_Display",
    "soh_signal": "BMS_SOH",
    "cell_voltage_signals": [
        "CMB_CellV_01", "CMB_CellV_02", "CMB_CellV_03",
        "CMB_CellV_04", "CMB_CellV_05", "CMB_CellV_06"
    ],
    "cell_temp_signals": [
        "CMB_CellT_01", "CMB_CellT_02", "CMB_CellT_03"
    ],
    "cells_in_series": 96,
    "cells_in_parallel": 3,
    "nominal_capacity_ah": 60,
    "nominal_cell_voltage": 3.7,
    "chemistry": "NMC"
}
```

**Time to create**: 15 minutes with their DBC file open. Map signal names, fill in pack specs.

---

## What Gets Reused vs What's Per-Customer

| Component | Lines of Code | Reused? | Per-Customer Work |
|---|---|---|---|
| `decode_customer_can.py` | ~50 | 100% reused | 0 |
| `extract_features.py` | ~80 | 100% reused | 0 |
| `ml_inference.py` | ~120 | 100% reused | 0 |
| `generate_report.py` | ~150 | 100% reused | 0 |
| `ml_sidecar.py` | ~100 | 100% reused | 0 |
| `plant_model_calibrated.py` | ~80 | 100% reused | 0 |
| `calibrate_plant.py` | ~100 | 100% reused | 0 |
| 5 ONNX models | — | 100% reused (fine-tune if chemistry differs) | 0 or 1 day |
| `pack_config.json` | ~25 | **PER CUSTOMER** | 15 minutes |
| Normalization stats (.npy) | — | Reused (retrain if fine-tuning) | 0 or included in fine-tune |
| **Total pipeline code** | **~680 lines** | **100% reusable** | **15 min config + optional 1 day fine-tune** |

---

## Delivery Timeline by Customer Number

| Customer | Calendar Time | What Happens |
|---|---|---|
| **#0 (foxBMS demo)** | Now → 4-6 weeks | Build everything. foxBMS SIL + fault injection + ML sidecar. |
| **#1 (Munich Electrification)** | +2 weeks | Internal pilot. Real Bologna bench data. Validate + fine-tune. |
| **#2** | +1-2 weeks | Swap config. Run pipeline. Generate reports. |
| **#3** | +1 week | Routine. Config + run + deliver. |
| **#10** | +2-3 days | Streamlined. Mostly automated. |

---

## File Structure (Final Pipeline)

```
taktflow-bms-ml/
├── models/bms/                    5 ONNX models (reusable)
├── data/bms-processed/            Normalization stats (reusable)
├── scripts/bms/                   Training scripts (if fine-tuning needed)
│
├── pipeline/                      ← THE REUSABLE PIPELINE
│   ├── decode_customer_can.py     Decode any CAN log with any DBC
│   ├── extract_features.py        Config-driven feature extraction
│   ├── ml_inference.py            All 5 ONNX models, sliding window
│   ├── generate_report.py         SOC audit, thermal, cell health reports
│   ├── ml_sidecar.py              Live CAN inference (bench deployment)
│   ├── plant_model_calibrated.py  Parameter-driven plant model
│   ├── calibrate_plant.py         Extract params from bench CAN logs
│   ├── run_audit.py               One-command: decode → infer → report
│   └── requirements.txt           cantools, python-can, onnxruntime, numpy
│
├── customers/                     ← PER-CUSTOMER CONFIG (15 min each)
│   ├── foxbms-demo/
│   │   └── pack_config.json
│   ├── munich-electrification/
│   │   └── pack_config.json
│   └── customer-template/
│       └── pack_config.json       Template with comments
│
└── reports/                       Generated output
    ├── foxbms-demo/
    ├── munich-electrification/
    └── ...
```

---

## One-Command Audit

```bash
# For any customer, any CAN log:
python pipeline/run_audit.py \
    --dbc customers/munich-electrification/bologna.dbc \
    --config customers/munich-electrification/pack_config.json \
    --log /path/to/their/test_run.blf \
    --output reports/munich-electrification/

# Output:
#   reports/munich-electrification/soc_audit.pdf
#   reports/munich-electrification/thermal_risk.pdf
#   reports/munich-electrification/cell_health.pdf
#   reports/munich-electrification/raw_predictions.csv
```

15 minutes to create the config. 1 command to run. 3 reports out.
