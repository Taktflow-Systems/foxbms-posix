# foxBMS POSIX vECU — Virtual Battery Management System

## What Is This?

This project takes **foxBMS 2** — a production-grade, open-source Battery Management System (BMS) written in C — and runs it entirely on a standard Linux PC instead of the original embedded hardware (TMS570 microcontroller).

**In plain terms:** a real BMS that normally runs on a tiny chip inside an electric vehicle battery pack now runs as a desktop application, talking to a simulated battery over virtual CAN bus. You can inject faults, watch the BMS react in real time, and verify every safety requirement — all without touching any hardware.

### Why Does This Matter?

| If you are… | This project shows… |
|---|---|
| **An interviewer** | End-to-end embedded systems competence: C firmware, CAN protocols, ISO 26262 safety analysis, ASPICE process discipline, Docker deployment, and a live web dashboard — all in one repo |
| **A beginner** | How a real automotive BMS works from the inside: state machines, fault detection, contactor control, and how the industry tests safety-critical software |
| **An engineer** | A reusable pattern for SIL (Software-in-the-Loop) testing of any embedded C project — stub the hardware, simulate the plant, test at full speed |

### Live Demo

Try it right now — no setup needed:

- **Dashboard**: [sil.taktflow-systems.com/bms/](https://sil.taktflow-systems.com/bms/) — live BMS with fault injection controls
- **Documentation**: [sil.taktflow-systems.com/bms-docs/](https://sil.taktflow-systems.com/bms-docs/) — full 60-page portfolio
- **Demo Guide**: [SIL Demo Guide](https://sil.taktflow-systems.com/bms-docs/sil-demo-guide.html) — step-by-step walkthrough

---

## How It Works

```
┌──────────────────┐       virtual CAN bus       ┌──────────────────────┐
│  Plant Model     │ ◄──────── vcan1 ────────► │  foxBMS vECU          │
│  (Python)        │                             │  (C binary on Linux)  │
│                  │  sends:                     │  processes:           │
│  Simulates a     │  • 18 cell voltages         │  • BMS state machine  │
│  battery pack    │  • pack current (0 A)       │  • fault detection    │
│  with 18 cells   │  • pack voltage (66.6 V)    │  • contactor control  │
│                  │  • cell temperatures (25°C)  │  • precharge sequence │
│                  │  • state requests            │  • 15+ CAN TX msgs   │
└──────────────────┘                             └──────────────────────┘
         │                                                │
         └──────────── both run on your laptop ───────────┘
```

**Key idea:** The BMS firmware doesn't know it's running on a PC. It processes CAN frames exactly like it would on real hardware. The only difference is that hardware registers are replaced with POSIX stubs (80+ functions), and the CAN bus is a Linux virtual interface instead of physical wires.

---

## What the BMS Does

The BMS follows a strict state machine — the same one used in real battery packs:

```
UNINIT → INIT → IDLE → STANDBY → PRECHARGE → NORMAL → ERROR
```

- **NORMAL**: Battery is operating. The BMS monitors voltages, currents, and temperatures every cycle.
- **ERROR**: A fault was detected (e.g., a cell exceeded 2.55 V). Contactors open to disconnect the battery — a real safety action.
- **PRECHARGE**: Before connecting the battery to the motor, the BMS slowly charges the DC-link capacitor to avoid a dangerous inrush current spike.

### Fault Detection (the safety-critical part)

The BMS continuously checks for dangerous conditions:

| Fault | What It Means | Detection Time |
|-------|---------------|----------------|
| **Overvoltage** | A cell exceeded its safe voltage limit | 585 ms |
| **Overcurrent** | Too much current flowing through the pack | 116 ms |
| **Overtemperature** | A cell is getting dangerously hot | 5,510 ms |

When a fault is confirmed (threshold counters prevent false alarms), the BMS transitions to ERROR and opens the contactors. This is exactly what happens in a real EV — the battery disconnects itself to prevent fire or damage.

---

## Project Scope at a Glance

| Metric | Value |
|--------|-------|
| Test cases | **2,005** (ASIL-D level) |
| Test pass rate | **29/31** scenarios (100% runnable) |
| Requirement IDs traced | **415** with **1,953** links, **0 orphans** |
| Documentation pages | **60** (ASPICE CL2 + ISO 26262) |
| Project completion | **98%** (113/115 criteria met) |

### Phases Completed

| Phase | What Was Done | Status |
|-------|---------------|--------|
| 1. BMS NORMAL | Get the BMS to reach NORMAL state with simulated battery | Done (10/10) |
| 2. Realistic Simulation | Plant model with accurate cell voltages, current, temperature | Done (8/8) |
| 2.5. SIL Probes | Instrument firmware to expose internal state for testing | Done (76/76) |
| 3. Fault Injection | Inject overvoltage, overcurrent, overtemperature faults | Done (10/11) |
| 4. Integration | Docker, CI pipeline, automated test suite | Done (3/3) |
| 5. Web Demo | Live dashboard, documentation site, portfolio | Done (6/7) |

---

## Quick Start

```bash
# Prerequisites: Ubuntu 24.04, GCC 13+, Python 3.12
git clone --recursive https://github.com/nhuvaoanh123/foxbms-posix.git
cd foxbms-posix

# Apply patches to foxBMS source
cd foxbms-2
for p in ../patches/patch_*.py; do python3 "$p"; done
cd ..

# Build
cd src && make clean && make -j4 && cd ..

# Set up virtual CAN
sudo ip link add vcan1 type vcan && sudo ip link set vcan1 up

# Run plant model (background)
cd src && python3 plant_model.py vcan1 &

# Run foxBMS vECU
FOXBMS_CAN_IF=vcan1 ./foxbms-vecu
```

### Smoke Test

After starting both processes, verify with `candump vcan1`:
- `0x220` BMS State: first byte `0x17` = state 7 (NORMAL) + 1 connected string
- `0x235` SOC: byte 5 = `0xC8` = 50%
- `0x250` Cell Voltages: non-zero data with mux cycling

---

## Documentation & Traceability

### Browse the Docs (HTML)

The full documentation is available as an interactive HTML site with search, navigation, and **clickable traceability links**:

```bash
# Build the HTML site (requires: pip install markdown)
python scripts/build-html.py
python scripts/build-trace-html.py

# Open in browser
xdg-open docs/site/index.html           # Linux
start docs/site/index.html              # Windows
```

Every requirement ID (e.g., SYS-REQ-020, SW-REQ-001) is a **colored link**. Hover to see upstream/downstream traces. Click to navigate.

### Documentation Map

| Section | Docs | What's Inside |
|---------|------|---------------|
| [STATUS.md](STATUS.md) | 1 | Implementation history, 14 fixes, architecture decisions |
| [PLAN.md](PLAN.md) | 1 | Roadmap: Phase 1–5 complete (113/115, 98%) |
| [docs/aspice-cl2/](docs/aspice-cl2/) | **29** | Full ASPICE CL2 package + ISO 26262 ASIL-D safety analysis |
| [docs/foxbms-upstream/](docs/foxbms-upstream/) | 25 | foxBMS module reference (state machine, diag, CAN, database) |
| [docs/project/](docs/project/) | 9 | Gap analysis, coverage matrix, troubleshooting, audits |
| [docs/business/](docs/business/) | 4 | ML anomaly detection, reusable SIL pipeline, HIL data plan |
| [docs/test/](docs/test/) | 3 | Fault injection test matrices |

### Traceability Validation

```bash
python scripts/trace-gen.py --check   # Validate all links (CI runs this too)
python scripts/trace-gen.py           # Generate traceability matrix
python scripts/trace-gen.py --stats   # Print summary
```

Current status: **415 IDs, 1,953 links, 0 broken, 0 untested leaves — PASS**

---

## Repository Structure

```
foxbms-posix/
├── README.md, STATUS.md, PLAN.md    ← You are here
├── setup.sh                          ← Single-command setup + build + test
├── foxbms-2/                         ← Upstream foxBMS v1.10.0 (submodule)
├── src/                              ← POSIX port source + tests
│   ├── foxbms_posix_main.c           Entry point + cooperative main loop
│   ├── hal_stubs_posix.c             80+ HAL stubs (replace real hardware)
│   ├── sil_layer.c/h                 SIL probe + override instrumentation
│   ├── posix_overrides.h             ARM → x86 translation overrides
│   ├── plant_model.py                Python battery simulator
│   ├── test_smoke.py                 Smoke test (BMS reaches NORMAL?)
│   ├── test_integration.py           21 integration criteria
│   ├── test_asil.py                  50 ASIL safety criteria
│   └── test_sil_probes.py            76 SIL probe criteria
├── patches/                          ← Python scripts to patch foxBMS source
├── scripts/                          ← Doc builder, traceability scanner
├── .github/workflows/ci.yml          ← CI: build + test + traceability
├── halcogen-headers/                 ← Pre-generated TMS570 register headers
└── docs/                             ← 60-page documentation portfolio
    ├── aspice-cl2/                   ASPICE CL2 + ISO 26262 ASIL-D
    ├── foxbms-upstream/              foxBMS module reference
    ├── project/                      Gap analysis, coverage, troubleshooting
    ├── business/                     ML integration, reusable pipeline
    └── test/                         Fault injection test matrices
```

---

## Glossary

New to automotive embedded? Here are the key terms used throughout this project:

| Term | What It Means |
|------|---------------|
| **BMS** | Battery Management System — the controller that keeps a battery pack safe |
| **CAN bus** | Controller Area Network — the standard communication bus in vehicles |
| **SIL** | Software-in-the-Loop — running firmware on a PC instead of real hardware |
| **HIL** | Hardware-in-the-Loop — testing with real hardware + simulated environment |
| **ASPICE** | Automotive SPICE — process maturity standard (like CMMI for automotive) |
| **ISO 26262** | Functional safety standard for road vehicles |
| **ASIL** | Automotive Safety Integrity Level — A (lowest) to D (highest risk) |
| **HARA** | Hazard Analysis and Risk Assessment — identifies what can go wrong |
| **vECU** | Virtual Electronic Control Unit — firmware running on a PC |
| **FTTI** | Fault Tolerant Time Interval — how fast the system must react to a fault |
| **Contactor** | A high-voltage relay that connects/disconnects the battery pack |
| **Precharge** | Slowly charging capacitors before full connection (prevents sparks) |

---

## Key Discoveries

Lessons learned while porting foxBMS to POSIX (useful for anyone doing similar work):

1. **DECAN_DATA_IS_VALID = 1** (not 0) — the cell voltage "invalid" flag is inverted from what you'd expect
2. **SBC_STATEMACHINE_RUNNING = 2** (not 3) — an enum value mismatch caused a system timeout that blocked BMS startup
3. **18 cells per module** — the battery configuration uses `BS_NR_OF_CELL_BLOCKS_PER_MODULE=18`
4. **IVT Voltage 3 (CAN ID 0x524)** — the redundancy module reads `highVoltage_mV[s][2]`, not `[s][0]`
5. **AFE runs in its own FreeRTOS task** — must call `MEAS_Control()` explicitly in cooperative scheduling mode
6. **FreeRTOS POSIX port doesn't preempt** — cooperative mode is the only reliable approach on Linux

## Environment Variables

- `FOXBMS_CAN_IF=vcan1` — SocketCAN interface name (default: vcan1)

## License

POSIX port files: Taktflow Systems 2026
foxBMS 2: BSD-3-Clause (Fraunhofer IISB)
