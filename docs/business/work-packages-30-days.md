# AI-for-BMS Testing — 30-Day Work Packages

**Date**: 2026-03-27
**Scope**: From current state (ML sidecar live on VPS with anomaly detection) to customer-ready Tier 0 + Tier 1 delivery capability
**Starting point**: foxBMS SIL demo live, ml_sidecar.py running, anomaly detection publishing on CAN 0x703/0x705

---

## Work Package Overview

```
Week 1 (Day 1-7)     WP1: Validate + Harden
                      Make the live demo bulletproof. Fix what's broken.

Week 2 (Day 8-14)    WP2: ONNX Models + Customer Pipeline
                      Wire up the 5 ONNX models. Build run_audit.py.

Week 3 (Day 15-21)   WP3: Report Generation + Bench Sidecar
                      PDF reports. DBC-driven sidecar for any CAN bus.

Week 4 (Day 22-30)   WP4: Package + Demo Script + First Customer Dry Run
                      Docker, documentation, rehearsed demo, dry run on real data.
```

---

## WP1: Validate + Harden (Day 1–7)

**Goal**: The live demo is stable, the anomaly model is tuned, and FOBSS validation gives us accuracy numbers we can cite.

### Day 1: Fix live demo issues

| Task | Detail | Done when |
|---|---|---|
| 1.1 Fix BMS SOC display | Sidecar shows `BMS_SOC=0.0%` — the 0x235 parser uses wrong byte offset. Fix and redeploy. | Dashboard shows ~50% SOC matching plant SOC |
| 1.2 Fix pack voltage/current | 0x233 parser uses simplified extraction. Wire up proper foxBMS big-endian decode (same fix as 0x270). | Pack V shows ~66V, current shows discharge mA |
| 1.3 Verify dashboard ML panel | Open sil.taktflow-systems.com/bms/, confirm all 6 gauges render correctly with live data | Screenshot showing active ML panel |

#### 1.1 Technical detail: BMS SOC parser fix

The sidecar reads 0x235 (SOC/SOE message) but foxBMS encodes SOC using its big-endian bit numbering, not raw byte order. Current code:

```python
# BROKEN — treats bytes as big-endian sequential
soc_raw = (data[0] << 8) | data[1]
```

Fix using foxBMS decode table:

```python
# CORRECT — use foxBMS bit numbering
d = int.from_bytes(data[:8], 'big')
soc_raw = _fox_decode(d, 7, 16)  # start_bit=7, length=16 per DBC
self.bms_soc_pct = soc_raw / 100.0  # 0.01% units → %
```

Test: after fix, sidecar log should show `BMS_SOC=50.0%` (initial value from plant model).

#### 1.2 Technical detail: Pack V/I parser fix

Same issue on 0x233. The pack voltage is encoded at start_bit=7, length=17 (unsigned mV). The pack current is at start_bit=20, length=24 (signed mA, two's complement).

```python
# Fix in BMSSensorBuffers.update_from_can()
elif can_id == CAN_ID_PACK_VALUES and len(data) >= 8:
    d = int.from_bytes(data[:8], 'big')
    self.pack_voltage_mv = float(_fox_decode(d, 7, 17))
    current_raw = _fox_decode(d, 20, 24)
    if current_raw & (1 << 23):  # sign-extend 24-bit
        current_raw -= (1 << 24)
    self.pack_current_ma = float(current_raw)
```

Verify with candump: `candump vcan1,233:7FF -n 1` → decode manually → compare with sidecar log.

#### 1.3 Acceptance test

```bash
# On VPS after fix:
ssh root@152.53.245.209
tail -3 /var/log/foxbms-ml-sidecar.log
# Expected:
# [10] BMS_SOC=50.0% SOC=waiting spread=14mV anomaly=0.12 frames=91000

# On browser:
# Open https://sil.taktflow-systems.com/bms/
# ML Intelligence panel should show:
#   SOC LSTM: ---% (waiting for ONNX)
#   Imbalance: 14 mV
#   Anomaly: 0.120
#   Status dot: green "Active"
```

**Deliverable**: Live dashboard with correct numbers in all ML gauges.

### Day 2: Tune anomaly detection for foxBMS

| Task | Detail | Done when |
|---|---|---|
| 2.1 Capture normal baseline from VPS | Record 30 min of normal SIL CAN data: `candump vcan1 -l -n 100000 > foxbms_normal.log` | Baseline .log file (>50K frames) |
| 2.2 Retrain anomaly model on foxBMS data | Parse CAN log → extract features → train IsolationForest on real foxBMS operating profile instead of synthetic | anomaly_model.pkl trained on real SIL data |
| 2.3 Validate: inject OV fault, verify score > 0.7 | Use web dashboard fault injection → check anomaly score rises | Score goes from ~0.1 to >0.7 on overvoltage |
| 2.4 Validate: inject OT fault, verify score rises | Same with overtemperature | Anomaly score > 0.5 during temp injection |

#### 2.1 Technical detail: Capture baseline

```bash
# On VPS — capture 30 min of normal CAN traffic
ssh root@152.53.245.209
cd /opt/foxbms-sil
# Wait until BMS is in NORMAL state (check dashboard)
timeout 1800 candump vcan1 -L > /tmp/foxbms_normal_30min.log
wc -l /tmp/foxbms_normal_30min.log
# Expected: ~500K-1M lines (plant sends every 1ms)
```

#### 2.2 Technical detail: Retrain on real data

Create a training script that parses candump output instead of synthetic data:

```python
# train_from_candump.py (new file, ~60 lines)
# 1. Parse candump log: extract 0x270 (cell V), 0x280 (cell T), 0x521 (current)
# 2. Decode using foxBMS big-endian table
# 3. Compute features: [V_mean, V_std, I, T, V_spread] every 1 second
# 4. Train IsolationForest on these features
# 5. Save anomaly_model.pkl + anomaly_scaler.pkl
```

The key difference from synthetic training: the model learns YOUR plant model's specific noise profile, OCV curve shape, and IR drop characteristics. This means:
- Normal anomaly score drops from ~0.34 (synthetic baseline, doesn't know foxBMS) to ~0.05-0.15 (knows what foxBMS looks like)
- Fault injection should score higher (clearer separation between normal and anomalous)

#### 2.3-2.4 Acceptance test: Fault injection validation

```bash
# Terminal 1: watch anomaly score
ssh root@152.53.245.209 "timeout 30 candump vcan1,705:7FF"

# Terminal 2: inject overvoltage via web dashboard
# Click "Overvoltage" → "Inject" on sil.taktflow-systems.com/bms/
# Or via curl:
# (fault injection goes through WebSocket, so use dashboard)

# Expected CAN 0x705 sequence:
#   Before: 00 32 ... (0x0032 = 50/1000 = 0.050 normal)
#   After:  02 BC ... (0x02BC = 700/1000 = 0.700 anomaly!)
#   Clear:  00 32 ... (back to normal after clear)
```

**Deliverable**: Anomaly model tuned on real foxBMS data with verified fault detection.

### Day 3-4: FOBSS dataset validation

| Task | Detail | Done when |
|---|---|---|
| 3.1 Download FOBSS dataset from KIT Radar | 128MB TAR, CC-BY license. Contains real foxBMS 2 monitoring data from 44-cell pack. | FOBSS data in taktflow-bms-ml/data/fobss/ |
| 3.2 Create FOBSS pack_config.json | Map FOBSS signal names to model features. 44 cells, same foxBMS CAN protocol. | Config file ready |
| 3.3 Run SOC LSTM on FOBSS data | Batch inference, measure RMSE vs FOBSS ground truth SOC | Number: "SOC LSTM achieves X.X% RMSE on foxBMS hardware data" |
| 3.4 Run Thermal CNN on FOBSS data | Score each window, check for false positives on normal operation | Number: "Thermal CNN: X false positives per Y windows" |
| 3.5 Run Imbalance CNN on FOBSS data | Score cell voltage spread, compare with FOBSS cell-level measurements | Number: "Imbalance detection accuracy: X%" |
| 3.6 Document validation results | Write validation-results.md with all numbers, pass/fail per model, honest caveats | Citable accuracy numbers for customer conversations |

#### 3.1 Technical detail: FOBSS dataset

FOBSS (foxBMS Battery Open Source Storage) from KIT Radar:
- **URL**: https://radar.kit.edu (search "FOBSS foxBMS")
- **Size**: 128MB TAR, CC-BY 4.0 license
- **Content**: Real foxBMS 2 monitoring data from 44-cell modular NMC pack
- **Signals**: Cell voltages (per-cell), temperatures, pack current — same CAN protocol as foxBMS v1.10
- **Gap to our SIL**: 44 cells vs 18 cells — but per-cell voltage is topology-independent

```bash
# Download and extract
cd taktflow-bms-ml/data
mkdir -p fobss && cd fobss
wget "https://radar.kit.edu/FOBSS_DATASET_URL" -O fobss.tar.gz
tar xzf fobss.tar.gz
ls -la
# Expected: CSV or HDF5 files with cell voltage time series
```

#### 3.3 Technical detail: SOC LSTM validation on FOBSS

```python
# validate_fobss.py (new file, ~100 lines)
import numpy as np
import onnxruntime as ort

# Load FOBSS data
fobss = load_fobss_csv("fobss/monitoring_data.csv")

# Extract features (per-cell voltage, no topology dependency)
# FOBSS has 44 cells → average to get representative cell voltage
cell_v_avg = np.mean(fobss["cell_voltages"], axis=1)  # per-cell V
pack_i = fobss["pack_current"]
t_avg = np.mean(fobss["cell_temps"], axis=1)
t_max = np.max(fobss["cell_temps"], axis=1)
features = np.column_stack([cell_v_avg, pack_i, t_avg, t_max, np.zeros(len(cell_v_avg))])

# Load SOC LSTM + normalization
model = ort.InferenceSession("models/bms/soc_lstm.onnx")
mean = np.load("data/bms-processed/soc_norm_mean.npy")
std = np.load("data/bms-processed/soc_norm_std.npy")

# Sliding window inference
predictions = []
for i in range(200, len(features)):
    window = features[i-200:i].astype(np.float32).reshape(1, 200, 5)
    window_norm = (window - mean) / (std + 1e-8)
    soc_pred = model.run(None, {model.get_inputs()[0].name: window_norm})[0][0]
    predictions.append(float(soc_pred))

# Compare with FOBSS ground truth SOC
ground_truth = fobss["soc"][200:]
rmse = np.sqrt(np.mean((np.array(predictions) - ground_truth)**2))
print(f"SOC LSTM on FOBSS: RMSE = {rmse:.2f}%")
# Decision gate:
#   < 3%  → proceed as planned, strong claim
#   3-5%  → usable, cite with caveat
#   > 5%  → retrain on per-cell voltage (3-5 day detour)
#   > 10% → pack-level model doesn't transfer, focus on cell-level models
```

#### 3.6 Validation results document structure

```markdown
# Model Validation Results — FOBSS Dataset

## SOC LSTM
- Training data: BMW i3 (72 trips) + NASA PCoE (7565 cycles)
- Validation data: FOBSS foxBMS monitoring (44-cell NMC, KIT Radar)
- RMSE: X.XX%
- Max error: X.XX%
- Verdict: [PASS / CONDITIONAL / FAIL]

## Thermal CNN
- Training data: NREL (364 thermal abuse tests)
- Validation: FOBSS normal operation (expect 0 anomalies)
- False positive rate: X per Y windows
- Verdict: [PASS / CONDITIONAL / FAIL]

## Imbalance CNN
- Validation: FOBSS cell voltage spread
- Detection accuracy: X%
- Verdict: [PASS / CONDITIONAL / FAIL]

## IsolationForest (Anomaly Detection)
- Trained on: foxBMS SIL normal operation (30 min baseline)
- Validated on: foxBMS SIL with fault injection (OV, OT, OC)
- Normal score range: 0.0XX – 0.1XX
- Fault score range: 0.6XX – 0.9XX
- Separation margin: clear / marginal / insufficient
- Verdict: [PASS / CONDITIONAL / FAIL]
```

**Deliverable**: Measured accuracy numbers on real foxBMS data. Can now say "validated on foxBMS monitoring data from KIT Radar" instead of "trained on BMW i3."

### Day 5: VPS stability hardening

| Task | Detail | Done when |
|---|---|---|
| 5.1 Create systemd service for ml_sidecar | Auto-restart on crash. Start after vcan1 is up. | `systemctl status foxbms-ml-sidecar` shows active |
| 5.2 Create systemd service for web server | Same — auto-restart, depends on CAN. | `systemctl status foxbms-web` shows active |
| 5.3 Log rotation | logrotate config for /var/log/foxbms-*.log (keep 7 days, 10MB max) | Logs don't fill disk |
| 5.4 Health check endpoint | Add `/health` to web server — returns JSON with uptime, ML status, frame count | `curl .../health` returns JSON with ml_active=true |

**Deliverable**: SIL demo survives VPS reboot automatically.

### Day 6-7: Buffer / catch-up

Reserve for:
- Fixing bugs found during validation
- FOBSS data format issues
- VPS deployment problems
- Updating PLAN.md and STATUS.md

**WP1 Exit Criteria**:
- [ ] Dashboard shows correct BMS SOC, pack V/I, ML anomaly, ML imbalance
- [ ] Anomaly model trained on real foxBMS SIL data (not synthetic)
- [ ] FOBSS validation: SOC LSTM RMSE measured and documented
- [ ] VPS auto-restarts all services after reboot
- [ ] Health check endpoint responds

---

## WP2: ONNX Models + Customer Pipeline (Day 8–14)

**Goal**: All 5 ONNX models producing predictions on the live demo. Offline audit pipeline works end-to-end.

### Day 8-9: Wire ONNX models to live sidecar

| Task | Detail | Done when |
|---|---|---|
| 8.1 Install onnxruntime on VPS | `pip install onnxruntime` | Import succeeds |
| 8.2 Copy ONNX models to VPS | scp taktflow-bms-ml/models/bms/*.onnx → /opt/foxbms-sil/models/ | 3 ONNX files on VPS |
| 8.3 Copy normalization stats | scp soc_norm_mean.npy, soc_norm_std.npy → VPS | Normalization stats on VPS |
| 8.4 Enable ONNX in sidecar | Remove --no-onnx flag, restart sidecar with --models-dir /opt/foxbms-sil/models/ | Sidecar log shows "Loaded SOC LSTM", "Loaded Thermal CNN" |
| 8.5 Wait for 200-step SOC window | ~200 seconds after start, SOC LSTM should produce first prediction | CAN 0x700 shows non-zero ML SOC |
| 8.6 Verify dashboard | ML SOC gauge shows value, diff vs BMS SOC displayed | Screenshot with SOC LSTM prediction live |

#### 8.1-8.3 Technical detail: ONNX deployment to VPS

```bash
# From dev machine:
cd taktflow-bms-ml

# Check model files exist and sizes
ls -la models/bms/*.onnx
# soc_lstm.onnx       ~2.2 MB  (BiLSTM 128→64, 200-step window)
# thermal_cnn.onnx    ~166 KB  (CNN, 50-step window)
# soh_transformer.onnx ~336 KB (Transformer, 30-step window)

ls -la data/bms-processed/soc_norm_*.npy
# soc_norm_mean.npy   ~160 B   (5 features)
# soc_norm_std.npy    ~160 B   (5 features)

# Deploy to VPS
ssh root@152.53.245.209 "mkdir -p /opt/foxbms-sil/models/bms"
scp models/bms/soc_lstm.onnx \
    models/bms/thermal_cnn.onnx \
    models/bms/soh_transformer.onnx \
    root@152.53.245.209:/opt/foxbms-sil/models/bms/

scp data/bms-processed/soc_norm_mean.npy \
    data/bms-processed/soc_norm_std.npy \
    root@152.53.245.209:/opt/foxbms-sil/models/bms/

# Install ONNX Runtime on VPS
ssh root@152.53.245.209 "pip3 install --break-system-packages onnxruntime"

# Verify import
ssh root@152.53.245.209 "python3 -c 'import onnxruntime; print(onnxruntime.__version__)'"
```

#### 8.4-8.6 Technical detail: Enable ONNX in sidecar

```bash
# Update sidecar to use ONNX models
ssh root@152.53.245.209 << 'EOF'
pkill -f ml_sidecar.py
sleep 1
cd /opt/foxbms-sil/src

# Start WITH ONNX models (remove --no-onnx)
nohup python3 ml_sidecar.py vcan1 \
    --models-dir /opt/foxbms-sil/models/bms \
    --interval 1.0 \
    >> /var/log/foxbms-ml-sidecar.log 2>&1 &

sleep 5
tail -10 /var/log/foxbms-ml-sidecar.log
# Expected:
# Loaded SOC LSTM: /opt/foxbms-sil/models/bms/soc_lstm.onnx
# Loaded normalization stats from /opt/foxbms-sil/models/bms
# Loaded Thermal CNN: /opt/foxbms-sil/models/bms/thermal_cnn.onnx
# Loaded SOH Transformer: /opt/foxbms-sil/models/bms/soh_transformer.onnx
EOF

# After 200 seconds, SOC LSTM should produce first prediction
# Watch for it:
ssh root@152.53.245.209 "timeout 210 candump vcan1,700:7FF -n 1"
# Expected: vcan1 700 [8] XX XX YY YY ZZ ZZ 00 00
# where XX XX = ML SOC (0.01% units)
```

#### Memory budget check

| Model | RAM estimate | Inference time |
|---|---|---|
| SOC LSTM (BiLSTM 128→64) | ~20 MB | ~5-10 ms |
| Thermal CNN | ~5 MB | ~2 ms |
| SOH Transformer | ~10 MB | ~3 ms |
| IsolationForest + scaler | ~5 MB | <1 ms |
| Python + numpy + onnxruntime | ~150 MB | — |
| **Total** | **~190 MB** | **~15 ms per cycle** |

VPS has 8 GB RAM. foxbms-vecu uses ~10 MB, plant_model.py uses ~30 MB, web server uses ~40 MB. Total headroom: ~7.7 GB. No concern.

**Deliverable**: Live dashboard with all ONNX models running. SOC LSTM, Thermal CNN, Imbalance predictions visible.

### Day 10-11: Build run_audit.py (offline pipeline)

| Task | Detail | Done when |
|---|---|---|
| 10.1 Create pipeline/ directory | pipeline/run_audit.py, pipeline/decode_can.py, pipeline/extract_features.py, pipeline/ml_inference.py | Directory structure matches pipeline-reusable.md |
| 10.2 Implement decode_can.py | cantools-based BLF/ASC decoder. Input: DBC + log. Output: CSV. | `python decode_can.py --dbc test.dbc --log test.blf --output signals.csv` works |
| 10.3 Implement extract_features.py | Config-driven feature extraction. Reads pack_config.json. Normalizes to per-cell V. | `python extract_features.py --config config.json --csv signals.csv` outputs numpy arrays |
| 10.4 Implement ml_inference.py | Loads 5 ONNX models, runs sliding-window inference on extracted features. | `python ml_inference.py --features features.npz --output predictions.csv` produces 5 columns |
| 10.5 Implement run_audit.py | Orchestrates: decode → extract → infer → output CSV. Single command. | `python run_audit.py --dbc x.dbc --config c.json --log x.blf --output reports/` |
| 10.6 Test on foxBMS SIL CAN dump | candump a CAN log from VPS, run pipeline offline, verify predictions match live sidecar | Offline predictions within 1% of live sidecar values |

#### 10.1 Technical detail: Pipeline directory structure

```
foxbms-posix/
└── pipeline/                        ← NEW DIRECTORY
    ├── __init__.py
    ├── run_audit.py                 Orchestrator: decode → extract → infer → report
    ├── decode_can.py                cantools-based BLF/ASC/CSV decoder
    ├── extract_features.py          Config-driven feature extraction + normalization
    ├── ml_inference.py              ONNX model wrapper (all 5 models)
    ├── generate_report.py           PDF/Markdown report generator with plots
    ├── ml_sidecar_bench.py          Live CAN sidecar (DBC-driven, any CAN adapter)
    ├── train_anomaly.py             Customer-specific anomaly baseline training
    └── requirements.txt             cantools, python-can, onnxruntime, numpy, matplotlib
```

#### 10.2 Technical detail: decode_can.py

```python
#!/usr/bin/env python3
"""Decode CAN log (BLF/ASC/CSV) to time-aligned signal CSV using cantools."""

import cantools
import can
import csv
import argparse
from pathlib import Path
from collections import defaultdict

def decode_log(dbc_path: str, log_path: str, output_csv: str) -> dict:
    """Decode CAN log file using DBC definitions.

    Supports: .blf (Vector BLF), .asc (Vector ASC), .csv (generic),
              .log (candump), .trc (PEAK)

    Returns: dict with stats {messages_decoded, signals_found, duration_s}
    """
    db = cantools.database.load_file(dbc_path)
    ext = Path(log_path).suffix.lower()

    # Select reader based on file extension
    if ext == ".blf":
        reader = can.BLFReader(log_path)
    elif ext == ".asc":
        reader = can.ASCReader(log_path)
    elif ext in (".csv", ".log"):
        reader = _parse_candump_log(log_path)  # custom parser
    else:
        raise ValueError(f"Unsupported log format: {ext}")

    # Decode all messages
    signals = defaultdict(list)  # signal_name → [(timestamp, value)]
    stats = {"messages_total": 0, "messages_decoded": 0, "decode_errors": 0}

    for msg in reader:
        stats["messages_total"] += 1
        try:
            decoded = db.decode_message(msg.arbitration_id, msg.data)
            stats["messages_decoded"] += 1
            for name, value in decoded.items():
                signals[name].append((msg.timestamp, value))
        except (cantools.database.DecodeError, KeyError):
            stats["decode_errors"] += 1

    # Write time-aligned CSV
    # Find common timebase: 100ms bins
    all_timestamps = set()
    for entries in signals.values():
        for ts, _ in entries:
            all_timestamps.add(round(ts, 1))  # 100ms resolution

    sorted_times = sorted(all_timestamps)
    signal_names = sorted(signals.keys())

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp"] + signal_names)

        for t in sorted_times:
            row = [f"{t:.3f}"]
            for name in signal_names:
                # Find nearest value at or before this timestamp
                entries = signals[name]
                val = ""
                for ts, v in reversed(entries):
                    if ts <= t + 0.05:  # within 50ms
                        val = f"{v:.6f}" if isinstance(v, float) else str(v)
                        break
                row.append(val)
            writer.writerow(row)

    stats["signals_found"] = len(signal_names)
    stats["duration_s"] = sorted_times[-1] - sorted_times[0] if sorted_times else 0
    return stats
```

#### 10.4 Technical detail: ml_inference.py

```python
#!/usr/bin/env python3
"""Run all 5 ONNX models on extracted features."""

import numpy as np
import onnxruntime as ort
from pathlib import Path

class BMSModelSuite:
    """Load and run all BMS ONNX models."""

    def __init__(self, model_dir: str):
        d = Path(model_dir)
        self.models = {}

        # Load available models (gracefully skip missing ones)
        for name, filename, window in [
            ("soc", "soc_lstm.onnx", 200),
            ("soh", "soh_transformer.onnx", 30),
            ("thermal", "thermal_cnn.onnx", 50),
        ]:
            path = d / filename
            if path.exists():
                self.models[name] = {
                    "session": ort.InferenceSession(str(path)),
                    "window": window,
                }

        # Load normalization stats
        mean_path = d / "soc_norm_mean.npy"
        std_path = d / "soc_norm_std.npy"
        if mean_path.exists() and std_path.exists():
            self.soc_mean = np.load(str(mean_path))
            self.soc_std = np.load(str(std_path))
        else:
            self.soc_mean = self.soc_std = None

    def predict_all(self, features: np.ndarray) -> dict:
        """Run all models on feature matrix.

        features: (N, 5) array [V_cell, I, T_avg, T_max, velocity]
        Returns: dict with predictions per model
        """
        results = {}

        # SOC LSTM: sliding window of 200 steps
        if "soc" in self.models:
            window = self.models["soc"]["window"]
            session = self.models["soc"]["session"]
            input_name = session.get_inputs()[0].name
            preds = []
            for i in range(window, len(features)):
                x = features[i-window:i].astype(np.float32).reshape(1, window, -1)
                if self.soc_mean is not None:
                    x = (x - self.soc_mean) / (self.soc_std + 1e-8)
                soc = session.run(None, {input_name: x})[0][0]
                preds.append(float(soc))
            results["ml_soc"] = np.array(preds)
            results["ml_soc_offset"] = window  # first N samples have no prediction

        # Thermal CNN: sliding window of 50 steps
        if "thermal" in self.models:
            window = self.models["thermal"]["window"]
            session = self.models["thermal"]["session"]
            input_name = session.get_inputs()[0].name
            # Thermal features: [T_avg, T_max, T_spread, dT/dt, I]
            t_features = features[:, [2, 3, 2, 2, 1]].copy()
            # Compute dT/dt (finite difference)
            t_features[1:, 3] = np.diff(features[:, 2])  # dT_avg/dt
            t_features[0, 3] = 0
            preds = []
            for i in range(window, len(t_features)):
                x = t_features[i-window:i].astype(np.float32).reshape(1, window, -1)
                risk = session.run(None, {input_name: x})[0][0]
                preds.append(float(np.clip(risk, 0, 1)))
            results["ml_thermal_risk"] = np.array(preds)
            results["ml_thermal_offset"] = window

        # Cell imbalance: direct computation (no ONNX needed)
        # Already in features as voltage spread
        results["ml_imbalance_computed"] = True

        return results
```

#### 10.5 Technical detail: run_audit.py orchestrator

```python
#!/usr/bin/env python3
"""One-command BMS ML audit: CAN log → decode → infer → report.

Usage:
    python run_audit.py --dbc customer.dbc --config pack_config.json \
                        --log test_drive.blf --output reports/
"""

import argparse, json, sys
from pathlib import Path
from decode_can import decode_log
from extract_features import extract_features
from ml_inference import BMSModelSuite
from generate_report import generate_all_reports

def main():
    parser = argparse.ArgumentParser(description="BMS ML Audit Pipeline")
    parser.add_argument("--dbc", required=True, help="DBC file path")
    parser.add_argument("--config", required=True, help="pack_config.json path")
    parser.add_argument("--log", required=True, help="CAN log file (.blf/.asc/.csv)")
    parser.add_argument("--models", default="models/bms/", help="ONNX model directory")
    parser.add_argument("--output", default="reports/", help="Output directory")
    args = parser.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    config = json.load(open(args.config))

    print(f"=== BMS ML Audit: {config.get('customer', 'Unknown')} ===")

    # Stage 1: Decode
    print("[1/4] Decoding CAN log...")
    csv_path = out / "decoded_signals.csv"
    stats = decode_log(args.dbc, args.log, str(csv_path))
    print(f"  {stats['messages_decoded']}/{stats['messages_total']} messages decoded")
    print(f"  {stats['signals_found']} signals found, {stats['duration_s']:.0f}s duration")

    # Stage 2: Extract features
    print("[2/4] Extracting features...")
    features, bms_soc = extract_features(str(csv_path), config)
    print(f"  Feature matrix: {features.shape}")

    # Stage 3: ML inference
    print("[3/4] Running ML inference...")
    suite = BMSModelSuite(args.models)
    predictions = suite.predict_all(features)
    for name, data in predictions.items():
        if isinstance(data, np.ndarray):
            print(f"  {name}: {len(data)} predictions")

    # Stage 4: Generate reports
    print("[4/4] Generating reports...")
    generate_all_reports(config, features, predictions, bms_soc, str(out))

    print(f"\n=== Audit complete. Reports in {out}/ ===")
    for f in sorted(out.glob("*.pdf")) + sorted(out.glob("*.md")):
        print(f"  {f.name}")

if __name__ == "__main__":
    main()
```

#### 10.6 Acceptance test

```bash
# On dev machine:
# 1. Dump CAN from VPS
ssh root@152.53.245.209 "timeout 60 candump vcan1 -L" > foxbms_60s.log

# 2. Run pipeline offline
python pipeline/run_audit.py \
    --dbc src/foxbms_signals.dbc \
    --config customers/foxbms-demo/pack_config.json \
    --log foxbms_60s.log \
    --models taktflow-bms-ml/models/bms/ \
    --output reports/foxbms-test/

# 3. Verify output
ls reports/foxbms-test/
# Expected: decoded_signals.csv, predictions.csv, soc_audit.md, thermal_risk.md, cell_health.md

# 4. Compare offline predictions with live sidecar
# ML SOC from predictions.csv ≈ ML SOC from CAN 0x700 (within 1%)
```

**Deliverable**: `run_audit.py` works end-to-end on a CAN log file.

### Day 12: Customer config template

| Task | Detail | Done when |
|---|---|---|
| 12.1 Create customers/template/pack_config.json | Commented template with all fields explained | Template file ready |
| 12.2 Create customers/foxbms-demo/pack_config.json | foxBMS-specific config (hardcoded signal names, 18S, 3Ah) | Audit pipeline works on foxBMS CAN log |
| 12.3 Test with BMW i3 data | Create BMW i3 config, run audit on one trip CSV | SOC audit report shows LSTM vs coulomb counting comparison |

**Deliverable**: Config template + 2 working configs (foxBMS + BMW i3).

### Day 13-14: Buffer / integration testing

- Run full pipeline on 3 different data sources (foxBMS SIL, BMW i3 CSV, FOBSS)
- Fix edge cases (missing signals, short logs, different DBC formats)
- Measure pipeline runtime (should be <5 min for 1-hour CAN log)

**WP2 Exit Criteria**:
- [ ] All 5 ONNX models running on live VPS dashboard
- [ ] SOC LSTM shows prediction after 200s warmup
- [ ] `run_audit.py` produces predictions.csv from BLF/ASC/CSV input
- [ ] Pipeline tested on 3 different data sources
- [ ] Customer config template documented

---

## WP3: Report Generation + Bench Sidecar (Day 15–21)

**Goal**: Pipeline produces PDF reports. Sidecar works on real CAN hardware (not just vcan).

### Day 15-16: Report generator

| Task | Detail | Done when |
|---|---|---|
| 15.1 Implement generate_report.py | Takes predictions.csv + raw signals → generates 3 reports | Python script produces 3 output files |
| 15.2 SOC audit report | ML SOC vs BMS SOC comparison. RMSE, max drift, end-of-test gap. Plot overlay. Finding text. | soc_audit.md with embedded plot (matplotlib) |
| 15.3 Thermal risk report | Peak risk score, risk timeline, cell group with highest risk. Finding text. | thermal_risk.md with risk overlay plot |
| 15.4 Cell health report | Voltage spread at rest, weakest cell, deviation from mean, trend if multi-log. | cell_health.md with bar chart |
| 15.5 PDF export | Convert markdown reports to PDF (weasyprint or pandoc) | 3 PDF files in reports/ directory |
| 15.6 Test: run full pipeline → PDFs | foxBMS SIL log → decode → infer → report → 3 PDFs | PDFs open correctly, plots readable |

#### 15.1-15.5 Technical detail: Report generator

```python
# generate_report.py — produces 3 reports with matplotlib plots

import numpy as np
import matplotlib
matplotlib.use("Agg")  # headless rendering
import matplotlib.pyplot as plt
from pathlib import Path

def generate_soc_report(config, features, predictions, bms_soc, output_dir):
    """SOC Audit Report: ML SOC vs BMS SOC comparison with plot."""
    ml_soc = predictions.get("ml_soc")
    if ml_soc is None:
        return None

    offset = predictions.get("ml_soc_offset", 200)
    bms_aligned = bms_soc[offset:offset+len(ml_soc)] if bms_soc is not None else None

    # Metrics
    if bms_aligned is not None and len(bms_aligned) == len(ml_soc):
        rmse = float(np.sqrt(np.mean((ml_soc - bms_aligned)**2)))
        max_diff = float(np.max(np.abs(ml_soc - bms_aligned)))
        end_drift = float(ml_soc[-1] - bms_aligned[-1])
    else:
        rmse = max_diff = end_drift = None

    # Plot: SOC comparison + delta
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), height_ratios=[3, 1])
    t = np.arange(len(ml_soc)) / 10  # 10Hz

    ax1.plot(t, ml_soc, label="ML SOC (LSTM)", color="#8B5CF6", linewidth=1.5)
    if bms_aligned is not None:
        ax1.plot(t[:len(bms_aligned)], bms_aligned, label="BMS SOC",
                 color="#22C55E", linewidth=1.5, alpha=0.8)
    ax1.set_ylabel("SOC (%)"); ax1.legend(); ax1.grid(True, alpha=0.3)

    if bms_aligned is not None:
        diff = ml_soc[:len(bms_aligned)] - bms_aligned
        ax2.fill_between(t[:len(diff)], diff, alpha=0.3, color="#EAB308")
        ax2.axhline(0, color="white", linewidth=0.5)
        ax2.set_ylabel("Delta (%)"); ax2.set_xlabel("Time (s)")

    fig.tight_layout()
    fig.savefig(Path(output_dir) / "soc_comparison.png", dpi=150,
                facecolor="#0F0F1A", bbox_inches="tight")
    plt.close(fig)

    # Markdown report with metrics table + interpretation
    interpretation = (
        f"RMSE {rmse:.2f}% — {'excellent' if rmse < 2 else 'moderate drift' if rmse < 5 else 'significant drift'}"
        if rmse else "No BMS SOC reference available"
    )
    report = f"""# SOC Audit Report — {config.get('customer', 'BMS')}
| Metric | Value |
|--------|-------|
| ML SOC RMSE vs BMS | {f'{rmse:.2f}%' if rmse else 'N/A'} |
| Max difference | {f'{max_diff:.2f}%' if max_diff else 'N/A'} |
| End-of-test drift | {f'{end_drift:+.2f}%' if end_drift else 'N/A'} |
| Interpretation | {interpretation} |

![SOC Comparison](soc_comparison.png)
"""
    (Path(output_dir) / "soc_audit.md").write_text(report)
```

Thermal risk and cell health reports follow the same structure: compute metrics → plot → markdown.

#### 15.6 Acceptance test

```bash
python pipeline/run_audit.py \
    --dbc src/foxbms_signals.dbc \
    --config customers/foxbms-demo/pack_config.json \
    --log foxbms_60s.log --output reports/test-full/

ls reports/test-full/
# Expected: soc_audit.md, soc_comparison.png, thermal_risk.md,
#           thermal_timeline.png, cell_health.md, cell_voltage_bar.png, predictions.csv
```

**Deliverable**: `run_audit.py --output reports/` produces 3 PDF reports.

### Day 17-18: DBC-driven bench sidecar

| Task | Detail | Done when |
|---|---|---|
| 17.1 Create pipeline/ml_sidecar_bench.py | Config-driven sidecar: reads DBC + pack_config.json, decodes any CAN bus, runs ONNX, publishes on 0x700-0x705 | Sidecar starts with `--dbc x.dbc --config c.json --can can0` |
| 17.2 Test with python-can virtual bus | Create virtual bus in Python, feed foxBMS-format frames, verify sidecar decodes + infers | Unit test passes |
| 17.3 Test with PCAN on USB | Connect PCAN adapter, run sidecar on can0, verify with candump | candump shows 0x700-0x705 frames from sidecar |
| 17.4 CANape DBC for ML signals | Create small DBC file for CAN 0x700-0x705 so customer can add to CANape | ML_Predictions.dbc importable in CANape |

#### 17.1 Technical detail: DBC-driven bench sidecar

The foxBMS-specific sidecar (`src/ml_sidecar.py`) uses hardcoded CAN IDs and foxBMS big-endian encoding. The bench sidecar uses cantools + DBC for any BMS:

```python
# pipeline/ml_sidecar_bench.py — works with ANY BMS
# Key difference: uses cantools.decode_message() instead of hardcoded foxBMS parsing

import cantools, can, json, time, collections, struct
import numpy as np
import onnxruntime as ort

class BenchSidecar:
    def __init__(self, dbc_path, config_path, models_dir, can_interface="can0"):
        self.db = cantools.database.load_file(dbc_path)
        self.config = json.load(open(config_path))
        self.bus = can.interface.Bus(can_interface, bustype="socketcan")
        self.suite = BMSModelSuite(models_dir)

        # Map customer signal names to internal feature slots
        self.pack_v_signal = self.config["pack_voltage"]
        self.pack_i_signal = self.config["pack_current"]
        self.temp_signals = self.config["cell_temp_signals"]
        self.n_cells = self.config["cells_in_series"]

        self.window = collections.deque(maxlen=200)
        self.state = {"pack_v": 0, "pack_i": 0, "t_avg": 25, "t_max": 25}

    def run(self):
        last_inference = 0
        while True:
            msg = self.bus.recv(timeout=0.1)
            if msg is None:
                continue

            # Decode using DBC — works for ANY BMS
            try:
                decoded = self.db.decode_message(msg.arbitration_id, msg.data)
            except (cantools.database.DecodeError, KeyError):
                continue

            # Update state from decoded signals
            if self.pack_v_signal in decoded:
                self.state["pack_v"] = decoded[self.pack_v_signal]
            if self.pack_i_signal in decoded:
                self.state["pack_i"] = decoded[self.pack_i_signal]
            # Temperature: average of all temp signals present
            temps = [decoded[s] for s in self.temp_signals if s in decoded]
            if temps:
                self.state["t_avg"] = np.mean(temps)
                self.state["t_max"] = np.max(temps)

            # Per-cell normalization (makes model topology-independent)
            cell_v = self.state["pack_v"] / self.n_cells
            self.window.append([cell_v, self.state["pack_i"],
                                self.state["t_avg"], self.state["t_max"], 0.0])

            # Infer at 1 Hz
            now = time.monotonic()
            if now - last_inference >= 1.0 and len(self.window) >= 200:
                last_inference = now
                features = np.array(self.window, dtype=np.float32)
                results = self.suite.predict_all(features.reshape(1, -1, 5))
                self._publish(results)

    def _publish(self, results):
        """Publish ML predictions on CAN 0x700-0x705."""
        if "ml_soc" in results and len(results["ml_soc"]) > 0:
            soc = results["ml_soc"][-1]
            data = struct.pack(">H6x", int(soc * 100))
            self.bus.send(can.Message(arbitration_id=0x700, data=data))
        # ... same for 0x701-0x705
```

#### 17.4 Technical detail: ML Predictions DBC

```dbc
// ML_Predictions.dbc — add to CANape alongside customer DBC
VERSION ""
NS_ :
BS_:
BU_: ML_Sidecar

BO_ 1792 ML_SOC: 8 ML_Sidecar
 SG_ ML_SOC_Pct : 0|16@1+ (0.01,0) [0|100] "%" Vector__XXX
 SG_ BMS_SOC_Pct : 16|16@1+ (0.01,0) [0|100] "%" Vector__XXX
 SG_ SOC_Diff : 32|16@1- (0.01,0) [-50|50] "%" Vector__XXX

BO_ 1793 ML_SOH: 8 ML_Sidecar
 SG_ ML_SOH_Pct : 0|16@1+ (0.01,0) [0|100] "%" Vector__XXX

BO_ 1794 ML_Thermal: 8 ML_Sidecar
 SG_ ML_ThermalRisk : 0|16@1+ (0.001,0) [0|1] "" Vector__XXX

BO_ 1795 ML_Imbalance: 8 ML_Sidecar
 SG_ ML_CellSpread_mV : 0|16@1+ (1,0) [0|1000] "mV" Vector__XXX

BO_ 1797 ML_Anomaly: 8 ML_Sidecar
 SG_ ML_AnomalyScore : 0|16@1+ (0.001,0) [0|1] "" Vector__XXX
```

Customer imports this DBC into CANape → all ML signals appear as recordable measurements.

**Deliverable**: Bench-ready sidecar that works with any DBC + any CAN adapter.

### Day 19: Anomaly baseline training from customer data

| Task | Detail | Done when |
|---|---|---|
| 19.1 Implement pipeline/train_anomaly.py | Takes customer CAN log (normal operation) → extracts features → trains IsolationForest → saves model | `python train_anomaly.py --dbc x.dbc --config c.json --log normal.blf` |
| 19.2 Validate: train on foxBMS SIL → test on fault injection | Train on 10 min normal → inject OV → score should be >0.7 | Demonstrated on foxBMS demo |
| 19.3 Document: "how to record your normal baseline" | 1-page instruction for customer HIL team: what to record, how long, which signals matter | Customer-facing instruction document |

**Deliverable**: Customer can train anomaly baseline from their own bench data.

### Day 20-21: Buffer / testing

- End-to-end test: DBC + CAN log → config → decode → infer → report → PDFs
- Test with different CAN log formats (BLF, ASC, MF4)
- Performance: verify <5 min for 1-hour log, <15ms inference latency for live sidecar
- Fix bugs from integration

**WP3 Exit Criteria**:
- [ ] `run_audit.py` produces 3 PDF reports with plots
- [ ] Bench sidecar works with DBC + python-can on real CAN adapter
- [ ] CANape DBC for ML signals created
- [ ] Anomaly baseline training from customer CAN log works
- [ ] Full pipeline tested end-to-end on 2+ data sources

---

## WP4: Package + Demo + First Dry Run (Day 22–30)

**Goal**: Everything packaged for customer delivery. Demo rehearsed. Dry run on real-world data.

### Day 22-23: Docker packaging

| Task | Detail | Done when |
|---|---|---|
| 22.1 Dockerfile for pipeline | Single container: Python + onnxruntime + cantools + all pipeline scripts | `docker run pipeline --dbc x.dbc --log x.blf` produces reports |
| 22.2 docker-compose for full SIL | vECU + plant + ml_sidecar + web dashboard + test runner | `docker compose up` → all services running, dashboard accessible |
| 22.3 Test: clean machine → docker compose up → dashboard | On a fresh Ubuntu VM, clone repo, docker compose up, verify everything works | Reproduced in <10 min |

#### 22.1 Technical detail: Pipeline Dockerfile

```dockerfile
# pipeline/Dockerfile
FROM python:3.11-slim

WORKDIR /pipeline

# Install system deps for matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    can-utils iproute2 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /pipeline/
COPY ../taktflow-bms-ml/models/bms/ /pipeline/models/bms/
COPY ../taktflow-bms-ml/data/bms-processed/soc_norm_*.npy /pipeline/models/bms/

ENTRYPOINT ["python", "run_audit.py"]
```

Usage:
```bash
docker run --rm -v $(pwd)/data:/data -v $(pwd)/reports:/reports \
    pipeline --dbc /data/customer.dbc \
             --config /data/pack_config.json \
             --log /data/test_drive.blf \
             --output /reports/
```

#### 22.2 Technical detail: Full SIL docker-compose

```yaml
# docker-compose.yml (updated with ML sidecar)
version: "3.8"
services:
  vecu:
    build: .
    container_name: foxbms-vecu
    privileged: true
    command: ["/bin/bash", "-c", "modprobe vcan; ip link add vcan1 type vcan; ip link set vcan1 up; python3 /app/plant_model.py vcan1 & sleep 0.5; exec /app/foxbms-vecu"]
    networks: [canbus]

  ml-sidecar:
    build: .
    container_name: foxbms-ml
    privileged: true
    depends_on: [vecu]
    command: ["/bin/bash", "-c", "ip link add vcan1 type vcan 2>/dev/null; ip link set vcan1 up; python3 /app/train_anomaly_bms.py --output-dir /app; exec python3 /app/ml_sidecar.py vcan1 --models-dir /app/models/bms"]
    networks: [canbus]

  web:
    build: .
    container_name: foxbms-web
    privileged: true
    depends_on: [vecu]
    ports: ["8080:8080"]
    command: ["/bin/bash", "-c", "ip link add vcan1 type vcan 2>/dev/null; ip link set vcan1 up; exec python3 /app/web/server.py --can vcan1 --port 8080"]
    networks: [canbus]

  test:
    build: .
    container_name: foxbms-test
    privileged: true
    depends_on: [vecu]
    command: ["/bin/bash", "-c", "ip link add vcan1 type vcan 2>/dev/null; ip link set vcan1 up; sleep 10; python3 /app/test_smoke.py vcan1"]
    networks: [canbus]

networks:
  canbus:
    driver: bridge
```

```bash
# Test: clean machine
docker compose up -d
sleep 15
curl http://localhost:8080/health
# Expected: {"ml_active": true, "uptime_s": 12, "bms_state": "NORMAL"}
docker compose down
```

**Deliverable**: One-command SIL environment for demos and customer delivery.

### Day 24-25: Demo script + recording

| Task | Detail | Done when |
|---|---|---|
| 24.1 Write 10-minute demo script | Step-by-step: open dashboard → explain gauges → inject fault → show ML detection → show report | Demo script document |
| 24.2 Rehearse demo 3 times | Time it. Fix flow issues. Prepare talking points for each screen. | Demo is smooth, under 10 min |
| 24.3 Record terminal session | asciinema or screen recording of: start SIL → run audit → show PDFs | Recording file for async demos |
| 24.4 Prepare customer-facing README | "How to evaluate this": clone, docker compose up, open browser, try fault injection | Customer README.md |

#### 24.1 Technical detail: 10-minute demo script

```
DEMO SCRIPT — foxBMS AI-Augmented BMS Testing
Total time: 10 minutes | Presenter: An Dao | Setup: browser + terminal

──────────────────────────────────────────────────────

[0:00–1:30] INTRO — The problem

  "Every BMS company has three teams that don't talk to each other:
   ML team with models in Jupyter, firmware team with code on metal,
   HIL team with CAN logs on a NAS. We connect them."

  Show slide: ML ←→ Firmware ←→ HIL gap diagram

[1:30–4:00] LIVE DEMO — Dashboard

  Open: https://sil.taktflow-systems.com/bms/

  Point out:
  1. "This is real foxBMS 2 firmware running on Linux"
     → State Machine panel: NORMAL (green)
     → Cell voltage grid: 18 cells, ~3700mV each

  2. "This is the ML sidecar running alongside on CAN"
     → ML Intelligence panel: 6 gauges
     → Anomaly: 0.12 (normal)
     → Imbalance: 14mV (healthy)
     → CAN monitor: 0x703/0x705 frames in amber

  3. "Watch what happens when I inject a fault"
     → Click Overvoltage → Cell 0 → Inject
     → Watch: anomaly score rises 0.12 → 0.75
     → Watch: BMS state goes to ERROR
     → Watch: contactors open
     → "ML detected the anomaly. BMS opened contactors."

  4. Click "Clear All Faults" → system recovers
     → Anomaly drops back to 0.12

[4:00–6:00] OFFLINE PIPELINE — Your data, our models

  Terminal:
  $ python pipeline/run_audit.py \
      --dbc bmw_i3.dbc \
      --config customers/bmw-i3/pack_config.json \
      --log data/trip_001.blf \
      --output reports/demo/

  Show output:
  "[1/4] Decoding CAN log... 45,000 messages"
  "[2/4] Extracting features... (72000, 5)"
  "[3/4] Running ML inference... soc: 71800 predictions"
  "[4/4] Generating reports..."

  Open: reports/demo/soc_audit.md
  → Show SOC comparison plot
  → "ML SOC RMSE 2.1% vs BMS coulomb counting"
  → "This is what we deliver from YOUR CAN log"

[6:00–8:00] BENCH DEPLOYMENT — Same code, your CAN bus

  Show architecture diagram:
  "We put this laptop on your bench, plug in a USB-CAN adapter,
   and in 15 minutes your CANape shows ML predictions alongside
   your BMS signals. No firmware changes."

  Show: ML_Predictions.dbc
  "Import this DBC into CANape and you see 5 new signals."

[8:00–9:30] PRICING + NEXT STEPS

  "Tier 0: Give us your DBC + one CAN log.
   48 hours later you get 3 reports.
   If we find something your BMS missed, we talk about Tier 1."

  Show pricing slide:
    Tier 0: Free (proof of value)
    Tier 1: €5-15k (sidecar on your bench)
    Tier 2: €20-40k (full SIL environment)
    Tier 3: €40-80k (ML test generation)

[9:30–10:00] Q&A

  Leave-behind: USB stick with sample reports + config template
```

#### 24.3 Terminal recording

```bash
# Record with asciinema
asciinema rec demo_foxbms_ai.cast \
    --title "foxBMS AI-Augmented BMS Testing" \
    --idle-time-limit 2

# Inside recording:
echo "=== foxBMS AI Pipeline Demo ==="
python pipeline/run_audit.py --dbc ... --log ... --output reports/demo/
cat reports/demo/soc_audit.md | head -20
echo "=== 3 reports generated ==="
ls -la reports/demo/

# Stop recording: Ctrl+D
# Upload: asciinema upload demo_foxbms_ai.cast
```

**Deliverable**: Rehearsed, timed demo. Recording for async sharing.

### Day 26-27: Dry run on real-world data

| Task | Detail | Done when |
|---|---|---|
| 26.1 Get real CAN log | Use BMW i3 driving data (already have 72 trips), or FOBSS foxBMS data, or ME bench data if available | At least 1 real CAN log ready |
| 26.2 Create pack_config.json | Map signal names for the chosen data source | Config created in <15 min |
| 26.3 Run full pipeline | decode → extract → infer → report → 3 PDFs | 3 reports generated |
| 26.4 Review reports critically | Are the findings actionable? Are the numbers believable? Would a customer pay for this? | Honest assessment written |
| 26.5 Fix report quality issues | Axis labels, unit conversions, finding text clarity, plot readability | Reports look professional |

#### 26.1-26.3 Technical detail: Dry run data sources (priority order)

**Option A: BMW i3 driving data** (already have, 72 trips)
```bash
# Data location: taktflow-bms-ml/data/bms-raw/bmw-i3-driving/
# Format: CSV (semicolon-separated, Latin-1 encoding)
# Columns: Timestamp, GPS_Lat, GPS_Long, Speed, Acceleration, Altitude,
#           Elevation, Battery_Voltage, Battery_Current, Battery_Temperature,
#           Cabin_Temp, SoC, Tire_Pressure
# Key signals for ML:
#   Battery_Voltage (V) → pack_voltage (col 7)
#   Battery_Current (A) → pack_current (col 8)
#   Battery_Temperature (°C) → cell_temp (col 9)
#   SoC (%) → ground truth SOC (col 11)
# Pack: 96S/94Ah NMC → per-cell: V/96 = ~3.75V

python pipeline/run_audit.py \
    --dbc customers/bmw-i3/bmw_i3.dbc \
    --config customers/bmw-i3/pack_config.json \
    --log taktflow-bms-ml/data/bms-raw/bmw-i3-driving/trip_001.csv \
    --output reports/bmw-i3-dry-run/
```

**Option B: FOBSS foxBMS data** (if downloaded in WP1)
```bash
python pipeline/run_audit.py \
    --dbc customers/fobss/foxbms_fobss.dbc \
    --config customers/fobss/pack_config.json \
    --log taktflow-bms-ml/data/fobss/monitoring_001.csv \
    --output reports/fobss-dry-run/
```

**Option C: ME bench data** (if available from Munich Electrification)
- Would be the strongest demo: real customer bench data
- Need: DBC + one BLF from S-CORE bench

#### 26.4 Technical detail: Critical review checklist

For each of the 3 reports, answer:

```
SOC Audit:
□ Is the RMSE number believable? (BMW i3: expect 1.5-3%, FOBSS: expect 2-5%)
□ Does the plot clearly show ML vs BMS SOC?
□ Can a non-expert understand the finding?
□ Is the interpretation text accurate (not overclaiming)?
□ Would YOU pay €5k for this report?

Thermal Risk:
□ Are there any periods where risk > 0.3?
□ If yes: is there a real thermal event, or is it a false positive?
□ If no: does the report say "no anomalies" clearly?
□ Is the cell group identification correct?

Cell Health:
□ Is the voltage spread realistic for the data source?
□ Does the weakest cell identification make physical sense?
□ Is the recommendation actionable?
□ Would a customer trust this to make a maintenance decision?
```

If any answer is "no" → fix before Day 28.

**Deliverable**: 3 professional PDF reports from real data, critically reviewed.

### Day 28-29: Customer pitch package

| Task | Detail | Done when |
|---|---|---|
| 28.1 One-page service description | Tier 0-3 summary, pricing, timeline, what we need from them | 1-page PDF |
| 28.2 Sample report (anonymized) | Redact customer-specific data from dry run reports, use as sample | Sample SOC audit PDF |
| 28.3 Update live demo | Ensure VPS demo is stable, dashboard shows all ML gauges, health endpoint works | sil.taktflow-systems.com/bms/ loads cleanly |
| 28.4 Prepare "leave-behind" package | USB stick or ZIP: sample reports + DBC template + pack_config template + README | ZIP file ready |

**Deliverable**: Complete pitch package for first customer meeting.

### Day 30: Retrospective + plan next 30 days

| Task | Detail | Done when |
|---|---|---|
| 30.1 Retrospective | What worked, what didn't, what took longer, what to cut next time | Written in lessons-learned.md |
| 30.2 Metrics | Lines of code written, models validated, pipeline runtime, demo count | Numbers documented |
| 30.3 Plan next 30 days | Tier 2 SIL environment, Tier 3 ML test generation, first customer engagement | Plan document |
| 30.4 Update PLAN.md | Mark Phase 6 (AI Integration) criteria | PLAN.md updated |

**Deliverable**: 30-day retrospective + next 30-day plan.

---

## Summary: 30-Day Deliverables

| Day | Work Package | Key Deliverable |
|---|---|---|
| **1** | Fix live demo | Dashboard shows correct ML values |
| **2** | Tune anomaly model | IsolationForest trained on real foxBMS data |
| **3-4** | FOBSS validation | Citable accuracy: "SOC LSTM X.X% RMSE on foxBMS data" |
| **5** | VPS hardening | systemd services, auto-restart, health check |
| **6-7** | Buffer | Catch-up, bug fixes |
| **8-9** | ONNX on VPS | All 5 models live on dashboard |
| **10-11** | run_audit.py | Offline pipeline: CAN log → predictions.csv |
| **12** | Config template | Customer pack_config.json template |
| **13-14** | Integration test | Pipeline tested on 3 data sources |
| **15-16** | Report generator | 3 PDF reports with plots |
| **17-18** | Bench sidecar | DBC-driven sidecar for real CAN hardware |
| **19** | Anomaly training | Customer baseline training from their CAN log |
| **20-21** | Buffer | End-to-end testing |
| **22-23** | Docker packaging | One-command SIL environment |
| **24-25** | Demo script | 10-min rehearsed demo + recording |
| **26-27** | Dry run | 3 professional reports from real data |
| **28-29** | Pitch package | 1-page service description + sample reports |
| **30** | Retrospective | Metrics, lessons learned, next 30-day plan |

---

## What You Can Sell After Day 30

| Capability | Status | Evidence |
|---|---|---|
| **Tier 0: Offline audit** | READY | run_audit.py → 3 PDFs from any CAN log |
| **Tier 1: Live sidecar** | READY | ml_sidecar_bench.py + CANape DBC |
| **Tier 2: SIL environment** | DEMO READY | docker compose, not yet customer-calibrated |
| **Tier 3: ML test generation** | NOT STARTED | Planned for day 31-60 |

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation | Affects |
|---|---|---|---|---|
| FOBSS dataset format doesn't match foxBMS v1.10 | Can't validate models on foxBMS data | Medium | Fall back to BMW i3 per-cell normalization validation | WP1 Day 3-4 |
| SOC LSTM RMSE > 5% on FOBSS | Can't claim accuracy for foxBMS | Medium | Retrain on per-cell voltage + FOBSS. Budget 3 extra days. | WP1 Day 4 |
| onnxruntime crashes on VPS (Debian ARM mismatch) | No ONNX models live | Low (VPS is x86_64) | Fall back to --no-onnx (anomaly only) | WP2 Day 8 |
| cantools can't parse customer DBC | Pipeline fails on first real customer | Medium | Support cantools + python-can fallback. Test with 3+ DBC files. | WP3 Day 17 |
| PDF generation fails (weasyprint dependency hell) | No PDF reports | Medium | Fall back to markdown reports + manual PDF export | WP3 Day 15 |
| VPS runs out of RAM with 5 ONNX models | Sidecar OOM killed | Low (8GB VPS) | Monitor RSS, limit model count if needed | WP2 Day 8 |
| Demo takes > 10 min | Loses customer attention | Medium | Cut SOH/RUL from demo (focus SOC + thermal + anomaly) | WP4 Day 24 |

---

## Dependencies

```
WP1 ──→ WP2 ──→ WP3 ──→ WP4
                  │
                  └──→ WP4 (reports needed for demo)

Critical path: WP1.FOBSS → WP2.ONNX → WP3.Reports → WP4.DryRun
```

No external dependencies except:
- FOBSS dataset download (public, CC-BY)
- VPS SSH access (already have)
- onnxruntime pip install (standard)
