# What BMS Customers Get — Value Proposition

**Date**: 2026-03-27 (updated)
**For**: An Dao — internal strategy doc
**Key correction**: Customers sell BMS (hardware + firmware + algorithms), NOT battery packs. Their customers are pack integrators / OEMs.

---

## Understanding the Customer

A BMS company sells:

```
BMS Company (our customer)
├── BMS Hardware: PCB, cell monitoring ICs (AFE), current sensor, contactors
├── BMS Firmware: state machine, SOC algorithm, fault detection, balancing
├── BMS Calibration: tuning thresholds, SOC parameters for each pack config
└── BMS Certification: ISO 26262, ASPICE, safety case documentation

Their customers buy the BMS and put it on THEIR battery pack:
  - Vehicle OEM (BMW, VW, Hyundai) → EV traction battery
  - ESS integrator (Fluence, Tesla Megapack) → grid storage
  - Industrial (forklift, AGV, marine) → custom packs
```

**What the BMS company cares about**:
1. Does our SOC algorithm work across all customer pack configurations?
2. Does our fault detection catch everything it should?
3. Can we prove it works for certification (ISO 26262 / ASPICE)?
4. Can we test faster without tying up the bench for every customer pack variant?
5. Can we add ML features to our BMS product to differentiate from competitors?

**What they do NOT care about**: battery cell chemistry research, pack thermal design, cell manufacturing. That's their customer's problem.

---

## How Our ML Pipeline Helps a BMS Company

### Problem 1: "We need to validate our SOC algorithm across 20 customer pack variants"

A BMS company has one SOC algorithm (coulomb counting, EKF, or their proprietary method). But they sell to 20 different customers with different packs:

```
Customer A: 96S NMC 811, 60Ah, prismatic
Customer B: 108S NMC 622, 94Ah, pouch
Customer C: 48S LFP, 100Ah, cylindrical
Customer D: 216S NMC 811, 50Ah, prismatic (800V architecture)
```

Each customer asks: "What's the SOC accuracy of your BMS on OUR pack?" The BMS company has to answer for each one.

**Today**: They test on the bench. Each pack variant = 1-2 weeks of bench time. 20 variants = 20-40 weeks. They can't afford this, so they test on 3-4 "representative" packs and extrapolate.

**With our pipeline**:

```bash
# For each customer pack:
python run_audit.py \
    --config customers/customer_A/pack_config.json \    # 96S NMC, 60Ah
    --log customers/customer_A/acceptance_test.blf \
    --output reports/customer_A/

# 15 min to create config, 5 min to run, 2 hours to review
# Repeat for all 20 variants
```

**What they get**: SOC accuracy report for each pack variant. "Your SOC algorithm has 1.8% RMSE on Customer A's 96S pack, 2.4% on Customer B's 108S pack, 5.1% on Customer C's LFP pack — that one needs parameter tuning."

**Why this matters to them**: Instead of 20 weeks of bench time, they get 20 reports in 1 week. They can calibrate their SOC algorithm per customer and prove accuracy with data.

**Revenue**: €10-20k for full variant validation. Recurring every time they update their SOC algorithm.

---

### Problem 2: "We need independent SOC validation for ISO 26262"

ISO 26262 Part 6 requires independent validation of safety-relevant functions. SOC estimation is safety-relevant (wrong SOC → wrong power limits → thermal runaway).

The BMS company's SOC algorithm **cannot validate itself**. They need an independent estimate.

**Today**: They use a different coulomb counting implementation, or a reference battery cycler (expensive lab equipment). Or they cite the SOC accuracy from their validation report and hope the assessor doesn't ask for independent confirmation.

**With our pipeline**:

```
Their BMS SOC (coulomb counting / EKF)
        ↕ compared against
Our ML SOC (LSTM trained on independent data)
        ↕ documented in
SOC Audit Report (PDF with RMSE, max drift, comparison plot)
```

Our LSTM is trained on BMW i3 + NASA data — **completely independent** from their SOC algorithm. It uses different math (neural network vs Kalman filter), different training data, different implementation. This is exactly what an ISO 26262 assessor wants to see.

**What they get**: A document for their safety case: "SOC estimation independently validated against ML baseline. RMSE: 2.1% on [customer pack]. Maximum instantaneous difference: 3.8%. Conclusion: SOC algorithm meets accuracy requirement SWR-SOC-001 (< 5% RMSE)."

**Why this matters**: Without independent validation, their ISO 26262 safety case has a gap. With it, they pass the assessment.

**Revenue**: €5-10k per validation report. Required annually or per major firmware update.

---

### Problem 3: "We need to test our fault detection on packs we don't physically have"

A BMS company designs fault detection logic (overvoltage, overtemperature, overcurrent, cell imbalance, open wire, etc.). They test on their own bench with their reference pack.

But Customer D has a 216S pack with 800V architecture. The BMS company doesn't have one of those in the lab. How do they prove their fault detection works on it?

**Today**: They extrapolate from smaller packs. Or they ask Customer D to do the testing (Customer D doesn't want to — that's why they bought a BMS, not a test rig).

**With our SIL pipeline**:

```
Plant model calibrated for Customer D's 216S/800V pack
  ↓
BMS firmware (their firmware, compiled for x86)
  ↓
Inject faults: OV on cell 150, OT on module 8, OC at 200A
  ↓
Measure: Did the BMS open contactors? How fast? Correct diagnostic code?
  ↓
Report: "Your fault detection works correctly on 216S/800V.
         Contactor opens in 1.5s for OV (requirement: <2s). PASS."
```

**What they get**: Fault detection validation report for pack configurations they don't physically have. They can deliver this to Customer D as part of the BMS qualification package.

**Revenue**: €15-30k per SIL validation (Tier 2). Each new customer pack variant is a new sale.

---

### Problem 4: "We want to add ML features to our BMS product"

This is the **product differentiation** angle. BMS companies compete on features:

```
BMS Company A (today):
  ✓ SOC (coulomb counting)
  ✓ Fault detection (threshold-based)
  ✓ Cell balancing (passive)
  ✗ No predictive features

BMS Company A (with our ML):
  ✓ SOC (coulomb counting + ML verification)
  ✓ Fault detection (threshold + ML anomaly scoring)
  ✓ Cell balancing (passive + ML-predicted balancing needs)
  ✓ Thermal risk prediction (ML, not just threshold)
  ✓ Cell health trending (which cell is degrading fastest)
  ✓ SOH estimation (ML lifecycle prediction)
```

**What we deliver**: An ONNX sidecar that runs on their gateway ECU (or a separate microcontroller). It reads their BMS CAN output and adds ML intelligence.

**Architecture for their product**:

```
Their BMS ECU (existing, no changes)
    │
    ├── CAN bus (standard BMS messages)
    │
    └── ML Gateway ECU (our delivery)
        ├── ONNX Runtime (SOC LSTM, Thermal CNN, Anomaly)
        ├── Reads BMS CAN output
        ├── Publishes ML predictions on separate CAN IDs
        └── Their customer's vehicle controller reads both BMS + ML signals
```

**Why this matters**: Their BMS now has predictive capabilities that competitors don't. "Our BMS detects thermal risks 20 seconds before threshold-based systems" is a sales differentiator.

**Revenue**: €30-50k initial integration. Royalty per BMS unit shipped ($1-5/unit). This is the long-term recurring revenue play.

---

### Problem 5: "We need to reduce bench time — bench is our bottleneck"

BMS companies have 1-3 bench setups. Each bench runs 1 test at a time. Test queue is 2-4 weeks deep. Every firmware change needs re-validation. Bench = bottleneck.

**With SIL**: Same tests run on laptop in Docker. No bench needed for regression tests. Bench reserved for final validation only.

```
Before:
  Firmware change → queue for bench (2 weeks) → run tests (3 days) → analyze (1 day)
  Total: 2-3 weeks per iteration

After:
  Firmware change → CI runs SIL tests (5 min) → pass → bench for final only (1 day)
  Total: same day for regression, 1 day for final
```

**Revenue**: €20-40k for SIL environment build. ROI: they save €50-100k/year in bench time.

---

## What We Actually Sell (Reframed for BMS Companies)

| Service | What they get | Why they buy it | Price |
|---|---|---|---|
| **SOC Variant Validation** | Accuracy report per customer pack configuration | Prove their SOC works on packs they don't have | €10-20k |
| **Independent SOC for ISO 26262** | ML-based independent validation for safety case | Pass certification assessment | €5-10k per report |
| **SIL Fault Detection Testing** | Virtual fault injection on any pack config | Test without physical hardware | €15-30k per pack |
| **ML Feature Add-on for BMS Product** | ONNX sidecar adding predictive capabilities | Product differentiation vs competitors | €30-50k + royalty |
| **Bench Time Reduction (SIL)** | Docker-based SIL for regression testing | Unblock bench bottleneck | €20-40k |
| **CAN Log Archive Analysis** | Anomaly mining across historical test data | Find issues hidden in old data | €5-15k per batch |

---

## The Reuse Story (Corrected)

When a BMS company buys our service, here's what's reusable across THEIR customers' pack variants:

| Component | Reused across variants? | What changes per variant |
|---|---|---|
| Our pipeline code (670 lines) | **100% reused** | Nothing |
| Our ONNX models (SOC, Thermal, Imbalance) | **100% reused** (NMC), retrain for LFP | Nothing for same chemistry |
| Their BMS firmware (SIL build) | **100% reused** — it's THEIR firmware | Nothing (same firmware, different pack config) |
| Plant model engine | **100% reused** | Parameters change (cell count, capacity, OCV curve) |
| pack_config.json | **Per variant** | 15 min to create from pack datasheet |
| plant_calibration.json | **Per variant** | Extracted from customer's acceptance test CAN log |
| Anomaly baseline | **Per variant** | 30 min of normal operation logged + retrain |

**Key insight**: The BMS company does one SIL build (their firmware compiled for x86). Then every new customer pack variant is just a config file + plant calibration. Our pipeline handles the rest.

```
BMS firmware (compiled once for x86)
  + pack_config_customer_A.json (96S, 60Ah, NMC)    → reports for A
  + pack_config_customer_B.json (108S, 94Ah, NMC)   → reports for B
  + pack_config_customer_C.json (48S, 100Ah, LFP)   → reports for C (retrain SOC if LFP)
  + pack_config_customer_D.json (216S, 50Ah, NMC)   → reports for D
```

**This is their scaling problem solved.** One SIL, N pack variants, automated validation.

---

## The One-Sentence Pitch (Corrected)

**For BMS company CTO**: "We validate your SOC algorithm across all your customer pack variants in 1 week instead of 20 weeks of bench time."

**For BMS company test lead**: "We give you a SIL environment where your firmware runs on a laptop, so your bench isn't the bottleneck anymore."

**For BMS company product manager**: "We add ML intelligence to your BMS product so you can sell thermal prediction and cell health trending that your competitors don't have."

**For BMS company safety engineer**: "We provide the independent SOC validation your ISO 26262 assessor is asking for."

---

## How the First Meeting Goes

> **Us**: "You sell BMS to how many different pack configurations?"
>
> **Them**: "12 active customers, maybe 20 pack variants."
>
> **Us**: "How do you validate SOC accuracy for each one?"
>
> **Them**: "We test on our reference pack and hope it transfers."
>
> **Us**: "What if we could run your firmware against every pack variant on a laptop, prove SOC accuracy for each one, and hand you a validation report for your safety case? No bench needed. 1 week instead of 20."
>
> **Them**: "Show me."
>
> **Us**: *opens sil.taktflow-systems.com/bms/*
> "This is foxBMS firmware with ML running alongside. Same architecture works with your firmware and your customers' packs. Give us your DBC and one of your customers' acceptance test logs. We'll show you the SOC accuracy report in 48 hours."
