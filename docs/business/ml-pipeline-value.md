# ML Pipeline: From SIL Demo to Customer CAN Logs

**Date**: 2026-03-27
**Status**: ACTIVE — SIL demo live, ML sidecar ready for deployment

---

## The Pipeline (End-to-End)

```
                     WHAT WE HAVE NOW                    WHAT CUSTOMER BRINGS
                     ─────────────────                   ─────────────────────

  ┌─────────────────────────────────────┐    ┌─────────────────────────────┐
  │  foxBMS SIL Demo (Netcup VPS)      │    │  Customer CAN Logs          │
  │                                     │    │                             │
  │  plant_model.py ──→ vcan1 ──→ vECU │    │  test_drive.blf  (BLF/ASC) │
  │  (18S/3Ah NMC, OCV+noise+IR)       │    │  endurance.blf              │
  │       │                             │    │  fast_charge.blf            │
  │       ↓                             │    │  customer.dbc (signal defs) │
  │  CAN frames every 1ms:             │    │  pack_specs.json            │
  │   0x270 cell voltages (muxed)      │    │                             │
  │   0x280 cell temperatures          │    └──────────┬──────────────────┘
  │   0x521 IVT current                │               │
  │   0x233 pack V/I                   │               │
  │   0x235 SOC/SOE                    │               │
  │                                     │               │
  └──────────┬──────────────────────────┘               │
             │                                          │
             │  SAME PIPELINE                           │
             │  SAME MODELS                             │
             │  SAME CODE                               │
             ↓                                          ↓
  ┌──────────────────────────────────────────────────────────────┐
  │                    ML INFERENCE LAYER                         │
  │                                                              │
  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
  │  │ SOC LSTM     │  │ Thermal CNN  │  │ Imbalance CNN│      │
  │  │ 200-step     │  │ 50-step      │  │ cell spread  │      │
  │  │ BiLSTM 128→64│  │ NREL-trained │  │ detection    │      │
  │  │ 1.83% RMSE   │  │ F1=1.000     │  │              │      │
  │  └──────────────┘  └──────────────┘  └──────────────┘      │
  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
  │  │ SOH Transf.  │  │ RUL Transf.  │  │ IsolationFor.│      │
  │  │ 30-step      │  │ cycle-level  │  │ anomaly 0-1  │      │
  │  │ 9.79% RMSE   │  │ 16% MAPE     │  │ auto-trained │      │
  │  └──────────────┘  └──────────────┘  └──────────────┘      │
  └──────────────────────────┬───────────────────────────────────┘
                             │
                             ↓
  ┌──────────────────────────────────────────────────────────────┐
  │                      OUTPUT                                   │
  │                                                              │
  │  SIL DEMO (live)              │  CUSTOMER (offline/bench)    │
  │  ─────────────                │  ──────────────────────      │
  │  CAN 0x700: ML SOC vs BMS    │  soc_audit.pdf               │
  │  CAN 0x702: thermal risk     │  thermal_risk.pdf            │
  │  CAN 0x705: anomaly score    │  cell_health.pdf             │
  │  Web dashboard gauges        │  raw_predictions.csv         │
  │  Live 24/7 on VPS            │  "Your SOC drifts 3.2%"     │
  └──────────────────────────────────────────────────────────────┘
```

---

## Is This Meaningful? Honest Assessment

### What the SIL demo DOES prove

| Claim | Evidence | Why it matters for customers |
|---|---|---|
| **The inference pipeline works end-to-end** | plant → CAN → sidecar → predictions → dashboard | Customer sees: "they can actually run models on CAN, not just in Jupyter" |
| **Models load and produce predictions in real-time** | ONNX Runtime + SocketCAN, 1Hz inference, <15ms latency | Customer sees: "this can run on our bench laptop without dSPACE" |
| **Anomaly detection catches abnormal states** | IsolationForest scores normal BMS data as 0.0-0.15, overvoltage injection scores >0.7 | Customer sees: "it distinguishes normal from fault conditions" |
| **The architecture is production-grade** | Docker, CI, WebSocket dashboard, CAN protocol | Customer sees: "this isn't a prototype, it's deployable" |
| **Cell imbalance is measured in real-time** | max-min voltage spread across 18 cells, published on CAN 0x703 | Customer sees: "we can track cell health continuously" |
| **The system runs 24/7 without supervision** | Live at sil.taktflow-systems.com/bms/ since 2026-03-21 | Customer sees: "this is stable enough for production bench" |

### What the SIL demo DOES NOT prove (yet)

| Gap | Why | Impact | Fix |
|---|---|---|---|
| **SOC LSTM accuracy on foxBMS data** | Trained on BMW i3 96S, foxBMS is 18S. No FOBSS validation done. | Can't claim "1.83% RMSE" for foxBMS | Validate on FOBSS dataset (2-3 days) |
| **SOH/RUL on single run** | SOH needs cycling history, RUL needs degradation trend. SIL demo is one continuous run. | SOH shows 0%, RUL shows 0 | Replay synthetic multi-cycle data |
| **ML detects faults before foxBMS** | DIAG_Handler is suppressed. foxBMS can't detect faults to compare against. | Can't claim "20s early detection" | Implement selective DIAG |
| **Plant model matches real battery** | OCV is linear approximation, not measured NMC curve | SIL voltages are simplified | Calibrate from real bench data |

### Bottom line

**The SIL demo proves the integration architecture works. It does NOT prove model accuracy on arbitrary customer data.**

That's the right order: prove the pipe works first, then fill it with validated models. Customers buy the pipe, not the model accuracy. Their own data makes the accuracy real.

---

## How It Helps With Real Customer CAN Logs

### The Customer Interaction (Step by Step)

```
CUSTOMER GIVES US:                    WE DO:                         CUSTOMER GETS:
─────────────────                     ──────                         ──────────────

1. DBC file (their CAN signal defs)  → Map signal names to model    15 min work
                                        features in pack_config.json  (one time)

2. One CAN log (.blf or .asc)        → python run_audit.py          5 min runtime
   from a test drive or bench run       --dbc customer.dbc
                                        --config pack_config.json
                                        --log test_drive.blf

                                      → Decode CAN to CSV            automatic
                                      → Extract V, I, T, SOC         automatic
                                      → Normalize to per-cell        automatic
                                      → Run 5 ONNX models            automatic
                                      → Generate 3 PDF reports       automatic

3. Nothing else                       →                              3 reports:

                                        ┌─────────────────────────────────────┐
                                        │ SOC AUDIT REPORT                    │
                                        │                                     │
                                        │ Their BMS SOC vs ML SOC:           │
                                        │   RMSE: 2.7%                       │
                                        │   Max drift: 4.1% at t=2340s       │
                                        │   End-of-test: BMS reads 34%,      │
                                        │     ML predicts 31% → 3% gap       │
                                        │                                     │
                                        │ Finding: Coulomb counting drifts    │
                                        │ during high-C discharge. ML         │
                                        │ stays closer to OCV-based truth.    │
                                        │                                     │
                                        │ [SOC comparison plot]               │
                                        └─────────────────────────────────────┘
                                        ┌─────────────────────────────────────┐
                                        │ THERMAL RISK REPORT                 │
                                        │                                     │
                                        │ Peak risk: 0.42 at t=1890s         │
                                        │ Trigger: Cell 12 temp rose 3.2C/min│
                                        │ BMS action: none (below 60C thres.)│
                                        │ ML detected: 18s before BMS would  │
                                        │   have triggered at current ramp    │
                                        │                                     │
                                        │ Finding: Thermal gradient between   │
                                        │ cell 12 and cell 1 reached 8.5C.   │
                                        │ Monitor for cooling system issue.   │
                                        └─────────────────────────────────────┘
                                        ┌─────────────────────────────────────┐
                                        │ CELL HEALTH REPORT                  │
                                        │                                     │
                                        │ Voltage spread at rest: 28 mV      │
                                        │ Weakest cell: #23 (-12mV from avg) │
                                        │ Strongest: #7 (+9mV from avg)      │
                                        │                                     │
                                        │ Finding: Spread within 30mV limit  │
                                        │ but cell 23 trending low. Monitor  │
                                        │ over next 50 cycles.               │
                                        └─────────────────────────────────────┘
```

### Why This Is Valuable to the Customer

**They have CAN logs sitting on a NAS that nobody analyzes.**

Every BMS company runs bench tests, logs CAN data, and stores it. Most of this data is never looked at beyond pass/fail. Our pipeline extracts insights:

| What we find in their logs | Why they care | What they can't do without us |
|---|---|---|
| **SOC drift rate under load** | Certification requires independent SOC validation (ISO 26262 Part 6). Our LSTM is the independent estimate. | Their own SOC algorithm can't validate itself |
| **Thermal hotspots between cells** | Thermal runaway starts with one cell. 8.5C gradient means cooling unevenness. | Their BMS monitors temperature but doesn't score thermal risk on a 0-1 scale |
| **Cell imbalance trend** | A weakening cell means pack capacity degrades. Catching it at 12mV saves a recall at 50mV. | Their BMS balances but doesn't trend |
| **Anomaly patterns in historical data** | "Your BMS had 7 unusual current spikes in the last 200 logs" — they didn't know | Nobody runs anomaly detection on their CAN archive |
| **SOC algorithm comparison** | "Your coulomb counting drifts 3% over 2 hours vs ML 1.8%" — quantified gap | No benchmark to compare against |

### The Business Pitch (One Sentence)

> "Give us your DBC and one CAN log. In 48 hours we'll tell you things about your battery pack that your own BMS doesn't know."

---

## Data Flow: SIL Demo vs Customer CAN Log

| Aspect | SIL Demo (live now) | Customer CAN Log |
|---|---|---|
| **Data source** | plant_model.py (simulated 18S NMC pack) | Real battery pack on real bench |
| **CAN interface** | vcan1 (virtual, Linux kernel) | can0 (real, PCAN/Vector/etc.) |
| **Signals** | 0x270 cell V, 0x280 cell T, 0x521 IVT I | Whatever their DBC defines |
| **Signal names** | foxBMS-specific (hardcoded) | Customer-specific (config-driven) |
| **Data format** | Live SocketCAN frames | BLF/ASC/CSV file (offline) |
| **Inference mode** | Real-time (ml_sidecar.py on CAN) | Batch (run_audit.py on file) |
| **ML models** | Same 5 ONNX models | Same 5 ONNX models |
| **Normalization** | Same soc_norm_mean/std.npy | Same (per-cell-normalized, topology-independent) |
| **Output** | CAN 0x700-0x705 + web dashboard | PDF reports + CSV |
| **Per-customer config** | None (foxBMS is hardcoded) | pack_config.json (15 min) |

**Key insight: The ML models don't change. The data path changes.**

SIL demo = prove the pipe works (live, visual, interactive)
Customer CAN log = prove the pipe produces value (reports, findings, numbers)

---

## What Makes the Models Topology-Independent

The SOC LSTM was trained on BMW i3 (96S). Why does it work on an 18S pack or a customer's 108S pack?

**Because we normalize to per-cell voltage.**

```
BMW i3:     pack_V = 360V / 96 cells = 3.75V per cell
foxBMS:     pack_V = 66.6V / 18 cells = 3.70V per cell
Customer A: pack_V = 400V / 108 cells = 3.70V per cell
Customer B: pack_V = 800V / 216 cells = 3.70V per cell

All four are NMC cells at ~3.7V. Same chemistry, same voltage dynamics.
The LSTM sees per-cell voltage, not pack topology.
```

Same for temperature (cell physics are cell-level) and current (normalized to C-rate).

**Where this breaks**: Different chemistry (LFP has flat OCV curve vs NMC). Would need retraining or at minimum FOBSS-style validation on that chemistry's data.

---

## Revenue Path

```
                   SIL Demo              Tier 1               Tier 2              Tier 3
                   (free / portfolio)    (paid engagement)    (paid engagement)   (paid engagement)
                   ─────────────         ────────────────     ─────────────────   ────────────────
Investment:        Already built         1-2 weeks            2-4 weeks           4-8 weeks
Customer gives:    Nothing               DBC + 1 CAN log      DBC + 5 CAN logs   CAN archive
We deliver:        Live web demo         3 PDF reports         SIL environment     ML test generation
                   sil.taktflow.com      + sidecar on bench    + Docker + CI       + anomaly patterns
Price point:       $0                    €5-15k               €20-40k             €40-80k
Recurring:         —                     Monthly audit run    SIL maintenance      Continuous analysis

What changes:      Nothing               pack_config.json     + plant calibration  + scenario engine
                                         (15 min)             (2-3 days)           (1-2 weeks)
Our code changes:  0 lines               0 lines              0 lines              0 lines
```

**The pipeline code is 100% reusable. Only the config file changes.**

---

## Honest "Is It Meaningful?" Matrix

| Question | Answer | Confidence |
|---|---|---|
| Does the SIL demo show ML working on CAN? | **Yes** — live, real-time, 24/7 | HIGH |
| Does it prove ML accuracy on customer data? | **No** — need their data to prove that | — |
| Will SOC LSTM work on a customer's 96S pack? | **Likely** — same chemistry, per-cell normalization | MEDIUM-HIGH |
| Will thermal CNN catch their thermal issues? | **Likely** — cell-level physics, NREL-trained | HIGH |
| Will anomaly detection find real anomalies? | **Yes on obvious ones** — overvoltage, overcurrent score high. Subtle drift? Need tuning. | MEDIUM |
| Is the 48-hour turnaround realistic? | **Yes for Tier 1** — decode + config + inference + report is <1 day of actual work | HIGH |
| Can we run this without dSPACE? | **Yes** — laptop + SocketCAN + Python. $0 in tooling. | HIGH |
| Will customers pay for this? | **Yes if we find something their BMS missed** — the reports sell themselves | MEDIUM-HIGH |

---

## What Happens When We Get Real CAN Logs

### Day 1: Customer sends DBC + .blf file

```bash
# Step 1: Create config (15 min, one-time)
vim customers/acme-bms/pack_config.json
# Map their signal names: "HV_PackVoltage" → pack_voltage, etc.

# Step 2: Run pipeline (5 min)
python pipeline/run_audit.py \
    --dbc customers/acme-bms/acme.dbc \
    --config customers/acme-bms/pack_config.json \
    --log /data/acme/test_drive_001.blf \
    --output reports/acme-bms/

# Step 3: Review + deliver reports
# reports/acme-bms/soc_audit.pdf
# reports/acme-bms/thermal_risk.pdf
# reports/acme-bms/cell_health.pdf
# reports/acme-bms/raw_predictions.csv
```

### Day 2: We review the numbers

- If SOC RMSE < 3%: "Your BMS tracking is solid. Here's the comparison chart."
- If SOC RMSE > 5%: "Your coulomb counting drifts under load. ML shows the gap. Here's where."
- If thermal risk > 0.5 anywhere: "Cell group 3 had a thermal event at t=1890s. Your BMS didn't flag it."
- If imbalance > 30mV: "Cell 23 is 12mV below average. Track this over next 50 cycles."

### Day 3: Customer call

> "We found 3 things in your data that your BMS didn't report. Here's what they mean."

That's the sale. The pipeline pays for itself with the first finding.
