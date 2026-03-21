# Service: BMS ML-SIL-HIL Integration

**Pitch**: Your ML team has models in notebooks. Your firmware team has CAN on the bench. We connect them.

---

## The Gap Every BMS Company Has

```
Their ML Team                    Their Firmware Team              Their HIL Team
─────────────                    ───────────────────              ──────────────
Python, PyTorch, Jupyter         C, AUTOSAR, RTOS                dSPACE, Vector, bench
trains SOC/SOH models            writes BMS firmware              runs test sequences
evaluates on test splits         tests on hardware                logs CAN data

     outputs: .pt / .onnx            outputs: .elf / .hex            outputs: .blf / .asc

           ╲                              │                              ╱
            ╲                             │                             ╱
             ╲                            │                            ╱
              ╲                           │                           ╱
               ╲                          │                          ╱
                ╲                         │                         ╱
                 ╲                        │                        ╱
                           NOBODY CONNECTS THESE

     ML models sit in a repo. BMS firmware runs on metal.
     CAN logs sit on a NAS. No pipeline runs them together.
```

**Their ML engineer** can train a SOC LSTM with 1.5% RMSE on a Kaggle dataset. But they can't:
- Deploy it on a CAN bus next to real firmware
- Feed it real BMS signals in real-time
- Compare ML output vs firmware output on the same data
- Inject ML-driven fault scenarios into a HIL bench
- Build a SIL environment where firmware + ML run together without hardware

**Their firmware engineer** can write a BMS state machine. But they can't:
- Validate their SOC algorithm against ML baselines
- Run their firmware on Linux for automated CI testing
- Create realistic plant models from ML training data
- Add predictive diagnostics without modifying the firmware

**Their HIL engineer** can run test sequences and log CAN data. But they can't:
- Run ML inference live on the bench CAN bus
- Generate test scenarios from ML anomaly patterns
- Build a SIL replica of the bench for pre-validation
- Extract plant model parameters from bench data automatically

**We do all three.**

---

## What We Deliver

### Tier 1: ML-on-CAN Sidecar (1-2 weeks)

Take their existing ML models (or ours) and deploy them as a CAN sidecar that runs alongside their BMS on the bench.

```
Their BMS ECU ──→ CAN bus ──→ ML Sidecar (our delivery)
                     │              reads BMS CAN output
                     │              runs ONNX inference
                     │              publishes ML predictions
                     │              on new CAN IDs
                     │
                     └──→ CANape / their tooling
                          sees both BMS + ML signals
```

**What they get**:
- Python sidecar process that reads their DBC, decodes signals, runs inference
- ML predictions on CAN (visible in their existing tooling)
- Side-by-side comparison: their SOC vs ML SOC, their threshold vs ML risk score
- Works on their bench today, no firmware changes

**What we need from them**: DBC file + 1 day of bench access to validate signal mapping.

**Why they can't do this themselves**: Their ML team doesn't know CAN. Their HIL team doesn't know ONNX. The sidecar sits in the gap.

---

### Tier 2: SIL Environment (2-4 weeks)

Build a software-in-the-loop replica of their BMS bench that runs on Linux without hardware.

```
Plant Model (calibrated from their bench data)
     │
     ├──→ Their BMS firmware (compiled for x86, or our foxBMS demo)
     │         runs on Linux, SocketCAN
     │
     ├──→ ML Sidecar (same as Tier 1)
     │         runs inference on virtual CAN
     │
     └──→ Automated test runner
              pytest, CI/CD, regression
```

**What they get**:
- Plant model calibrated from their real bench CAN logs (OCV curve, R_internal, thermal constants, cell spread)
- Their firmware running on Linux (if possible) or foxBMS as functional stand-in
- Same ML sidecar from Tier 1, running on virtual CAN
- Automated smoke test: start → reach NORMAL → run profile → check SOC/thermal/imbalance → pass/fail
- Docker compose for one-command startup

**What we need from them**: 3-5 CAN logs (charge, discharge, dynamic) + DBC + pack specs.

**Why they can't do this themselves**: Building a POSIX port of a BMS requires understanding FreeRTOS→cooperative loop, hardware register stubbing, CAN queue routing, HAL replacement. We already solved this for foxBMS (14 fixes, 170+ source files compiled on x86). We know the pattern.

---

### Tier 3: ML-Driven Test Generation (4-8 weeks)

Use ML models + their historical bench data to automatically generate test scenarios that find bugs their manual test plan misses.

```
Their CAN log archive ──→ Anomaly detection
                               │
                          "These 3 patterns are unusual"
                               │
                          Generate test scenarios
                               │
                     ┌─────────┼─────────┐
                     │         │         │
                SIL plant   SIL plant   SIL plant
                scenario 1  scenario 2  scenario 3
                     │         │         │
                  foxBMS     foxBMS     foxBMS
                     │         │         │
                  pass?      FAIL       pass?
                               │
                          "Scenario 2: cell 7 temp ramp
                           at 1.2C/min during fast charge
                           → BMS didn't open contactors
                           until 82C (expected: 60C warning)"
```

**What they get**:
- Automated scenario extraction from historical CAN logs
- ML-ranked test priorities (which patterns are most likely to trigger faults)
- SIL execution of generated scenarios (no bench time needed)
- Report: "We found 3 scenarios where your BMS response was slower than expected"

**Why they can't do this themselves**: This requires all three disciplines — ML for anomaly detection, firmware for SIL execution, HIL for bench correlation. That intersection is us.

---

## Our Proof of Competence (The foxBMS Demo)

foxBMS POSIX is not the product. It's the proof we can do this.

| What foxBMS Demo Shows | What It Proves for Their Project |
|---|---|
| 170+ BMS source files compiled for x86 | We can port their firmware to SIL |
| 14 hardware stubs (SBC, RTC, SPI, I2C, CAN, DMA...) | We know how to replace MCAL/HAL |
| Cooperative loop replacing FreeRTOS | We understand RTOS→POSIX translation |
| SocketCAN TX/RX with DBC encoding | We know automotive CAN protocols |
| Plant model with real BMW i3 driving data | We can calibrate from real bench data |
| 5 ML models (SOC, SOH, Thermal, RUL, Imbalance) | We have the ML pipeline ready |
| ML sidecar on CAN bus (architecture) | We've designed the integration pattern |
| BMS reaches NORMAL through real data flow | End-to-end, not a toy demo |

---

## Competitive Positioning

| Competitor | What They Sell | Their Gap | Our Edge |
|---|---|---|---|
| **dSPACE** | HIL hardware + VEOS SIL | $150k+ licensing. No ML integration. Customer must build their own models. | We integrate ML into their existing bench for 1/10 the cost |
| **Vector** | CANape + CANoe + vTESTstudio | Excellent tooling, but no ML inference on CAN. Their CAPL scripting can't run ONNX. | ML sidecar plugs into their Vector toolchain |
| **ETAS** | ISOLAR-EVE + INCA | AUTOSAR-focused SIL. Doesn't handle ML or non-AUTOSAR BMS. | We work with any BMS firmware, not just AUTOSAR |
| **MathWorks** | Simulink + BMS Toolbox | Model-based, not data-driven. Their SOC is EKF, not LSTM. Requires Simulink license ($10k+). | Data-driven ML, open-source, runs on a laptop |
| **In-house ML team** | Custom models trained on internal data | Models stay in Jupyter. No CAN deployment. No SIL pipeline. No firmware integration. | We ARE the integration layer they're missing |
| **Consulting firms** (AVL, Ricardo, FEV) | Full-service engineering | $200+/hr, months-long engagements. Overkill for "connect ML to CAN". | We deliver Tier 1 in 1-2 weeks, not months |

**Our positioning**: We're not competing with dSPACE on hardware or with their ML team on models. We're the **integration glue** between ML, firmware, and HIL. Nobody else does this specific thing.

---

## What We Need to Walk In With

| Item | Status | Notes |
|---|---|---|
| foxBMS POSIX demo running | DONE | BMS in NORMAL, 15+ CAN messages, plant model |
| ML sidecar architecture | DESIGNED | proposal-ml-integration.md in archive, ready to implement |
| 5 ONNX models trained | DONE | SOC 1.83%, SOH 0.85%, Thermal F1=1.0, RUL 16%, Imbalance |
| cantools + python-can workflow | DONE | Decode any DBC + CAN log |
| Plant model calibration script | TODO | Extract OCV, R_internal, thermal from CAN logs |
| Customer-facing report template | TODO | SOC audit, thermal report, cell health card |
| Docker one-command SIL | TODO | docker-compose for demo |
| 10-minute live demo script | TODO | Terminal recording or rehearsed sequence |

---

## Engagement Flow

```
Week 0:  Demo foxBMS + ML sidecar on our laptop (10 min)
         "This is foxBMS with our ML running alongside on CAN.
          Give us your DBC and one CAN log, we'll show you
          the same on your data within 48 hours."

Week 1:  They give us DBC + CAN log
         We decode, run ML, generate SOC audit + thermal report
         "Here's what we found. Your SOC drifts X%. Cell 23 is Y% weak."

Week 2:  If interested → Tier 1 engagement
         Deploy ML sidecar on their bench
         Live ML predictions on their CAN bus in CANape

Month 2: Tier 2 engagement
         Build SIL from their bench data
         Automated regression tests

Month 3+: Tier 3 engagement
          ML-driven test generation from their historical logs
```

---

## What Most BMS Companies Actually Struggle With

From talking to HIL engineers and attending bench sessions:

| Their Pain | How We Help |
|---|---|
| "We have 2TB of CAN logs on a NAS and nobody analyzes them" | We run ML on their logs, extract patterns, generate reports |
| "Our ML team trained a model 6 months ago and it's still in a notebook" | We deploy it on their CAN bus in 1 week |
| "We can't test SOC drift without running the bench for 8 hours" | SIL with calibrated plant model, runs in 5 minutes |
| "Our test plan is manual, we always miss edge cases" | ML-driven test generation from historical anomalies |
| "We need an independent SOC validation for certification" | Our LSTM is the independent estimate |
| "dSPACE quoted us $200k and 6 months" | We deliver Tier 1 in 2 weeks for a fraction |
| "Our firmware can only run on the target hardware" | We port it to POSIX (foxBMS is the proof) |
