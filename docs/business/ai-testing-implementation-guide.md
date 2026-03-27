# AI for BMS Testing — Implementation Guide

**For**: Customer HIL/SIL test teams deploying ML-augmented battery management testing
**From**: Taktflow Systems — foxBMS POSIX SIL Platform
**Date**: 2026-03-27
**Live demo**: https://sil.taktflow-systems.com/bms/

---

## What This Guide Covers

How to add machine learning to an existing BMS test environment. No firmware changes. No dSPACE. No MATLAB license. Works with any CAN-based BMS.

This guide has 4 tiers, from "try it in 1 hour" to "full production deployment":

```
Tier 0: Offline Audit      — give us a CAN log, get 3 reports back (1 hour)
Tier 1: Live CAN Sidecar   — ML running on your bench laptop (1-2 weeks)
Tier 2: SIL Environment    — your firmware on Linux + ML + CI (2-4 weeks)
Tier 3: ML Test Generation  — anomaly-driven test scenarios (4-8 weeks)
```

---

## Tier 0: Offline CAN Log Audit (1 Hour Setup)

### What you need

| Item | Source | Format |
|---|---|---|
| One CAN log from your bench | Your NAS / test server | .blf, .asc, or .csv |
| Your DBC file | Your CAN team | .dbc |
| Pack specifications | Your BMS spec sheet | cell count, chemistry, capacity |

### What we run

```bash
# Step 1: Create signal mapping (15 min, one-time)
cat > pack_config.json << 'EOF'
{
    "customer": "Your Company",
    "pack_voltage": "BMS_HV_Voltage",
    "pack_current": "BMS_HV_Current",
    "soc_signal": "BMS_SOC_Display",
    "cell_voltage_signals": ["CMB_CellV_01", "CMB_CellV_02", ...],
    "cell_temp_signals": ["CMB_CellT_01", "CMB_CellT_02", ...],
    "cells_in_series": 96,
    "nominal_capacity_ah": 60,
    "chemistry": "NMC"
}
EOF

# Step 2: Run audit (5 min compute time)
python pipeline/run_audit.py \
    --dbc your_bms.dbc \
    --config pack_config.json \
    --log bench_test_001.blf \
    --output reports/
```

### What you get back

```
reports/
├── soc_audit.pdf          ← ML SOC vs your BMS SOC comparison
│                             "Your coulomb counting drifts 3.2% over 2 hours"
├── thermal_risk.pdf       ← Cell temperature risk scoring
│                             "Cell group 3 peaked at risk=0.42 during fast charge"
├── cell_health.pdf        ← Imbalance and cell spread analysis
│                             "Cell 23 is 12mV below average — monitor over 50 cycles"
└── raw_predictions.csv    ← All 5 model outputs, timestamped, for your own analysis
```

### What the models detect

| Model | What it finds | Training data | Why your BMS can't do this |
|---|---|---|---|
| **SOC LSTM** | Coulomb counting drift rate under dynamic load | BMW i3 (72 trips) + NASA PCoE (7565 cycles) | Your BMS SOC can't validate itself — needs independent estimate |
| **Thermal CNN** | Temperature gradient anomalies (e.g., one cell heating faster) | NREL (364 thermal abuse tests) | Your BMS checks thresholds (>60C); ML scores continuous risk 0.0-1.0 |
| **Imbalance CNN** | Which cell is weakest, by how much, and trending | Multi-chemistry EV pack data | Your BMS balances reactively; ML predicts which cell will need it |
| **SOH Transformer** | Capacity fade trend over cycles | LiionPro-DT (2M rows, 5-year degradation) | Needs cycling history — your bench logs have this |
| **Anomaly IsolationForest** | "Something unusual happened" across all signals | Auto-trained on your normal operation data | General-purpose anomaly flag your BMS doesn't have |

### Cost: $0 tooling + 1 hour of our time

---

## Tier 1: Live CAN Sidecar (1-2 Weeks)

### Architecture

```
Your Bench
┌──────────────────────────────────────────────────────┐
│                                                      │
│  Your BMS ECU ──→ CAN bus ──→ Your existing tools   │
│                      │         (CANape, CANoe, etc.) │
│                      │                                │
│                      │         ┌────────────────────┐│
│                      └────────→│ ML Sidecar         ││
│                                │ (our laptop/Pi)    ││
│                                │                    ││
│                                │ Reads: 0x233,0x270 ││
│                                │ Runs: 5 ONNX models││
│                                │ Publishes:          ││
│                                │  0x700 ML SOC      ││
│                                │  0x702 Thermal risk││
│                                │  0x705 Anomaly     ││
│                                └────────────────────┘│
│                                        │              │
│                      CAN bus ←─────────┘              │
│                         │                             │
│                    CANape sees both:                   │
│                    BMS signals + ML predictions       │
└──────────────────────────────────────────────────────┘
```

### Hardware needed

| Item | Cost | Purpose |
|---|---|---|
| Linux laptop or Raspberry Pi 4 | You already have one | Runs ML sidecar |
| USB-CAN adapter (PCAN, Kvaser, etc.) | ~€200 if not already on bench | Connects to your CAN bus |
| Python 3.10+ | Free | Runtime |

### Software setup (on your bench laptop)

```bash
# 1. Install dependencies
pip install onnxruntime numpy scikit-learn joblib python-can cantools

# 2. Clone our pipeline
git clone https://github.com/taktflow-systems/bms-ml-pipeline.git
cd bms-ml-pipeline

# 3. Create your signal mapping
cp customers/template/pack_config.json customers/your-company/
vim customers/your-company/pack_config.json
# Map your DBC signal names → model features (15 min)

# 4. Train anomaly baseline on YOUR normal data
# Record 30 min of normal bench operation → normal_baseline.blf
python pipeline/train_anomaly.py \
    --dbc your_bms.dbc \
    --config customers/your-company/pack_config.json \
    --log normal_baseline.blf
# Output: anomaly_model.pkl, anomaly_scaler.pkl
# Now the anomaly detector knows what YOUR normal looks like

# 5. Start live sidecar
python pipeline/ml_sidecar.py \
    --dbc your_bms.dbc \
    --config customers/your-company/pack_config.json \
    --can can0 \
    --models models/bms/
# Publishing ML predictions on CAN 0x700-0x705

# 6. See predictions in CANape / candump
candump can0,700:7F0
# 0x700 = ML SOC, 0x702 = thermal risk, 0x705 = anomaly score
```

### What you get in CANape

Add these signals to your measurement:

| CAN ID | Signal | Unit | Interpretation |
|---|---|---|---|
| 0x700 | ML_SOC | % (×0.01) | ML predicts SOC. Compare with your BMS SOC. If gap > 3%, investigate drift. |
| 0x701 | ML_SOH | % (×0.01) | State of Health estimate. Decreasing = capacity fade. |
| 0x702 | ML_ThermalRisk | 0.000-1.000 | 0=normal, >0.3=elevated, >0.7=alert. Compare with your threshold logic. |
| 0x703 | ML_Imbalance | mV | Max-min cell voltage. Increasing = cell divergence. |
| 0x705 | ML_Anomaly | 0.000-1.000 | General anomaly score. >0.7 = something unusual. |

### Integration with your test automation

```python
# In your pytest / Robot Framework / custom test runner:

import can

def check_ml_soc_matches_bms(bus, tolerance_pct=3.0, duration_s=60):
    """Verify ML SOC and BMS SOC agree within tolerance."""
    ml_soc = None
    bms_soc = None
    start = time.time()

    while time.time() - start < duration_s:
        msg = bus.recv(timeout=1.0)
        if msg.arbitration_id == 0x700:
            ml_soc = struct.unpack(">H", msg.data[0:2])[0] / 100.0
        elif msg.arbitration_id == 0x235:
            bms_soc = decode_bms_soc(msg.data)

        if ml_soc is not None and bms_soc is not None:
            diff = abs(ml_soc - bms_soc)
            assert diff < tolerance_pct, \
                f"SOC mismatch: ML={ml_soc:.1f}% BMS={bms_soc:.1f}% diff={diff:.1f}%"
            ml_soc = bms_soc = None  # reset for next check

def check_no_thermal_anomaly(bus, threshold=0.5, duration_s=300):
    """Verify no thermal anomalies during test run."""
    start = time.time()
    while time.time() - start < duration_s:
        msg = bus.recv(timeout=1.0)
        if msg.arbitration_id == 0x702:
            risk = struct.unpack(">H", msg.data[0:2])[0] / 1000.0
            assert risk < threshold, \
                f"Thermal anomaly: risk={risk:.3f} > {threshold} at t={time.time()-start:.0f}s"

def check_cell_balance(bus, max_spread_mv=30, duration_s=60):
    """Verify cell voltages are balanced."""
    start = time.time()
    while time.time() - start < duration_s:
        msg = bus.recv(timeout=1.0)
        if msg.arbitration_id == 0x703:
            spread = struct.unpack(">H", msg.data[0:2])[0]
            assert spread < max_spread_mv, \
                f"Cell imbalance: spread={spread}mV > {max_spread_mv}mV"
```

### Cost: €5-15k engagement + 1 day bench access

---

## Tier 2: SIL Environment (2-4 Weeks)

### What this is

Your BMS firmware running on Linux, with a calibrated plant model derived from your real bench data, plus ML inference — all in Docker, all in CI.

```
┌─────────────────────────────────────────────────────────┐
│  Docker Compose (one command: docker compose up)         │
│                                                          │
│  ┌──────────────────────┐  ┌──────────────────────────┐ │
│  │  Plant Model          │  │  Your BMS Firmware       │ │
│  │  (calibrated from     │  │  (compiled for x86       │ │
│  │   your bench CAN logs)│  │   POSIX, or foxBMS demo) │ │
│  │                       │  │                          │ │
│  │  OCV curve: YOUR data │  │  State machine: NORMAL   │ │
│  │  R_internal: measured │  │  SOC counting: running   │ │
│  │  Thermal: calibrated  │  │  Diagnostics: active     │ │
│  │  Cell spread: measured│  │  CAN TX: 15+ messages    │ │
│  └───────────┬───────────┘  └────────────┬─────────────┘ │
│              │           vcan1            │               │
│              └────────────┬──────────────┘               │
│                           │                              │
│  ┌────────────────────────┴──────────────────────────┐   │
│  │  ML Sidecar                                       │   │
│  │  5 ONNX models + anomaly detection                │   │
│  │  Reads BMS CAN → publishes ML CAN 0x700-0x705    │   │
│  └────────────────────────┬──────────────────────────┘   │
│                           │                              │
│  ┌────────────────────────┴──────────────────────────┐   │
│  │  Test Runner (pytest)                             │   │
│  │  test_smoke.py: BMS reaches NORMAL                │   │
│  │  test_soc.py: ML SOC vs BMS SOC within 3%        │   │
│  │  test_thermal.py: no anomalies during profile     │   │
│  │  test_fault.py: overvoltage → contactor opens     │   │
│  │  test_ml_sidecar.py: predictions published on CAN │   │
│  └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Plant model calibration (from your bench data)

We extract real battery parameters from your CAN logs — no guessing:

```python
# calibrate_plant.py — run once on your bench CAN log

# 1. OCV curve: voltage at rest periods (|I| < 0.5A for > 60s)
#    Result: piecewise linear OCV(SOC) table from YOUR cells
#
# 2. Internal resistance: dV/dI at load steps
#    Result: R_internal in mOhm (per-cell)
#
# 3. Cell spread: std of cell voltages at rest
#    Result: manufacturing variation in mV (for realistic simulation)
#
# 4. Thermal mass: temperature rise during known power dissipation
#    Result: J/K (for thermal model)
#
# Input:  your_bench_run.blf + pack_config.json
# Output: plant_calibration.json (drives the plant model)
```

### What changes per customer

| Component | Lines of code | Changes? |
|---|---|---|
| Plant model engine | 80 lines | 0 changes — parameter-driven |
| ML sidecar | 420 lines | 0 changes — same CAN protocol |
| Test runner | 200 lines | 0 changes — same pass/fail criteria |
| ONNX models | 5 files | 0 changes (or optional fine-tune if different chemistry) |
| **pack_config.json** | 25 lines | **YES — signal names + cell count** |
| **plant_calibration.json** | 30 lines | **YES — extracted from your bench data** |

### CI integration

```yaml
# .github/workflows/sil-regression.yml
name: BMS SIL Regression
on: [push, schedule]
jobs:
  sil-test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - name: Start SIL environment
        run: docker compose up -d
      - name: Wait for BMS NORMAL
        run: python test_smoke.py vcan1
      - name: Run ML-augmented tests
        run: |
          python -m pytest tests/ \
            --junitxml=results.xml \
            -v
      - name: Trend analysis
        run: python tools/trend-analyze.py results/
```

### Cost: €20-40k engagement

---

## Tier 3: ML-Driven Test Generation (4-8 Weeks)

### The idea

Use ML anomaly detection on your **historical CAN log archive** to find patterns that should be tested but aren't in your manual test plan.

```
Your CAN Log Archive (2TB on NAS)
         │
         ↓
┌────────────────────────────────┐
│  Anomaly Mining                │
│                                │
│  For each log:                 │
│    decode → extract features   │
│    → run IsolationForest       │
│    → flag unusual windows      │
│                                │
│  "Found 47 unusual patterns    │
│   across 200 test runs"        │
└────────────┬───────────────────┘
             │
             ↓
┌────────────────────────────────┐
│  Pattern Clustering            │
│                                │
│  Cluster 47 anomalies into     │
│  categories:                   │
│    A: thermal gradient (12x)   │
│    B: SOC jump (8x)            │
│    C: current spike (15x)      │
│    D: cell voltage divergence  │
│    E: sensor dropout (7x)      │
└────────────┬───────────────────┘
             │
             ↓
┌────────────────────────────────┐
│  Test Scenario Generation      │
│                                │
│  For each cluster:             │
│    Extract representative      │
│    time series → create plant  │
│    model scenario that         │
│    reproduces the pattern      │
│                                │
│  "5 new test scenarios your    │
│   manual plan doesn't cover"   │
└────────────┬───────────────────┘
             │
             ↓
┌────────────────────────────────┐
│  SIL Execution                 │
│                                │
│  Run each scenario on SIL:     │
│    plant_model → vECU → ML     │
│                                │
│  Check:                        │
│    Did BMS detect the fault?   │
│    How fast? (ms to contactor  │
│    open)                       │
│    Did ML detect it earlier?   │
│                                │
│  "Scenario B: BMS didn't open  │
│   contactors. ML flagged it    │
│   at t=280s. Your threshold    │
│   was never reached."          │
└────────────────────────────────┘
```

### Example: What we find in real CAN archives

| Pattern | How we find it | What it means | Your BMS response | ML response |
|---|---|---|---|---|
| **Cell 12 heats 2x faster than neighbors during fast charge** | Thermal CNN risk > 0.4 for cell group 3 only | Cooling duct partially blocked, or cell aging faster | Nothing (temp still below 60C threshold) | Risk score 0.42 — flagged as elevated |
| **SOC jumps 3% when current transitions to regen** | SOC LSTM disagrees with BMS by >3% during transition | Coulomb counting accumulates error during current sign change | SOC shows jump (normal for coulomb counting) | ML SOC is smooth (learned from 72 real trips) |
| **Voltage of cell 23 drops 8mV more than others after 200 cycles** | Imbalance trend across multiple logs | Cell degrading faster — will need balancing more frequently | Balancing activates reactively | ML predicts which cell will diverge next |
| **Current sensor reads 0.5A when contactors are open** | Anomaly score > 0.7 during idle state | Current sensor offset / calibration drift | Not detected (0.5A is within noise threshold) | Flagged as anomalous (trained on clean idle data) |
| **Pack voltage oscillates ±2V at 10Hz during discharge** | Spectral analysis of voltage signal | Loose HV connection or contactor chatter | Not detected (average voltage is fine) | Anomaly score spikes during oscillation |

### Automated test scenario extraction

```python
# For each anomaly cluster, we extract:
scenario = {
    "name": "thermal_gradient_fast_charge",
    "source": "bench_run_2026-03-15_001.blf t=1890-2100s",
    "signals": {
        "current_profile": [...],    # extracted from CAN log
        "cell_temp_profile": [...],  # the anomalous pattern
        "expected_bms_action": "none (below threshold)",
        "expected_ml_score": ">0.4 thermal risk",
    },
    "test_criteria": {
        "thermal_risk_peak": {"operator": ">", "value": 0.3},
        "bms_contactor_open": {"operator": "==", "value": False},
        "cell_temp_gradient": {"operator": ">", "value": 5.0, "unit": "degC"},
    },
}

# This scenario runs automatically on SIL:
# 1. Plant model replays the extracted current + temp profile
# 2. foxBMS processes it (does it detect anything?)
# 3. ML sidecar scores it (does it flag the gradient?)
# 4. Test runner checks criteria (pass/fail)
```

### Cost: €40-80k engagement

---

## How the Anomaly Model Improves Over Time

### Phase 1: Synthetic baseline (day 0 — what we deploy now)

The IsolationForest trains on synthetic "normal BMS" data: 4 operating regimes (idle, precharge, transition, normal) with realistic voltage/current/temperature distributions. This catches obvious anomalies (overvoltage, overcurrent, extreme temperature) but may false-positive on patterns specific to YOUR pack.

### Phase 2: Customer baseline (day 1 — after first bench access)

We record 30 minutes of YOUR normal operation and retrain:

```bash
python train_anomaly.py --log your_normal_baseline.blf --dbc your.dbc
```

Now the model knows what YOUR pack looks like. False positives drop because it's seen your specific:
- Cell voltage spread (your manufacturing tolerance)
- Temperature distribution (your cooling system)
- Current profile (your typical drive cycle)
- SOC operating range (your charge/discharge limits)

### Phase 3: Continuous learning (month 1+ — ongoing)

As you run more bench tests, we can retrain on the growing dataset:

```bash
python train_anomaly.py --log-dir /path/to/all/normal/logs/ --dbc your.dbc
```

The anomaly detection gets better with more data because the boundary between "normal" and "unusual" gets sharper.

### Phase 4: Chemistry-specific ONNX models (optional)

If your pack uses LFP (flat OCV curve) instead of NMC, the SOC LSTM may underperform. We can fine-tune on your data:

```bash
python fine_tune_soc.py \
    --base-model models/bms/soc_lstm.onnx \
    --data your_soc_labeled_data.csv \
    --epochs 10 \
    --output models/bms/soc_lstm_lfp.onnx
```

This requires labeled SOC data (e.g., from your BMS test bench with reference SOC from coulomb counting + OCV reset). 3-5 days of work.

---

## What Makes This Different From "Just Run ML"

The gap every company has is not "we don't have ML models" — many have trained models in notebooks. The gap is:

```
Their ML team                     Our pipeline
─────────────                     ────────────

model.predict(test_data)          CAN log → decode → normalize → window →
                                  inference → CAN publish → test assert →
                                  CI report → trend analysis
```

**We don't sell models. We sell the pipe.**

| What they have | What they're missing | What we provide |
|---|---|---|
| Trained ONNX model | CAN bus deployment | ml_sidecar.py (420 lines) |
| BLF CAN logs on NAS | Feature extraction pipeline | extract_features.py + pack_config.json |
| Bench with CANape | ML predictions in CANape | CAN 0x700-0x705 protocol |
| pytest test framework | ML-based assertions | check_ml_soc_matches_bms() |
| CI/CD pipeline | SIL regression with ML | docker-compose + trend-analyze.py |
| 2TB of historical data | Anomaly mining | IsolationForest + pattern clustering |

---

## Quick Start Checklist

### Customer preparation (before we arrive)

- [ ] Export one DBC file for your BMS CAN messages
- [ ] Export 3 CAN logs: one charge, one discharge, one dynamic cycle (.blf or .asc)
- [ ] Document: cell count, chemistry, nominal capacity, voltage limits
- [ ] Provide bench access for 1 day (Tier 1) or send logs by email (Tier 0)

### Our preparation

- [ ] Create pack_config.json from their DBC (15 min)
- [ ] Run offline audit on their 3 logs (30 min)
- [ ] Prepare demo: their data on our SIL dashboard
- [ ] Train customer-specific anomaly baseline (if bench data available)

### Deliverables

| Tier | Timeline | Deliverable |
|---|---|---|
| **Tier 0** | 48 hours | 3 PDF reports (SOC audit, thermal risk, cell health) |
| **Tier 1** | 1-2 weeks | ML sidecar running on bench CAN + CANape integration |
| **Tier 2** | 2-4 weeks | Docker SIL environment + CI pipeline + test suite |
| **Tier 3** | 4-8 weeks | Anomaly-driven test scenarios + execution reports |

---

## Live Demo

The ML sidecar is running right now at **https://sil.taktflow-systems.com/bms/**

Look at the **ML Intelligence** panel at the bottom of the dashboard:
- **Anomaly score**: ~0.34 (normal — foxBMS running healthy)
- **Imbalance**: ~14 mV (normal spread for 18-cell simulated pack)
- **SOC LSTM**: waiting for 200-step window (ONNX models not loaded in demo)
- **CAN monitor**: 0x703 and 0x705 frames visible in amber

This is the same code that would run on your bench. Only the config file changes.
